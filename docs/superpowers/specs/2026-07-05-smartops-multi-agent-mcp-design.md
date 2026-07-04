# SmartOps 多 Agent + MCP 架构设计

> 版本：v1.0
> 日期：2026-07-05
> 状态：设计稿待审核

---

## 1. 背景与目标

SmartOps 当前是单 Agent 架构（LangChain `create_agent` + DeepSeek），直接通过 HTTP/Paramiko 调用 Loki、SSH 采集器和 RAG 知识库。问题在于：

- **职责耦合**：Agent 同时承担理解、调度、执行、报告，难以独立优化
- **日志/指标流混乱**：SSH 采集器 pull 日志 → PostgreSQL → 再 push Loki，数据流绕路
- **扩展性差**：新增数据源（如 Prometheus、应用日志）需要在单 Agent 里堆更多 tool
- **无监督协作**：无法并行查多个数据源再汇总

本次改造目标：

1. **日志/指标采集重构**：promtail 直推 Loki，node_exporter + Prometheus 统一指标平台
2. **多 Agent 架构**：LangGraph Supervisor + 3 个子 Worker，职责清晰
3. **MCP 进程内封装**：Loki 和 Prometheus 的接口标准化为 MCP 风格
4. **根因分析闭环**：Coordinator 自动汇总多源信息生成 RCA 报告 + 修复建议

---

## 2. 部署架构

```
云服务器（有公网 IP）
┌──────────────────────────────────┐
│ Docker Compose                   │
│ ├── Loki（:3100）                 │
│ │   接收 promtail 日志推送        │
│ └── Prometheus（:9090）           │
│     拉取 node_exporter 指标       │
└──────────┬──────────────┬────────┘
           │ HTTP          │ HTTP
           ▼               ▼
┌──────────────────────────────────┐
│ 本地电脑（运行 SmartOps）         │
│ Flask + LangGraph Supervisor     │
│ ├── Log Agent → Loki MCP（进程内）│
│ ├── Infra Agent → Prom MCP       │
│ │              → SSH（心跳/探活） │
│ └── Knowledge Agent → RAG（本地） │
└──────────────────────────────────┘

被管服务器（每台）
├── promtail → syslog/nginx/mysql 日志 → Loki（云）
└── node_exporter（:9100） → 被 Prometheus 拉取
```

### 2.1 部署变更一览

| 组件 | 现状 | 改造后 |
|------|------|--------|
| Loki | 本地 Docker | 云服务器 Docker |
| Prometheus | 无 | 新增，云服务器 Docker |
| promtail | 无 | 每台被管服务器新增 |
| node_exporter | 无 | 每台被管服务器新增 |
| SSH 采集器 | 采集指标 + 日志 + 心跳 | 仅心跳检测 + 探活 |
| 日志流 | SSH → PostgreSQL → Loki | promtail → Loki |
| 指标流 | SSH → PostgreSQL | node_exporter → Prometheus |

### 2.2 云服务器 docker-compose 新增 Prometheus

```yaml
services:
  loki:
    image: grafana/loki:3.0.0
    ports: ["3100:3100"]
    volumes: [loki-data:/loki]
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    restart: unless-stopped

volumes:
  loki-data:
  prometheus-data:
```

---

## 3. Agent 架构

### 3.1 总览

```
用户问题
    │
    ▼
┌───────────────────────────────────────────────┐
│           Supervisor Agent（LangGraph）         │
│  State：messages, next, intermediate_results   │
│                                                │
│  1. 理解问题                                   │
│  2. 判断需要哪些信息                            │
│  3. 按需调度 Worker（循环决策）                 │
│  4. 所有结果收齐 → 生成 RCA 报告 + 修复建议     │
└──────┬────────────┬───────────────┬────────────┘
       │            │               │
       ▼            ▼               ▼
 ┌──────────┐ ┌──────────┐ ┌──────────────┐
 │Log Worker│ │Infra     │ │Knowledge     │
 │          │ │Worker    │ │Worker        │
 │Loki MCP  │ │Prom MCP  │ │RAG 知识库    │
 │          │ │SSH 探活  │ │              │
 └──────────┘ └──────────┘ └──────────────┘
```

### 3.2 Supervisor Agent（LangGraph StateGraph）

使用 LangGraph 的循环图模式：

```python
class AgentState(TypedDict):
    messages: list                    # 对话历史
    next: Literal["FINISH", "log_worker", "infra_worker", "knowledge_worker"]
    intermediate_results: dict        # {worker_name: result}
    final_report: str                 # 最终 RCA 报告
```

**工作循环：**

```
用户输入 → state.messages 追加
    │
    ▼
Supervisor 节点（LLM 推理）
    │
    ├─ "我不需要工具" → 直接回答 → FINISH
    │
    ├─ "需要日志分析"
    │   → log_worker 节点 → 结果存入 intermediate_results → 回到 Supervisor
    │
    ├─ "需要指标分析"
    │   → infra_worker 节点 → 结果存入 intermediate_results → 回到 Supervisor
    │
    ├─ "需要查知识库"
    │   → knowledge_worker 节点 → 结果存入 intermediate_results → 回到 Supervisor
    │
    └─ "信息够了" → 生成 RCA 报告 → FINISH
```

**路由逻辑（decide_next 条件边）：**

Supervisor LLM 输出决定 next 字段。LangGraph 根据该值路由到对应 Worker 或结束。Worker 执行完后回到 Supervisor 继续决策，形成循环。

### 3.3 Worker 定义

Worker 不作为独立 Agent（不再调 LLM），而是作为 **工具函数** 由 Supervisor 按需调用：

| Worker | 工具函数 | 功能 | 数据源 |
|--------|---------|------|--------|
| **Log Worker** | `analyze_logs(server_name, hours, level)` | 查日志、统计错误码、提取关键报错 | Loki MCP |
| **Infra Worker** | `analyze_metrics(server_name, duration)` | 查 CPU/内存/磁盘/网络趋势，异常检测 | Prometheus MCP |
| | `health_check(server_name)` | 心跳检测、SSH 探活 | Paramiko |
| **Knowledge Worker** | `search_sop(query, top_k)` | 语义搜索运维文档、历史故障、SOP | RAG 知识库 |

**为什么要这样做（不把 Worker 做成独立 Agent）：**

- 减少 LLM 调用次数：每层独立 Agent 意味着每步多一次 LLM 推理，增加延迟和幻觉风险
- 职责单一：Worker 只负责"查数据、做分析"，不负责"理解问题、决策下一步"
- 失败隔离：Worker 函数异常不影响 Supervisor 的状态机

---

## 4. MCP 进程内封装层

### 4.1 设计原则

- **不跑独立进程**：MCP Server 以 Python 模块形式存在，直接被 Flask 进程调用
- **MCP 风格接口**：每个模块暴露 `mcp_tools` 列表，工具函数带输入输出 schema
- **可拆分**：以后需要拆成独立 MCP Server 供其他 Client 使用时，只需要加一层 stdio/HTTP 桥

### 4.2 Loki MCP 模块

**文件：** `llm/mcp/loki_mcp.py`

```python
# 模拟 MCP Server 的工具定义
class LokiMCPServer:
    def __init__(self, url: str):
        self.url = url  # 云服务器 Loki URL

    def query_logs(self, server_name: str, hours: int = 1,
                   level: str = "", keywords: list[str] = None) -> list[dict]:
        """查询 Loki 原始日志"""
        ...

    def analyze_errors(self, server_name: str, hours: int = 1) -> dict:
        """分析错误日志：统计错误码、提取关键报错"""
        ...
        return {
            "total_errors": 23,
            "error_codes": {"500": 15, "502": 5, "504": 3},
            "error_samples": [...],
            "time_distribution": [...]
        }
```

**暴露的工具给 Agent：**

| 工具名 | 参数 | 返回 |
|--------|------|------|
| `query_logs` | server, hours, level, keywords | 日志行列表 |
| `analyze_errors` | server, hours | 错误统计 + 样本 |
| `count_by_level` | server, hours | {error: N, warn: N, info: N} |

### 4.3 Prometheus MCP 模块

**文件：** `llm/mcp/prometheus_mcp.py`

```python
class PrometheusMCPServer:
    def __init__(self, url: str):
        self.url = url

    def query_metric(self, metric_name: str,
                     server_ip: str = "") -> dict:
        """查询 Prometheus 即时指标"""
        ...

    def range_query(self, metric_name: str, server_ip: str,
                    duration: str = "1h") -> list[dict]:
        """查询指标趋势"""
        ...

    def check_alerts(self) -> list[dict]:
        """查询 Prometheus Alertmanager 告警"""
        ...
```

**暴露的工具给 Agent：**

| 工具名 | 参数 | 返回 |
|--------|------|------|
| `query_metric` | metric, server_ip | 当前值 |
| `range_query` | metric, server_ip, duration | 时序数据列表 |
| `check_alerts` | — | 当前活跃告警列表 |

---

## 5. 原有组件改造

### 5.1 SSH 采集器（`collector/scheduler.py`）

**去向：** 职责大幅精简

| 原职责 | 改造后 |
|--------|--------|
| 采集 CPU/内存/磁盘 → PostgreSQL | ❌ 删除（由 node_exporter + Prometheus 替代） |
| 采集 syslog → PostgreSQL + Loki | ❌ 删除（由 promtail 直推 Loki 替代） |
| 告警检查 | ❌ 删除（告警移至 Prometheus Alertmanager 或 Supervisor 层） |
| 心跳检测 + 服务器状态更新 | ✅ 保留 |
| 离线检测 + 自动标记 | ✅ 保留 |

### 5.2 `llm/tools.py`

**去向：** 工具列表大幅调整

| 工具 | 变化 | 原因 |
|------|------|------|
| `get_server_list` | ✅ 保留 | 仍查 PostgreSQL |
| `get_server_status` | 🔄 改造 | 数据源改为 Prometheus |
| `get_metrics_history` | ❌ 删除 | 由 Infra Worker 通过 Prometheus MCP 替代 |
| `get_logs` | ❌ 删除 | 由 Log Worker 通过 Loki MCP 替代 |
| `search_knowledge_base` | ✅ 保留 | 知识库不变 |

### 5.3 `store/models.py`

| 模型 | 变化 |
|------|------|
| `Server` | ✅ 保留，仅心跳信息 |
| `Metric` | ⚠️ 保留但不再由采集器写入，历史数据可查；新数据走 Prometheus |
| `Log` | ⚠️ 保留作为历史缓存，新日志不再写入 |
| `Alert` | ✅ 保留，但告警来源改为 Prometheus Alertmanager webhook |
| `Conversation` / `Message` / `Probe` | ✅ 保留不变 |

### 5.4 `api.py`

- `receive_logs` 端点：保留兼容旧客户端，但标记为废弃
- `/api/servers/<name>/history`：数据源保持 PostgreSQL（已有历史数据），新增可选查 Prometheus

### 5.5 `.env` 新增配置

```
# 云服务器地址（替换 localhost）
CLOUD_LOKI_URL=http://your-cloud-ip:3100
CLOUD_PROMETHEUS_URL=http://your-cloud-ip:9090
```

---

## 6. Supervisor 与当前对话系统的集成

### 6.1 无痛替换

当前 `agent.py` 的 `chat()` 是唯一入口，改造后保留相同签名：

```python
# agent.py — 保留旧入口，内部转发
from llm.supervisor import Supervisor

def chat(conversation_id: int, user_input: str) -> str:
    """保留现有接口签名，后端改为 Supervisor"""
    history = load_history(conversation_id)
    supervisor = Supervisor()
    reply = supervisor.run(history + [("human", user_input)])
    save_message(conversation_id, user_input, reply)
    return reply
```

API 层和前端完全无感知。

### 6.2 对话状态管理

LangGraph 的 State 包含 `messages` 对话历史和 `intermediate_results` 中间结果，每个循环写入数据库：

```
用户提问 → Supervisor 调度 → Worker 执行 → Supervisor 汇总
  ↓                              ↓
  save Message(human)        intermediate_results 暂存于内存
  ↓
Worker 结果 → Supervisor 继续
                   ↓
            信息足够 → 生成 RCA 报告 → save Message(ai)
```

数据库 Message 表结构不变，只记录最终结果。中间过程（Worker 分析结果）在 State 中流转，不出库。

---

## 7. 根因分析报告（RCA）格式

当 Supervisor 判断信息足够时，自动生成标准结构：

```json
{
  "summary": "一句话说清楚故障根因",
  "timeline": [
    {"time": "14:23", "event": "nginx 500 错误开始出现", "source": "loki"},
    {"time": "14:25", "event": "CPU 飙升到 95%", "source": "prometheus"},
    {"time": "14:30", "event": "服务自动恢复", "source": "loki"}
  ],
  "root_cause": "xxx 导致 xxx",
  "impact": "影响范围：xxx 服务 xxx 用户",
  "evidence": {
    "log_analysis": "Log Worker 的结果摘要",
    "metric_analysis": "Infra Worker 的结果摘要",
    "knowledge_ref": "Knowledge Worker 找到的相关历史故障/SOP"
  },
  "recommendation": [
    "具体可操作步骤 1：`命令`",
    "具体可操作步骤 2：`命令`",
    "长期改进建议"
  ]
}
```

---

## 8. 实施计划

### Phase 1：基础设施部署

| # | 任务 | 验证 |
|---|------|------|
| 1 | 云服务器部署 Loki + Prometheus docker-compose | `curl localhost:3100/ready` 和 `curl localhost:9090/-/ready` 返回 OK |
| 2 | 被管服务器安装 promtail + node_exporter | promtail → Loki 有日志写入，Prometheus 能查到 node 指标 |
| 3 | 添加 node_exporter 到 Prometheus 抓取配置 | `up{job="node"}` 返回 1 |

### Phase 2：MCP 封装层

| # | 任务 | 验证 |
|---|------|------|
| 4 | 实现 `llm/mcp/loki_mcp.py` | 能查到 Loki 里 promtail 推送的日志 |
| 5 | 实现 `llm/mcp/prometheus_mcp.py` | 能查到 node_exporter 的 `node_cpu_seconds_total` 指标 |

### Phase 3：Agent 改造

| # | 任务 | 验证 |
|---|------|------|
| 6 | 安装 langgraph，实现 `llm/supervisor.py` 图结构 | 单步循环能正确路由 |
| 7 | 实现 Worker tools（日志/指标/知识库） | 每个 Worker 返回正确格式 |
| 8 | 实现 Supervisor RCA 报告生成 | 端到端：用户提问 → 报告输出 |

### Phase 4：清理与测试

| # | 任务 | 验证 |
|---|------|------|
| 9 | 精简 SSH 采集器（只留心跳） | 不报错，Server 状态正常更新 |
| 10 | 更新 `tools.py` 删除废弃工具 | Agent 不引用已删除工具 |
| 11 | 端到端测试：完整问题链路 | 多轮对话、多 Worker 调用、RCA 输出 |

---

## 9. 文件变更清单

### 新增

```
llm/mcp/__init__.py           MCP 模块包入口
llm/mcp/loki_mcp.py           Loki MCP 封装
llm/mcp/prometheus_mcp.py     Prometheus MCP 封装
llm/supervisor.py             LangGraph Supervisor Agent
llm/workers.py                子 Worker tool 定义
```

### 修改

```
llm/agent.py                  入口保留，内部转发 Supervisor
llm/tools.py                  工具列表精简
collector/scheduler.py        仅保留心跳 + 离线检测
collector/ssh_client.py       去掉 get_logs
api.py                        receive_logs 废弃标记
requirements.txt              新增 langgraph
.env                          新增 CLOUD_LOKI_URL, CLOUD_PROMETHEUS_URL
docker-compose.yml            新增 Prometheus 服务
```

### 删除

无。废弃代码逐步删除，不在同一 PR 中操作。

---

## 10. 风险与注意事项

| 风险 | 影响 | 缓解 |
|------|------|------|
| promtail → Loki 网络延迟 | 日志查询延迟高 | 增加缓存/超时重试 |
| LangGraph 循环死循环 | Supervisor 无限调度 | 设置最大循环次数（如 10 次） |
| Worker 结果格式不统一 | Supervisor 难以汇总 | 定义 Worker 返回的 JSON Schema |
| 旧的 Metric/Log 表数据丢失 | 历史数据不可查 | 保留写权限，只停止新增 |
| 云服务器宕机 | 日志/指标不可用 | 降级：使用本地缓存的 PostgreSQL 数据 |

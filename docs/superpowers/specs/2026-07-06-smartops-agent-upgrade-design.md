# SmartOps Agent 改造 — Worker 升级为独立 ReAct Agent

> 版本：v1.0
> 日期：2026-07-06
> 状态：设计稿

---

## 1. 背景与目标

当前多 Agent 架构中，3 个 Worker 是纯工具函数（无 LLM），导致：

- **指令理解能力弱**：用正则 `_extract_server` 从用户问题里提取参数，丢失时间范围、关键词、过滤条件等细节
- **知识库检索不可控**：`knowledge_worker` 硬编码 `top_k=3`，无法根据问题复杂度动态调整
- **输出格式固定**：返回嵌套 dict，Supervisor 拼接到报告里需要额外转换逻辑
- **无法精细调控**：用户说「看看过去 3 小时的 500 错误」→ 只能查 1 小时默认值

### 目标

将每个 Worker 从纯工具函数改造为独立的 `create_react_agent`，各自拥有 LLM + system prompt + 工具集，自主理解用户意图并执行分析。

---

## 2. 架构

```
用户: "web-01 最近 3 小时有没有 500 错误？"
        ↓
┌──────────────────────────────────────────────────┐
│ Supervisor Agent (LLM + 路由决策)                  │
│                                                    │
│ 1. 理解问题，决定下一步                             │
│ 2. 按需路由到 Worker                                │
│ 3. 收集所有 Worker 的分析结论文本                    │
│ 4. next=FINISH → 生成最终 RCA 报告                  │
└──────┬──────────────┬──────────────┬──────────────┘
       │              │              │
       ▼              ▼              ▼
┌──────────────┐ ┌────────────┐ ┌──────────────┐
│ Log Agent    │ │Infra Agent │ │ Knowledge    │
│              │ │            │ │ Agent        │
│ LLM          │ │LLM         │ │LLM           │
│ System Prompt│ │System Prompt││System Prompt │
│              │ │            │ │              │
│ query_logs   │ │query_metric│ │search_       │
│ analyze_     │ │range_query │ │knowledge_base│
│ errors       │ │check_alerts│ │              │
│ count_by_    │ │            │ │              │
│ level        │ │            │ │              │
└──────┬───────┘ └──────┬─────┘ └──────┬───────┘
       │                │              │
       └────────────────┴──────────────┘
                        ↓
              Supervisor 汇集文本分析结论
                        ↓
                  生成 RCA 报告
```

### 数据流

```
用户输入 → Supervisor.invoke()
    ↓
Supervisor State 初始化:
  messages: [("human", user_input)]
  next: "supervisor"
  intermediate_results: {}     ← 存 Worker 返回的文本
  iteration: 0
    ↓
Supervisor Node (LLM 决策)
    ↓ next = "log_worker"
Log Worker Node → log_agent.invoke({"messages": [prompt, ("human", user_input)]})
    ↓ intermediate_results["log_worker"] = "分析结论文本"
    ↓ iteration++
Supervisor Node (LLM 决策，已看到 log_worker 的结果)
    ↓ next = "FINISH"
Finish Node → 生成 RCA 报告
    ↓ final_report
END
```

---

## 3. Worker Agent 定义

### 3.1 公共配置

```python
from langchain_openai import ChatOpenAI
import os

_LLM = ChatOpenAI(
    model="deepseek-v4-flash",
    base_url="https://opencode.ai/zen/go/v1",
    api_key=os.getenv("OPENCODE_API_KEY"),
)
```

### 3.2 Log Worker Agent

```python
from langgraph.prebuilt import create_react_agent
from llm.mcp.loki_mcp import query_logs, analyze_errors, count_by_level

log_worker_agent = create_react_agent(
    llm=_LLM,
    tools=[query_logs, analyze_errors, count_by_level],
    prompt="""你是一个运维日志分析专家，通过 Loki 日志系统排查问题。

可用工具：
- query_logs(server_name, hours, level) → 查询原始日志文本
- analyze_errors(server_name, hours) → 统计错误码分布
- count_by_level(server_name, hours) → 按级别统计日志数量

关键规则：
1. 先调 count_by_level 了解日志整体分布
2. 如果有 error/warn，调 analyze_errors 查错误码统计
3. 需要看具体内容时调 query_logs，注意用 level 和 keywords 参数精确过滤
4. 从用户问题中提取时间范围（默认 1h）、服务器名
5. 最后给出结构化分析结论

输出格式（Markdown）：
📋 **日志分析结论**
- 服务器: xxx
- 时间范围: xxx
- 日志分布: error=N, warn=N, info=N
- 主要异常: 描述异常类型和数量
- 关键样本: 1-2 条典型错误行
- 建议: 下一步排查方向""",
    max_iterations=6,
)
```

### 3.3 Infra Worker Agent

```python
from llm.mcp.prometheus_mcp import query_metric, range_query, check_alerts

infra_worker_agent = create_react_agent(
    llm=_LLM,
    tools=[query_metric, range_query, check_alerts],
    prompt="""你是一个基础设施指标分析专家，通过 Prometheus 监控系统排查问题。

可用工具：
- query_metric(metric_name, server_ip) → 查询指标当前值
- range_query(metric_name, server_ip, duration) → 查询指标历史趋势
- check_alerts() → 查看当前活跃告警

关键规则：
1. 先查出要分析的服务器 IP（从上下文推断）
2. 分别查 CPU、内存、磁盘核心指标
3. 调用 check_alerts 查看是否有相关告警
4. 超过 80% 阈值的指标标记为异常
5. 如果趋势需要深入了解，调 range_query 看历史变化

输出格式（Markdown）：
📊 **基础设施分析结论**
- 服务器: xxx
- CPU: xx%（↑ 异常/正常）
- 内存: xx%（↑ 异常/正常）
- 磁盘: xx%（↑ 异常/正常）
- 关联告警: xxx
- 建议: 具体的修复建议""",
    max_iterations=6,
)
```

### 3.4 Knowledge Worker Agent

```python
from llm.tools import search_knowledge_base

knowledge_worker_agent = create_react_agent(
    llm=_LLM,
    tools=[search_knowledge_base],
    prompt="""你是一个运维知识库专家，通过 RAG 知识库检索运维文档和故障处理方案。

可用工具：
- search_knowledge_base(query, top_k) → 语义搜索运维知识

关键规则：
1. 从用户问题中提取关键词（服务器名、故障类型、组件名）
2. 构造精确的搜索 query，分多次搜索不同角度
3. top_k 默认 3，复杂问题可调到 5
4. 从结果中提取：故障原因、解决方案、命令示例
5. 如果搜不到相关内容，如实说明「知识库中未找到」

输出格式（Markdown）：
📚 **知识库检索结果**
- 搜索关键词: xxx
- 找到 N 条相关文档:
  1. 文档标题 / 摘要 / 方案
- 适用建议: 如何应用到当前问题""",
    max_iterations=4,
)
```

---

## 4. Supervisor 改造

### 4.1 State 调整

```python
class AgentState(TypedDict):
    messages: Annotated[Sequence[dict], add_messages]
    next: Literal["FINISH", "log_worker", "infra_worker", "knowledge_worker"]
    intermediate_results: dict      # Worker 返回文本 → {worker_name: "分析结论"}
    final_report: str
    iteration: int
```

`intermediate_results` 从存 dict 改为存文本，Supervisor 直接读文本：

```
现状:   intermediate_results["log_worker"] = {"total_errors": 23, ...}
改造后: intermediate_results["log_worker"] = "📋 日志分析结论\n- 服务器: web-01\n- 错误: 23 条..."
```

### 4.2 Worker 节点

```python
def log_worker_node(state: AgentState) -> dict:
    """日志 Worker 节点 — 使用独立 ReAct Agent"""
    question = state["messages"][-1].content if state["messages"] else "分析日志"
    try:
        result = log_worker_agent.invoke({
            "messages": [("human", question)]
        })
        response = result["messages"][-1].content
    except Exception as e:
        response = f"❌ 日志分析异常: {e}"

    return {
        "intermediate_results": {
            **state.get("intermediate_results", {}),
            "log_worker": response,
        },
        "iteration": state.get("iteration", 0) + 1,
    }
```

### 4.3 Supervisor 决策 prompt 调整

让 Supervisor 能看到 Worker 返回的文本结果：

```python
def _format_results(results: dict) -> str:
    """格式化 intermediate_results 为摘要"""
    if not results:
        return "尚无数据"
    parts = []
    for name, text in results.items():
        # 取前 200 字作为摘要
        summary = text[:200] + "..." if len(text) > 200 else text
        parts.append(f"【{name}】\n{summary}")
    return "\n\n".join(parts)
```

### 4.4 RCA 报告生成

Supervisor 直接读文本，不需要再解析 dict：

```python
def supervisor_finish(state: AgentState) -> dict:
    """Supervisor 结束节点 — 生成最终 RCA 报告"""
    # 使用 LLM 将所有 Worker 的文本汇总为 RCA 报告
    info = _format_results(state["intermediate_results"])
    prompt = f"""你是一个运维主管，根据下面各分析师的报告生成最终 RCA 报告。

{info}

请用以下格式输出：
# RCA 诊断报告

## 📋 概要
一句话总结

## 🕐 时间线
关键事件时间线

## 🔍 根因
详细根因分析

## 📊 证据
引用各分析师的结论

## 🔧 修复建议
1. ...
2. ...

## 💡 预防措施
长期改进建议"""
    
    resp = _LLM.invoke([("system", prompt)])
    return {"final_report": resp.content}
```

---

## 5. 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `llm/workers.py` | 🔄 重写 | 不再是纯函数，改为 3 个 `create_react_agent` 单例 |
| `llm/supervisor.py` | 🔄 修改 | Worker 节点调用 agent；State 中间结果适配文本；RCA 生成用 LLM 汇总 |
| `tests/test_workers.py` | 🔄 更新 | mock agent 调用，测试不依赖真实 LLM |

无需改动文件：
- `llm/tools.py` — 不变，Worker Agent 直接引用已有 tools
- `llm/agent.py` — 不变，chat() 接口签名不动
- `llm/mcp/` — 不变，tools 定义不动

---

## 6. 对比

| 维度 | 改造前 | 改造后 |
|------|--------|--------|
| Log Worker | 正则 + 硬编码调 3 个工具 | ReAct Agent，自主决定调哪些、调几次 |
| Infra Worker | 硬编码 3 条 PromQL | LLM 理解要查什么，动态构造查询 |
| Knowledge Worker | 固定 top_k=3 搜一次 | 自主决定搜索词和搜索次数 |
| 参数提取 | `_extract_server()` 正则 | LLM 自然语言理解 |
| 返回值 | 嵌套 dict | 结构化 Markdown 文本 |
| Supervisor 汇总 | 拼 dict + `_auto_report` 兜底 | LLM 读文本直接生成 RCA |
| 容错 | Worker 函数 try/except | Agent 内部自动重试（ReAct loop）|
| 扩展新能力 | 改 workers.py 加函数 | 加工具 + 改 Agent prompt |

---

## 7. 注意事项

1. **LLM 调用次数**：每个 Worker Agent 独立调用 LLM。一次完整的问题分析可能涉及 3-5 次 LLM 调用（Supervisor 决策 ×2 + Worker 内部 ReAct 循环 ×3），注意 API 成本和延迟
2. **超时控制**：每个 Worker Agent 设 `max_iterations=6`，防止死循环
3. **`intermediate_results` 格式变化**：前端（对话页）现有代码读取 `intermediate_results` 的逻辑需要确认不依赖旧 dict 格式
4. **Supervisor 决策精度**：Worker 返回文本后，Supervisor 需要理解文本含义再做下一步决策，prompt 需要调整以指导 LLM 识别「信息是否足够」

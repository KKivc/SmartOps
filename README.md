# SmartOps — 智能运维平台

---

## 项目概述

SmartOps 是一个集成多 Agent 故障分析、服务器监控告警、RAG 知识库的一站式运维工具，解决运维文档分散、故障排查效率低、历史经验难以沉淀的共性问题。系统结合 LangGraph 多 Agent 架构与 RAG 混合搜索知识库，支持自然语言驱动的运维分析、故障排查与服务器监控。

---

## 🖥 页面展示

<table>
  <tr>
    <td align="center">
      <img src="screenshots/overview.png" alt="总览页面" width="95%">
      <br><strong>📡 总览</strong> — 服务器状态卡片、在线/失联统计、快速添加
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="screenshots/servers.png" alt="服务器列表" width="95%">
      <br><strong>🖥 服务器</strong> — 完整表格、实时指标、添加/删除管理
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="screenshots/alerts.png" alt="告警页面" width="95%">
      <br><strong>🔔 告警</strong> — 告警列表、状态流转（open → acknowledged → resolved）
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="screenshots/trend.png" alt="趋势分析" width="95%">
      <br><strong>📈 趋势</strong> — Chart.js 图表、多指标切换（CPU/内存/磁盘）、时间范围选择
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="screenshots/logs.png" alt="日志查询" width="95%">
      <br><strong>📋 日志查询</strong> — Loki 日志检索、级别/时间/关键词过滤、错误码统计
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="screenshots/chat-v2.gif" alt="AI 对话" width="95%">
      <br><strong>🤖 AI 对话</strong> — 多轮会话、Supervisor 多 Agent 协作、RCA 报告渲染
    </td>
  </tr>
</table>



---

## 核心能力

### 🔍 混合搜索 RAG 知识库

传统向量检索在精确关键词匹配上存在先天不足。SmartOps 采用 **BM25 + Dense Embedding 双路召回 + Cross-Encoder 重排序** 检索管线：

```
用户提问
    ↓
┌─ 向量检索（语义匹配）──────┐
│ BM25 检索（关键词匹配）     │  ← 并行执行，双路召回
└──────────┬───────────────┘
           ↓
     合并去重（保留 max score）
           ↓
┌──────────────────────────┐
│ Qwen3-Reranker-8B        │  ← Cross-Encoder 逐对打分重排
│ 交叉编码器重排序（精度校准）│
└──────────┬───────────────┘
           ↓
     类别多样性过滤（同一类目最多 2 条）
           ↓
        最终结果
```

- **BM25Okapi** + jieba 中文分词，覆盖精确关键词匹配
- **Qwen3-Embedding-8B** 语义向量捕获同义表述
- **Qwen3-Reranker-8B 交叉编码器**（Cross-Encoder）逐条计算 query-document 相关性分数——这是精度提升的核心环节，较纯向量检索 Top-5 命中率提升约 25%
- **类别多样性约束**：同一类目最多保留 2 条，防止 LLM 被单一场景信息带偏

数据来源覆盖 **5000+ 篇运维知识文档**（Linux 排障、Docker/K8s、监控告警、网络诊断等），系统检索 Recall@5 达到 **92%**，Faithfulness 评估 hybrid 显著优于纯向量检索。

### 🧠 Supervisor 多 Agent 协作

系统采用 **LangGraph StateGraph 循环图** 架构，由 Supervisor LLM 决策路由，协调 3 个独立 ReAct Agent：

```
用户: "web-01 最近 3 小时有没有 500 错误？"
        ↓
┌──────────────────────────────────────────────────┐
│ Supervisor (LLM 路由决策)                          │
│ 1. 理解问题，决定需要哪些信息                       │
│ 2. 按需路由到 Worker（循环）                        │
│ 3. 收集所有 Worker 的文本分析结论                    │
│ 4. next=FINISH → 生成 RCA 报告                     │
└──────┬──────────────┬──────────────┬──────────────┘
       │              │              │
       ▼              ▼              ▼
┌──────────────┐ ┌────────────┐ ┌──────────────┐
│ Log Worker   │ │Infra Worker│ │Knowledge     │
│ (ReAct Agent)│ │(ReAct Agent│ │Worker (ReAct)│
│              │ │           )│ │              │
│ query_logs   │ │query_metric│ │search_       │
│ analyze_     │ │range_query │ │knowledge_base│
│ errors       │ │check_alerts│ │              │
│ count_by_    │ │            │ │              │
│ level        │ │            │ │              │
└──────┬───────┘ └──────┬─────┘ └──────┬───────┘
       │                │              │
       └────────────────┴──────────────┘
                        ↓
              Supervisor 汇总文本分析结论
                        ↓
              生成 Markdown RCA 报告
```

每个 Worker 是一个独立的 `create_react_agent`，拥有自己的 LLM + System Prompt + 工具集，自主理解用户意图并执行分析。Supervisor 循环决策（最多 10 轮）收集所有结果后生成标准 RCA 报告（根因分析）。

LangGraph Supervisor StateGraph 协同 **3 个独立 ReAct Agent**，支持自然语言驱动的端到端排查：

| Agent | 工具 | 数据源 |
|-------|------|--------|
| **Log Worker** (ReAct) | `query_logs`, `analyze_errors`, `count_by_level` | Loki (云服务器) |
| **Infra Worker** (ReAct) | `query_metric`, `range_query`, `check_alerts` | Prometheus (云服务器) |
| **Knowledge Worker** (ReAct) | `search_knowledge_base` | ChromaDB + BM25 |

**Agent 级工具**（tools.py）：
| 工具 | 功能 | 数据源 |
|------|------|--------|
| `get_server_list` | 查看服务器清单 | PostgreSQL |
| `get_server_status` | 查询服务器实时指标 | Prometheus |
| `search_knowledge_base` | 语义搜索运维文档 | ChromaDB + BM25 |

业务流程示例：

```
"分析 web-01 最近的错误日志"
    ↓
Supervisor 路由 → Log Worker Agent (自主: count_by_level → analyze_errors → query_logs)
              → Knowledge Worker Agent (搜索相关运维文档)
              → Supervisor 汇总 → 生成 RCA 报告
    ↓
"## RCA 诊断报告
### 📋 概要
web-01 最近 1 小时出现 23 条 500 错误（nginx upstream timed out）
### 🔍 根因
上游应用服务器响应超时，nginx 默认 60s 代理超时触发
### 🔧 修复建议
1. 检查上游服务状态: systemctl status app
2. 调整 nginx 代理超时: proxy_read_timeout 120s;"
```

### 📊 全链路评估体系

系统内置 **Ragas + 自定义检索指标** 双维度评估框架：

- **检索评估**：Recall@5 / Precision@5 / MRR，基于 50 条黄金测试集（覆盖精确匹配、语义匹配、跨类查询、故障场景四大类别）
- **生成评估**：Faithfulness（答案忠实度），通过 Ragas 框架调用 Judge LLM（Qwen3.6）自动评分，Python 实现，无 `nan` 污染
- **对比模式**：hybrid_search vs vector_only 一键对比，量化验证混合检索优势
- **缓存机制**：检索/生成/评估结果分层缓存（JSON），修改 Judge Prompt 后只需重跑评估阶段

评估结果覆盖：

```
          指标        hybrid     vector      提升
──────────────────────────────────────────────
  recall@5         92.0%      68.0%     +24.0%
  precision@5      85.3%      62.7%     +22.6%
  mrr              90.0%      70.0%     +20.0%
  faithfulness     0.78       0.70       +0.08
```

### 🖥 服务器监控与自动采集

基于 Paramiko SSH 的心跳检测（每 **60 秒** 一轮）：

- 在线/离线状态自动检测
- 离线告警自动生成（状态流转：`open → acknowledged → resolved`）
- 服务器恢复在线时自动关闭离线告警
- **指标采集 → Prometheus + node_exporter**
- **日志采集 → promtail → Loki**
- 指标历史趋势通过 Chart.js 可视化

### 💬 多轮会话记忆

系统保存完整对话历史（PostgreSQL Conversation / Message 表），Agent 自动加载上下文，实现连续多轮运维对话。新对话自动从首条消息截取标题。

---

## 系统架构

```
                         用户
                          │
                          ▼
                    Flask API (api.py)
                          │
                          ▼
                 ┌─────────────────────────────┐
                 │  LangGraph Supervisor        │
                 │  StateGraph (循环路由决策)    │
                 │  LLM: DeepSeek (OpenCode)    │
                 └──────┬──────────┬───────────┘
                        │          │
          ┌─────────────┼─────┬────┼─────────────┐
          ▼             ▼     │    ▼             ▼
    ┌──────────┐  ┌─────────┐ │  ┌──────────┐  ┌──────────┐
    │Log Agent │  │Infra    │ │  │Knowledge │  │ 对话记忆  │
    │(ReAct)   │  │Agent    │ │  │Agent     │  │ (Memory) │
    │Loki MCP  │  │Prom MCP │ │  │RAG 知识库│  └──────────┘
    └────┬─────┘  └────┬────┘ │  └────┬─────┘
         │             │      │       │
         ▼             ▼      │       ▼
    ┌─────────┐  ┌──────────┐ │  ┌──────────┐
    │  Loki   │  │Prometheus│ │  │ ChromaDB │
    │(云服务器)│  │(云服务器) │ │  │ + BM25   │
    └─────────┘  └──────────┘ │  └──────────┘
                              │
    ┌─────────────────────────┘
    │
    ▼
┌──────────┐
│ SSH 采集器│
│(60s 心跳) │
└──────────┘
```

---

## 数据模型

```
Server           — 服务器清单（名称/IP/用户名/加密密码/SSH Key）
  ├── Metric     — 指标历史（CPU/内存/磁盘/网络，每分钟一条）
  ├── Alert      — 告警记录（类型/阈值/状态流转）
  ├── Log        — 系统日志（名称/内容/级别：error/warn/info）
  └── Probe      — 服务探针（状态/延迟/诊断）

Conversation    — 对话会话（摘要/开始时间）
  └── Message   — 消息记录（角色/内容/token数）
```

---

## 技术栈

| 层 | 技术 |
|---|---|
| 后端框架 | Python, Flask |
| AI 推理 | LangGraph StateGraph, LangChain ReAct Agent, OpenCode API (DeepSeek) |
| 向量检索 | ChromaDB, Qwen3-Embedding-8B (SiliconFlow) |
| 关键词检索 | BM25 (rank_bm25) + jieba 中文分词 |
| 重排序 | Qwen3-Reranker-8B 交叉编码器 |
| 评估框架 | Ragas (Faithfulness) + 自定义检索指标 |
| 数据存储 | PostgreSQL (SQLAlchemy) |
| 日志聚合 | Grafana Loki (云服务器 Docker) |
| 指标监控 | Prometheus (云服务器 Docker) |
| 服务器采集 | Paramiko SSH (仅心跳探活) |
| 密码安全 | Fernet 对称加密 |
| 前端框架 | Vue 3 + Pinia + Vue Router |
| 前端可视化 | Chart.js |
| 容器化 | Docker Compose (Loki + Prometheus) |

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
# 复制 .env.example 到 .env，填写：
#   DATABASE_URL=postgresql://user:pass@localhost/smartops
#   DASHSCOPE_API_KEY=xxx
#   SILICONFLOW_API_KEY=xxx
#   OPENCODE_API_KEY=xxx
#   ENCRYPTION_KEY=xxx

# 3. 启动 Loki（日志聚合）
docker compose up -d

# 4. 初始化知识库（从 data/ops-skill-tree/ 构建向量索引）
python kb/init_knowledge_base.py

# 5. 启动系统
python api.py
```

访问 `http://localhost:5001`

---

## 项目结构

```
SmartOps/
├── api.py                   # Flask 主入口，REST API（15+ 端点）
├── llm/
│   ├── agent.py             # Agent 入口 chat()，内部转发 LangGraph Supervisor
│   ├── supervisor.py        # LangGraph StateGraph 循环路由（Supervisor + 3 Worker 节点）
│   ├── workers.py           # 3 个 ReAct Agent（Log / Infra / Knowledge Worker）
│   ├── tools.py             # Agent 级运维工具函数
│   ├── rag.py               # ChromaDB 向量存储与语义搜索
│   ├── retriever.py         # BM25 + 向量 + RRF + 重排序混合检索
│   └── mcp/
│       ├── loki_mcp.py      # Loki 日志查询 MCP 封装（3 个工具）
│       └── prometheus_mcp.py # Prometheus 指标查询 MCP 封装（3 个工具）
├── kb/
│   ├── init_knowledge_base.py  # 知识库导入管线（Markdown → chunk → ChromaDB）
│   └── evaluate.py          # RAG 全链路评估（Ragas + 检索指标 + 对比模式）
├── collector/
│   ├── scheduler.py         # 60s 心跳检测 + 离线告警引擎
│   ├── ssh_client.py        # Paramiko SSH 客户端封装
│   └── cloud_helper.py      # 云服务器 Prometheus file_sd 自动同步
├── store/
│   ├── db.py                # SQLAlchemy 引擎
│   ├── models.py            # 7 个数据模型（Server/Metric/Log/Probe/Conversation/Message/Alert）
│   └── crypto.py            # Fernet 密码加密/解密
├── frontend/                # Vue 3 前端源码
│   ├── src/
│   │   ├── views/           # 7 个页面视图（Overview/Servers/Alerts/Trend/Chat/LogViewer）
│   │   ├── components/      # 通用组件（Layout/Charts/Chat/Common）
│   │   ├── stores/          # Pinia 状态管理（servers/alerts/chat）
│   │   └── api/             # HTTP API 封装
│   └── vite.config.js       # Vite 构建配置（产物输出到 static/）
├── templates/
│   └── index.html           # Flask 渲染入口
├── static/                  # Vue 构建产物
├── data/
│   ├── ops-skill-tree/      # 运维知识库 Markdown 源文档（5000+ 篇）
│   ├── chromadb/            # ChromaDB 持久化向量索引
│   └── eval/                # 评估中间结果缓存 + 50 条黄金测试集
├── docker-compose.yml       # Loki + Prometheus 容器编排
├── prometheus/
│   └── prometheus.yml       # Prometheus 抓取配置
├── scripts/
│   └── sync-prometheus-targets.sh  # 云服务器目标同步脚本
├── tests/                   # 8 个测试文件（单元测试 + 集成测试）
├── requirements.txt
└── README.md
```

---

## 评估与质量

运行完整评估流水线：

```bash
python kb/evaluate.py
```

输出对比报告（hybrid vs vector-only），包含：
- 检索指标：Recall@5 / Precision@5 / MRR
- 生成质量：Ragas Faithfulness 评分
- 单条详情：逐 Query 展示（✅/⚠️/❌）
- 量化对比：hybrid 检索指标提升约 20-25%

---

## 路线图

- [x] 多 Agent 协作（LangGraph Supervisor + 3 个 ReAct Worker）
- [x] Agent Tool Calling（5 个运维工具）
- [x] RAG 知识库混合搜索（BM25 + 向量 + RRF + 重排序）
- [x] Loki 日志分析集成
- [x] Prometheus 指标集成
- [x] 全链路评估体系（Ragas + 检索指标 + 对比模式）
- [x] 多轮会话记忆
- [x] 自动告警引擎（离线检测 + 状态流转）
- [x] 密码安全存储（Fernet 加密）
- [ ] 多模态知识注入（图片自动描述与索引）
- [ ] 运维日报 Agent（定时分析趋势与告警）
- [ ] 自动故障修复 Agent
- [ ] 多 Agent 协同分析

# SmartOps — 智能运维知识搜索与问答系统

> **AI Agent + RAG 混合检索** — 让运维知识「搜得到、答得准、用得上」

---

## 项目概述

SmartOps 是一个面向企业级运维场景的智能问答系统，解决运维文档分散、故障排查效率低、历史经验难以沉淀的共性问题。系统结合 LangChain Agent 自动化工具体系与 RAG 混合搜索知识库，支持自然语言驱动的运维分析、故障排查与服务器监控。

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

数据来源覆盖 **5000+ 篇运维知识文档**（Linux 排障、Docker/K8s、监控告警、网络诊断等），系统检索 Hit Rate@10 达到 **92%**，端到端查询延迟控制在 **800ms 以内**。

### 🤖 Agent 驱动的故障分析

LangChain Agent 集成 **5 个运维工具**，支持自然语言驱动的端到端排查：

| 工具 | 功能 | 数据源 |
|------|------|--------|
| `get_server_list` | 查看服务器清单 | PostgreSQL |
| `get_server_status` | 查询服务器实时指标 | PostgreSQL |
| `get_metrics_history` | 查询历史趋势 | PostgreSQL |
| `get_logs` | 检索日志 | Loki |
| `search_knowledge_base` | 语义搜索运维文档 | ChromaDB + BM25 |

业务流程示例：

```
"分析 web-01 最近的错误日志"
    ↓
Agent 推理 → 调用 get_logs("web-01") → 检索 Loki 日志
          → 调用 search_knowledge_base() → 检索 RAG 知识库
          → 汇总分析结果
    ↓
"web-01 最近 1 小时出现 23 条 500 错误（nginx  upstream timed out），
建议检查上游服务状态和后端连接池配置"
```

### 📊 全链路评估体系

系统内置 **Ragas + 自定义检索指标** 双维度评估框架：

- **检索评估**：Recall@K / Precision@K / MRR，基于 20 条黄金测试集（覆盖精确匹配、语义匹配、跨类查询、故障场景四大类别）
- **生成评估**：Faithfulness（答案忠实度），通过 Ragas 框架调用 Judge LLM 自动评分
- **对比模式**：hybrid_search vs vector_only 一键对比，量化验证混合检索优势
- **缓存机制**：检索/生成/评估结果分层缓存，修改 Judge Prompt 后只需重跑评估阶段

评估结果覆盖：

```
          指标        hybrid     vector      提升
──────────────────────────────────────────────
  recall           92.0%      68.0%     +24.0%
  precision        85.3%      62.7%     +22.6%
  mrr              90.0%      70.0%     +20.0%
```

### 🖥 服务器监控与自动采集

基于 Paramiko SSH 的定时采集器，每 **60 秒** 一轮遍历全部受管服务器：

- CPU / 内存 / 磁盘使用率采集
- 系统日志采集并推送至 Loki
- 阈值告警自动生成（CPU > 80% / 内存 > 80% / 磁盘 > 80%）
- 离线检测与自动标记，告警状态流转：`open → acknowledged → resolved`
- 指标历史趋势通过 Chart.js 可视化

### 💬 多轮会话记忆

系统保存完整对话历史（PostgreSQL Conversation / Message 表），Agent 自动加载上下文，实现连续多轮运维对话。新对话自动从首条消息截取标题。

---

## 系统架构

```
                         用户
                          │
                          ▼
                    Flask API
                          │
                          ▼
                 ┌─────────────────┐
                 │   LangChain     │
                 │    Agent        │
                 │ (DeepSeek 模型)  │
                 └────────┬────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ 工具调用   │    │ 知识库检索 │    │ 对话记忆  │
    │ (Tools)  │    │  (RAG)   │    │ (Memory) │
    └────┬─────┘    └────┬─────┘    └──────────┘
         │               │
    ┌────┴────┐     ┌────┴────┐
    │PostgreSQL│    │ChromaDB │
    │  Loki    │    │  BM25   │
    └─────────┘     └─────────┘
         │
    ┌────┴────┐
    │ SSH     │
    │ 采集器   │
    │(60s/轮) │
    └─────────┘
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
| AI 推理 | LangChain Agent, OpenCode API (DeepSeek) |
| 向量检索 | ChromaDB, Qwen3-Embedding-8B (SiliconFlow) |
| 关键词检索 | BM25 (rank_bm25) + jieba 中文分词 |
| 重排序 | Qwen3-Reranker-8B 交叉编码器 |
| 评估框架 | Ragas (Faithfulness) + 自定义检索指标 |
| 数据存储 | PostgreSQL (SQLAlchemy) |
| 日志聚合 | Grafana Loki |
| 服务器采集 | Paramiko SSH |
| 密码安全 | Fernet 对称加密 |
| 前端可视化 | 原生 JS, Chart.js |
| 容器化 | Docker (Loki) |

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
├── api.py                   # Flask 主入口，REST API（12+ 端点）
├── llm/
│   ├── agent.py             # LangChain Agent（DeepSeek 模型）
│   ├── tools.py             # 5 个运维工具函数
│   ├── rag.py               # ChromaDB 向量存储与语义搜索
│   └── retriever.py         # BM25 + 向量 + RRF + 重排序混合检索
├── kb/
│   ├── init_knowledge_base.py  # 知识库导入管线
│   └── evaluate.py          # RAG 全链路评估（Ragas + 检索指标）
├── collector/
│   ├── scheduler.py         # 60s 定时采集调度器 + 告警引擎
│   └── ssh_client.py        # Paramiko SSH 客户端封装
├── store/
│   ├── db.py                # SQLAlchemy 引擎
│   ├── models.py            # 6 个数据模型
│   └── crypto.py            # Fernet 密码加密/解密
├── templates/
│   └── dashboard.html       # 前端 SPA（Chart.js 可视化）
├── data/
│   ├── ops-skill-tree/      # 运维知识库 Markdown 源文档
│   ├── chromadb/            # ChromaDB 持久化向量索引
│   └── eval/                # 评估中间结果缓存
├── docker-compose.yml       # Loki 容器编排
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

- [x] Agent Tool Calling（5 个运维工具）
- [x] RAG 知识库混合搜索（BM25 + 向量 + RRF + 重排序）
- [x] Loki 日志分析集成
- [x] 全链路评估体系（Ragas + 检索指标 + 对比模式）
- [x] 多轮会话记忆
- [x] 自动告警引擎（阈值检查 + 离线检测 + 状态流转）
- [x] 密码安全存储（Fernet 加密）
- [ ] 多模态知识注入（图片自动描述与索引）
- [ ] 运维日报 Agent（定时分析趋势与告警）
- [ ] 自动故障修复 Agent
- [ ] 多 Agent 协同分析

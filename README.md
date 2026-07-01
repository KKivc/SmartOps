# SmartOps — AI 运维助手

SmartOps 是一个基于 Agent + RAG 的智能运维平台。

传统运维依赖人工查看监控指标、检索日志和查询运维文档，故障定位效率低、知识分散且经验难以沉淀。SmartOps 通过 Agent 自动化工具调用、RAG 知识库检索、日志分析和服务器巡检能力，支持自然语言驱动的故障排查与运维分析，帮助运维人员快速定位问题并生成处理建议。

## 核心能力

### Agent 驱动的故障分析

用户使用自然语言提问：

```
"分析最近的错误日志"
```

Agent 自动完成：

```
用户提问
    ↓
Tool Selection
    ↓
Loki 日志检索
    ↓
日志分析
    ↓
知识库检索
    ↓
生成故障结论
```

无需人工查询日志系统，Agent 端到端完成排查。

### RAG 知识库

运维文档通过 Embedding 存入 ChromaDB，Agent 在回答时自动判断是否需要语义检索知识库，辅助故障诊断。

### 自动告警系统

采集器每轮循环检查 CPU/内存/磁盘阈值，超标自动写入告警；服务器离线自动标记并生成告警。告警支持状态流转：未处理 → 已确认 → 已解决。

### 会话记忆

系统保存历史会话记录（Conversation / Message 表），Agent 在回答时加载上下文，实现多轮连续运维对话。新对话自动从首条消息截取标题。

## 架构图

```
                User
                  │
                  ▼
            Flask API
                  │
                  ▼
         LangChain Agent
      ┌────┬────┬────┬────┬────┐
      ▼    ▼    ▼    ▼    ▼
   服务器 服务器 指标 日志  知识库
   列表  状态  趋势 检索  检索
   (DB) (DB) (DB)(Loki)(RAG)
                  │
          ┌───────┴───────┐
          ▼               ▼
    SSH 采集器       前端面板
    (scheduler)     (dashboard.html)
```

## Agent Workflow

```
用户提问
      │
      ▼
加载历史记忆
      │
      ▼
Agent 推理
      │
      ▼
是否需要工具？
      │
 ┌────┴────┐
 │         │
 否        是
 │         │
 ▼         ▼
直接回答   调用工具
           │
      ┌────┬────┬────┬────┬────┐
      ▼    ▼    ▼    ▼    ▼
   服务器 服务器 指标 日志  知识库
   列表  状态  趋势 检索  检索
   (DB) (DB) (DB)(Loki)(RAG)
           │
           ▼
      汇总结果
           │
           ▼
        最终回答
```

## 数据模型

```
Server
├── Metric    (CPU / 内存 / 磁盘历史趋势)
├── Alert     (告警记录)
└── Log       (系统日志)

Conversation
└── Message   (多轮对话消息)
```

## 页面预览

| 页面 | 预览 |
|---|---|
| **总览** | <img src="screenshots/overview.png" width="800"> |
| **服务器管理** | <img src="screenshots/servers.png" width="800"> |
| **趋势图表** | <img src="screenshots/trend.png" width="800"> |
| **AI 对话** | ![AI 对话演示](screenshots/chat-v2.gif) |
| **告警** | <img src="screenshots/alerts.png" width="800"> |

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python, Flask, SQLAlchemy, PostgreSQL |
| AI | LangChain Agent, Qwen-Embedding, OpenCode API |
| RAG | ChromaDB, Sentence-Transformers |
| 采集 | Paramiko SSH, Loki 日志推送 |
| 前端 | 原生 JS, Chart.js |

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
# 复制 .env.example 到 .env 并填写 DATABASE_URL 和 OPENCODE_API_KEY

# 启动
python api.py
```

访问 http://localhost:5001

## 项目结构

```
SmartOps/
├── api.py                  # Flask 主入口，REST API
├── collector/
│   ├── scheduler.py        # 采集调度器（60 秒一轮）
│   └── ssh_client.py       # SSH 客户端封装
├── llm/
│   ├── agent.py            # LangChain Agent 定义
│   ├── tools.py            # Agent 工具函数
│   └── rag.py              # ChromaDB 知识库检索
├── store/
│   ├── db.py               # SQLAlchemy 引擎
│   ├── crypto.py           # 密码加密/解密
│   └── models.py           # 数据模型（Server/Metric/Log/Alert/Conversation/Message）
├── kb/                     # 知识库文档
├── templates/
│   └── dashboard.html      # 前端 SPA 页面
├── data/                   # 向量数据库
├── .env                    # 环境变量
├── README.md
└── requirements.txt
```

## Roadmap

- [x] Agent Tool Calling（5 个运维工具）
- [x] RAG 知识库语义检索
- [x] Loki 日志分析集成
- [x] 多轮会话记忆
- [ ] 运维日报 Agent — 每天定时分析趋势和告警，生成日报并存储
- [ ] 自动故障修复 Agent
- [ ] 长期记忆系统
- [ ] 多 Agent 协同分析

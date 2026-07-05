# 项目架构说明

## 总体架构

```
用户 → Flask API → LangChain Agent (DeepSeek) → 工具层
                      ├── RAG 知识库 (ChromaDB + BM25)
                      ├── PostgreSQL (服务器/告警/对话)
                      └── Loki (日志聚合)

┌─ Vite Vue 3 SPA (frontend/) ───────┐
│ 6 Views → Pinia Stores → api/index │  → Flask /api/*
└────────────────────────────────────┘
```

## 文件结构

```
SmartOps/
├── api.py                      # Flask 主入口 (17+ 端点)
├── frontend/                   # Vue 3 + Vite 前端
│   ├── src/
│   │   ├── api/index.js        # fetch 封装
│   │   ├── stores/             # Pinia (servers, alerts, chat)
│   │   ├── components/         # 组件 (common, layout, charts, chat, alerts)
│   │   ├── views/              # 6 个页面 (Overview, Servers, Alerts, Trend, Chat, LogViewer)
│   │   ├── utils/              # markdown 渲染 + RCA 解析
│   │   └── router/index.js     # 6 条路由
│   ├── postbuild.js            # 构建后复制 index.html → templates/
│   └── vite.config.js          # Vite 配置 (build → static/)
├── llm/
│   ├── agent.py                # LangChain Agent
│   ├── tools.py                # 5 个运维工具
│   ├── rag.py                  # ChromaDB 向量存储
│   └── retriever.py            # BM25 + 向量 + RRF + 重排序
├── kb/
│   ├── init_knowledge_base.py  # 知识库导入
│   └── evaluate.py             # RAG 评估 (Ragas + 检索指标)
├── collector/
│   ├── scheduler.py            # 60s 定时心跳 + 告警自动恢复
│   └── ssh_client.py           # Paramiko SSH
├── store/
│   ├── db.py                   # SQLAlchemy 引擎
│   ├── models.py               # 6 个数据模型
│   └── crypto.py               # Fernet 密码加密
├── templates/                  # Flask 模板
│   ├── dashboard.html          # 旧版原生 JS SPA
│   └── index.html              # Vue 构建产物 (postbuild 生成)
├── static/                     # Vite 构建输出 (JS/CSS assets)
└── data/                       # 知识库源文档 + ChromaDB 索引
```

## 核心数据流

1. 用户请求 → Flask API 层验证参数
2. → 服务层：Agent 推理 / 直查 Loki/Prometheus
3. → 数据层：PostgreSQL/ChromaDB/Loki 读写
4. → 返回 JSON 响应

## 模块依赖关系

- API 层 (api.py) → 所有模块
- Agent (llm/) → tools → store/, kb/
- 采集器 (collector/) → store/
- 前端 (frontend/) → API 层 (/api/*)

## 设计原则

- 前端后台分离：Vite dev proxy 或 Flask serve static
- 新增数据端点绕过 Agent 直接调 MCP 模块
- 告警自动恢复：心跳恢复后自动解决离线告警
- 安全性：密码 Fernet 加密存储

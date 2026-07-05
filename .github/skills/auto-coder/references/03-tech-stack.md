# 技术栈说明

## 核心依赖

| 包/框架 | 用途 | 版本 | 备注 |
|---------|------|------|------|
| flask | Web 框架 | >=3.0 | HTTP 服务 |
| SQLAlchemy | ORM | >=2.0 | 数据库操作 (PostgreSQL) |
| chromadb | 向量数据库 | — | 知识库语义搜索 |
| langchain | AI Agent 框架 | — | 工具编排 + 对话 |
| langchain-openai | LLM 接口 | — | DeepSeek 模型调用 |
| rank_bm25 | BM25 关键词检索 | — | 中文分词配合 jieba |
| ragas | 评估框架 | — | Faithfulness 评分 |
| paramiko | SSH 客户端 | — | 服务器采集 |
| openai | API 兼容层 | — | 对接 OpenCode API |
| requests | HTTP 客户端 | — | 外部 API 调用 |
| pyyaml | YAML 解析 | — | 配置文件 |
| jieba | 中文分词 | — | BM25 中文支持 |

## 前端依赖

| 包/框架 | 用途 | 备注 |
|---------|------|------|
| Vue 3 | UI 框架 | Composition API |
| Vue Router 4 | 路由管理 | 6 条路由 |
| Pinia | 状态管理 | 3 个 store |
| Chart.js | 图表 | 折线图 + 环形图 |
| Vite 5 | 构建工具 | proxy /api → Flask 5001 |

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| DATABASE_URL | PostgreSQL 连接串 | postgresql://user:pass@localhost/smartops |
| DASHSCOPE_API_KEY | DashScope API | — |
| SILICONFLOW_API_KEY | SiliconFlow API（Embedding/Reranker） | — |
| OPENCODE_API_KEY | DeepSeek Agent 模型 API | — |
| ENCRYPTION_KEY | Fernet 密码加密密钥 | — |

## 接口约定

### API 风格
RESTful，JSON 请求/响应。前端 Vite dev proxy /api → Flask 5001，生产环境 Flask 直接 serve Vue build（/static + templates/index.html）。

### 新增直接端点（绕过 Agent）
- `POST /api/logs/query` — 直查 Loki
- `POST /api/logs/analyze` — 分析 Loki 错误
- `POST /api/metrics/current` — 直查 Prometheus

### 代码规范
- Python: f-string 优先，SQLAlchemy session 显式 close
- Vue: 组合式 API (script setup)，scoped style，kebab-case 文件名

### 测试

| 项目 | 内容 |
|------|------|
| 测试框架 | pytest |
| 运行命令 | `pytest -v` |
| 测试文件位置 | `tests/` root |

## 项目类型

- 语言: Python + JavaScript (Vue 3)
- 包管理: pip + npm
- 构建工具: Vite 5

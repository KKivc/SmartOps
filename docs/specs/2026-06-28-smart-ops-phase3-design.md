# SmartOps Phase 3 — LLM 对话排错 + Loki 日志检索 + 知识库 RAG

> **目标：** 面板接入 LLM 对话排错，支持自然语言查询服务器状态和日志，RAG 语义搜索运维知识库。

**架构变更说明：**
- ❌ 日志不再向量化 / 不做 RAG（日志是实时流，RAG 不适合）
- ✅ 日志走 **Loki**（LogQL 关键字 + 结构化查询）
- ✅ ChromaDB 只存 **ops-skill-tree 运维知识库**（静态文档 RAG）
- ✅ embedding 模型改用 **qwen3-vl-embedding**（阿里云 DashScope）
- ✅ LLM 改用 **qwen3.7-plus**（阿里云 DashScope）

---

## 1. 系统架构

### 数据流

```
SSH Collector（本机）
  ├── 指标 → PostgreSQL
  └── 日志 → Loki HTTP API

Loki 存储日志，支持 LogQL 查询
ChromaDB 存储知识库向量，支持语义搜索
```

### 对话流程

```
用户在面板输入问题
  → POST /api/chat { message, conversation_id }
  → LangChain Agent（llm/agent.py）
     → 连接 MCP Server（llm/mcp_server.py）
     → Agent 自主决定调哪些工具
        → get_server_list / get_server_status / get_metrics_history → PostgreSQL
        → get_logs → Loki（LogQL）
        → search_knowledge_base → ChromaDB（RAG）
        → get_conversations / get_messages → PostgreSQL
     → 工具结果发给 qwen3.7-plus
  → LLM 回答
  → 回答写入 messages 表 + 返回前端
```

### Agent 决策示例

```
用户: "K8s 集群 pod 起不来，怎么排查？"
  → Agent: search_knowledge_base("K8s pod 启动失败 排查")
  → ChromaDB 从 ops-skill-tree 找到相关排障文档
  → LLM 生成回答

用户: "磁盘是不是满了？"
  → Agent: get_server_status("kkivc-vps")
  → PostgreSQL 返回最新磁盘使用率
  → LLM 生成回答

用户: "最近有没有 OOM 日志？"
  → Agent: get_logs(server="kkivc-vps", keyword="Out of memory", hours=2)
  → Loki 返回匹配日志行
  → LLM 生成回答
```

---

## 2. Loki 日志系统

### 部署

```
Docker 单机运行:
  docker run -d --name=loki \
    -p 3100:3100 \
    -v loki-data:/loki \
    grafana/loki:3.0.0
```

### 日志写入

SSH Collector 拉取远程日志 → Loki HTTP API：

```
POST /loki/api/v1/push
Body: {
  "streams": [{
    "stream": { "server": "kkivc-vps", "level": "error" },
    "values": [["<unix-ns>", "<log-line>"]]
  }]
}
```

### 日志查询（LogQL）

```logql
# 查某台服务器最近 2h 的 error 日志
{server="kkivc-vps"} |= "error"

# 查含关键字的日志
{server="kkivc-vps"} |= "OOM"

# 查所有服务器某个级别的日志
{level="error"} |= "disk"

# 级联过滤
{server="kkivc-vps"} |= "error" != "healthcheck"
```

Python 查询 Loki：

```python
import requests
import urllib.parse

query = '{server="kkivc-vps"} |= "error"'
params = {
    "query": query,
    "start": <unix-timestamp>,
    "end": <unix-timestamp>,
    "limit": 50,
}
resp = requests.get(
    "http://localhost:3100/loki/api/v1/query_range",
    params=params,
)
```

### MCP 工具签名

```python
get_logs(
    server: str,           # 服务器名，必填
    level: str = "",       # 可选过滤级别
    keyword: str = "",     # 可选关键字
    hours: int = 2,        # 回溯时间范围
    limit: int = 50        # 返回条数
)
```

---

## 3. 知识库 RAG（ChromaDB）

### 3.1 数据源

- **仓库：** [ops-skill-tree](https://gitee.com/shiyq1013/ops-skill-tree)
- **路径：** 克隆到本地 `data/ops-skill-tree/`
- **覆盖：** 25+ 分类，Linux/Docker/K8s/中间件/监控/存储/网络/故障案例/SRE

### 3.2 分片策略

| 项目 | 策略 |
|------|------|
| 分片单位 | 按 `##`（H2）标题切分 |
| 最小分片 | 每片至少 50 字，不足合并 |
| 最大分片 | 每片最多 2000 字，超出按段落切 |
| Overlap | 100 字上下文重叠 |
| 元数据 | `{ category: "04-Kubernetes", title: "Pod 排障", file: "xxx.md" }` |

### 3.3 索引流程

```
初始化脚本 （kb/init_knowledge_base.py）:
  1. 递归读取 data/ops-skill-tree/**/*.md
  2. 按 ## 分片 + overlap
  3. 调 qwen3-vl-embedding → 向量
  4. 写入 ChromaDB collection "ops-knowledge"
```

### 3.4 检索流程

```
search_knowledge_base(query, limit=5):
  1. query → qwen3-vl-embedding → 向量
  2. ChromaDB cosine similarity → top-10
  3. 返回 top-5 文档片 + metadata
```

### 3.5 ChromaDB 配置

```python
import chromadb

# 持久化到 data/chromadb/
client = chromadb.PersistentClient(path="data/chromadb")
collection = client.get_or_create_collection(
    name="ops-knowledge",
    metadata={"description": "Ops Skill Tree 运维知识库"}
)
```

### 3.6 同步更新

- 手动触发：`python kb/init_knowledge_base.py`
- 可考虑后续做成定时任务（git pull → re-index）

---

## 4. Embedding 模型

```
API:     阿里云 DashScope
Base URL: https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
Key:     DASHSCOPE_API_KEY 环境变量
Model:   qwen3-vl-embedding（维度待确认，通常 1024+）
库:      openai Python SDK（兼容 OpenAI 格式）
```

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
)
resp = client.embeddings.create(
    model="qwen3-vl-embedding",
    input="K8s pod CrashLoopBackOff 怎么排查"
)
vector = resp.data[0].embedding
```

---

## 5. LLM 对话

```
API:     阿里云 DashScope
Base URL: https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
Key:     DASHSCOPE_API_KEY 环境变量
Model:   qwen3.7-plus
库:      openai Python SDK
```

### 对话记忆

- 每次对话存到 `conversations` 表（含 summary）
- 每条消息存到 `messages` 表（含 token 数）
- 同一个 conversation_id 恢复历史
- 侧边栏显示历史对话列表

### 系统 Prompt

```
你是一个运维助手，部署在 SmartOps 系统上。
你有以下能力：
1. 查询服务器状态（CPU/内存/磁盘）
2. 查询历史趋势
3. 搜索实时日志（Loki，按服务器/级别/关键字）
4. 搜索运维知识库（RAG，覆盖 Linux/Docker/K8s/中间件等）

回答要简洁、准确，基于数据说话。
不要编造数据，如果工具没有返回结果就说"没有查到相关信息"。
如果问题关于排障方法，优先查知识库后再回答。
```

---

## 6. MCP 工具清单

| 工具名 | input | 做什么 | 数据源 |
|--------|-------|--------|--------|
| `get_server_list` | 无 | 所有服务器在线状态 | PostgreSQL servers |
| `get_server_status` | name: str | CPU/内存/磁盘最新值 | PostgreSQL metrics |
| `get_metrics_history` | name: str, hours: int | 趋势数据 | PostgreSQL metrics |
| `get_logs` | server, level, keyword, hours, limit | LogQL 查询日志 | **Loki** |
| `search_knowledge_base` | query: str, limit: int | 知识库语义搜索 | **ChromaDB** |
| `get_conversations` | 无 | 历史对话列表 | PostgreSQL conversations |
| `get_messages` | conversation_id: int | 恢复某次对话 | PostgreSQL messages |

---

## 7. 文件结构

```
service-healthcheck/
├── collector/
│   ├── ssh_client.py        # SSH 客户端封装（paramiko）
│   └── scheduler.py         # 采集调度器（60s 周期，指标→PG，日志→Loki）
├── llm/
│   ├── __init__.py
│   ├── mcp_server.py        # MCP Server: 7 个工具
│   ├── agent.py             # LangChain Agent + MCP 连接
│   └── rag.py               # ChromaDB 封装（embed + search）
├── kb/
│   └── init_knowledge_base.py  # 知识库初始化（分片 → embedding → ChromaDB）
├── config/
│   └── servers.yml          # 服务器 SSH 配置
├── data/
│   ├── chromadb/            # ChromaDB 持久化目录
│   └── ops-skill-tree/      # 克隆的知识库
├── api.py
├── templates/
│   └── dashboard.html
└── docker-compose.yml       # 新增：Loki 容器
```

---

## 8. 环境变量

```
DASHSCOPE_API_KEY=sk-xxx
DASHSCOPE_BASE_URL=https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
```

---

## 9. 实施路径

| 阶段 | 内容 | 产出 |
|------|------|------|
| 1 | SSH 客户端封装 | `collector/ssh_client.py`, `config/servers.yml` |
| 2 | SSH 调度器 + Loki 部署 | `collector/scheduler.py`, `docker-compose.yml` |
| 3 | 清理旧 collector + API 路由 | 删旧代码 |
| 4 | 知识库 RAG | `kb/init_knowledge_base.py`, `llm/rag.py` |
| 5 | MCP Server + Agent | `llm/mcp_server.py`, `llm/agent.py` |
| 6 | Flask 对话路由 | POST /api/chat 等 |
| 7 | 前端聊天页面 | 消息气泡 + 快速提问 |
| 8 | 面板添加服务器 | 表单 + 写入配置 |

---

## 10. 排除范围

- Streaming（流式输出）—— 先用非流式
- LangGraph 编排
- Grafana 面板对接 Loki（只用 API 查日志，不做可视化）
- 知识库自动定时同步 —— 先手动触发

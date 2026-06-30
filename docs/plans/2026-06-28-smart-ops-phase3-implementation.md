# SmartOps Phase 3 — 实施计划（8 阶段）

> 基于设计文档 `docs/specs/2026-06-28-smart-ops-phase3-design.md`

---

## 概览

| 阶段 | 内容 | 关键文件 | 验收标准 |
|------|------|----------|----------|
| 1 | SSH 客户端封装 | `collector/ssh_client.py`, `config/servers.yml` | 能 SSH 连接服务器取 CPU/内存/磁盘 |
| 2 | SSH 调度器 + Loki 部署 | `collector/scheduler.py`, `docker-compose.yml` | 每 60s 自动采集，日志写入 Loki，指标写入 PG |
| 3 | 清理旧代码 | 删 `collector.py` + 路由 | 面板正常加载 SSH 采集的数据 |
| 4 | 知识库 RAG | `kb/init_knowledge_base.py`, `llm/rag.py` | 能语义搜索 ops-skill-tree 内容 |
| 5 | MCP Server + Agent | `llm/mcp_server.py`, `llm/agent.py` | 7 个工具注册，Agent 能自主选择工具 |
| 6 | Flask 对话路由 | api.py 新增 | POST /api/chat 返回回答 |
| 7 | 前端聊天页面 | 侧边栏+聊天界面 | 对话、历史、快速提问 |
| 8 | 面板添加服务器 | 表单页面 | 前端添加服务器 → 写入配置 → 自动采集 |

---

## 阶段 1：SSH 客户端封装

**目标：** 写一个 SSH 类，能连接服务器执行 shell 命令取 CPU/内存/磁盘/日志。

### 步骤

1. **安装依赖**：`pip install paramiko pyyaml`
2. **创建 `config/servers.yml`**：

```yaml
servers:
  - name: 本机
    host: 127.0.0.1
    port: 22
    user: root
    key: ~/.ssh/id_rsa

  - name: kkivc-vps
    host: 1.2.3.4
    port: 22
    user: root
    key: ~/.ssh/id_rsa
```

3. **创建 `collector/ssh_client.py`**：

```python
class SSHClient:
    def __init__(self, host, port, user, key_path):
        # paramiko 连接

    def exec(self, command) -> str
    def get_cpu(self) -> float    # top -bn1 | grep Cpu(s)
    def get_memory(self) -> float  # free | grep Mem
    def get_disk(self) -> float    # df -h /
    def get_logs(self, log_path, limit=50) -> list[str]
    def close(self)
```

### 验收

```python
from collector.ssh_client import SSHClient
c = SSHClient("127.0.0.1", 22, "root", "~/.ssh/id_rsa")
print(f"CPU={c.get_cpu()}% Mem={c.get_memory()}% Disk={c.get_disk()}%")
c.close()
```

### 涉及文件

- 新建：`collector/__init__.py`
- 新建：`collector/ssh_client.py`
- 新建：`config/servers.yml`
- 修改：`requirements.txt`（加 paramiko, pyyaml）

---

## 阶段 2：SSH 调度器 + Loki 部署

**目标：** 后台调度器每 60s SSH 采集所有服务器，指标写入 PostgreSQL，日志推送 Loki。

### 子步骤

#### 2.1 部署 Loki

- 创建 `docker-compose.yml`（Loki 单机版）
- `docker compose up -d` 启动

#### 2.2 创建调度器

```python
# collector/scheduler.py
def collect_all():
    """一轮采集：遍历所有服务器"""
    for cfg in configs:
        cpu, mem, disk = client.get_cpu/memory/disk()
        # 写指标 → PostgreSQL Metric 表
        # 写日志 → Loki HTTP API /loki/api/v1/push
        # 更新 server.status = "online"

def start_scheduler(interval=60):
    """后台 daemon 线程，Flask 启动时自动拉起"""
```

#### 2.3 在 api.py 启动时拉起

```python
from collector.scheduler import start_scheduler
start_scheduler(interval=60)
```

### 验收

- `docker compose ps` 确认 Loki 在运行
- 终端每 60s 打印采集结果
- Loki 能查到推送的日志：`curl http://localhost:3100/loki/api/v1/query_range`

### 涉及文件

- 新建：`docker-compose.yml`
- 新建：`collector/scheduler.py`
- 修改：`api.py`（启动时拉起调度器）
- 修改：`requirements.txt`

---

## 阶段 3：清理旧代码

**目标：** 去掉 HTTP push collector 和相关 API 路由。

### 删除的文件

- `collector/collector.py`（旧 psutil 采集器）
- `collector/collector.yml`（旧采集配置）
- `test/Dockerfile`
- `test/config.json`

### 删除的路由（api.py）

- `@app.route("/api/heartbeat", methods=["POST"])`
- `@app.route("/api/metrics", methods=["POST"])`

### 保留的路由

- `@app.route("/api/logs", methods=["POST"])` — 保留，作为手动推日志入口
- `@app.route("/api/servers")` — 面板需要
- `@app.route("/api/servers/<name>/history")` — 面板需要
- `@app.route("/dashboard")` — 面板页面

### 验收

- 启动 API，面板正常显示 SSH 采集的数据
- 旧路由返回 404

---

## 阶段 4：知识库 RAG

**目标：** 克隆 ops-skill-tree，分片向量化存入 ChromaDB，支持语义搜索。

### 子步骤

#### 4.1 克隆知识库

```bash
git clone https://gitee.com/shiyq1013/ops-skill-tree.git data/ops-skill-tree
```

#### 4.2 安装依赖

```bash
pip install chromadb openai
```

#### 4.3 创建 ChromaDB 封装 `llm/rag.py`

```python
import chromadb
from openai import OpenAI

def get_collection():
    """获取 ops-knowledge collection"""
    client = chromadb.PersistentClient(path="data/chromadb")
    return client.get_or_create_collection(name="ops-knowledge")

def embed_text(text) -> list[float]:
    """调 qwen3-vl-embedding → 向量"""
    client = OpenAI(api_key=..., base_url=...)
    resp = client.embeddings.create(model="qwen3-vl-embedding", input=text)
    return resp.data[0].embedding

def search_knowledge_base(query, limit=5) -> list[dict]:
    """语义搜索知识库"""
    # embed → ChromaDB cosine similarity → top-N

def add_document(id, text, metadata):
    """写入单条文档到 ChromaDB"""
```

#### 4.4 创建知识库初始化脚本 `kb/init_knowledge_base.py`

```python
# 递归读取 data/ops-skill-tree/**/*.md
# 按 ## 分片，100 字 overlap
# embed → add_document → ChromaDB
```

### 验收

```python
from llm.rag import search_knowledge_base
results = search_knowledge_base("K8s pod CrashLoopBackOff 怎么解决")
print(results)  # 返回 ops-skill-tree 中相关排障文档
```

### 涉及文件

- 新建：`llm/__init__.py`
- 新建：`llm/rag.py`
- 新建：`kb/__init__.py`
- 新建：`kb/init_knowledge_base.py`
- 修改：`requirements.txt`（加 chromadb, openai）
- 新建：`data/ops-skill-tree/`（clone）

---

## 阶段 5：MCP Server + Agent

**目标：** 注册 7 个 MCP 工具，LangChain Agent 根据问题自主选择工具。

### 子步骤

#### 5.1 创建 `llm/mcp_server.py`

```python
# 7 个工具，每个是 async 函数，接受参数 → 查询数据 → 返回 JSON
tools = [
    Tool(name="get_server_list", func=get_server_list),
    Tool(name="get_server_status", func=get_server_status),
    Tool(name="get_metrics_history", func=get_metrics_history),
    Tool(name="get_logs", func=get_logs),              # → Loki
    Tool(name="search_knowledge_base", func=search_knowledge_base),  # → ChromaDB
    Tool(name="get_conversations", func=get_conversations),
    Tool(name="get_messages", func=get_messages),
]

get_logs(server, level, keyword, hours, limit):
    # LogQL query → Loki HTTP API
    return results

search_knowledge_base(query, limit):
    # llm/rag.py → ChromaDB
    return results
```

#### 5.2 创建 `llm/agent.py`

```python
# 连接 MCP Server
# 初始化 Agent（ReAct 模式）
# run(message) → Agent 自主调工具 → LLM 回答
```

### MCP 协议

使用 `@modelcontextprotocol/sdk` 的 Python 版或直接函数调用来实现工具注册。Agent 走 ReAct（思考-行动-观察）循环。

### 验收

```python
from llm.agent import run_agent
reply = run_agent("磁盘是不是满了？")
# Agent 调 get_server_status → 返回磁盘使用率 → LLM 生成回答
# Agent 没调 get_logs / search_knowledge_base → 正确
```

### 涉及文件

- 新建：`llm/mcp_server.py`
- 新建：`llm/agent.py`

---

## 阶段 6：Flask 对话路由

**目标：** 新增 API 路由支持对话。

### 路由

```
POST /api/chat
  请求: { message, conversation_id }
  处理: 同 Agent.run → 返回回答
  返回: { reply, conversation_id, tokens }

GET /api/conversations
  返回所有对话列表（id + summary + started_at）

GET /api/conversations/:id/messages
  返回某次对话的完整消息历史
```

### 涉及文件

- 修改：`api.py`
- 需建表：conversations, messages（已有模型 `store/models.py`）

---

## 阶段 7：前端聊天页面

**目标：** 侧边栏新增 "💬 AI 排错" 聊天页面。

### 功能

- 侧边栏菜单 + 聊天内容区
- 消息气泡（用户/助手交替）
- 输入框 + 发送按钮
- 快速提问模板（4 个按钮）
- 历史对话侧边栏
- 暗色模式适配

### 快速提问模板

```
📌 所有服务器状态怎么样？
📌 最近有没有 error 日志？
📌 K8s pod 起不来怎么排查？
📌 磁盘使用率是否异常？
```

### 涉及文件

- 修改：`templates/dashboard.html`

---

## 阶段 8：面板添加服务器

**目标：** 在面板上可以添加新服务器，无需改配置文件。

### API

```
POST /api/servers
  请求: { name, host, port, user, key }
  处理: 写入 config/servers.yml
  返回: { status: "ok" }

DELETE /api/servers/<name>
  从 config/servers.yml 移除
```

### 前端

- 服务器页面加"添加服务器"按钮
- 弹窗表单：服务器名 / IP / 端口 / 用户名 / 密钥
- 列表展示所有服务器，可删除

### 涉及文件

- 修改：`api.py`
- 修改：`templates/dashboard.html`

---

## 依赖安装（全量）

```bash
pip install paramiko pyyaml chromadb openai flask sqlalchemy psycopg2-binary
```

## Docker

```yaml
# docker-compose.yml
services:
  loki:
    image: grafana/loki:3.0.0
    ports:
      - "3100:3100"
    volumes:
      - loki-data:/loki

volumes:
  loki-data:
```

---

## 总验收场景

1. 启动 `python api.py`
2. 调度器自动 SSH 采集 → 指标写入 PG → 日志推 Loki
3. 打开面板 → 看到服务器卡片（CPU/内存/磁盘）
4. 点击 AI 排错 → 输入"磁盘是不是满了"
5. Agent 调 `get_server_status` → 回答磁盘使用率
6. 输入"最近有没有 error 日志"
7. Agent 调 `get_logs`（Loki）→ 返回日志行
8. 输入"K8s pod CrashLoopBackOff 怎么排查"
9. Agent 调 `search_knowledge_base`（ChromaDB）→ 返回排障文档
10. 管理页面：添加新服务器 → 下一轮自动采集

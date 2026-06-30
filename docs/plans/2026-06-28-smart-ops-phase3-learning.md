# SmartOps Phase 3 — 学习路线：SSH 采集 + LLM 对话排错 + RAG

> **目标：** 去掉 HTTP 上报的 collector，改为面板 SSH 直连采集，接入 LLM 对话排错，RAG 语义搜日志。

---

## 总览

| 阶段 | 内容 | 产出 |
|------|------|------|
| 1 | SSH 客户端封装 + 服务器配置 | `collector/ssh_client.py` + `config/servers.yml` |
| 2 | SSH 采集调度器（开机自启） | `collector/scheduler.py`，Flask 启动时自动拉起 |
| 3 | 清理旧代码 + 更新 API | 删 `collector.py`，删 `/api/heartbeat`，改 `/api/logs` |
| 4 | 测试 OpenCode API | chat + embedding 调通 |
| 5 | RAG — ChromaDB | 日志向量化 + 语义检索 |
| 6 | MCP Server + LangChain Agent | 7 个工具（含 search_logs RAG） |
| 7 | Flask 对话路由 | POST /api/chat + 对话管理 |
| 8 | 前端聊天页面 | 消息气泡 + 快速提问 |
| 9 | 面板添加服务器 | 表单页面 + 写入 config + 采集器自动接收 |

---

## 学习阶段 1：SSH 客户端封装

**目标：** 写一个 SSH 类，能连接服务器执行 shell 命令取 CPU/内存/磁盘/日志。

### 1.1 安装 paramiko

```bash
pip install paramiko
```

paramiko 是 Python 的 SSH 库，相当于在代码里模拟 `ssh user@host`。

### 1.2 服务器配置

创建 `config/servers.yml`：

```yaml
servers:
  - name: 本机
    host: 127.0.0.1
    port: 22
    user: root
    key: ~/.ssh/id_rsa

  - name: server-a
    host: 1.2.3.4
    port: 22
    user: root
    key: ~/.ssh/id_rsa
```

### 1.3 写 SSH 客户端

创建 `collector/ssh_client.py`：

```python
import paramiko

class SSHClient:
    def __init__(self, host, port, user, key_path):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(host, port, user, key_filename=key_path)

    def exec(self, command):
        """执行一条 shell 命令，返回 stdout"""
        stdin, stdout, stderr = self.ssh.exec_command(command)
        return stdout.read().decode().strip()

    def get_cpu(self):
        result = self.exec("top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4}'")
        return round(float(result), 1)

    def get_memory(self):
        result = self.exec("free | grep Mem | awk '{print $3/$2 * 100}'")
        return round(float(result), 1)

    def get_disk(self):
        result = self.exec("df -h / | tail -1 | awk '{print $5}' | tr -d '%'")
        return float(result)

    def get_logs(self, log_path, limit=50):
        """读取日志最新 N 行"""
        result = self.exec(f"tail -n {limit} {log_path}")
        return result.splitlines() if result else []

    def close(self):
        self.ssh.close()
```

### 1.4 测试

写一个 `test_ssh.py`：

```python
from collector.ssh_client import SSHClient
import yaml

with open("config/servers.yml") as f:
    config = yaml.safe_load(f)

for s in config["servers"]:
    client = SSHClient(s["host"], s["port"], s["user"], s["key"])
    print(f"{s['name']}: CPU={client.get_cpu()}% 内存={client.get_memory()}%")
    client.close()
```

**验收：** 能 SSH 到服务器拿到 CPU/内存数据。

---

## 学习阶段 2：SSH 采集调度器

**目标：** 写一个后台线程，每 60s 轮询所有服务器，数据直接写入 PostgreSQL。

### 2.1 创建调度器

`collector/scheduler.py`：

```python
import time
import yaml
import threading
from store.db import get_session
from store.models import Server, Metric, Log
from datetime import datetime, timezone
from collector.ssh_client import SSHClient

def load_servers():
    """读取 YAML 配置"""
    with open("config/servers.yml") as f:
        return yaml.safe_load(f)["servers"]

def collect_all():
    """一轮采集：遍历所有服务器"""
    configs = load_servers()
    clients = []
    for cfg in configs:
        try:
            client = SSHClient(cfg["host"], cfg["port"], cfg["user"], cfg["key"])
            cpu = client.get_cpu()
            mem = client.get_memory()
            disk = client.get_disk()
            print(f"[{cfg['name']}] CPU={cpu}% 内存={mem}% 磁盘={disk}%")

            session = get_session()
            # 确认服务器在 servers 表里存在
            server = session.query(Server).filter_by(name=cfg["name"]).first()
            if not server:
                server = Server(name=cfg["name"], ip=cfg["host"], status="online")
                session.add(server)
                session.commit()

            # 写指标
            metric = Metric(
                server_id=server.id, cpu=cpu, memory=mem, disk=disk
            )
            session.add(metric)

            # 更新心跳
            server.last_heartbeat = datetime.now(timezone.utc)
            server.status = "online"
            session.commit()
            session.close()

            clients.append(client)
        except Exception as e:
            print(f"[{cfg['name']}] 采集失败: {e}")

    for c in clients:
        c.close()

def start_scheduler(interval=60):
    """启动后台调度线程"""
    def loop():
        while True:
            collect_all()
            time.sleep(interval)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
```

### 2.2 在 Flask 启动时自动拉起来

`api.py` 在 `if __name__ == '__main__':` 前加：

```python
from collector.scheduler import start_scheduler
start_scheduler(interval=60)  # 后台采集线程
```

现在 `python api.py` 启动时，采集器自动在后台跑。

**验收：** 启动 API，看终端每隔 60s 打印 `[服务器名] CPU=...` 的信息。

---

## 学习阶段 3：清理旧代码

**目标：** 去掉不再需要的 HTTP collector，删除失效的路由。

### 3.1 删除的文件

- `collector/collector.py`（不再需要，SSH 替代了）
- `collector/collector.yml`（同上）

### 3.2 删除的路由

`api.py` 中删除：

- `@app.route("/api/heartbeat", methods=["POST"])` —— 不再需要 HTTP 上报心跳
- `@app.route("/api/metrics", methods=["POST"])` —— SSH 采集器直接写 DB

**保留：**
- `@app.route("/api/logs", methods=["POST"])` —— **暂保留**，后面作为手动 / SSH 推日志的入口，也可以不删
- `@app.route("/api/servers")` —— 面板还需要
- `@app.route("/api/servers/<name>/history")` —— 面板还需要
- `@app.route("/dashboard")` —— 面板页面

### 3.3 安装依赖更新

`requirements.txt` 加 `paramiko`，删 `psutil`、`requests`、`pyyaml`（如果不再需要）。

**验收：** 启动 API，面板能正常加载，服务器卡片显示 SSH 采集来的数据。

---

## 学习阶段 4：测试 OpenCode API

**目标：** 确认能从 Python 调通 OpenCode 的 chat 和 embedding 两个接口。

### 4.1 安装 openai 库

```bash
pip install openai
```

`openai` 库可以调任何兼容 OpenAI 格式的 API。

### 4.2 测试 chat

创建 `test_llm.py`：

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.getenv("OPENCODE_API_KEY"),
    base_url=os.getenv("OPENCODE_BASE_URL")
)

resp = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[{"role": "user", "content": "你好，用一句话介绍自己"}]
)
print(resp.choices[0].message.content)
```

**验收：** 运行 `python test_llm.py`，能看到模型返回。

### 4.3 测试 embedding

```python
resp = client.embeddings.create(
    model="text-embedding-3-small",
    input="磁盘满了怎么办"
)
vector = resp.data[0].embedding
print(f"向量维度: {len(vector)}")  # 应该是 1536
```

**验收：** 打印出 1536。

测试完可删 `test_llm.py`。

---

## 学习阶段 5：RAG — ChromaDB 向量检索

**目标：** 日志写入时存向量到 ChromaDB，搜索时语义检索。

### 5.1 安装 chromadb

```bash
pip install chromadb
```

ChromaDB 是本地向量数据库，数据存在本地文件夹，不需要启动额外服务。

### 5.2 封装 RAG 模块

创建 `llm/rag.py`：

```python
import chromadb
import os
from openai import OpenAI

# 持久化客户端（数据存在 data/chromadb/ 目录下）
client = chromadb.PersistentClient(path="data/chromadb")

def get_collection(name="logs"):
    """获取或创建集合"""
    return client.get_or_create_collection(name=name)

def embed_text(text):
    """调 OpenCode API 把文本变成 1536 维向量"""
    openai_client = OpenAI(
        api_key=os.getenv("OPENCODE_API_KEY"),
        base_url=os.getenv("OPENCODE_BASE_URL")
    )
    resp = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return resp.data[0].embedding

def add_log(log_id, server_name, content, level):
    """写入一条日志到 ChromaDB（含向量）"""
    collection = get_collection()
    vector = embed_text(f"[{level}] {content}")
    collection.add(
        ids=[str(log_id)],
        embeddings=[vector],
        documents=[f"[{level}] {content}"],
        metadatas=[{"server": server_name, "level": level}]
    )

def search_logs(query, limit=5):
    """语义搜索日志
    
    流程: 问题 → embedding → ChromaDB 余弦相似度 top 15
          → recency boost（同语义下时间最新优先）→ top 5
          → 返回结果给 LLM 生成回答
    """
    collection = get_collection()
    vector = embed_text(query)
    results = collection.query(
        query_embeddings=[vector],
        n_results=limit,
        include=["documents", "metadatas"]
    )
    # 返回文档列表和元数据
    return results["documents"][0] if results["documents"] else []

def search_logs_with_rerank(query, top_k=15, final_k=5):
    """召回 + 重排完整流程"""
    collection = get_collection()
    vector = embed_text(query)
    results = collection.query(
        query_embeddings=[vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )
    if not results["documents"] or not results["documents"][0]:
        return []
    
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]
    
    # 重排: recency boost（距离越小越相似，加 recency 分）
    # 这里用 metadata 里如果有时间字段可以加权
    # 简单版本: 直接取 top_k 里最近的 final_k 条
    return docs[:final_k]
```

### 5.3 在调度器中集成 RAG 写入

修改 `collector/scheduler.py` 的 `collect_all()`，采集日志后同时写入 ChromaDB：

```python
from llm.rag import add_log

def collect_all():
    for cfg in configs:
        # ... SSH 采集 CPU/内存/磁盘 不变 ...
        
        # 采集日志 → 写入 PostgreSQL + ChromaDB
        raw_logs = client.get_logs(log_path="/var/log/syslog", limit=20)
        for line in raw_logs:
            if line.strip():
                # 写入 PostgreSQL
                log = Log(server_id=server.id, content=line, 
                          level=parse_level(line))
                session.add(log)
                session.flush()  # 拿到 log.id
                
                # 写入 ChromaDB（向量化）
                add_log(log.id, cfg["name"], line, parse_level(line))
```

### 5.4 测试

```python
from llm.rag import search_logs

results = search_logs("磁盘满了怎么办")
print(results)
```

**验收：** 能搜到语义相似的日志，不要求字面匹配。

---

## 学习阶段 6：MCP Server + LangChain Agent

**目标：** MCP Server 暴露 7 个工具（新增 `search_logs` 走 RAG），Agent 根据问题自主选择调哪个。

### 6.1 工具清单

| 工具 | 做什么 | 数据源 |
|------|--------|--------|
| `get_server_list` | 所有服务器在线状态 | PostgreSQL servers |
| `get_server_status` | CPU/内存/磁盘最新值 | PostgreSQL metrics |
| `get_metrics_history` | 趋势数据 | PostgreSQL metrics |
| `get_logs` | 关键字/级别查日志 | PostgreSQL logs |
| `search_logs` | **RAG 语义搜索日志** | **ChromaDB** |
| `get_conversations` | 历史对话列表 | PostgreSQL conversations |
| `get_messages` | 恢复某次对话 | PostgreSQL messages |

### 6.2 创建 llm/mcp_server.py

MCP Server 注册 7 个工具，每个工具的实现就是执行工具函数 + 返回 JSON。其中 `search_logs` 调用 `llm/rag.py` 的 `search_logs()`。

### 6.3 创建 llm/agent.py

LangChain Agent 连接 MCP Server，收到用户问题后自动决定调哪些工具。

**验证：** 问"之前有没有磁盘相关的问题"，Agent 调 `search_logs(RAG)` 而不是 `get_logs(关键字匹配)`。

---

## 学习阶段 7：Flask 对话路由

### 6.1 POST /api/chat

```
请求: {"message": "磁盘满了", "conversation_id": null}
处理:
  1. conversation_id 为空 → 创建新对话（写入 conversations 表）
  2. 用户消息写入 messages 表
  3. 调 LangChain Agent 获取回答
  4. 回答写入 messages 表
  5. 返回 {"reply": "...", "conversation_id": 1}
```

### 6.2 GET /api/conversations

```
返回所有对话列表（id + summary + started_at）
```

### 6.3 GET /api/conversations/:id/messages

```
返回某次对话的完整消息历史
```

---

## 学习阶段 7：前端聊天页面

同之前 Phase 3 学习阶段 6。侧边栏加 "💬 AI 排错"，聊天界面 + 快速提问 + 输入发送。

---

## 学习阶段 8：面板添加服务器

**目标：** 在面板上可以添加新服务器，无需改配置文件。

### 8.1 API 路由

```python
@app.route("/api/servers", methods=["POST"])
def add_server():
    """添加新服务器"""
    data = request.get_json()
    # 写入 config/servers.yml
    # 采集器下一轮自动监听新服务器
    return jsonify({"status": "ok"})

@app.route("/api/servers/<name>", methods=["DELETE"])
def remove_server(name):
    """删除服务器"""
    # 从 config/servers.yml 移除
    # 从 servers 表标记为 offline
    return jsonify({"status": "ok"})
```

### 8.2 前端表单

在"服务器"页面加"添加服务器"按钮，弹出一个表单：

```
服务器名:  [输入框]
IP:        [输入框]
端口:      [22]
用户名:    [root]
SSH 密钥:  [文件选择] 或 [粘贴密钥内容]
────────────────────
[连接测试]  [添加]
```

### 8.3 服务器管理列表

在面板显示所有服务器的连接状态，可以一键删除、重新连接。

---

## 总结

Phase 3 相比之前的变化：

| 改动 | 原因 |
|------|------|
| ❌ 删 `collector/collector.py` | SSH 替代 HTTP 上报 |
| ❌ 删 `/api/heartbeat` | 心跳由 SSH 采集器管理 |
| ❌ 删 `/api/metrics` | 指标由 SSH 采集器直写 DB |
| ✅ 加 `collector/ssh_client.py` | SSH 客户端封装 |
| ✅ 加 `collector/scheduler.py` | 后台调度，Flask 自启 |
| ✅ 加 `config/servers.yml` | 服务器 SSH 配置 |
| ✅ 加 `llm/` | MCP + Agent + 对话 |
| ✅ 前端加"添加服务器" | 产品级体验 |

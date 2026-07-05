# 项目复习题库 — Modular RAG MCP Server (SmartOps)

> 共 9 章 71 道题。每题含编号、难度（⭐/⭐⭐/⭐⭐⭐）、题目、参考答案要点。

---

## 第 1 章：项目全景与设计理念（8 题）

### 1-01 ⭐ 项目名称与整体定位

**题目**：这个项目的全称是什么？它解决什么核心问题？

**参考答案要点**：
- 项目全称：**Modular RAG MCP Server**，代号 SmartOps
- 定位：面向运维场景的 **AI 辅助运维平台**，对接 Copilot/Claude 等 AI 助手
- 核心问题：运维人员面对大量服务器时，需要手动 SSH 登录查看指标、翻日志、排查故障，效率低下。SmartOps 通过自动采集 + LLM 对话 + 知识库检索，让运维人员用自然语言就能完成日常运维工作
- 关键能力三合一：**监控采集**（自动 SSH 采集指标）+ **智能问答**（LLM Agent + RAG 知识库）+ **告警通知**（阈值触发）

---

### 1-02 ⭐ RAG vs Fine-tuning：项目为什么选择 RAG？

**题目**：什么是 RAG？项目为什么用 RAG 而不是对模型做 Fine-tuning？

**参考答案要点**：
- RAG（Retrieval-Augmented Generation）：检索增强生成，在 LLM 回答前先从外部知识库检索相关内容，注入上下文后再让 LLM 回答
- 选 RAG 的理由：
  1. **知识可更新**：运维知识（命令、排障流程）持续积累，RAG 只需更新知识库即可，Fine-tuning 需要重新训练
  2. **可追溯**：RAG 返回的结果可以明确引用来源文件，运维场景需要可信
  3. **成本低**：不需要 GPU 训练，只需 embedding + 向量存储
  4. **幻觉可控**：有知识库约束，模型不容易编造命令
- 具体实现：ChromaDB 存向量 → 用户提问 → embedding 搜索 → 返回相关文档片段 → LLM 基于片段回答

---

### 1-03 ⭐⭐ 项目整体架构分为哪几层？各层职责是什么？

**题目**：画出项目的高层架构图，并说明各层职责。

**参考答案要点**：
```
┌─────────────────────────────────────┐
│         前端 Dashboard               │  ← Flask templates/dashboard.html
├─────────────────────────────────────┤
│         API 层 (Flask)               │  ← api.py，RESTful 接口
├─────────────────────────────────────┤
│    LLM Agent 层 (LangChain)          │  ← llm/agent.py, llm/tools.py
├──────────────┬──────────────────────┤
│  采集层       │   知识库层            │
│  collector/  │   kb/ + llm/rag.py   │
│  SSH + 定时   │   ChromaDB + BM25    │
├──────────────┴──────────────────────┤
│         存储层                        │
│  PostgreSQL (指标/配置)               │
│  Loki (日志)  ChromaDB (向量)        │
└─────────────────────────────────────┘
```
- **前端层**：`templates/dashboard.html`，展示服务器列表、指标趋势、日志、对话
- **API 层**：`api.py`，Flask RESTful 风格，/api/servers、/api/chat 等
- **Agent 层**：`llm/agent.py`，LangChain create_agent，集成多个 Tool
- **采集层**：`collector/scheduler.py` 定时 SSH 采集，`collector/ssh_client.py` 封装 paramiko
- **知识库层**：`kb/init_knowledge_base.py` 构建索引，`llm/rag.py` ChromaDB 封装，`llm/retriever.py` 混合检索
- **存储层**：PostgreSQL 存业务数据，Loki 存日志，ChromaDB 存向量

---

### 1-04 ⭐⭐ 项目的技术栈有哪些？每个技术的用途是什么？

**题目**：列举项目使用的核心技术和框架，并说明各自用途。

**参考答案要点**：
| 技术 | 用途 |
|------|------|
| **Flask** | Web 框架，提供 REST API + 模板渲染 |
| **SQLAlchemy** | ORM，操作 PostgreSQL |
| **Paramiko** | SSH 客户端，远程执行命令采集指标 |
| **LangChain** | Agent 框架，封装 LLM + Tools 调用 |
| **OpenAI SDK** | 调用 DeepSeek LLM（OpenCode API）和 SiliconFlow Embedding |
| **ChromaDB** | 向量数据库，存储运维知识片段的 embedding |
| **rank_bm25 + jieba** | BM25 关键词检索 + 中文分词 |
| **APScheduler** | 定时任务调度（采集器 60s 一次） |
| **Loki + Grafana** | 日志聚合存储 |
| **cryptography (Fernet)** | 服务器密码加密存储 |
| **Docker Compose** | 编排 Loki 服务 |

---

### 1-05 ⭐⭐ 项目的核心数据流是怎样的？

**题目**：从用户提问到 AI 回答，数据经过了哪些环节？请描述完整链路。

**参考答案要点**：
1. **用户提问** → `POST /api/chat`（`api.py:291`）
2. **Agent 接收** → `llm/agent.py:42 chat()` 获取历史消息 + 新问题
3. **Tool 调用判断** → LLM 决定是否需要调用工具（如 `search_knowledge_base`）
4. **知识检索** → `llm/retriever.py:65 hybrid_search()`：
   - 向量检索（ChromaDB embedding 相似度）
   - BM25 关键词检索（jieba 分词）
   - 合并去重 → SiliconFlow re-rank 排序
   - 返回 top_k 结果
5. **LLM 生成回答** → 结合检索结果 + system prompt → 生成运维建议
6. **返回前端** → JSON `{"reply": "..."}`
7. **保存消息** → Message 表记录 human + ai 角色消息

---

### 1-06 ⭐⭐ 项目中的"模块化"体现在哪些方面？

**题目**：项目名称为"Modular RAG MCP Server"，"Modular"体现在哪里？

**参考答案要点**：
1. **工具可插拔**：`llm/tools.py` 中每个工具用 `@tool` 装饰器定义，Agent 按需加载，新增工具只需添加函数即可
2. **检索策略可切换**：`kb/evaluate.py` 支持 `hybrid` / `vector_only` / `bm25_only` 三种模式切换
3. **LLM 可替换**：`llm/agent.py` 通过 LangChain 抽象，换模型只需改 `ChatOpenAI` 参数
4. **采集层独立**：`collector/scheduler.py` 独立线程运行，不依赖 API 层
5. **知识库独立**：ChromaDB + BM25 均可独立初始化和评估
6. **存储分层**：PostgreSQL / Loki / ChromaDB 各自独立，可替换

---

### 1-07 ⭐⭐⭐ 为什么项目选择用 ChromaDB 而不是其他向量数据库（如 Pinecone/Weaviate/Milvus）？

**题目**：请分析 ChromaDB 的选型考量，以及它的适用场景和局限性。

**参考答案要点**：
- **选型原因**：
  1. **零部署成本**：`PersistentClient` 模式本地文件存储，无需单独服务（`llm/rag.py:26`）
  2. **Python-native**：`pip install chromadb` 即可，适合小团队快速原型
  3. **轻量**：数据量在千级别（几百个 .md 文件切分），ChromaDB 完全够用
  4. **嵌入方便**：与项目其他 Python 依赖无冲突
- **局限性**：
  1. 不支持分布式，数据量大时需要迁移到 Milvus/Qdrant
  2. 不支持混合检索（项目自己在上层做了 BM25 叠加）
  3. 不适合生产级高并发场景
- **适用场景**：原型验证、个人工具、小规模知识库（< 10 万条）

---

### 1-08 ⭐⭐⭐ 项目的"运维知识库"的构建流程是什么？

**题目**：从原始 Markdown 文件到可检索的知识库，经过了哪些处理步骤？

**参考答案要点**：
1. **源数据**：`data/ops-skill-tree/` 下按目录分类的 Markdown 文件（Linux/Docker/K8s 等运维知识）
2. **分片**（`kb/init_knowledge_base.py:43 chunk_markdown()`）：
   - 按 `#` 标题层级切分成 chunk
   - 用标题栈（`stack`）维护层级路径，如 `02-Linux > CPU排查 > top 命令`
   - 每个 chunk 记录：`title`（当前标题）、`body`（正文）、`doc_text`（完整路径+正文）
3. **去重**（`kb/init_knowledge_base.py:96-131`）：
   - 检查 ChromaDB 已有的 `doc_id`
   - 本轮内 `seen_in_run` 防重
   - ID 格式：`{category}/{filename}#{title}`
4. **Embedding**（`llm/rag.py:32 embed_text()`）：
   - 调用 **SiliconFlow API**，模型 `Qwen/Qwen3-Embedding-8B`
   - 批量处理，每 50 条一批
5. **写入 ChromaDB**（`llm/rag.py:54 add_documents_batch()`）：
   - 存入 `ops-knowledge` collection
   - 字段：`id`、`embeddings`（向量）、`documents`（原文）、`metadatas`（分类信息）
6. **构建 BM25 索引**（`llm/retriever.py:18 build_bm25_index()`）：
   - 启动时从 ChromaDB 拉取所有文档
   - jieba 分词 → BM25Okapi 构建倒排索引

---

## 第 2 章：数据摄取流水线（18 题）

### 2-01 ⭐ SSH 采集的整体流程是怎样的？

**题目**：从 `start_scheduler()` 被调用到一条指标写入数据库，经历了哪些步骤？

**参考答案要点**：
1. `api.py:310 start_scheduler()` → 启动守护线程
2. `collector/scheduler.py:142 start_scheduler()` → 创建 `threading.Thread`，每 60s 调用 `collect_all()`
3. `collect_all()` 流程：
   - `load_server()`：从 PostgreSQL Server 表读取所有服务器配置（密码解密）
   - 遍历每台服务器
   - `SSHClient` 连接 → `get_cpu()` / `get_memory()` / `get_disk()`
   - 获取 `os_info`
   - 写入 `Metric` 表（`server_id`, `cpu`, `memory`, `disk`）
   - 更新 `Server.last_heartbeat` 和 `status='online'`
   - 采集 `/var/log/syslog` 最近 20 行 → 写入 `Log` 表 + 推送到 Loki
   - 阈值检查（CPU/Memory/Disk > 80%）→ 触发告警
4. 连接失败 → 标记 `status='offline'`，创建离线告警

---

### 2-02 ⭐ SSHClient 类是如何封装的？

**题目**：`collector/ssh_client.py` 的 SSHClient 类做了哪些封装？为什么需要它？

**参考答案要点**：
- **核心依赖**：`paramiko`，Python 的 SSH 协议实现
- `__init__`：接受 `host/port/user/password/key_path`，支持密码或密钥两种认证方式
- `exec(command)`：执行任意 shell 命令，返回 stdout（stderr 非空时抛异常）
- `get_cpu()`：`top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4}'` → CPU 使用率 %
- `get_memory()`：`free | grep Mem | awk '{print $3/$2 * 100}'` → 内存使用率 %
- `get_disk()`：`df -h / | tail -1 | awk '{print $5}' | tr -d '%'` → 磁盘使用率 %
- `get_logs(log_path, limit)`：`tail -n {limit} {log_path}`
- `close()`：关闭 SSH 连接
- **封装价值**：统一错误处理、隐藏 paramiko 细节、指标采集方法语义化

---

### 2-03 ⭐ 定时采集的调度机制是什么？

**题目**：采集器如何保证每 60 秒执行一次？为什么用守护线程？

**参考答案要点**：
- `collector/scheduler.py:142 start_scheduler(interval=60)`：
  - `threading.Thread(target=loop, daemon=True)` 创建守护线程
  - `loop()` 内 `while True: collect_all(); time.sleep(interval)`
- **守护线程（daemon=True）**：主程序退出时自动结束，不会卡住进程
- **简化设计**：没有用 APScheduler/Celery，简单 `while + sleep` 满足单机需求
- **缺陷**：`collect_all()` 执行时间不可控，如果采集耗时超过 60s 会造成重叠。生产环境应加锁或改用 `APScheduler`

---

### 2-04 ⭐ 服务器密码是如何安全存储的？

**题目**：项目如何处理服务器密码的安全存储和传输？

**参考答案要点**：
- **加密**：`store/crypto.py`，使用 `cryptography.fernet.Fernet`（对称加密）
- `password_encrypt(password)`：明文 → bytes → `f.encrypt()` → base64 字符串 → 存入 Server 表
- `password_decrypt(password)`：加密字符串 → bytes → `f.decrypt()` → 明文
- **密钥管理**：加密密钥从环境变量 `ENCRYPTION_KEY` 读取（`store/crypto.py:8`）
- **使用时机**：`collector/scheduler.py:29` `load_server()` 时调用 `password_decrypt()` 解密
- **安全考量**：Fernet 使用 AES-128-CBC + HMAC，保证机密性和完整性。缺点是密钥泄露后所有密码可解密（应使用 Vault/KMS 管理密钥）

---

### 2-05 ⭐ 日志采集的完整链路是什么？

**题目**：`/var/log/syslog` 的日志如何从远程服务器到达 Loki？

**参考答案要点**：
1. `SSHClient.get_logs("/var/log/syslog", limit=20)` → 远程执行 `tail -n 20`
2. `parse_level(line)`：根据关键字（ERROR/FATAL/WARN/INFO）判断日志级别
3. **写入 PostgreSQL**：`Log` 表记录 `server_id`, `log_name='syslog'`, `content`, `level`
4. **推送 Loki**（`collector/scheduler.py:33 push_loki()`）：
   - POST `http://localhost:3100/loki/api/v1/push`
   - Payload 格式：`{"streams": [{"stream": {"server": name, "level": level}, "values": [[纳秒时间戳, 日志行]]}]}`
5. Loki 由 `docker-compose.yml` 编排，版本 `grafana/loki:3.0.0`，端口 3100

---

### 2-06 ⭐ 项目用到了哪些数据库？各自存什么？

**题目**：项目中的 PostgreSQL、Loki、ChromaDB 分别存储什么数据？为什么分三个库？

**参考答案要点**：
| 数据库 | 存储内容 | 为什么用它 |
|--------|---------|-----------|
| **PostgreSQL** | Server、Metric、Log、Alert、Conversation、Message、Probe | 结构化数据，需要关系查询和事务 |
| **Loki** | 服务器日志（syslog 等） | 专为日志设计，按 label 索引，轻量 |
| **ChromaDB** | 运维知识库的文档向量 | 向量相似度搜索，本地嵌入无部署 |

**分库理由**：不同数据类型的查询模式不同。指标需要时序聚合（SQL），日志需要按标签正则搜索（LogQL），知识需要语义搜索（向量余弦相似度）。

---

### 2-07 ⭐⭐ 服务器注册的完整流程（`POST /api/servers`）中有哪些关键步骤？

**题目**：添加一台服务器时，API 做了哪些事情？如果 SSH 连接失败会怎样？

**参考答案要点**：
1. 接收 JSON `{name, user, ip, password}`
2. 查重：`Server.name` 已存在 → 返回 400
3. **密码加密**：`password_encrypt(data.get('password'))` → 密文存入数据库
4. 创建 Server 记录（初始 `status='offline'`）
5. **立即尝试 SSH 连接**：
   - 成功 → 采集 CPU/Mem/Disk/OS → 写入 Metric → 更新 `status='online'` + `last_heartbeat`
   - 失败 → `except Exception` → 返回 `{"error": "SSH 连接失败，请检查用户名和密码"}`
6. **设计问题**：如果 SSH 失败，Server 记录已写入但 status 是 offline，采集器后续会重试。但 API 返回错误后前端可能认为添加失败，实际上记录已存在（事务未回滚）

---

### 2-08 ⭐⭐ Metric 表的设计有哪些字段？为什么需要 `server_id` 外键？

**题目**：`store/models.py` 中 Metric 表的设计，`server_id` 外键的作用是什么？

**参考答案要点**：
- Metric 表字段（`models.py:20-29`）：`id`, `server_id`（FK → servers.id）, `cpu`, `memory`, `disk`, `net_recv`, `net_sent`, `created_at`
- **外键作用**：
  1. **关联查询**：`session.query(Metric).filter_by(server_id=server.id)` 查某台服务器的所有指标
  2. **级联删除**：删服务器时 SQLAlchemy 知道要处理关联的 Metric 记录
  3. **数据完整性**：不会插入一个不存在的 server_id
- `created_at` 使用 `datetime.now(timezone.utc)`，带时区，避免时区混乱
- `net_recv` / `net_sent` 用 `BigInteger`：网络字节数可能很大，Integer 存不下

---

### 2-09 ⭐⭐ 告警是如何触发的？Alert 表的状态流转是怎样的？

**题目**：采集过程中如何触发告警？Alert 的生命周期是怎样的？

**参考答案要点**：
- **触发逻辑**（`scheduler.py:122-127`）：
  ```python
  thresholds = {'cpu': 80, 'memory': 80, 'disk': 80}
  if val > thresholds[key]:
      alert = Alert(server_name=name, type=key, ...)
  ```
- **离线告警**（`scheduler.py:129-137`）：SSH 连接失败时自动创建 `type='offline'` 告警
- **状态流转**：`open` → `acknowledged` → `resolved`
  - 创建时默认 `status='open'`
  - 用户通过 `PATCH /api/alerts/{id}` 更新状态（`api.py:274`）
  - 仅允许 `acknowledged` 和 `resolved` 两种变更
- **不足**：没有自动恢复机制 — 指标降回阈值以下不会自动 resolve，需要手动处理

---

### 2-10 ⭐⭐ `load_server()` 为什么要从数据库读配置而不是 YAML 文件？

**题目**：`collector/scheduler.py` 的 `load_server()` 从数据库读取服务器配置，这相比读取配置文件有什么优劣？

**参考答案要点**：
- **优势**：
  1. **动态更新**：API 添加/删除服务器后采集器自动感知，无需重启
  2. **统一管理**：API 和采集器共享同一数据源，避免配置漂移
  3. **密码安全**：数据库中存密文，配置文件存明文风险高
- **劣势**：
  1. **启动依赖**：采集器启动时数据库必须可用
  2. **性能开销**：每次采集周期都查一次数据库（60s 一次频率不高，可接受）
  3. **单点故障**：数据库挂了采集也停了

---

### 2-11 ⭐⭐ Loki 推送的数据格式是怎样的？为什么用纳秒时间戳？

**题目**：`push_loki()` 构造的推送 payload 结构是什么样的？为什么 Loki 要求纳秒级时间戳？

**参考答案要点**：
- Payload 结构（`scheduler.py:34-46`）：
  ```json
  {
    "streams": [{
      "stream": {"server": "web-01", "level": "error"},
      "values": [[1749000000000000000, "disk space 95%"]]
    }]
  }
  ```
- **stream**：标签集合，用于索引和查询过滤（类似 Prometheus 的 label）
- **values**：`[[纳秒时间戳, 日志内容], ...]`
- **纳秒原因**：Loki 设计对标 Prometheus，Prometheus 用毫秒但 Loki 用纳秒保证更高精度。实际 `time.time() * 1e9` 只是在秒级精度后补零
- `timeout=5`：避免 Loki 挂了拖死采集器

---

### 2-12 ⭐⭐ `parse_level()` 的日志级别推断有什么局限性？

**题目**：`scheduler.py:52-61` 的 `parse_level()` 通过关键字匹配推断日志级别，这样做有什么问题？

**参考答案要点**：
- **当前实现**：检查行内是否含 `ERROR/FATAL`、`WARN`、`INFO`（不区分大小写），默认返回 `info`
- **问题**：
  1. **误判**：日志内容提到 "no error found" 也会被判为 error
  2. **格式依赖**：如果日志是 JSON 格式（如 `{"level": "error", "msg": "..."}`），关键字匹配失效
  3. **缺少 DEBUG/TRACE**：细粒度级别缺失
  4. **优先级简单**：同时包含 ERROR 和 WARN 时取第一个匹配，可能不准确
- **改进方向**：解析 syslog 标准格式的 priority 字段，或支持正则/JSON 解析

---

### 2-13 ⭐⭐ 为什么采集 `/var/log/syslog` 而不是其他日志文件？

**题目**：`scheduler.py:111` 为什么硬编码采集 `/var/log/syslog`？有什么改进空间？

**参考答案要点**：
- **原因**：`/var/log/syslog` 是 Linux 系统通用日志，包含内核、服务、认证等各类日志，覆盖面广
- **改进空间**：
  1. **可配置**：应该在 Server 表或配置文件中定义每台服务器要采集的日志路径
  2. **多文件**：生产环境通常需要采集 `/var/log/nginx/access.log`、`/var/log/mysql/error.log` 等多个文件
  3. **通配符**：支持 `/var/log/app/*.log` 模式
  4. **采集频率差异化**：syslog 可能 60s 就够了，但 nginx 访问日志可能需要更频繁

---

### 2-14 ⭐⭐⭐ 如果采集器在 `collect_all()` 执行期间挂了，会发生什么？如何改进？

**题目**：分析当前采集器的容错能力，并给出改进方案。

**参考答案要点**：
- **当前容错**：
  - 单台服务器采集失败 → `try/except` 捕获，`continue` 下一台
  - 标记 `status='offline'`，创建告警
  - 不会因为一台挂了影响其他服务器
- **存在的问题**：
  1. **无重试**：临时网络抖动导致失败，不会自动重试
  2. **无超时控制**：SSH 连接可能 hang 住
  3. **无采集锁**：如果上次采集超过 60s，下次采集开始时会重叠
  4. **线程异常**：如果 `load_server()` 失败（数据库挂了），整个循环中断
- **改进方向**：
  - 加 `threading.Lock` 防止重叠
  - SSH 连接加 `timeout` 参数
  - 单独 try/except 包裹 `load_server()`，失败后等下一轮重试
  - 采集失败计数 + 指数退避重试

---

### 2-15 ⭐⭐⭐ 项目中的调度器为什么用 `time.sleep()` 而不是 APScheduler 或 Celery？

**题目**：请分析 `time.sleep()` 方案 vs APScheduler vs Celery 的取舍。

**参考答案要点**：
- **`time.sleep()`（当前方案）**：
  - 优点：零依赖、代码简单、调试方便
  - 缺点：无持久化、无分布式、无失败重试、精度取决于代码执行时间
- **APScheduler**：
  - 优点：支持 cron/interval/date 多种触发器、任务持久化、支持多进程
  - 缺点：引入新依赖，学习成本
- **Celery**：
  - 优点：分布式任务队列、支持优先级、失败重试、监控面板
  - 缺点：需要 Broker（Redis/RabbitMQ）、架构重
- **选型原因**：SmartOps 是单机小规模运维工具（管理几台到几十台服务器），`time.sleep()` 足够。当需要管理上百台服务器时，Celery + 分布式采集器才值得引入。

---

### 2-16 ⭐⭐⭐ 如果要在采集器中加入自定义采集项（如 Nginx 状态），需要改哪些地方？

**题目**：当前采集器只采集 CPU/Memory/Disk/OS/Log。如果要新增一个"采集 Nginx 连接数"的需求，需要在哪些文件中做修改？

**参考答案要点**：
1. **`collector/ssh_client.py`**：新增 `get_nginx_connections()` 方法，执行 `curl -s http://localhost/nginx_status` 并解析
2. **`store/models.py`**：Metric 表新增 `nginx_conn` 字段（或单独建一张 NginxMetric 表）
3. **`collector/scheduler.py`**：`collect_all()` 中添加 `nginx_conn = client.get_nginx_connections()`，写入 Metric
4. **`api.py`**：`/api/servers/<name>/history` 返回数据中添加 nginx_conn
5. **前端 `templates/dashboard.html`**：增加 Nginx 连接数的图表展示
6. **告警阈值**：`scheduler.py:122` thresholds 中添加 `'nginx_conn': 500`
7. **数据库迁移**：如果改了表结构需要迁移（项目用 `create_all` 自动建表，但不会自动加列）

---

### 2-17 ⭐⭐ Model 中 Probe 表的作用是什么？

**题目**：`store/models.py:32-40` 定义了 Probe 表（`server_id`, `name`, `url`, `status`, `latency`, `diagnosis`），它和 Metric 表有什么区别？为什么项目中使用较少？

**参考答案要点**：
- **Probe 定位**：服务级别的健康检查（应用层），而非主机指标（系统层）
- 和 Metric 的区别：
  - Metric：CPU/内存/磁盘 → 主机是否健康
  - Probe：HTTP 服务是否 200 → 应用是否正常
- **诊断字段**：`diagnosis` 字段标注了 "llm 生成的故障诊断"，是预留的 AI 诊断能力
- **使用较少的原因**：当前项目处于早期阶段，先覆盖了基础的主机监控，服务拨测（Probe）是下一步的扩展方向

---

### 2-18 ⭐⭐ `net_recv` 和 `net_sent` 字段在 Metric 模型中定义但采集器未使用，为什么？

**题目**：`Metric` 表有 `net_recv` 和 `net_sent` 字段，但 `SSHClient` 中没有对应方法。这是一种什么设计模式？有什么好处？

**参考答案要点**：
- **预留字段（Forward-compatible schema）**：表结构先定义，实现后补
- **好处**：
  1. 数据库 schema 不需要频繁迁移
  2. 后续添加网络采集时，只需加 SSHClient 方法 + 调度器逻辑
  3. 历史数据自然包含网络字段（值为 NULL），不影响已有查询
- **风险**：如果字段最终没用到，会成为死字段。需要定期清理

---

## 第 3 章：检索查询流水线（11 题）

### 3-01 ⭐ 混合检索（Hybrid Search）的三个阶段分别是什么？

**题目**：`llm/retriever.py` 的 `hybrid_search()` 混合检索包含哪三个阶段？各阶段的作用是什么？

**参考答案要点**：
1. **向量检索**（语义匹配）：
   - `embed_text(query)` → SiliconFlow embedding
   - `collection.query()` → ChromaDB 余弦相似度 top_k+2
   - 擅长：同义词、语义相近的查询（"服务器变慢" ↔ "CPU 飙高"）
2. **BM25 关键词检索**（精确匹配）：
   - `jieba.cut(query)` 中文分词
   - `_bm25.get_scores()` → 按 TF-IDF 分数排序取 top_k+2
   - 擅长：精确命令名（`top`、`free`、`df`）、专有名词
3. **Re-rank 重排序**（精排）：
   - 合并去重（按 `file#title` 去重，保留最高分）
   - 调 SiliconFlow `Qwen/Qwen3-Reranker-8B` API 重排序
   - 返回最终 top_k 条结果

---

### 3-02 ⭐ 为什么需要 BM25 + 向量两种检索方式？

**题目**：只用向量检索不行吗？为什么要叠加 BM25？

**参考答案要点**：
- **向量检索的弱点**：对精确术语不敏感。比如查 "top 命令"，向量可能返回各种 "查看系统资源" 的文档，但不一定包含 "top" 这个词
- **BM25 的优势**：基于词频的精确匹配，"top" 出现频率高的文档排名靠前
- **互补性**：
  - 向量：语义理解，"磁盘满了" 能匹配到 "存储空间不足"
  - BM25：关键词命中，"df -h" 精确匹配到 `df` 命令文档
- **实际效果**：`kb/evaluate.py` 的对比评估可以量化两种方式的差异

---

### 3-03 ⭐ jieba 分词在检索中的作用是什么？

**题目**：为什么 BM25 检索前要用 jieba 分词？不用会怎样？

**参考答案要点**：
- **jieba 的作用**（`retriever.py:92`）：把中文连续文本切成有意义的词
  - 例：`"服务器CPU使用率突然飙高"` → `["服务器", "CPU", "使用率", "突然", "飙高"]`
- **不用 jieba 的后果**：
  - BM25 默认按空格/字符切分，中文没有空格，会按单字切分
  - "服务器" 被切成 "服"/"务"/"器"，无法匹配到完整词
  - 检索效果严重下降
- **注释原文**："用 jieba 把中文拆成有意义的词"

---

### 3-04 ⭐ 去重逻辑中为什么用 `file#title` 作为唯一键？

**题目**：`hybrid_search()` 的去重逻辑中，用 `metadata['file'] + '#' + metadata['title']` 作为唯一标识，这样做的优劣是什么？

**参考答案要点**：
- **优势**：
  1. 同一文档片段在向量和 BM25 中可能都被检索到，去重避免重复
  2. file + title 组合天然唯一（因为知识库构建时 ID 格式即如此）
- **保留最高分**：向量和 BM25 对同一文档给出不同分数，保留 `max(score)` 合理
- **潜在问题**：
  - 如果 title 相同但内容不同（不同文件相同标题），会被错误去重 — 但这里用 file 做了区分，没问题
  - 如果 metadata 缺少 file 或 title 字段，KeyError。生产环境应加 `.get()` 兜底

---

### 3-05 ⭐⭐ 为什么要做 Re-rank？直接用向量检索的分数排序不行吗？

**题目**：向量检索已经有相似度分数了，为什么还要调一个独立的 Re-rank API？

**参考答案要点**：
- **向量分数的问题**：
  1. Embedding 模型和 Reranker 模型的优化目标不同：Embedding 关注"语义相似"，Reranker 关注"是否回答了问题"
  2. 向量检索在粗排阶段效果好（从大量文档中快速召回候选），但精排精度不如 Reranker
  3. Cross-encoder（Reranker）比 Bi-encoder（Embedding）更准确，但更慢 — 所以只在候选集上跑
- **架构设计**：经典的多阶段检索 pipeline
  - 粗排（向量 + BM25）→ 召回候选集（top_k+2 条）
  - 精排（Reranker）→ 最终 top_k 条
- **代价**：多一次 API 调用，增加约 200-500ms 延迟

---

### 3-06 ⭐⭐ `build_bm25_index()` 什么时候被调用？为什么用全局变量？

**题目**：BM25 索引用 `_bm25`, `_doc_ids`, `_doc_metadatas`, `_doc_texts` 四个全局变量存储，这种设计有什么考量？

**参考答案要点**：
- **调用时机**（`retriever.py:89-90`）：
  ```python
  if _bm25 is None:
      build_bm25_index()
  ```
  延迟初始化：第一次调用 `hybrid_search()` 时才构建
- **也用 `api.py:308` 在启动时显式调用**：`build_bm25_index()`
- **全局变量原因**：
  1. **避免重复构建**：索引构建需要从 ChromaDB 拉全量数据 + jieba 分词，开销大
  2. **单进程**：Flask 开发服务器单进程，全局变量安全
- **问题**：多进程生产环境（gunicorn 多 worker）每个进程需要独立构建，且修改知识库后索引不会自动更新

---

### 3-07 ⭐⭐ `rerank()` 函数调用的是哪个 API？请求和响应格式是怎样的？

**题目**：`llm/retriever.py:36-62` 的 `rerank()` 函数的完整 API 调用细节。

**参考答案要点**：
- **API**：`https://api.siliconflow.cn/v1/rerank`
- **模型**：`Qwen/Qwen3-Reranker-8B`
- **请求格式**：
  ```json
  {
    "model": "Qwen/Qwen3-Reranker-8B",
    "query": "用户原始问题",
    "documents": ["候选文档1", "候选文档2", ...],
    "top_n": 3
  }
  ```
- **响应格式**：
  ```json
  {
    "results": [
      {"index": 2, "relevance_score": 0.95},
      {"index": 0, "relevance_score": 0.72},
      {"index": 1, "relevance_score": 0.45}
    ]
  }
  ```
- **返回**：按 `relevance_score` 降序排列，取 `top_n` 条

---

### 3-08 ⭐⭐ `embed_text()` 为什么用 SiliconFlow 而不是其他 Embedding 服务？

**题目**：`llm/rag.py:32-51` 的 `embed_text()` 调 SiliconFlow API，为什么选它？

**参考答案要点**：
- **模型**：`Qwen/Qwen3-Embedding-8B`，中文语义理解能力强
- **统一供应商**：和 LLM（DeepSeek via OpenCode）、Re-ranker 都走 SiliconFlow，API 管理简单
- **性价比**：SiliconFlow 的 Embedding API 价格较低
- **批量支持**：一次 API 调用可传 `[text1, text2, ...]` 批量向量化，减少网络往返
- `single` 参数：自动判断单条还是批量，返回对应格式

---

### 3-09 ⭐⭐⭐ 混合检索的融合策略是"合并去重 + Re-rank"，还有其他融合方式吗？为什么当前方案是合适的？

**题目**：除了合并去重 + Re-rank 外，常见的混合检索融合策略还有哪些？当前方案为什么合适？

**参考答案要点**：
- **常见融合策略**：
  1. **RRF（Reciprocal Rank Fusion）**：对不同检索源的排名取倒数求和，不依赖分数绝对值
  2. **分数归一化 + 加权求和**：min-max 归一化后按权重相加
  3. **合并去重 + Re-rank**（当前方案）
- **当前方案的优势**：
  1. Re-ranker 通过 Cross-encoder 重新计算 query-document 相关性，比简单加权更准确
  2. 合并去重后候选集小（最多 10 条），Re-ranker 开销可控
  3. 不依赖分数的可比性（向量余弦距离 vs BM25 TF-IDF 分数不在同一量纲）
- **为什么不用 RRF**：RRF 只用排名不用分数，丢失了分数置信度信息。但 Re-ranker 方案有额外 API 成本

---

### 3-10 ⭐⭐ 向量检索中 `score = 1 - distance` 的含义是什么？

**题目**：`llm/rag.py:92` 将 ChromaDB 返回的 `distance` 转换为 `score = 1 - distance`，这里的 distance 是什么？为什么这样转换？

**参考答案要点**：
- **ChromaDB 的 distance**：默认用余弦距离（cosine distance），取值 [0, 2]
  - `0` = 方向完全相同（最相似）
  - `2` = 方向完全相反
  - `1` = 正交（不相关）
- **转换为相似度**：`score = 1 - distance`
  - distance=0 → score=1.0（完全匹配）
  - distance=1 → score=0.0（不相关）
  - distance=2 → score=-1.0（完全相反）
- **注释原文**："ChromaDB 返回的是距离——0 表示完全一样，1 表示完全无关"

---

### 3-11 ⭐⭐⭐ 如果要给混合检索增加"缓存热门查询"功能，应该在哪个环节加？怎么设计？

**题目**：运维场景中，很多查询是重复的（如"服务器 CPU 高怎么办"）。设计一个查询缓存方案。

**参考答案要点**：
- **缓存位置**：`hybrid_search()` 入口处，查缓存 → 命中直接返回 → 未命中走完整 pipeline
- **缓存 key**：查询文本的 MD5（或直接归一化后的 query 字符串）
- **缓存内容**：最终的 top_k 结果列表（含 content, metadata, score）
- **缓存策略**：
  - LRU Cache：`functools.lru_cache(maxsize=128)` 最简单
  - 或 Redis TTL（如 1 小时过期），支持多进程
- **失效策略**：知识库更新时清空全部缓存
- **代价**：缓存可能返回过时结果（知识库更新后旧结果还在缓存中）

---

## 第 4 章：MCP 服务设计（7 题）

### 4-01 ⭐ Flask API 提供了哪些核心路由？按功能分类。

**题目**：列举 `api.py` 中所有的路由及其功能分组。

**参考答案要点**：
| 分组 | 路由 | 方法 | 功能 |
|------|------|------|------|
| 前端 | `/` | GET | 渲染 Dashboard 页面 |
| 服务器管理 | `/api/servers` | GET | 列出所有服务器 + 最新指标 |
| | `/api/servers` | POST | 添加服务器（含 SSH 验证） |
| | `/api/servers/<name>` | DELETE | 删除服务器 |
| 监控数据 | `/api/servers/<name>/history` | GET | 历史指标趋势（最近 60 条） |
| | `/api/servers/<name>/logs` | GET | 查询日志（支持 level 过滤） |
| 日志接收 | `/api/logs` | POST | 接收外部推送的日志 |
| 对话 | `/api/conversations` | GET/POST | 列出/创建对话 |
| | `/api/conversations/<id>` | DELETE | 删除对话及消息 |
| | `/api/conversations/<id>/messages` | GET | 获取对话消息 |
| 聊天 | `/api/chat` | POST | AI 对话（核心接口） |
| 告警 | `/api/alerts` | GET | 告警列表 |
| | `/api/alerts/<id>` | PATCH | 更新告警状态 |

共 **12 个路由**，覆盖服务器管理、监控、告警、对话四大功能域。

---

### 4-02 ⭐ `/api/chat` 的请求和响应格式是什么？

**题目**：`POST /api/chat` 接收什么参数？返回什么？与 Conversation/Message 的关系？

**参考答案要点**：
- **请求**：`{"conversation_id": 1, "message": "服务器 web-01 的 CPU 怎么样？"}`
- **响应**：`{"reply": "web-01 的 CPU 当前使用率为 45%，正常范围内。"}`
- **处理流程**（`api.py:291-300`）→ `llm/agent.py:42 chat()`：
  1. 校验 `conversation_id` 和 `message` 必填
  2. 调用 `agent.chat(conversation_id, message)`
  3. Agent 内部：加载历史消息 → 追加用户消息 → 调用 LLM → 保存 AI 回复
- **与 Message 的关系**：每次对话的 human 和 ai 消息都存入 Message 表，通过 `conversation_id` 关联

---

### 4-03 ⭐⭐ 删除 Conversation 时为什么要先删 Message 再删 Conversation？

**题目**：`api.py:228-241` 删除对话时，为什么先手动删除 Message 再删除 Conversation？

**参考答案要点**：
- 代码（`api.py:237`）：
  ```python
  session.query(Message).filter(Message.conversation_id == conversation_id).delete()
  session.delete(conv)
  ```
- **原因**：注释写得很清楚 — "数据库可能没有级联"
- **Message 的外键**（`models.py:62`）：`ForeignKey('conversations.id', ondelete='CASCADE')` — 虽然定义了 `ondelete='CASCADE'`，但这是 DDL 级别的，SQLAlchemy ORM 层面不一定自动级联
- **防御性编程**：手动删除子记录保证数据完整性，避免 Message 变成孤儿记录
- 如果数据库支持 CASCADE 且 SQLAlchemy 配置了 `cascade="all, delete-orphan"`，则不需要手动删

---

### 4-04 ⭐⭐ `POST /api/servers` 添加服务器接口的事务问题

**题目**：添加服务器时，如果 SSH 连接失败，Server 记录是否已经写入数据库？这会导致什么问题？

**参考答案要点**：
- **执行顺序**（`api.py:76-118`）：
  1. 创建 Server 对象 → `session.add(server)` → `session.commit()` ✅ 已写入
  2. 尝试 SSH 连接 → 失败 → `except Exception` → `session.close()` → 返回错误
- **问题**：Server 记录已持久化（status='offline'），但 API 返回了错误，用户可能认为添加失败而重复添加
- 更重要的是：第 84 行 `commit()` 之后，即使 SSH 异常，也没有 `rollback()`
- **更好的做法**：
  - SSH 成功后再 commit，或者
  - 失败时 delete 已创建的 server 并 commit，或者
  - 先不 commit，最后统一 commit

---

### 4-05 ⭐⭐ `server_history()` 为什么用 `reversed()`？

**题目**：`api.py:156` 中 `for m in reversed(metric)` 为什么要反转？数据库查询已经 `order_by(id.desc())` 了。

**参考答案要点**：
- 查询：`.order_by(Metric.id.desc()).limit(60)` → 最新在前（降序）
- `reversed()` → 反转后在列表中变成最旧在前（升序）
- **目的**：前端画时序图时，x 轴从左到右是旧→新，数据必须按时间升序排列
- 这是一个"数据库层降序取最新 N 条 + 应用层反转适配前端"的模式
- **另一种写法**：直接 `order_by(Metric.created_at.asc())`，但 limit 60 取不到最新的 60 条

---

### 4-06 ⭐⭐⭐ 项目的 API 设计存在哪些可以改进的地方？

**题目**：从 RESTful 规范、错误处理、安全性等角度分析 API 设计的改进空间。

**参考答案要点**：
1. **RESTful 规范**：
   - 成功响应格式不统一：`{"status": "ok"}` / `{"success": true}` / `{"success": "add success"}`，应统一
   - HTTP 状态码使用不规范：部分错误返回 200 + error 字段
2. **错误处理**：
   - `POST /api/servers` 事务问题（SSH 失败但记录已写入）
   - 很多地方缺少 try/except，数据库异常会直接 500
3. **安全性**：
   - **无认证**：任何能访问 `127.0.0.1:5001` 的人都能操作
   - 密码在日志中可能泄露（SSH 错误信息可能含密码）
   - 无请求频率限制
4. **分页**：`/api/alerts` 硬编码 `limit(100)`，对话列表无分页
5. **输入校验**：`POST /api/servers` 没有校验 `name` 是否合法（空字符串、特殊字符）

---

### 4-07 ⭐ `/api/logs` 的 POST 路由是谁调用的？它的设计意图是什么？

**题目**：`api.py:14-37` 的 `POST /api/logs` 接收外部推送日志，和采集器的 `push_loki()` 有什么区别？

**参考答案要点**：
- **设计意图**：允许**被监控服务器主动推送日志**到 SmartOps，而非总是由 SmartOps 主动拉取
- **模式差异**：
  - 采集器 `push_loki()`：拉模式（pull）→ SSH 登录 → `tail` → 推送到 Loki
  - `/api/logs`：推模式（push）→ 被监控服务器上的 agent 主动 POST 日志 → 写入 PostgreSQL
- **注意**：当前这个路由只写 PostgreSQL 的 Log 表，**没有推送到 Loki**。这意味着主动推送的日志不会出现在 Loki 中，存在日志存储不一致的问题
- **请求格式**：`{"server_name": "web-01", "logs": [{"log_name": "app", "content": "...", "level": "error"}]}`

---

## 第 5 章：可插拔架构设计（6 题）

### 5-01 ⭐ LangChain Agent 是如何创建的？使用了哪些 Tools？

**题目**：`llm/agent.py` 中 Agent 的创建代码，以及 5 个 Tool 的功能。

**参考答案要点**：
- **Agent 创建**（`llm/agent.py:40`）：
  ```python
  agent = create_agent(model=llm, tools=tools, system_prompt=prompt)
  ```
- **5 个 Tools**（全来自 `llm/tools.py`）：
  1. `get_server_list()`：返回所有服务器列表（name, ip, status, os）
  2. `get_server_status(server_name)`：查指定服务器的最新 CPU/Mem/Disk/Net
  3. `get_metrics_history(server_name, hours)`：查历史指标趋势
  4. `get_logs(server_name, hours, level)`：从 Loki 查日志
  5. `search_knowledge_base(query, top_k)`：混合搜索运维知识库

---

### 5-02 ⭐ `@tool` 装饰器的作用是什么？

**题目**：`llm/tools.py` 中每个函数用 `from langchain_core.tools import tool` 的 `@tool` 装饰器修饰，它做了什么？

**参考答案要点**：
- `@tool` 是 LangChain 提供的工具装饰器，自动将 Python 函数转为 LangChain Tool 对象
- **自动生成**：
  1. **name**：函数名作为工具名（LLM 用它来选择调用哪个工具）
  2. **description**：函数的 docstring 作为工具描述（LLM 据此理解工具的用途和使用方式）
  3. **args_schema**：从函数签名 + 类型注解自动生成参数 schema（如 `server_name: str`）
- **关键**：docstring 的质量直接影响 LLM 是否能正确选择和使用工具。写得模糊 → LLM 不会调

---

### 5-03 ⭐⭐ Agent 的 system prompt 中有什么设计考量？

**题目**：`llm/agent.py:18-34` 的 prompt 设计，为什么强调"回答不超过 8 行"、"结论先说"、"命令用反引号"？

**参考答案要点**：
- **"回答不超过 8 行"**：运维场景追求效率，运维人员不想看长篇大论
- **"结论先说，再说理由"**：倒金字塔原则，紧急情况下先知道"怎么办"再理解"为什么"
- **"命令用 ` 括起来"**：方便运维人员直接复制粘贴执行
- **"基于数据，不编造"**：AI 运维最重要的可靠性原则，宁可说不知道也别瞎说
- **"建议要具体到命令"**：模糊建议如"检查一下网络"无用，`ping 10.0.0.1` 才有用
- **"信息不够就说缺什么"**：引导用户补充信息，而非猜测

---

### 5-04 ⭐⭐ 如果要新增一个 Tool（如"重启服务"），需要修改哪些文件？

**题目**：在 Agent 中新增一个 `restart_service(server_name, service_name)` 工具，需要改哪些地方？

**参考答案要点**：
1. **`llm/tools.py`**：新增 `@tool` 函数，实现 SSH 连接 + `systemctl restart {service}`
2. **`llm/agent.py:37`**：`tools` 列表中添加新工具
3. **`collector/ssh_client.py`**（可选）：添加 `restart_service(name)` 方法以复用
4. **不需要改** `api.py` — Agent 自动感知新工具，LLM 根据 prompt 决定何时调用
- 这体现了 **可插拔架构**：新增功能只需添加 Tool，不需要改动框架代码

---

### 5-05 ⭐⭐ Agent 的对话记忆是如何实现的？

**题目**：`llm/agent.py:42 chat()` 中，对话历史如何加载和利用？为什么不用 LangChain 的 Memory 模块？

**参考答案要点**：
- **实现方式**（`agent.py:48-57`）：
  1. 从 Message 表按 `conversation_id` 查询所有消息
  2. 按 role 转为 `[('human', content), ('ai', content), ...]` 格式
  3. 追加当前问题 `('human', user_input)`
  4. 传给 `agent.invoke({"messages": history})`
- **为什么不用 LangChain Memory**：
  - LangChain Memory 默认存内存，进程重启丢失
  - 项目用 PostgreSQL 持久化存储，更可靠
  - 自己实现的更可控，没有额外依赖
- **特点**：这是**短期记忆**（对话历史）。完整对话被加载，长对话会导致 token 消耗增加

---

### 5-06 ⭐⭐⭐ `agent.invoke()` 的内部调用链是怎样的？

**题目**：当用户问 "web-01 的 CPU 怎么样"，从 `agent.invoke()` 到返回结果，LLM 和 Tool 之间如何交互？

**参考答案要点**：
1. `agent.invoke({"messages": history})` → LangChain Agent Executor 开始执行
2. **LLM 推理**：分析 prompt + 消息 + 可用工具 → 决定调用 `get_server_status(server_name="web-01")`
3. **Tool 执行**：`get_server_status("web-01")` → 查数据库 → 返回 `{"cpu": 45, "memory": 60, ...}`
4. **LLM 再推理**：收到工具返回值 → 结合 prompt 生成自然语言回复："web-01 的 CPU 使用率 45%，正常。内存 60%，略有偏高。"
5. **返回**：`agent.invoke()` 返回 `{"messages": [... , AIMessage("web-01 的 CPU...")]}`
- **关键**：LLM 可能多次调用工具（Agentic Loop），比如先查服务器列表，再查具体指标，再查历史趋势，最后查知识库
- LangChain 的 Agent 框架自动处理这个 ReAct 循环：**Thought → Action → Observation → Thought → ... → Final Answer**

---

## 第 6 章：可观测性与 Dashboard（6 题）

### 6-01 ⭐ Dashboard 展示了哪些信息？

**题目**：`templates/dashboard.html` 是项目前端，你认为它应该展示哪些模块？

**参考答案要点**（基于 API 推断）：
1. **服务器列表**：名称、IP、OS、在线状态、最后心跳时间、CPU/内存/磁盘当前值
2. **指标趋势图**：选中某台服务器，展示 CPU/内存/磁盘的历史曲线
3. **日志面板**：选中服务器，按级别过滤查看最近日志
4. **告警列表**：展示 open/acknowledged/resolved 告警
5. **对话面板**：AI 对话界面，左侧历史对话列表，右侧聊天窗口
- 单页应用（SPA）风格，所有功能在一个页面完成

---

### 6-02 ⭐ 告警的三个状态各代表什么含义？

**题目**：Alert 的 `status` 字段有 `open`、`acknowledged`、`resolved` 三个状态，各表示什么？

**参考答案要点**：
- `open`：告警刚触发，还没有人处理
- `acknowledged`：运维人员已确认看到，正在处理中
- `resolved`：问题已解决，告警关闭
- **状态流转**：`open → acknowledged → resolved`（单向，不允许回退）
- 代码（`api.py:278`）：仅允许 `acknowledged` 和 `resolved` 两种变更
- 这是标准的告警生命周期管理，避免告警被忽视

---

### 6-03 ⭐⭐ 为什么服务器状态用 `last_heartbeat` 而不是实时检测？

**题目**：`Server.status` 依赖 `last_heartbeat` 时间戳判断在线状态，这种设计的优劣是什么？

**参考答案要点**：
- **机制**：采集成功时更新 `last_heartbeat = datetime.now(timezone.utc)` + `status = 'online'`，失败时 `status = 'offline'`
- **优势**：不需要单独的探活机制，采集周期本身就是心跳
- **劣势**：
  1. 不是实时检测 — 采集间隔 60s，离线检测最多延迟 60s
  2. 没有超时判断 — 如果采集器自己挂了，所有服务器保持旧状态
  3. 前端直接用 `status` 字段，但没有基于 `last_heartbeat` 的二次判定（如超过 120s 未更新 → 视为离线）

---

### 6-04 ⭐⭐ 项目如何实现日志的筛选和查询？

**题目**：`/api/servers/<name>/logs` 和 `get_logs` Tool 的日志查询有什么不同？

**参考答案要点**：
- **`/api/servers/<name>/logs`**（`api.py:164-191`）：
  - 从**PostgreSQL Log 表**查询
  - 支持 `?limit=50&level=error` 参数
  - 返回采集器存入的结构化日志
- **`get_logs` Tool**（`llm/tools.py:94-128`）：
  - 从**Loki** 查询
  - 支持 `server_name`、`hours`（时间范围）、`level` 过滤
  - 返回原始日志文本（`'\n'.join(logs)`）
- **差异**：两个数据源 — PostgreSQL 有结构化 Log 表，Loki 有完整日志流。设计上存在数据冗余，但两者用途不同：PG 用于 API 快速查询，Loki 用于 Agent 全文搜索

---

### 6-05 ⭐⭐⭐ 如果要给 Dashboard 增加实时 WebSocket 推送，需要改哪些地方？

**题目**：当前 Dashboard 依赖轮询刷新数据。如果要实现指标实时推送（WebSocket），架构如何调整？

**参考答案要点**：
1. **Flask-SocketIO**：引入 `flask-socketio`，在采集器写入新 Metric 后 emit 事件
2. **`collector/scheduler.py`**：`collect_all()` 写入 Metric 后，通过 Redis pub/sub 或直接调用 Flask-SocketIO emit
3. **`api.py`**：新增 WebSocket endpoint，客户端连接时订阅对应服务器的指标频道
4. **`templates/dashboard.html`**：前端用 Socket.IO JS 库接收推送，实时更新图表
5. **改动范围**：`requirements.txt` 加 `flask-socketio`，`api.py` 加 SocketIO 初始化，`scheduler.py` 加推送逻辑，前端改轮询为 WebSocket

---

### 6-06 ⭐⭐ 项目的可观测性覆盖了哪些维度？还缺什么？

**题目**：从"三大支柱"（Metrics / Logs / Traces）角度看，SmartOps 覆盖了哪些？缺少什么？

**参考答案要点**：
- **已覆盖**：
  - **Metrics** ✅：CPU、Memory、Disk、网络字节数，60s 采集，存 PostgreSQL
  - **Logs** ✅：syslog 采集，存 PostgreSQL + Loki，支持按级别/服务器查询
- **缺失**：
  - **Traces** ❌：没有分布式链路追踪（如 OpenTelemetry/Jaeger），无法追踪请求跨服务调用链
  - **Profiling** ❌：没有 CPU/内存 profiling
- **告警维度**：仅覆盖主机指标（CPU/Mem/Disk/Offline），缺少应用层告警（如 HTTP 5xx 率、响应时间）
- **自身可观测**：SmartOps 自身（Flask 应用）没有暴露 metrics，无法监控自己的健康状态

---

## 第 7 章：评估体系（5 题）

### 7-01 ⭐ 评估脚本的核心目的是什么？

**题目**：`kb/evaluate.py` 是做什么的？它评估了什么？

**参考答案要点**：
- **目的**：对比不同检索 pipeline 的效果，量化混合检索 vs 纯向量搜索的差距
- **评估对象**：检索系统（不是 LLM 生成质量），关注"找到的文档对不对"
- **三种模式**：
  1. `hybrid_search`：向量 + BM25 + Re-rank（当前 pipeline）
  2. `vector_only`：纯向量搜索（基线）
  3. `bm25_only`：纯 BM25 搜索
- **输出**：整体 Recall@5 / Precision@5 / MRR，单条 query 详情，对比提升

---

### 7-02 ⭐ 测试集的 20 条 query 覆盖了哪几种难度？

**题目**：`TEST_QUERIES` 中的 20 条 query 按难度分成了哪四类？

**参考答案要点**：
1. **精确关键词查询**（5 条）：`"top 命令查看 CPU"`、`"docker 启动容器命令"` — 期望精确匹配到特定命令文档
2. **模糊语义查询**（5 条）：`"服务器 CPU 突然飙高怎么排查"`、`"网站访问很慢"` — 考验语义理解能力
3. **跨类别查询**（5 条）：`"容器网络不通，宿主机能通但容器不行"` — 需要跨 Docker + Linux 两个类别
4. **场景化故障查询**（5 条）：`"线上服务突然不可用，我该按什么步骤排查"` — 复杂故障场景，需要综合理解

---

### 7-03 ⭐⭐ 三个评估指标 Recall@k、Precision@k、MRR 分别衡量什么？

**题目**：`compute_retrieval_metrics()` 计算的三个指标各代表什么含义？

**参考答案要点**：
- **Recall@5**（召回率）：相关文档中，前 5 个结果找回了多少比例
  - 公式：`匹配到的相关文件数 / 总相关文件数`
  - 衡量"有没有漏掉"
  - 例：总共 3 个相关文件，找回了 2 个 → Recall = 66%
- **Precision@5**（精确率）：前 5 个结果中，有多少比例是真正相关的
  - 公式：`相关文件数 / 返回文件数（去重）`
  - 衡量"有没有找错"
  - 例：返回了 5 个文件，其中 3 个相关 → Precision = 60%
- **MRR**（Mean Reciprocal Rank）：第一个相关文档出现的位置的倒数
  - 公式：`1 / 第一个相关文档的排名`
  - 衡量"正确答案排在第几位"
  - 例：第一个相关文档排第 1 → MRR=1.0，排第 3 → MRR=0.33

---

### 7-04 ⭐⭐ 为什么评估使用 `relevant_files` 而不是 `relevant_ids`？

**题目**：`compute_retrieval_metrics()` 注释说"只匹配 `#` 前面的文件路径，不匹配标题"，为什么这样设计？

**参考答案要点**：
- 原因注释原文："标题名因分片策略而异"
- **实际考量**：
  1. Markdown 标题可能在分片时被截断、嵌套、重命名
  2. 同一文件的不同 chunk 都算相关（比如查 "top 命令"，文件中任何一个 chunk 提到 top 都算命中）
  3. 文件级别的标注比 chunk 级别更稳定、更易维护
- **代价**：粒度较粗 — 整个文件都被视为相关，即使只有其中一小段真正相关
- **改进方向**：精确标注到 chunk ID，但维护成本高

---

### 7-05 ⭐⭐⭐ 如果要加入 Ragas 评估（Faithfulness / Answer Relevancy），需要怎么设计？

**题目**：当前只评估了检索质量。如果要评估 LLM 生成答案的质量，如何设计？

**参考答案要点**：
- **Ragas 核心指标**：
  1. **Faithfulness（忠实度）**：生成的答案是否完全基于检索到的上下文，有没有编造
  2. **Answer Relevancy（答案相关性）**：答案是否直接回答了问题
  3. **Context Precision**：检索到的上下文中相关比例
  4. **Context Recall**：答案所需信息在检索上下文中被覆盖的程度
- **实现步骤**：
  1. 准备测试集：`{question, answer, contexts, ground_truth}`
  2. 获取 LLM 生成的 `answer` + 检索到的 `contexts`
  3. Ragas 内部用 LLM 做评判（LLM-as-judge）：
     - Faithfulness：从 answer 中提取 claims → 逐一检查是否被 contexts 支持
     - Answer Relevancy：对 answer 生成反向问题 → 计算与原问题的相似度
  4. 需要引入 `ragas` 包 + 额外 LLM 调用（评判成本）
- **当前项目的切入位置**：`kb/evaluate.py` 的 `run_comparison()` 之后追加生成质量评估

---

## 第 8 章：测试体系与工程质量（5 题）

### 8-01 ⭐ 项目用了什么测试框架？测试覆盖了哪些内容？

**题目**：`requirements.txt` 中的 `pytest` 是做什么用的？项目中测试的现状如何？

**参考答案要点**：
- **测试框架**：`pytest`（`requirements.txt:2`）
- **现状**：`pytest` 已安装但项目中没有可见的测试文件（`tests/` 目录不存在，无 `test_*.py`）
- **推断**：项目处于早期原型阶段，测试体系尚未建立
- **应该有但缺失的测试**：
  - `collector/ssh_client.py` 的单元测试（mock SSH）
  - `llm/rag.py` 的 embedding 和搜索测试
  - `llm/tools.py` 的 Tool 函数测试
  - `api.py` 的 API 集成测试（Flask test client）

---

### 8-02 ⭐⭐ 如果要为 `SSHClient` 写单元测试，如何避免真的连 SSH？

**题目**：`SSHClient` 依赖 paramiko 连接远程服务器。写单元测试时如何 mock？

**参考答案要点**：
- **Mock 策略**：
  1. `unittest.mock.patch('paramiko.SSHClient')` mock 整个 paramiko 客户端
  2. Mock `exec_command()` 返回预设的 stdout 数据（如 `"CPU: 45.0"`）
  3. `SSHClient.__init__` 中的 `connect()` 也需要 mock
- **示例思路**：
  ```python
  def test_get_cpu(mocker):
      mock_ssh = mocker.patch('paramiko.SSHClient')
      mock_stdout = mocker.MagicMock()
      mock_stdout.read.return_value.decode.return_value = "45.0"
      mock_ssh.return_value.exec_command.return_value = (None, mock_stdout, mocker.MagicMock())
      client = SSHClient(host='1.2.3.4', port='22', user='root', password='test')
      assert client.get_cpu() == 45.0
  ```
- **更好的设计**：`SSHClient` 应支持依赖注入（传入 transport 对象），测试时注入 fake transport

---

### 8-03 ⭐⭐ `api.py` 中的 `if __name__ == '__main__'` 块做了哪些初始化？启动顺序重要吗？

**题目**：`api.py:303-311` 启动时依次执行了 `init_db()` → `build_bm25_index()` → `start_scheduler()` → `app.run()`，为什么是这个顺序？

**参考答案要点**：
- **启动顺序**：
  1. `init_db()`：建表（如果表不存在），必须最先执行，后续依赖数据库
  2. `build_bm25_index()`：从 ChromaDB 加载文档构建索引，Agent 回答时使用
  3. `start_scheduler()`：启动后台采集线程，开始 60s 循环
  4. `app.run()`：启动 Flask，阻塞主线程
- **顺序重要**：
  - `init_db()` 必须在采集器和 Agent 之前
  - `build_bm25_index()` 在 `app.run()` 之前完成，否则第一个请求到来时索引未就绪
  - `start_scheduler()` 是守护线程，必须 `app.run()` 前启动，否则 app.run() 阻塞后无法回到启动代码
- **使用 `with app.app_context()`**：因为 `init_db()` 需要 Flask 应用上下文

---

### 8-04 ⭐ 环境变量的管理方式是什么？

**题目**：项目中哪些地方依赖环境变量？如何加载它们？

**参考答案要点**：
- **加载方式**：`store/__init__.py` 和 `llm/__init__.py` 都调用了 `load_dotenv()`（python-dotenv），从 `.env` 文件加载
- **关键环境变量**：
  1. `DATABASE_URL`：PostgreSQL 连接串（`store/db.py:5`）
  2. `ENCRYPTION_KEY`：Fernet 加密密钥（`store/crypto.py:8`）
  3. `DASHSCOPE_API_KEY` / `DASHSCOPE_BASE_URL`：DashScope API（`llm/rag.py:14-15`，定义了但未使用）
  4. `SILICONFLOW_API_KEY`：SiliconFlow embedding + re-rank（`llm/rag.py:18`、`llm/retriever.py:10`）
  5. `OPENCODE_API_KEY`：DeepSeek LLM（`llm/agent.py:15`）
- `.env` 文件未提交到 git（`.gitignore` 中应有 `.env`），密钥不会泄露

---

### 8-05 ⭐⭐⭐ 项目的工程质量可以从哪些方面提升？

**题目**：从代码质量、测试、CI/CD、监控等角度，分析项目工程化的提升方向。

**参考答案要点**：
1. **测试**：零测试覆盖，优先加 `SSHClient` 和 `rag.py` 的单元测试
2. **CI/CD**：`.github/` 目录已存在，可加 GitHub Actions 自动化测试 + lint
3. **代码质量**：
   - 部分函数过长（`collect_all()` 60 行），应拆分
   - `store/crypto.py` 顶层 try/except 裸捕获，初始化失败没有明确报错
   - 多处硬编码（Loki URL、采集间隔、阈值），应抽到配置文件
4. **日志**：项目自身没有结构化日志（只有 `print()`），生产环境应使用 `logging` 模块
5. **数据库迁移**：用 `create_all` 自动建表，不适合生产（需要用 Alembic 做 migration）
6. **Docker 化**：只有 Loki 走了 Docker Compose，SmartOps 本身没有容器化
7. **类型注解**：目前没有使用类型注解（只有简单的 `: str`），引入 mypy 有帮助

---

## 第 9 章：存储与持久化架构（5 题）

### 9-01 ⭐ 项目的数据库连接管理是如何实现的？

**题目**：`store/db.py` 的 session 管理模式是怎样的？`pool_pre_ping=True` 有什么作用？

**参考答案要点**：
- **模式**：SQLAlchemy ORM + Session Factory
  ```python
  engine = create_engine(DATABASE_URL, pool_pre_ping=True)
  SessionLocal = sessionmaker(bind=engine)
  
  def get_session():
      return SessionLocal()
  ```
- **Session 生命周期**：每次调用 `get_session()` 创建新 session，调用方负责 `session.close()`
- **`pool_pre_ping=True`**：每次从连接池取连接时，先发一个 `SELECT 1` 验证连接是否有效。如果数据库重启导致连接断开，会自动重建，避免 `MySQL server has gone away` 类错误
- **注意**：项目没有用 `scoped_session`（线程安全 session），多线程场景（采集器线程 + Flask 请求线程）可能存在 session 竞争

---

### 9-02 ⭐ ChromaDB 的 `PersistentClient` 模式是如何工作的？

**题目**：`llm/rag.py:26` 使用 `chromadb.PersistentClient(path=CHROMA_PATH)`，数据存在哪里？和 `HttpClient` 的区别是什么？

**参考答案要点**：
- **PersistentClient**：
  - 数据存在本地磁盘 `data/chromadb/` 目录
  - 使用 SQLite3 + Apache Parquet 做元数据和向量存储
  - 零依赖，不需要启动额外服务
  - 适合单机、开发环境
- **HttpClient**：
  - 连接远程 ChromaDB 服务器
  - 支持多客户端共享同一知识库
  - 适合生产环境、团队共享
- 当前 `CHROMA_PATH = 'data/chromadb'`，数据在项目目录下，方便备份

---

### 9-03 ⭐⭐ `ondelete='CASCADE'` 在 Message 表的外键上为什么"可能没有生效"？

**题目**：`models.py:62` Message 表的外键有 `ondelete='CASCADE'`，但代码仍手动删除。SQLAlchemy 中 CASCADE 的行为取决于什么？

**参考答案要点**：
- `ondelete='CASCADE'` 是 **DDL 级别**：在数据库表定义中生效（`ALTER TABLE ... ADD FOREIGN KEY ... ON DELETE CASCADE`）
- SQLAlchemy ORM 的 `cascade` 参数是 **ORM 级别**：控制 `session.delete()` 时的行为
- **为什么可能不生效**：
  1. `ondelete='CASCADE'` 只在数据库执行 DELETE 语句时触发
  2. SQLAlchemy `session.delete()` 默认不触发数据库级 CASCADE，因为 ORM 有自己的 cascade 逻辑
  3. 不同数据库对 CASCADE 支持不同（SQLite 默认不开启外键约束）
- **正确做法**：在 relationship 侧加 `cascade="all, delete-orphan"`，或在删除时显式处理子记录

---

### 9-04 ⭐⭐ `store/__init__.py` 和 `llm/__init__.py` 各只有一行 `load_dotenv()`，为什么需要两个？

**题目**：为什么 `store/__init__.py` 和 `llm/__init__.py` 都调用了 `load_dotenv()`？只在一个地方调用不行吗？

**参考答案要点**：
- **原因**：Python 的导入顺序不确定 — 谁先被 import 谁先加载
- **场景**：
  - 如果只用 `store/__init__.py` 加载 `.env`，但 `llm/rag.py` 先被导入 → `os.getenv('SILICONFLOW_API_KEY')` 拿到 `None`
  - 反之亦然
- **`load_dotenv()` 的幂等性**：多次调用不会重复加载，第二次调用发现环境变量已存在就跳过
- **另一种设计**：在项目入口 `api.py` 头部统一加载一次，但这要求所有模块都在 `api.py` 之后导入（通过 `sys.path.insert` 控制顺序，不可靠）

---

### 9-05 ⭐⭐⭐ 如果项目要从 SQLite 迁移到 PostgreSQL，哪些地方需要改动？

**题目**：当前项目已经在用 PostgreSQL（通过 `DATABASE_URL` 环境变量）。如果原本是用 SQLite 开发的，迁移过程需要考虑什么？

**参考答案要点**：
- **SQLAlchemy 层面**：只需改 `DATABASE_URL` — 从 `sqlite:///data.db` 改为 `postgresql://user:pass@host/dbname`，ORM 代码不变
- **数据类型差异**：
  1. `DateTime` 时区处理：SQLite 不存储时区，PostgreSQL `TIMESTAMPTZ` 存储时区。项目已用 `datetime.now(timezone.utc)`，兼容
  2. `Boolean`：SQLite 用 0/1，PostgreSQL 用 TRUE/FALSE，SQLAlchemy 自动适配
  3. `Text` vs `VARCHAR`：SQLite 不区分，PostgreSQL 中 `Text` 无长度限制、`String(20)` 有限制
- **表结构**：`create_all` 自动建表，兼容。但如果已有 SQLite 数据需要 `pgloader` 或手动迁移
- **连接参数**：PostgreSQL 需要 `pool_pre_ping=True`（项目已设置）
- **外键约束**：SQLite 需 `PRAGMA foreign_keys = ON`，PostgreSQL 默认开启。`ondelete='CASCADE'` 在 PostgreSQL 中一定生效，不需要手动删子记录

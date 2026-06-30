# SmartOps Phase 3 — 教学稿 阶段 4 总结 + 阶段 5 计划

---

## 阶段 4 总结：知识库 RAG

### 踩过的坑

| 问题 | 原因 | 解决 |
|------|------|------|
| 克隆到根目录 | 没建 `data/` 目录，clone 到了项目根 | `mv ops-skill-tree data/ops-skill-tree` |
| `add_document` 未定义 | `rag.py` 里只写了 `get_collection` 和 `embed_text`，没写写入函数 | 补上 `add_document` 函数 |
| 脚本跑完没输出 | `if __name__ == '__main__'` 缩进了 `main()` 里面 | 移到外面，取消缩进 |
| `DASHSCOPE_API_KEY` 读不到 | 单独跑的脚本没调 `load_dotenv()` | 加上 `from dotenv import load_dotenv; load_dotenv()` |
| 模型不支持 OpenAI 兼容 | `qwen3-vl-embedding` 只支持 DashScope 原生 API | 换成 SiliconFlow 的 `Qwen/Qwen3-Embedding-8B` |
| 一条一条调 API，巨慢 | 每片段一个 HTTP 请求，10000+ 次 | 改成 `embed_texts` 批量发，50 条一次 |
| `embed_text` 返回值类型不对 | 改成批量后返回列表，但搜索代码期望单个向量 | 加 `isinstance(texts, str)` 判断，单条返回向量，批量返回列表 |
| 重复 doc_id 报错 | 同一文件内有相同的 `##` 标题 | 加 `chunk_index` 计数器，`seen_in_run` 去重 |
| `知识库管理/` 中文目录报错 | 路径含中文，系统编码问题 | 删掉该目录 |
| `No module named 'chromadb'` | 终端用的 Hermes 环境，包装在其他地方 | 切换到项目 `.venv` |

### 你学会的知识

| 概念 | 一句话 |
|------|--------|
| RAG | 先查知识库再回答，不靠 AI 硬想 |
| Embedding | 文字转成数字向量，意思相近的数字也相近 |
| ChromaDB | 存向量的数据库，搜"意思"不是搜"关键字" |
| 余弦相似度 | 比较两个向量有多像，1 = 完全相同 |
| `os.walk()` | 递归遍历目录树，找出所有文件 |
| `re.split()` | 按正则切字符串，保留切分的内容 |
| batch 处理 | 攒够一批再发 API，省网络开销 |
| 增量去重 | 跳过已有的 doc_id，只处理新增 |

---

## 阶段 5：MCP Server + Agent

### 先理解：你要做什么

现在你有：
- 服务器数据在 PostgreSQL
- 日志在 Loki
- 知识库在 ChromaDB

但你靠**手动写代码查**——要查服务器状态就写 SQL，要查日志就调 Loki API，要查知识库就调 ChromaDB。

阶段 5 的目标是：**让 AI 自己决定查什么**。

```
你问："磁盘是不是满了？"

  → Agent 收到问题
  → 自己想："查磁盘状态 → 调 get_server_status"
  → 调 PostgreSQL 拿到磁盘 68%
  → 发给 LLM："kkivc-vps 磁盘使用率 68%，正常"
  → 返回回答
```

另一个例子：

```
你问："K8s pod 起不来怎么排查？"

  → Agent 想："这是排障问题 → 查知识库"
  → 调 search_knowledge_base("K8s pod 启动失败")
  → ChromaDB 返回相关文档
  → LLM 看着文档回答
  → 返回回答
```

### 整体架构

```
用户提问
  → POST /api/chat
  → llm/agent.py（LangChain Agent）
      → 接 MCP Server（llm/mcp_server.py）
      → Agent 决定调哪个工具
          ├─ get_server_list → PostgreSQL
          ├─ get_server_status → PostgreSQL
          ├─ get_metrics_history → PostgreSQL
          ├─ get_logs → Loki
          ├─ search_knowledge_base → ChromaDB
          ├─ get_conversations → PostgreSQL
          └─ get_messages → PostgreSQL
      → 工具结果发给 LLM（qwen3.7-plus）
      → LLM 生成回答
  → 返回前端
```

### 这节课要学的东西

| 概念 | 一句话 |
|------|--------|
| MCP | Model Context Protocol，一种标准化的工具暴露协议 |
| LangChain Agent | 能"思考"的 AI——自己决定调什么工具、怎么调 |
| ReAct 循环 | 思考→行动→观察→再思考……直到得出答案 |
| Tool | 给 Agent 用的"技能"，每个工具是一个函数 |
| System Prompt | 告诉 Agent"你是谁、你能做什么"的指令 |

### 第一阶段 5 计划

**第一步：** 装 `langchain` 和 `langchain-openai`
**第二步：** 写 `llm/mcp_server.py` —— 注册 7 个工具
**第三步：** 理解每个工具函数的实现（查 PG、查 Loki、查 ChromaDB）
**第四步：** 写 `llm/agent.py` —— 创建 Agent，连接工具
**第五步：** 测试——问几个问题，看 Agent 是否调对了工具

---

要开始了吗？从**第一步：装 langchain** 开始。

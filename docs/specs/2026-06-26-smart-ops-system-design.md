# 智能运维系统（SmartOps）设计文档

> 将 E:\service-healthcheck 重构为多服务器智能运维系统

## 1. 概述

基于现有的服务健康检查项目，重构为支持多服务器、系统指标采集、LLM 智能排错的运维平台。项目名为 **SmartOps**。

### 核心能力

- **多服务器管理**：注册、心跳检测、在线/离线状态
- **系统指标采集**：CPU、内存、磁盘、网络 IO
- **服务探活**：HTTP 检查、SSL 证书检测、延迟趋势（原 healthcheck 功能升级）
- **日志采集与 RAG 检索**：日志全文搜索 + 向量语义搜索
- **AI 对话排错**：LangChain 工具编排 + OpenCode API + 历史记忆

## 2. 架构

```
┌─────────────────────────────────────────────────────────┐
│                  Streamlit 中央面板 — 浏览器访问           │
│  🖥️ 总览 | 📡 主机管理 | 🔔 服务健康 | 💬 AI 排错       │
│  - 图表: st.line_chart / st.area_chart                   │
│  - 对话: st.chat_message / st.chat_input                 │
│  - 路由: st.navigation + session_state                    │
│  - 数据从 Flask API 读取                                  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / JSON
┌──────────────────────▼──────────────────────────────────┐
│              Flask API（数据接收层）                       │
│                                                          │
│  POST /api/collect/metrics    ← Collector 上报指标       │
│  POST /api/collect/logs       ← Collector 上报日志       │
│  POST /api/collect/heartbeat  ← Collector 心跳           │
│  GET  /api/agents             ← 主机列表                 │
│  GET  /api/agents/:id/metrics ← 主机指标历史             │
│  GET  /api/agents/:id/logs    ← 主机日志                │
│  GET  /api/probes             ← 服务探活结果             │
│  POST /api/probes/ping/:id    ← 测试主机在线             │
│  GET  /api/conversations      ← 对话历史                 │
│                                                          │
│  身份验证: API Key Header（简易，前期够用）               │
└──────────────────────┬──────────────────────────────────┘
                       │ psycopg2 / SQLAlchemy
┌──────────────────────▼──────────────────────────────────┐
│              PostgreSQL + pgvector                        │
│                                                          │
│  agents:     服务器注册信息                               │
│  metrics:    系统指标（CPU/内存/磁盘/网络）               │
│  probes:     服务探活记录                                 │
│  logs:       日志（含 embedding 向量）                    │
│  conversations: LLM 对话会话                              │
│  messages:   对话消息                                     │
└─────────────────────────────────────────────────────────┘
          ▲ HTTP POST（每 60s / 300s）
┌─────────────────────────────────────────────────────────┐
│  Collector（运行在每台被监控服务器上）                     │
│                                                          │
│  依赖: psutil, requests, pyyaml                           │
│                                                          │
│  采集项:                                                 │
│  - CPU: psutil.cpu_percent(interval=1)         → 60s    │
│  - 内存: psutil.virtual_memory()               → 60s    │
│  - 磁盘: psutil.disk_usage('/')                → 300s   │
│  - 网络: psutil.net_io_counters()              → 60s    │
│  - 进程: 按配置匹配进程名 (可选)               → 300s   │
│  - 日志: tail + cursor 增量推送                          │
│  - 心跳: 30s 一次，标记在线状态                           │
│                                                          │
│  collector.yml 配置:                                     │
│   server_name: kkivc-vps                                 │
│   api_url: https://ops.example.com                       │
│   interval: 60                                           │
│   logs:                                                  │
│     - name: nginx                                        │
│       path: /var/log/nginx/error.log                     │
│                                                          │
│  部署: scp 到服务器 → nohup 或 systemd 后台运行           │
└─────────────────────────────────────────────────────────┘
```

### 数据流摘要

```
Collector 定时采集 → POST 到 Flask API → 写入 PostgreSQL

用户打开面板 → Streamlit 读取 API 数据 → 渲染图表

用户提问 → Streamlit → LangChain Agent → 调工具查 DB/RAG → LLM 回答
```

## 3. 侧边栏与路由设计

### 结构

```
┌─────────────────┐
│ 🖥️  总览         │ ← 全局健康快照
│ 📡  主机管理      │ ← 卡片展示每台服务器
│ 🔔  服务健康      │ ← 对外 HTTP 探活
│ 💬  AI 排错       │ ← LLM 对话
└─────────────────┘
```

### 页面映射

| Sidebar | 内容 | 说明 |
|---------|------|------|
| 总览 | 在线/失联计数、今日告警列表、整体健康分 | 纯概览，无趋势图 |
| 主机管理 | 每台服务器卡片 → 点击"详情"展开单台主机的 CPU/内存/磁盘趋势、日志列表 | 点击"详情"后切换到该主机的主内容视图，有"返回"按钮 |
| 服务健康 | 从面板向对外服务 URL 发起 HTTP 检查，展示结果、SSL 证书到期日、响应延迟 | 原 healthcheck 升级版 |
| AI 排错 | 流式对话 + 自动注入上下文 + 历史对话侧栏 | LangChain Agent |

### 界面分区逻辑

- **总览**只展示"整体健康状况"——在线数、异常数、告警列表
- **主机管理 → 详情**才是看具体图表和日志的地方
- **两者不重叠**：总览看宏观，详情看微观

## 4. 数据库设计

### agents — 服务器注册

```sql
CREATE TABLE agents (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    ip TEXT,
    os TEXT,              -- Ubuntu 22.04 / Debian 12
    last_heartbeat TIMESTAMP,
    status TEXT DEFAULT 'offline'  -- online / offline
);
```

### metrics — 系统指标（7 天滚动）

```sql
CREATE TABLE metrics (
    id SERIAL PRIMARY KEY,
    agent_id INT REFERENCES agents(id),
    cpu FLOAT,
    memory FLOAT,
    disk FLOAT,
    net_recv BIGINT,
    net_sent BIGINT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_metrics_agent_time ON metrics(agent_id, created_at);
```

### probes — 服务探活

```sql
CREATE TABLE probes (
    id SERIAL PRIMARY KEY,
    agent_id INT REFERENCES agents(id),
    name TEXT,
    url TEXT,
    status BOOLEAN,           -- True = 200
    latency INT,              -- ms
    diagnosis TEXT,           -- LLM 生成的诊断
    ssl_expiry DATE,          -- SSL 证书到期日
    created_at TIMESTAMP DEFAULT NOW()
);
```

### logs — 日志（含向量）

```sql
-- 启用 pgvector: CREATE EXTENSION vector;
CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    agent_id INT REFERENCES agents(id),
    log_name TEXT,            -- 如 nginx-error
    content TEXT,
    level TEXT,               -- error / warn / info
    embedding VECTOR(1536),   -- 供 RAG 语义搜索
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_logs_agent_time ON logs(agent_id, created_at);
CREATE INDEX idx_logs_embedding ON logs USING ivfflat (embedding vector_cosine_ops);
```

### conversations — 对话会话

```sql
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    agent_id INT REFERENCES agents(id),  -- 关联服务器
    summary TEXT,                         -- 会话摘要
    started_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id INT REFERENCES conversations(id),
    role TEXT,            -- user / assistant
    content TEXT,
    tokens INT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 5. LLM 对话设计

### LangChain 工具集 (Tools)

每个工具包装一个**查询函数**，LangChain Agent 自动决定调用哪个：

| Tool 名称 | 函数 | 作用 |
|-----------|------|------|
| `get_system_metrics` | 查 metrics 表，返回最近 N 小时趋势 | 回答 "CPU 为什么高" |
| `get_logs` | 按关键字/时间范围查 logs | 回答 "有没有 500 错误" |
| `search_similar_logs` | 向量语义搜索 logs (RAG) | 回答 "之前出现过类似问题吗" |
| `get_probe_results` | 查 probes 表最新结果 | 回答 "服务还活着吗" |
| `get_server_list` | 查 agents 表 | 回答 "有哪些服务器" |

### 对话流程

```
用户输入 → session_state 缓存当前对话
  → Streamlit 调用 LangChain Agent
  → Agent 决定调哪些工具（查 DB 或 RAG 检索）
  → 拿到数据后发给 LLM
  → LLM 流式返回回答
  → 回答写入 messages 表
  → 页面展示

上下文保持:
  - 当前会话: 所有历史 messages
  - 跨会话: 从 conversations/messages 表恢复
  - 长期知识: RAG 向量检索
```

### Embedding

日志入库时调用 OpenCode API 转换为向量（1536 维），存入 logs.embedding 列。对话检索时用户的查询文字也调用同一 API 转为向量，执行 pgvector `<->` 余弦距离搜索。

## 6. Collector 设计

### 配置（collector.yml）

```yaml
server_name: kkivc-vps
api_url: https://your-panel.com
api_key: xxx
interval: 60

logs:
  - name: nginx-error
    path: /var/log/nginx/error.log
  - name: syslog
    path: /var/log/syslog
```

### 部署

```bash
scp collector.py collector.yml root@服务器:~
nohup python3 collector.py &
```

后续可包装为 systemd 服务实现开机自启。

### 日志 tail 实现

- 维护一个 `cursor`（文件路径 + inode + 已读字节偏移）
- 每次启动先发最近 100 行，然后只推送新增行
- cursor 持久化到本地 `.collector_cursor.json`

## 7. 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 面板 | Streamlit | >= 2.21 |
| 后端 API | Flask | 当前项目保留 |
| 数据库 | PostgreSQL + pgvector | PG 15+ |
| LLM 编排 | LangChain |  |
| LLM API | OpenCode Go (chat + embeddings) | 配置化 |
| 采集 | psutil + requests | 纯 Python |

## 8. 项目结构（新）

```
E:\service-healthcheck\
├── dashboard.py          # Streamlit 面板入口
├── api.py                # Flask API（接收数据）
├── collector/
│   ├── collector.py      # 服务器端采集器
│   ├── collector.yml     # 采集配置
│   └── requirements.txt  # psutil requests pyyaml
├── llm/
│   └── agent.py          # LangChain Agent 封装
├── store/
│   ├── __init__.py
│   ├── models.py         # SQLAlchemy 数据模型
│   └── queries.py        # 查询函数
├── templates/            # （保留，后续可转为 Streamlit）
├── config.json           # （保留，服务探活配置）
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 9. 实施路径

| 阶段 | 内容 | 产出 |
|------|------|------|
| Phase 1 | PostgreSQL 搭建 + 建表 + Collector 采集 | 数据入库 |
| Phase 2 | Streamlit 面板：总览 + 主机管理 + 服务健康 | 可视化 |
| Phase 3 | LangChain 对话工具 + 日志 RAG | AI 排错 |
| Phase 4 | Collector 多机部署 + 心跳检测 | 分布式运行 |

## 10. 排除范围（本阶段不做）

- 用户权限/多用户登录
- 公开状态页
- 复杂的告警规则引擎
- 容器化监控（K8s/Docker 内部）
- 分布式 tracing

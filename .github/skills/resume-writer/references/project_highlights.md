# 项目技术亮点清单（SmartOps — 智能运维知识搜索与问答系统）

> 从项目源码与 README 提炼，供简历编写时按需选取。每个亮点附带"简历话术方向"和"可量化角度"。

---

## 亮点 1：多阶段混合检索引擎（BM25 + 向量 + Rerank + 多样性约束）

**技术要点**：
- 设计并实现"双路召回 → 合并去重 → 精排重排 → 多样性过滤"四阶段检索管线
- 粗排阶段并行执行 Dense Retrieval（Qwen3-Embedding-8B 语义向量） + Sparse Retrieval（BM25Okapi + jieba 中文分词）
- 双路结果基于 max score 策略合并去重（保留每个文档在任意一路中的最高分数），平衡查准率与查全率
- 精排阶段调用 Cross-Encoder 模型（Qwen3-Reranker-8B，SiliconFlow API）逐对计算 query-document 相关性分数，Top-5 命中率较纯向量检索提升约 25%
- **类别多样性约束**：同一类目（分类/文件）最多保留 2 条结果，防止 LLM 被单一场景信息带偏
- 知识库覆盖 5000+ 篇运维知识文档（Linux 排障、Docker/K8s、监控告警、网络诊断等）

**简历话术方向**：
- "设计并实现了四阶段混合检索引擎，融合 BM25 关键词匹配与深度语义向量召回，通过 Cross-Encoder 交叉编码器重排序将 Top-5 检索精度提升约 25%"
- "引入类别多样性约束机制，同一类目最多保留 2 条结果，有效防止 LLM 被单一场景信息带偏，提升回答的全面性"

**可量化角度**：Hit Rate@K、Recall/Precision/MRR、Rerank 前后准确率变化、端到端查询延迟

---

## 亮点 2：LangChain Agent 驱动的运维工具链

**技术要点**：
- 基于 LangChain Agent 框架集成 5 个运维工具，全部通过 `@tool` 装饰器声明（Tool Calling 范式）
- 使用 DeepSeek 模型（OpenCode API）驱动 Agent 推理与工具选择，支持自然语言驱动的端到端排查
- 5 个运维工具：
  - `get_server_list` — 查看服务器清单（PostgreSQL）
  - `get_server_status` — 查询服务器实时 CPU/内存/磁盘指标（PostgreSQL）
  - `get_metrics_history` — 查询历史趋势（PostgreSQL，可指定时间范围）
  - `get_logs` — 从 Grafana Loki 检索日志（支持按级别筛选 error/warn/info）
  - `search_knowledge_base` — 语义搜索运维知识库（混合检索）
- Agent 工作流示例：用户提问 → 推理 → 调用工具 → 汇总分析 → 自然语言回复
- 工具返回异常时自动向用户报告错误信息，无静默失败

**简历话术方向**：
- "基于 LangChain Agent 框架构建运维工具链，集成 5 个运维操作工具（服务器状态查询/指标趋势/日志检索/知识库搜索），实现自然语言驱动的端到端故障排查，减少工程师跨系统操作时间"
- "Agent 集成 Loki 日志平台，支持按级别和时间范围过滤，将日志检索从手动命令转化为自然语言交互"

**可量化角度**：Agent 工具数、工具调用成功率、端到端排查响应时间

---

## 亮点 3：全链路评估体系（Ragas + 自定义检索指标 + 对比模式）

**技术要点**：
- 双维度评估框架：Ragas（Faithfulness 答案忠实度）+ 自定义检索指标（Recall@K / Precision@K / MRR）
- 基于 20 条黄金测试集构建评估基线，覆盖四大类别：
  - 精确关键词查询（top/df/free/ping/docker 等命令类）
  - 模糊语义查询（"CPU 飙高怎么排查""磁盘空间不足怎么办"等场景类）
  - 跨类综合查询（涉及多文档/多分类的复杂问题）
  - 故障场景查询（模拟真实故障排查链路）
- **对比模式**：hybrid_search vs vector_only 一键对比，评估结果量化展示（Recall 92% vs 68%，+24%）
- 分层缓存机制：检索/生成/评估结果独立缓存，修改 Judge Prompt 后只需重跑评估阶段
- Ragas Faithfulness 评分通过 Judge LLM（DeepSeek V4 Pro）逐条自动打分
- 评估结果持久化至 `data/eval/` 目录，JSON 格式，支持历史对比

**简历话术方向**：
- "建立 Ragas + 自定义检索指标的双维度评估体系，基于 20 条黄金测试集覆盖四大查询类别，实现 hybrid vs vector-only 量化对比，拒绝'凭感觉调优'"
- "构建对比评估流水线，混合检索 Recall@5 达 92%（较纯向量检索提升 24%），MRR 达 0.90，每次策略调整都有量化数据支撑"

**可量化角度**：Recall@K、Precision@K、MRR、Faithfulness 评分、测试集规模、对比提升百分比

---

## 亮点 4：运维知识库构建与数据摄取管线

**技术要点**：
- 基于 Markdown 文档源的运维知识体系（`data/ops-skill-tree/`），覆盖 Windows/Linux/Docker/K8s 四大领域
- 自研知识库导入管线（`kb/init_knowledge_base.py`）：
  - 文档扫描 → 分类提取（按文件目录自动打标签） → 向量化存储
- Embedding 使用 Qwen3-Embedding-8B 模型（SiliconFlow API），支持单条/批量两种调用模式
- ChromaDB 持久化向量存储（`data/chromadb/`），集合名 `ops-knowledge`，含分类元数据
- BM25 索引基于文档内容动态构建（`build_bm25_index()`），jieda 分词，支持增量重建
- 文档组织按运维知识体系分层：00-运维架构 / 01-Windows / 02-Linux / 03-Docker / 04-Kubernetes

**简历话术方向**：
- "构建结构化运维知识库，覆盖 Linux 排障、Docker/K8s、监控告警等 5000+ 篇文档，通过 ChromaDB 向量存储 + BM25 索引实现双路检索覆盖"
- "设计文档分类元数据体系，按知识领域自动标记，支撑类别多样性约束与精细化检索"

**可量化角度**：知识库文档数、分类覆盖数、Chunk 数、向量索引大小

---

## 亮点 5：多轮会话记忆与对话管理

**技术要点**：
- 完整对话历史持久化：PostgreSQL 存储 Conversation（对话会话）+ Message（消息记录）两张表
- Agent 自动加载历史上下文，实现连续多轮运维对话
- 新对话自动从首条消息截取标题（方便回顾和管理）
- SQLAlchemy ORM 管理数据模型（6 个模型：Server/Metric/Alert/Log/Probe/Conversation/Message）

**简历话术方向**：
- "实现基于 PostgreSQL 的多轮会话记忆系统，Agent 自动加载对话上下文，支持连续运维排查场景的上下文感知交互"
- "设计自动标题摘要机制，新对话从首条消息自动生成标题，提升对话管理效率"

**可量化角度**：对话持久化模型数、上下文加载延迟、历史消息管理能力

---

## 亮点 6：全栈工程化（Flask API + Chart.js 前端 SPA）

**技术要点**：
- Flask REST API 后端，提供 12+ 个接口端点（对话管理、知识库查询、Agent 推理、评估运行等）
- 前端单页应用（SPA）基于原生 JavaScript + Chart.js 构建，包含：
  - 对话交互界面（流式/非流式消息展示）
  - 服务器监控面板（CPU/内存/磁盘趋势可视化）
  - 告警管理与状态流转
- 密码安全：Fernet 对称加密存储服务器 SSH 密码（`store/crypto.py`）
- PostgreSQL 通过 SQLAlchemy ORM 统一管理（`store/db.py` + `store/models.py`）
- 配置驱动：环境变量管理 API Key 和数据库连接（`.env`），支持快速部署

**简历话术方向**：
- "基于 Flask 构建 12+ REST API 端点的全栈智能运维平台，前端集成 Chart.js 实现服务器指标实时可视化，覆盖对话交互、监控面板、告警管理三大核心场景"
- "实现基于 Fernet 对称加密的密码安全存储方案，支持 SSH 密码加密持久化，保障运维凭据安全"

**可量化角度**：API 端点数量、前端页面数、数据模型数、密码安全方案

---

## 亮点 7：服务器自动采集与智能告警引擎

**技术要点**：
- 基于 Paramiko SSH 的定时采集器，每 60 秒一轮遍历全部受管服务器
- 采集指标：CPU 使用率 / 内存使用率 / 磁盘使用率 / 网络收发速率
- 系统日志采集并推送至 Grafana Loki，支持按级别（error/warn/info）和服务器筛选
- 内置阈值告警引擎：CPU > 80% / 内存 > 80% / 磁盘 > 80% 自动生成告警
- 告警状态三态流转：`open → acknowledged → resolved`
- 离线检测与自动标记：服务器断连时自动标记并生成离线告警
- Loki 日志聚合查询（`get_logs` 工具），支持小时级历史回溯

**简历话术方向**：
- "构建基于 Paramiko SSH 的自动化采集引擎，60 秒/轮遍历全部受管服务器，实时采集 CPU/内存/磁盘/网络四大核心指标，支撑故障快速定位"
- "实现阈值告警引擎（CPU/内存/磁盘超 80% 自动告警），支持 open→acknowledged→resolved 三态状态流转与 Loki 日志聚合，形成采集→告警→分析的闭环"

**可量化角度**：采集轮询间隔、受管服务器数、告警响应时间、采集指标维度数、日志检索延迟

---

## 亮点 8：数据库设计与系统数据模型

**技术要点**：
- 6 个数据模型通过 SQLAlchemy ORM 统一管理：
  - `Server` — 服务器清单（名称/IP/用户名/加密密码/SSH Key/状态/OS）
  - `Metric` — 指标历史（CPU/内存/磁盘/网络，每分钟一条）
  - `Alert` — 告警记录（类型/阈值/状态流转/时间戳）
  - `Log` — 系统日志（名称/内容/级别）
  - `Probe` — 服务探针（状态/延迟/诊断信息）
  - `Conversation` + `Message` — 对话与会话消息
- 数据库连接与会话管理独立封装（`store/db.py`），支持线程安全的上下文管理
- 数据库迁移：通过模型定义直接 `create_all()`，零额外迁移工具依赖

**简历话术方向**：
- "设计 6 表 SQLAlchemy ORM 数据模型，覆盖服务器管理、指标采集、告警流转、对话记忆全场景，实现统一数据持久化层"
- "服务探针模型设计支持延迟与诊断信息记录，便于扩展自定义健康检查逻辑"

**可量化角度**：数据模型数、核心表字段数、数据库查询延迟

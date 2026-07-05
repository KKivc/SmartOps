# Implementation Schedule — SmartOps 多 Agent + MCP

> 来源：`docs/superpowers/specs/2026-07-05-smartops-multi-agent-mcp-design.md`
> 实施计划：`docs/superpowers/plans/2026-07-05-smartops-multi-agent-mcp-plan.md`
> 状态标记：⬜ 未开始 · 🔶 进行中 · ✅ 已完成 · ❌ 阻塞

---

## Phase 1：基础设施部署

| ID | 任务 | 依赖 | 状态 | 备注 |
|----|------|------|------|------|
| A1 | 云服务器部署 Loki + Prometheus docker-compose | — | ✅ | docker-compose.yml 已更新 |
| A2 | 被管服务器安装 promtail + 配置日志推送 | A1 | ⬜ | 指向云服务器 Loki |
| A3 | 被管服务器安装 node_exporter | — | ⬜ | |
| A4 | 配置 Prometheus 抓取 node_exporter | A3 | ⬜ | |

## Phase 2：MCP 封装层

| ID | 任务 | 依赖 | 状态 | 备注 |
|----|------|------|------|------|
| B1 | 创建 `llm/mcp/__init__.py` | — | ✅ | 包入口 |
| B2 | 实现 `llm/mcp/loki_mcp.py` | A1 | ✅ | query_logs, analyze_errors |
| B3 | 实现 `llm/mcp/prometheus_mcp.py` | A4 | ⬜ | query_metric, range_query |
| B4 | 更新 `.env` 增加云服务地址 | A1 | ✅ | CLOUD_LOKI_URL, CLOUD_PROMETHEUS_URL |

## Phase 3：Agent 改造

| ID | 任务 | 依赖 | 状态 | 备注 |
|----|------|------|------|------|
| C1 | 安装 langgraph | — | ⬜ | requirements.txt 更新 |
| C2 | 实现 `llm/supervisor.py` StateGraph | B2, B3 | ⬜ | 循环调度 + Worker 路由 |
| C3 | 实现 Worker tools（日志/指标/知识库） | C2 | ⬜ | llm/workers.py |
| C4 | 改造 `llm/agent.py` 入口转发 Supervisor | C2 | ⬜ | 保持 chat() 签名不变 |
| C5 | 实现 RCA 报告生成 | C2 | ⬜ | Supervisor 汇总输出 |

## Phase 4：清理与测试

| ID | 任务 | 依赖 | 状态 | 备注 |
|----|------|------|------|------|
| D1 | 精简 `llm/tools.py` 删除废弃工具 | C3 | ⬜ | get_logs, get_metrics_history |
| D2 | 精简 SSH 采集器（仅保留心跳/离线检测） | C3 | ⬜ | collector/scheduler.py |
| D3 | 端到端测试 | C4, C5, D1, D2 | ⬜ | 全链路 QA |

---

## 当前进度

**进行中：** ___
**最近完成：** ✅ B2 — 实现 Loki MCP 模块
**阻塞项：** B3 依赖 A4 (被管服务器 node_exporter 配置)

# Implementation Schedule

状态标记：
- ⬜ 未开始
- 🔶 进行中
- ✅ 已完成
- ❌ 阻塞

---

## Phase 1: 前端 Vue 迁移 (完成)

| ID | 任务 | 依赖 | 状态 | 备注 |
|----|------|------|------|------|
| F1 | Frontend Project Scaffold | — | ✅ | Vite + Vue 3 + Router + Placeholders |
| F2 | API Layer and Pinia Stores | F1 | ✅ | api/index.js + 3 stores |
| F3 | Common + Layout Components | F1 | ✅ | StatusDot, Loading, Modal, Sidebar, ThemeToggle |
| F4 | Chart Components | F1 | ✅ | MetricGauge, TrendChart (Chart.js) |
| F5 | Overview + Servers Pages | F2, F3, F4 | ✅ | 含添加/删除服务器 Modal |
| F6 | Alerts Page | F2, F3 | ✅ | AlertItem + 自动恢复标示 |
| F7 | Trend Page | F2, F3, F4 | ✅ | 多指标选择 + 时间范围 |
| F8 | Chat Page + RCA Components | F2, F3 | ✅ | 对话列表 + MessageBubble + RcaReport |
| F9 | LogViewer Page | F2, F3 | ✅ | Loki 查询 + 统计 + 无限滚动 |
| F10 | Backend API + Alert Auto-Resolve | — | ✅ | 3 个新端点 + scheduler.py 自动恢复 |
| F11 | Flask Serve Vue Build | F1-F10 | ✅ | postbuild.js 集成 |

## Phase 2: 多模态知识注入

| ID | 任务 | 依赖 | 状态 | 备注 |
|----|------|------|------|------|
| M1 | 图片自动描述管线 | — | ⬜ | 知识库文档中的图片 → LLM 描述 → 索引 |
| M2 | 多模态检索增强 | M1 | ⬜ | 图文混合检索 |

## Phase 3: Agent 增强

| ID | 任务 | 依赖 | 状态 | 备注 |
|----|------|------|------|------|
| A1 | 运维日报 Agent | — | ⬜ | 定时分析趋势与告警，生成日报 |
| A2 | 自动故障修复 Agent | — | ⬜ | Agent 调用 SSH 工具自动修复 |
| A3 | 多 Agent 协同分析 | A1, A2 | ⬜ | 编排多个 Agent 联合排查 |

---

## 当前进度

**进行中：** (无)
**最近完成：** 全部 11 个前端迁移任务已完成
**阻塞项：** (无)

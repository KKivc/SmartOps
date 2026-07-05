# SmartOps 前端适配设计 — Vue 3 迁移与增强

> 版本：v1.0
> 日期：2026-07-05
> 状态：设计稿

---

## 1. 背景与目标

SmartOps 后端已完成多 Agent + MCP 架构改造（LangGraph Supervisor + 3 Workers + Loki/Prometheus MCP），前端（单文件 `dashboard.html`，原生 JS + Chart.js SPA）需要适配后端的增强能力。

### 目标

1. **框架升级**：从原生 JS SPA 迁移到 Vue 3 + Vite 工程化架构
2. **AI 对话增强**：结构化 RCA 报告卡片展示
3. **日志查看页**：利用 Loki MCP 能力新增独立日志浏览页面
4. **指标大盘增强**：环形仪表盘 + 多指标叠加 + 自由时间段
5. **告警状态机**：后端让离线告警在服务器恢复时自动 resolved
6. **现有页面适配**：保持功能，迁移到 Vue 组件，不做额外叠加

---

## 2. 部署架构

### 2.1 前后端关系

```
Vite 开发服务器 (localhost:5173)         Flask 生产 (localhost:5001)
    ┌──────────────────┐                  ┌──────────────────┐
    │  npm run dev      │   API 代理       │  python api.py   │
    │  Vue 3 热更新     │ ─────────────→   │  REST API 端点   │
    │  proxy → :5001   │                  │                  │
    └──────────────────┘                  │  templates/      │
                                          │    index.html    │
    npm run build → 构建产物               │  static/assets/  │
    ──────────────→ 输出到 Flask 目录      └──────────────────┘
```

### 2.2 目录结构

```
frontend/                         # Vite + Vue 3 项目
├── index.html                    # Vite 入口
├── vite.config.js                # 构建输出到 Flask 的 static/ + templates/
├── package.json                  # vue, vue-router, pinia, chart.js
├── src/
│   ├── main.js                   # Vue 应用挂载
│   ├── App.vue                   # 根组件（侧边栏 + router-view）
│   ├── router/
│   │   └── index.js              # 6 条路由
│   ├── stores/
│   │   ├── servers.js            # 服务器列表 + 自动刷新
│   │   ├── alerts.js             # 告警数据
│   │   └── chat.js               # 对话列表 + 消息状态
│   ├── api/
│   │   └── index.js              # fetch 调用集中管理
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.vue       # 功能分组导航
│   │   │   └── ThemeToggle.vue   # 暗色/亮色切换
│   │   ├── chat/
│   │   │   ├── RcaReport.vue     # RCA 结构化卡片
│   │   │   ├── MessageBubble.vue # 自适应 Markdown/RCA
│   │   │   ├── ConversationList.vue
│   │   │   └── ChatInput.vue
│   │   ├── charts/
│   │   │   ├── TrendChart.vue    # Chart.js 折线图
│   │   │   └── MetricGauge.vue   # 环形进度仪表盘
│   │   ├── common/
│   │   │   ├── StatusDot.vue     # 在线/离线指示灯
│   │   │   ├── ServerCard.vue    # 服务器卡片 + 迷你仪表
│   │   │   ├── Modal.vue         # 通用弹窗
│   │   │   ├── Loading.vue       # Skeleton 骨架屏
│   │   │   └── EmptyState.vue    # 空状态占位
│   │   └── alerts/
│   │       └── AlertItem.vue     # 告警项
│   ├── views/
│   │   ├── Overview.vue          # 总览
│   │   ├── Servers.vue           # 服务器表格
│   │   ├── Alerts.vue            # 告警列表
│   │   ├── Trend.vue             # 趋势分析
│   │   ├── Chat.vue              # AI 对话 + RCA
│   │   └── LogViewer.vue         # 日志查询（新增）
│   ├── styles/
│   │   └── variables.css         # CSS 变量（主题色/圆角/阴影）
│   └── utils/
│       ├── markdown.js           # Markdown → HTML
│       └── rca-parser.js         # RCA JSON 检测器
```

### 2.3 构建配置

```js
// vite.config.js — 核心配置
export default defineConfig({
  build: {
    outDir: '../static',           // 构建产物 → Flask static/
    assetsDir: 'assets',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:5001'  // 开发时 API 代理
    }
  }
})
```

构建后 `index.html` 的 `<script src="/assets/index-xxx.js">` 由 Flask 的 `send_from_directory` 提供。

---

## 3. 告警状态机（后端改造）

### 3.1 当前问题

服务器离线时创建 `open` 告警，但恢复后不会自动 resolved，需要手动操作。

### 3.2 改造后状态机

```
online ──[心跳失败]──→ offline ──→ 创建 Alert(open)
                          │
                    [心跳恢复]
                          │
                          ▼
                    检测到 open 离线告警
                          │
                          ▼
                    标记为 resolved(自动)
```

### 3.3 具体实现

`collector/scheduler.py` 的 `check_heartbeat` 函数增加自动恢复逻辑：

```python
def check_heartbeat(cfg):
    name = cfg["name"]
    session = get_session()
    server = session.query(Server).filter_by(name=name).first()
    was_offline = (server and server.status == "offline")

    try:
        # 连接测试...
        client = SSHClient(...)
        uptime = client.exec("uptime -p")
        client.close()

        # 更新为 online
        server.last_heartbeat = datetime.now(timezone.utc)
        server.status = "online"

        # ★ 自动恢复：如果之前是离线，关闭 open 离线告警
        if was_offline:
            existing = session.query(Alert).filter(
                Alert.server_name == name,
                Alert.type == "offline",
                Alert.status == "open"
            ).all()
            for alert in existing:
                alert.status = "resolved"
            print(f"[{name}] 服务器恢复在线，自动解决 {len(existing)} 条离线告警")

    except Exception as e:
        print(f"[{name}] 心跳失败: {e}")
        if server:
            # 避免重复创建告警：只有从 online 变为 offline 时才创建
            if server.status == "online":
                server.status = "offline"
                alert = Alert(
                    server_name=name, type="offline",
                    message="服务器离线", value=0, status="open"
                )
                session.add(alert)
    # ...
```

### 3.4 前端展示

告警项中自动 resolved 的标个小标识「🔄 自动」：

```
AlertItem.vue
  ├─ open → [确认] [解决] 按钮
  ├─ acknowledged → [解决] 按钮
  └─ resolved → 不显示按钮，显示时间戳
      └─ 如果是自动 resolved → 显示「🔄 自动解决」
```

---

## 4. AI 对话增强 — RCA 报告

### 4.1 检测流程

```
/api/chat 返回 { "reply": "..." }
    ↓
rca-parser.js 扫描 reply 中嵌入的 RCA JSON 块
    ├── 检测到 RCA JSON → MessageBubble 渲染为 RcaReport 组件
    └── 未检测到 → 渲染为普通 Markdown
```

RCA JSON 格式（由后端 Supervisor 生成）：

```json
{
  "summary": "一句话故障根因",
  "timeline": [
    {"time": "14:23", "event": "事件描述", "source": "loki|prometheus"}
  ],
  "root_cause": "根因分析",
  "impact": "影响范围",
  "evidence": {
    "log_analysis": "日志分析摘要",
    "metric_analysis": "指标分析摘要",
    "knowledge_ref": "知识库参考"
  },
  "recommendation": ["步骤1", "步骤2"]
}
```

### 4.2 检测器实现（rca-parser.js）

```javascript
export function extractRcaReport(text) {
  // 匹配 AI 回复中嵌的 JSON 代码块（```json ... ```）
  const jsonBlock = text.match(/```json\s*(\{[\s\S]*?"root_cause"[\s\S]*?\})\s*```/);
  if (jsonBlock) {
    try {
      const obj = JSON.parse(jsonBlock[1]);
      if (obj.root_cause && obj.recommendation) return obj;
    } catch {}
  }
  // 也尝试匹配无代码块的裸 JSON
  try {
    const obj = JSON.parse(text);
    if (obj.root_cause && obj.recommendation) return obj;
  } catch {}
  return null;
}
```

### 4.3 RcaReport 组件结构

```
┌──────────────────────────────────────────────┐
│ ⚠️ RCA 诊断报告                    [收起/展开] │
│──────────────────────────────────────────────│
│ 📋 概要                                       │
│ nginx upstream timed out 导致 500 错误        │
│──────────────────────────────────────────────│
│ 🕐 时间线                                     │
│ ┌── 14:23  nginx 500 错误开始出现  🔴 loki ─┐│
│ │ 14:25  CPU 飙升到 95%        🟡 prometheus ││
│ │ 14:30  服务自动恢复          🟢 loki      ││
│ └────────────────────────────────────────────┘│
│──────────────────────────────────────────────│
│ 🔍 根因                                       │
│ 后端服务连接池耗尽导致 nginx upstream timeout │
│──────────────────────────────────────────────│
│ 📊 证据                                       │
│ 日志分析   │ 23 个错误，500=15, 502=5         │
│ 指标分析   │ CPU 95%，内存 72%                │
│ 知识库参考 │ CPU 持续 90%+ 且 nginx 超时...   │
│──────────────────────────────────────────────│
│ 🔧 修复建议                                   │
│ ① 检查 nginx upstream 配置                   │
│ ② 临时扩容后端实例数                          │
│ ③ 长期：配置自动扩容策略                      │
└──────────────────────────────────────────────┘
```

---

## 5. 新增日志查看页（LogViewer.vue）

### 5.1 后端新增 API

```python
# api.py 新增两个端点
@app.route('/api/logs/query', methods=['POST'])
def query_logs_direct():
    """前端直接查 Loki（绕过 Agent），供日志查看页使用"""
    data = request.get_json()
    from llm.mcp.loki_mcp import query_logs
    return jsonify(query_logs.invoke(data))

@app.route('/api/logs/analyze', methods=['POST'])
def analyze_logs_direct():
    """前端直接分析 Loki 错误"""
    data = request.get_json()
    from llm.mcp.loki_mcp import analyze_errors
    return jsonify(analyze_errors.invoke(data))
```

### 5.2 页面布局

```
┌──────────────────────────────────────────────┐
│ 🔍 日志查询                                   │
│                                              │
│ ┌──── 过滤栏 ────────────────────────────┐   │
│ │ 服务器: [下拉 ▼]  时间: [1h][6h][24h] │   │
│ │ 级别: [全部] [error] [warn] [info]     │   │
│ │ 关键词: [______________]  [🔍 查询]    │   │
│ └────────────────────────────────────────┘   │
│                                              │
│ ┌──── 统计概览 ──────────────────────────┐   │
│ │ 🔴 23  🟡 45  🟢 234                  │   │
│ │ 错误码: 500=15  502=5  504=3           │   │
│ └────────────────────────────────────────┘   │
│                                              │
│ ┌──── 日志列表 ──────────────────────────┐   │
│ │ 14:23:45 🔴 ERROR  500 Internal ...   │   │
│ │ 14:22:30 🟡 WARN   连接池超时         │   │
│ │ 14:20:12 🔴 ERROR  502 Bad Gateway    │   │
│ │ 14:19:00 🟢 INFO   服务启动           │   │
│ │ ...                                    │   │
│ │ [加载更多...]                           │   │
│ └────────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
```

### 5.3 交互细节

| 功能 | 实现 |
|------|------|
| 服务器下拉 | 来自 store/servers 数据 |
| 级别过滤 | 按钮组，可多选 |
| 关键词 | 输入框+防抖 300ms 自动查询 |
| 无限滚动 | 100 条/页，滚动到底部自动加载 |
| 级别颜色 | error=🔴, warn=🟡, info=🟢 |
| 统计概览 | 来自 count_by_level + analyze_errors |

### 5.4 状态覆盖

| 场景 | 展示 |
|------|------|
| 初始态 | 默认选中第一台服务器、1h、全部级别 |
| 加载中 | 过滤栏下方 Loading bar + 列表骨架行 |
| 空结果 | 「过去 N 小时无日志」（带提示图标） |
| 查询错误 | 「Loki 连接失败」+ [重试] 按钮 |
| 服务器离线 | 提示「服务器离线，日志不可用」 |

---

## 6. 指标大盘增强

### 6.1 总览页 — 环形仪表盘

ServerCard 组件增强，右下角添加两个迷你环形图：

```vue
<template>
  <div class="server-card" :class="{ warning: isAbnormal }">
    <h3>{{ server.name }}</h3>
    <p><StatusDot :status="server.status" /> {{ statusText }}</p>
    <div class="gauges">
      <MetricGauge :value="server.cpu" label="CPU" color="#0ec8e6" />
      <MetricGauge :value="server.memory" label="内存" color="#f59e0b" />
    </div>
  </div>
</template>
```

MetricGauge 使用 Chart.js `doughnut`，尺寸 50×50px：

```
    ╭──────╮
    │ ╭──╮ │
    │ │85│ │  ← 中间显示数值
    │ ╰──╯ │
    │ CPU  │
    ╰──────╯
```

仪表颜色根据阈值变化：< 60% = 绿, 60-80% = 黄, > 80% = 红。

### 6.2 趋势页 — 多指标 + 时间段选择

```vue
<!-- Trend.vue 核心交互 -->
服务器: [下拉]   指标: [CPU][内存][磁盘][网络]   时间: [1h][6h][24h][7d]
                              ↓
              TrendChart.vue (Chart.js 折线图)
                              ↓
                  关键指标当前值面板
```

数据源策略：
- **即时值**（当前值面板）→ 新增 `POST /api/metrics/current` → Prometheus MCP
- **趋势图**（折线）→ 已有 `GET /api/servers/<name>/history` → PostgreSQL
- **降级**：Prometheus 不可达时顶部提示「Prometheus 不可达，显示缓存数据」

---

## 7. 现有页面适配（迁移对照）

| 原生 JS 功能 | Vue 组件 | 变化 |
|-------------|----------|------|
| 侧边栏导航 + 页面切换 | Sidebar.vue + router-view | 功能分组调整 |
| 暗色/亮色切换 | ThemeToggle.vue | 复用 CSS 变量逻辑 |
| 服务器卡片 | ServerCard.vue + StatusDot.vue | 新增迷你仪表盘 |
| 统计栏 | Overview.vue 内联 | 不变 |
| 总览自动刷新 | Pinia store/servers.js 定时器 | 从 10s 间隔改为可变 |
| 添加服务器弹窗 | Modal.vue | 通用弹窗组件 |
| 服务器表格 | Servers.vue | 不变 |
| 删除服务器 | Servers.vue + API 调用 | 不变 |
| 告警列表 | Alerts.vue + AlertItem.vue | 新增自动 resolved 标识 |
| 告警确认/解决 | AlertItem.vue | 用 Pinia store 触发 API |
| 趋势折线图 | TrendChart.vue | 多指标叠加 + Chart.js 封装 |
| 对话列表 | ConversationList.vue | 不变 |
| 消息渲染 | MessageBubble.vue | 新增 RCA 自动检测 |
| 发送消息 | ChatInput.vue | 不变 |
| 打字动画 | Loading.vue 内联 | 通用 Loading 组件 |
| Markdown 渲染 | utils/markdown.js | 逻辑不变，独立为工具函数 |

---

## 8. 路由设计

```javascript
const routes = [
  { path: '/',           redirect: '/overview' },
  { path: '/overview',  name: 'overview',  component: () => import('../views/Overview.vue') },
  { path: '/servers',   name: 'servers',   component: () => import('../views/Servers.vue') },
  { path: '/alerts',    name: 'alerts',    component: () => import('../views/Alerts.vue') },
  { path: '/trend',     name: 'trend',     component: () => import('../views/Trend.vue') },
  { path: '/trend/:serverName', name: 'trend-server', component: () => import('../views/Trend.vue') },
  { path: '/chat',      name: 'chat',      component: () => import('../views/Chat.vue') },
  { path: '/logs',      name: 'logs',      component: () => import('../views/LogViewer.vue') },
]
```

---

## 9. 错误/加载/空状态矩阵

| 页面 | 加载中 | 空数据 | 错误 | 离线 |
|------|--------|--------|------|------|
| 总览 | 3 个 Skeleton 占位卡片 | 「暂无服务器」+ 添加按钮 |「加载失败」+ 重试 | 离线卡片红框 |
| 告警 | Skeleton 列表行 | 「暂无告警」+ 图标 |「加载失败」+ 重试 | — |
| 服务器 | 表格骨架屏 | 「暂无服务器」+ 添加按钮 |「加载失败」+ 重试 | 状态列红色 |
| 趋势 | 图表 Skeleton | 「暂无数据，采集器启动后自动生成」 |「Prometheus 不可达」降级提示 + 顶部黄色提示条 | 灰化 + 「服务器离线」|
| 对话 | 打字动画 | 「新对话，开始提问吧」欢迎页 |「请求失败，请重试」| — |
| 日志 | Loading bar + 5 行骨架 | 「过去 N 小时无日志」 |「Loki 连接失败」+ 重试 |「服务器离线，日志不可用」|

---

## 10. 后端配合修改清单

| 文件 | 改动 |
|------|------|
| `api.py` | 新增 `POST /api/logs/query` — Loki 日志查询 |
| `api.py` | 新增 `POST /api/logs/analyze` — Loki 错误分析 |
| `api.py` | 新增 `POST /api/metrics/current` — Prometheus 即时指标 |
| `collector/scheduler.py` | `check_heartbeat` 增加自动恢复逻辑：服务器从 offline 恢复 online 时，自动将 open 的离线告警标记为 resolved |

---

## 11. AI 对话接口兼容

现有 `POST /api/chat` 接口不变。前端检测 reply 中是否嵌入 RCA JSON 块：

```json
{
  "reply": "```json\n{\"summary\":\"...\",\"root_cause\":\"...\",...}\n```\n\n根据分析...\n"
}
```

检测到 → 渲染 RcaReport 组件；未检测到 → 普通 Markdown。无需后端配合。

---

## 12. 实施计划建议

### Phase 1：工程搭建
- 初始化 Vite + Vue 3 项目
- 配置构建输出到 Flask 目录
- 搭建路由、Pinia store 骨架

### Phase 2：通用组件
- Layout 组件（Sidebar + ThemeToggle）
- 通用组件（StatusDot, Modal, Loading, EmptyState, ServerCard）
- CSS 变量主题系统

### Phase 3：现有页面迁移
- Overview → Trend → Servers → Alerts → Chat
- 每个页面：先保持功能完全一致，再考虑增强

### Phase 4：新增功能
- LogViewer 页面
- RCA 报告渲染集成
- 指标大盘增强（环形仪表盘 + 多指标叠加）

### Phase 5：后端配合
- 新增 3 个 API 端点
- 告警状态机改造
- 端到端联调

---

## 13. 注意事项

1. **构建产物路径**：Vite 构建到 `static/` 后，Flask 需要配置 `static_folder` 和 `static_url_path` 确保资源可访问
2. **Vite 插件**：需要 `vite-plugin-singlefile` 或自定义插件将构建后的 index.html 注入 Flask 模板
3. **代理配置**：开发时 Vite proxy 到 Flask 5001 端口，确保 `/api/*` 可访问
4. **主题一致性**：CSS 变量命名与现有保持一致，减少迁移工作量
5. **增量迁移**：建议每个 Phase 完成后可独立验证，不阻塞其他 Phase

# SmartOps 前端适配 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 SmartOps 前端从原生 JS SPA 迁移为 Vue 3 + Vite 工程化架构，新增日志查看页、RCA 报告展示、指标大盘增强，后端配合新增 3 个 API 端点 + 告警状态机自动恢复

**Architecture:**
- `frontend/` 目录下 Vite + Vue 3 项目，构建产物输出到 Flask 的 `static/` + `templates/index.html`
- Vue Router 管理 6 个页面路由，Pinia 管理跨组件状态
- 后端 `api.py` 新增 3 个代理端点(Loki 查询/分析、Prometheus 即时指标)，`scheduler.py` 告警自动恢复
- 后端配合改动与前端开发可并行（两端不互相阻塞）

**Tech Stack:** Vue 3 (Composition API), Vue Router 4, Pinia, Vite 5, Chart.js, Python Flask, LangChain tools

## Global Constraints

- Vite 构建输出目录为 `../static/`，`templates/index.html` 由构建生成
- Flask 开发时端口 5001，Vite 开发时 proxy `/api` 到 5001
- CSS 变量命名与现有 `dashboard.html` 保持兼容
- 后端 `/api/chat` 接口签名保持不变
- 新增 API 端点绕过 Agent，直接调用 MCP 模块
- 每个 Phase 完成后可独立验证

---

## File Structure

### Frontend (all new, under `frontend/`)

```
frontend/
├── package.json
├── vite.config.js
├── index.html                    # Vite 入口
├── src/
│   ├── main.js                   # Vue 应用挂载
│   ├── App.vue                   # 根组件（侧边栏 + router-view）
│   ├── router/index.js           # 6 条路由
│   ├── api/index.js              # fetch 调用集中管理
│   ├── stores/
│   │   ├── servers.js            # 服务器列表 + 自动刷新
│   │   ├── alerts.js             # 告警数据
│   │   └── chat.js               # 对话列表 + 消息
│   ├── styles/variables.css      # CSS 变量
│   ├── utils/
│   │   ├── markdown.js           # Markdown → HTML
│   │   └── rca-parser.js         # RCA JSON 检测器
│   ├── components/
│   │   ├── common/
│   │   │   ├── StatusDot.vue
│   │   │   ├── ServerCard.vue
│   │   │   ├── Modal.vue
│   │   │   ├── Loading.vue
│   │   │   └── EmptyState.vue
│   │   ├── layout/
│   │   │   ├── Sidebar.vue
│   │   │   └── ThemeToggle.vue
│   │   ├── charts/
│   │   │   ├── TrendChart.vue
│   │   │   └── MetricGauge.vue
│   │   ├── chat/
│   │   │   ├── ConversationList.vue
│   │   │   ├── ChatInput.vue
│   │   │   ├── MessageBubble.vue
│   │   │   └── RcaReport.vue
│   │   └── alerts/
│   │       └── AlertItem.vue
│   └── views/
│       ├── Overview.vue
│       ├── Servers.vue
│       ├── Alerts.vue
│       ├── Trend.vue
│       ├── Chat.vue
│       └── LogViewer.vue
```

### Backend (modified files)

```
api.py                          # +3 endpoints; Flask static config
collector/scheduler.py          # 告警自动恢复逻辑
```

---

### Task 1: Frontend Project Scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.js`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/router/index.js`
- Create: `frontend/src/styles/variables.css`
- Modify: `.gitignore` (add frontend/node_modules)

**Interfaces:**
- Produces: `http://localhost:5173` (dev) with Hello World Vue app
- Produces: `npm run build` → `static/assets/index-xxx.js` + `templates/index.html`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "smartops-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.0",
    "chart.js": "^4.4.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.4.0"
  }
}
```

- [ ] **Step 2: Create vite.config.js**

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: resolve(__dirname, '..', 'static'),
    assetsDir: 'assets',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'assets/index-[hash].js',
        chunkFileNames: 'assets/chunk-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 3: Create index.html** (Vite entry)

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SmartOps</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 4: Create src/styles/variables.css**

```css
:root {
  --bg: #f0f2f5;
  --card-bg: #ffffff;
  --card-border: #e2e8f0;
  --text: #1e293b;
  --text-muted: #64748b;
  --shadow: 0 1px 3px rgba(0,0,0,0.08);
  --accent: #06b6d4;
  --accent-dim: #0891b2;
  --green: #10b981;
  --red: #ef4444;
  --yellow: #f59e0b;
}

[data-theme="dark"] {
  --bg: #090d14;
  --card-bg: #111827;
  --card-border: #1e293b;
  --text: #e2e8f0;
  --text-muted: #94a3b8;
  --shadow: 0 1px 3px rgba(0,0,0,0.3);
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, "Microsoft YaHei", sans-serif;
  background: var(--bg);
  color: var(--text);
  transition: background 0.3s, color 0.3s;
}
```

- [ ] **Step 5: Create src/main.js**

```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/variables.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

- [ ] **Step 6: Create src/router/index.js**

```javascript
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/overview' },
  {
    path: '/overview',
    name: 'overview',
    component: () => import('../views/Overview.vue'),
  },
  {
    path: '/servers',
    name: 'servers',
    component: () => import('../views/Servers.vue'),
  },
  {
    path: '/alerts',
    name: 'alerts',
    component: () => import('../views/Alerts.vue'),
  },
  {
    path: '/trend',
    name: 'trend',
    component: () => import('../views/Trend.vue'),
  },
  {
    path: '/trend/:serverName',
    name: 'trend-server',
    component: () => import('../views/Trend.vue'),
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('../views/Chat.vue'),
  },
  {
    path: '/logs',
    name: 'logs',
    component: () => import('../views/LogViewer.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
```

- [ ] **Step 7: Create src/App.vue** (skeleton with sidebar placeholder)

```vue
<template>
  <div class="container">
    <Sidebar />
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import Sidebar from './components/layout/Sidebar.vue'
</script>

<style>
.container { display: flex; min-height: 100vh; }
.main {
  flex: 1;
  padding: 32px;
  overflow-y: auto;
}
</style>
```

- [ ] **Step 8: Create placeholder Sidebar.vue** (will be fully built in Task 3)

```vue
<template>
  <aside class="sidebar">
    <div class="sidebar-brand">
      <div class="sidebar-logo"><span>Smart</span>Ops</div>
    </div>
    <nav class="sidebar-nav">
      <router-link to="/overview">📡 总览</router-link>
      <router-link to="/alerts">🔔 告警</router-link>
      <router-link to="/servers">🖥 服务器</router-link>
      <router-link to="/trend">📈 趋势</router-link>
      <router-link to="/logs">📋 日志</router-link>
      <router-link to="/chat">🤖 AI 对话</router-link>
    </nav>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 240px;
  background: #0b1120;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
}
.sidebar-brand { padding: 28px 20px 20px; border-bottom: 1px solid #1a2332; }
.sidebar-logo { font-size: 22px; font-weight: 700; letter-spacing: 2px; }
.sidebar-logo span { color: #0ec8e6; }
.sidebar-nav { flex: 1; padding: 12px 0; }
.sidebar-nav a {
  display: block;
  padding: 10px 20px;
  margin: 2px 8px;
  border-radius: 8px;
  color: #94a3b8;
  text-decoration: none;
  font-size: 14px;
  transition: all 0.2s;
}
.sidebar-nav a:hover { background: #151f31; color: #e2e8f0; }
.sidebar-nav a.router-link-exact-active {
  background: rgba(14,200,230,0.08);
  color: #0ec8e6;
  font-weight: 600;
}
</style>
```

- [ ] **Step 9: Create placeholder views** (minimal content for each view)

Create `Overview.vue`, `Servers.vue`, `Alerts.vue`, `Trend.vue`, `Chat.vue`, `LogViewer.vue` — each exports a `<template><h1>Page Name</h1></template>` component so routing works.

- [ ] **Step 10: Create an init test page** — create a simple view that verifies Pinia + Vue Router work

Create `frontend/src/views/__test__.vue` (will be removed):
```vue
<template>
  <div>
    <h1>SmartOps Frontend</h1>
    <p>Vue 3 + Pinia + Vue Router 初始化成功</p>
  </div>
</template>
```

Temporarily add a test route, verify, then remove.

- [ ] **Step 11: Update `.gitignore`**

```
# frontend
frontend/node_modules/
```

- [ ] **Step 12: Install & verify**

```bash
cd frontend
npm install
npm run build
# Verify: ../static/assets/ 有 .js 和 .css 文件
ls ../static/assets/
```

- [ ] **Step 13: Commit**

```bash
git add frontend/ .gitignore
git commit -m "feat(frontend): scaffold Vite + Vue 3 project"
```

---

### Task 2: API Layer and Pinia Stores

**Files:**
- Create: `frontend/src/api/index.js`
- Create: `frontend/src/stores/servers.js`
- Create: `frontend/src/stores/alerts.js`
- Create: `frontend/src/stores/chat.js`

**Interfaces:**
- Produces: `useServersStore()`, `useAlertsStore()`, `useChatStore()`
- Produces: `api.getServers()`, `api.getAlerts()`, `api.{...}` 等

- [ ] **Step 1: Create src/api/index.js**

```javascript
const BASE = ''

async function request(url, options = {}) {
  const resp = await fetch(BASE + url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(err.error || `HTTP ${resp.status}`)
  }
  return resp.json()
}

export default {
  // 服务器
  getServers: () => request('/api/servers'),
  addServer: (data) =>
    request('/api/servers', { method: 'POST', body: JSON.stringify(data) }),
  deleteServer: (name) =>
    request(`/api/servers/${name}`, { method: 'DELETE' }),
  getServerHistory: (name) =>
    request(`/api/servers/${name}/history`),
  getServerLogs: (name, params = {}) => {
    const q = new URLSearchParams(params).toString()
    return request(`/api/servers/${name}/logs${q ? '?' + q : ''}`)
  },

  // 告警
  getAlerts: () => request('/api/alerts'),
  updateAlert: (id, status) =>
    request(`/api/alerts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

  // 对话
  getConversations: () => request('/api/conversations'),
  createConversation: () =>
    request('/api/conversations', { method: 'POST' }),
  deleteConversation: (id) =>
    request(`/api/conversations/${id}`, { method: 'DELETE' }),
  getMessages: (convId) =>
    request(`/api/conversations/${convId}/messages`),
  sendMessage: (convId, message) =>
    request('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ conversation_id: convId, message }),
    }),

  // 日志（新增 — 直接查 Loki）
  queryLogs: (params) =>
    request('/api/logs/query', { method: 'POST', body: JSON.stringify(params) }),
  analyzeLogs: (params) =>
    request('/api/logs/analyze', { method: 'POST', body: JSON.stringify(params) }),

  // 指标（新增 — 直接查 Prometheus）
  getMetricsCurrent: (params) =>
    request('/api/metrics/current', { method: 'POST', body: JSON.stringify(params) }),
}
```

- [ ] **Step 2: Create src/stores/servers.js**

```javascript
import { defineStore } from 'pinia'
import api from '../api'

export const useServersStore = defineStore('servers', {
  state: () => ({
    list: [],
    loading: false,
    error: null,
    refreshTimer: null,
  }),
  getters: {
    onlineCount: (state) => state.list.filter((s) => s.status === 'online').length,
    offlineCount: (state) => state.list.filter((s) => s.status !== 'online').length,
    serverNames: (state) => state.list.map((s) => s.name),
  },
  actions: {
    async fetchServers() {
      this.loading = true
      this.error = null
      try {
        this.list = await api.getServers()
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
    startAutoRefresh(interval = 10000) {
      this.stopAutoRefresh()
      this.refreshTimer = setInterval(() => this.fetchServers(), interval)
    },
    stopAutoRefresh() {
      if (this.refreshTimer) {
        clearInterval(this.refreshTimer)
        this.refreshTimer = null
      }
    },
  },
})
```

- [ ] **Step 3: Create src/stores/alerts.js**

```javascript
import { defineStore } from 'pinia'
import api from '../api'

export const useAlertsStore = defineStore('alerts', {
  state: () => ({
    list: [],
    loading: false,
    error: null,
  }),
  getters: {
    openCount: (state) => state.list.filter((a) => a.status === 'open').length,
  },
  actions: {
    async fetchAlerts() {
      this.loading = true
      this.error = null
      try {
        this.list = await api.getAlerts()
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
    async updateAlertStatus(id, status) {
      await api.updateAlert(id, status)
      await this.fetchAlerts()
    },
  },
})
```

- [ ] **Step 4: Create src/stores/chat.js**

```javascript
import { defineStore } from 'pinia'
import api from '../api'

export const useChatStore = defineStore('chat', {
  state: () => ({
    conversations: [],
    currentConvId: null,
    messages: [],
    loading: false,
    sending: false,
    convLoading: false,
  }),
  actions: {
    async fetchConversations() {
      this.convLoading = true
      try {
        this.conversations = await api.getConversations()
      } finally {
        this.convLoading = false
      }
    },
    async createConversation() {
      const conv = await api.createConversation()
      this.conversations.unshift(conv)
      return conv
    },
    async deleteConversation(id) {
      await api.deleteConversation(id)
      this.conversations = this.conversations.filter((c) => c.id !== id)
      if (this.currentConvId === id) {
        this.currentConvId = null
        this.messages = []
      }
    },
    async selectConversation(id) {
      this.currentConvId = id
      this.loading = true
      try {
        this.messages = await api.getMessages(id)
      } finally {
        this.loading = false
      }
    },
    async sendMessage(text) {
      if (!this.currentConvId) {
        const conv = await this.createConversation()
        this.currentConvId = conv.id
      }
      this.sending = true
      // 追加用户消息到本地
      this.messages.push({ role: 'human', content: text })
      try {
        const data = await api.sendMessage(this.currentConvId, text)
        this.messages.push({ role: 'ai', content: data.reply })
      } finally {
        this.sending = false
      }
    },
  },
})
```

- [ ] **Step 5: Verify by adding a quick test**

暂不写完整测试 — Pinia store 的验证在后续视图组件中通过实际渲染完成。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/ frontend/src/stores/
git commit -m "feat(frontend): add API layer and Pinia stores"
```

---

### Task 3: Common + Layout Components

**Files:**
- Create: `frontend/src/components/common/StatusDot.vue`
- Create: `frontend/src/components/common/Loading.vue`
- Create: `frontend/src/components/common/EmptyState.vue`
- Create: `frontend/src/components/common/Modal.vue`
- Create: `frontend/src/components/common/ServerCard.vue`
- Create: `frontend/src/components/layout/Sidebar.vue` (replace placeholder)
- Create: `frontend/src/components/layout/ThemeToggle.vue`

**Interfaces:**
- Produces: Reusable components used by all view pages

- [ ] **Step 1: Create StatusDot.vue**

```vue
<template>
  <span class="status-dot" :class="status" :title="status === 'online' ? '在线' : '失联'"></span>
</template>

<script setup>
defineProps({ status: { type: String, default: 'offline' } })
</script>

<style scoped>
.status-dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
.status-dot.online {
  background: #10b981;
  box-shadow: 0 0 8px rgba(16,185,129,0.6);
  animation: pulse 2s infinite;
}
.status-dot.offline {
  background: #ef4444;
  box-shadow: 0 0 8px rgba(239,68,68,0.4);
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>
```

- [ ] **Step 2: Create Loading.vue**

```vue
<template>
  <div v-if="loading" class="loading-wrapper">
    <div v-if="type === 'skeleton'" class="skeleton-list">
      <div v-for="i in count" :key="i" class="skeleton-item" :style="{ height: height + 'px' }"></div>
    </div>
    <div v-else-if="type === 'spinner'" class="spinner"></div>
    <div v-else-if="type === 'bar'" class="loading-bar"><div class="bar-inner"></div></div>
  </div>
</template>

<script setup>
defineProps({
  loading: { type: Boolean, default: true },
  type: { type: String, default: 'skeleton' },
  count: { type: Number, default: 3 },
  height: { type: Number, default: 60 },
})
</script>

<style scoped>
.skeleton-list { display: flex; flex-direction: column; gap: 12px; width: 100%; }
.skeleton-item {
  background: linear-gradient(90deg, var(--card-border) 25%, var(--card-bg) 50%, var(--card-border) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 8px;
}
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
.loading-bar { width: 100%; height: 3px; background: var(--card-border); border-radius: 2px; overflow: hidden; }
.bar-inner { width: 30%; height: 100%; background: var(--accent); border-radius: 2px; animation: bar 1.5s infinite; }
@keyframes bar { 0% { transform: translateX(-100%); } 100% { transform: translateX(400%); } }
.spinner { width: 24px; height: 24px; border: 3px solid var(--card-border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
```

- [ ] **Step 3: Create EmptyState.vue**

```vue
<template>
  <div class="empty-state">
    <p>{{ message }}</p>
    <button v-if="actionText" class="add-btn" @click="$emit('action')">{{ actionText }}</button>
  </div>
</template>

<script setup>
defineProps({ message: { type: String, required: true }, actionText: { type: String, default: '' } })
defineEmits(['action'])
</script>

<style scoped>
.empty-state { width: 100%; text-align: center; padding: 60px 20px; color: var(--text-muted); }
.empty-state p { font-size: 15px; margin-bottom: 16px; }
.add-btn {
  padding: 8px 18px; background: var(--accent); color: #fff;
  border: none; border-radius: 8px; cursor: pointer;
  font-size: 14px; font-weight: 600; transition: background 0.2s;
}
.add-btn:hover { background: var(--accent-dim); }
</style>
```

- [ ] **Step 4: Create Modal.vue**

```vue
<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
      <div class="modal-box">
        <h3>{{ title }}</h3>
        <slot />
        <div class="modal-actions">
          <button class="btn-cancel" @click="$emit('close')">取消</button>
          <button class="btn-confirm" @click="$emit('confirm')">确认</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
defineProps({ visible: { type: Boolean, default: false }, title: { type: String, default: '' } })
defineEmits(['close', 'confirm'])
</script>

<style scoped>
.modal-overlay { position: fixed; inset: 0; z-index: 1000; background: rgba(0,0,0,0.4); display: flex; justify-content: center; align-items: center; }
.modal-box { background: var(--card-bg); border-radius: 16px; padding: 32px; width: 400px; max-width: 90vw; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
.modal-box h3 { font-size: 18px; margin-bottom: 20px; }
.modal-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 24px; }
.modal-actions button { padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; transition: all 0.2s; }
.btn-cancel { background: var(--bg); color: var(--text-muted); border: 1px solid var(--card-border); }
.btn-confirm { background: var(--accent); color: #fff; border: none; }
.btn-confirm:hover { background: var(--accent-dim); }
</style>
```

- [ ] **Step 5: Create ServerCard.vue**

```vue
<template>
  <div class="server-card" :class="{ warning: isAbnormal }" @click="$emit('click')">
    <h3>{{ server.name }}</h3>
    <p><StatusDot :status="server.status" />{{ server.status === 'online' ? '在线' : '失联' }}</p>
    <div class="gauges">
      <MetricGauge :value="server.cpu" label="CPU" :color="gaugeColor(server.cpu)" />
      <MetricGauge :value="server.memory" label="内存" :color="gaugeColor(server.memory)" />
    </div>
  </div>
</template>

<script setup>
import StatusDot from './StatusDot.vue'
import MetricGauge from '../charts/MetricGauge.vue'

const props = defineProps({ server: { type: Object, required: true } })
defineEmits(['click'])

const isAbnormal = computed(() =>
  props.server.status !== 'online' || (props.server.cpu != null && props.server.cpu > 90)
)

function gaugeColor(value) {
  if (value == null) return '#94a3b8'
  if (value > 80) return '#ef4444'
  if (value > 60) return '#f59e0b'
  return '#10b981'
}
</script>

<style scoped>
.server-card {
  background: var(--card-bg); border: 1px solid var(--card-border);
  border-radius: 12px; padding: 24px; box-shadow: var(--shadow);
  width: 240px; height: 250px; display: flex; flex-direction: column;
  justify-content: center; align-items: center; text-align: center;
  cursor: pointer; transition: all 0.25s; position: relative;
}
.server-card:hover {
  transform: translateY(-3px); border-color: var(--accent);
  box-shadow: 0 8px 24px rgba(6,182,212,0.12);
}
.server-card.warning { border-color: #ef4444 !important; box-shadow: 0 0 0 1px #ef4444, var(--shadow); }
.server-card h3 { margin-bottom: 12px; font-size: 17px; }
.server-card p { margin: 4px 0; color: var(--text-muted); font-size: 13px; }
.gauges { display: flex; gap: 16px; margin-top: 12px; }
</style>
```

- [ ] **Step 6: Replace Sidebar.vue** with the full version including grouped nav + theme toggle

```vue
<template>
  <aside class="sidebar">
    <div class="sidebar-brand">
      <div class="sidebar-logo"><span>Smart</span>Ops</div>
      <span class="sidebar-subtitle">智能运维平台</span>
    </div>
    <nav class="sidebar-nav">
      <div class="sidebar-label">监控</div>
      <router-link to="/overview" active-class="active">📡 总览</router-link>
      <router-link to="/alerts" active-class="active">🔔 告警</router-link>
      <router-link to="/servers" active-class="active">🖥 服务器</router-link>
      <router-link to="/trend" active-class="active">📈 趋势</router-link>
      <div class="sidebar-label">分析</div>
      <router-link to="/logs" active-class="active">📋 日志查看</router-link>
      <router-link to="/chat" active-class="active">🤖 AI 对话</router-link>
    </nav>
    <div class="sidebar-footer">
      <ThemeToggle />
    </div>
  </aside>
</template>

<script setup>
import ThemeToggle from './ThemeToggle.vue'
</script>

<style scoped>
.sidebar {
  width: 240px; background: #0b1120; color: #e2e8f0;
  display: flex; flex-direction: column; min-height: 100vh;
}
.sidebar-brand { padding: 28px 20px 20px; border-bottom: 1px solid #1a2332; }
.sidebar-logo { font-size: 22px; font-weight: 700; letter-spacing: 2px; }
.sidebar-logo span { color: #0ec8e6; }
.sidebar-subtitle { display: block; font-size: 11px; color: #475569; margin-top: 6px; letter-spacing: 1px; }
.sidebar-nav { flex: 1; padding: 12px 0; }
.sidebar-label { padding: 16px 20px 6px; font-size: 11px; font-weight: 600; color: #475569; letter-spacing: 1px; }
.sidebar-nav a {
  display: block; padding: 10px 20px; margin: 2px 8px;
  border-radius: 8px; cursor: pointer; font-size: 14px;
  color: #94a3b8; text-decoration: none; transition: all 0.2s;
}
.sidebar-nav a:hover { background: #151f31; color: #e2e8f0; }
.sidebar-nav a.active {
  background: rgba(14,200,230,0.08); color: #0ec8e6; font-weight: 600;
  position: relative;
}
.sidebar-nav a.active::before {
  content: ''; position: absolute; left: -8px; top: 50%;
  transform: translateY(-50%); width: 3px; height: 20px;
  background: #0ec8e6; border-radius: 0 3px 3px 0;
}
.sidebar-footer { padding: 16px 20px; border-top: 1px solid #1a2332; }
</style>
```

- [ ] **Step 7: Create ThemeToggle.vue**

```vue
<template>
  <button class="theme-btn" @click="toggleTheme">{{ isDark ? '☀️' : '🌙' }}</button>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const isDark = ref(false)

onMounted(() => {
  isDark.value = document.documentElement.dataset.theme === 'dark'
})

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.dataset.theme = isDark.value ? 'dark' : ''
}
</script>

<style scoped>
.theme-btn {
  width: 100%; padding: 10px; background: #151f31;
  color: #94a3b8; border: none; border-radius: 8px;
  cursor: pointer; font-size: 16px; transition: all 0.2s; text-align: center;
}
.theme-btn:hover { background: #1e293b; color: #e2e8f0; }
</style>
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/
git commit -m "feat(frontend): add common and layout components"
```

---

### Task 4: Chart Components

**Files:**
- Create: `frontend/src/components/charts/TrendChart.vue`
- Create: `frontend/src/components/charts/MetricGauge.vue`

- [ ] **Step 1: Create MetricGauge.vue**

```vue
<template>
  <div class="gauge-wrapper" :title="`${label}: ${displayValue}`">
    <canvas ref="canvas" width="70" height="70"></canvas>
    <div class="gauge-label">{{ label }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { Chart, DoughnutController, ArcElement, Tooltip } from 'chart.js'

Chart.register(DoughnutController, ArcElement, Tooltip)

const props = defineProps({
  value: { type: Number, default: null },
  label: { type: String, default: '' },
  color: { type: String, default: '#94a3b8' },
})

const canvas = ref(null)
const displayValue = ref('-')
let chartInstance = null

function createChart() {
  if (!canvas.value) return
  const val = props.value ?? 0
  displayValue.value = props.value != null ? Math.round(props.value) + '%' : '-'
  const remaining = Math.max(0, 100 - val)

  if (chartInstance) chartInstance.destroy()
  chartInstance = new Chart(canvas.value, {
    type: 'doughnut',
    data: {
      datasets: [{
        data: [val, remaining],
        backgroundColor: [props.color, 'rgba(0,0,0,0.08)'],
        borderWidth: 0,
        cutout: '70%',
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        tooltip: { enabled: props.value != null },
      },
    },
  })
}

onMounted(createChart)
watch(() => props.value, createChart)
</script>

<style scoped>
.gauge-wrapper { display: flex; flex-direction: column; align-items: center; }
.gauge-label { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
</style>
```

- [ ] **Step 2: Create TrendChart.vue**

```vue
<template>
  <div class="chart-wrapper">
    <canvas ref="canvas"></canvas>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onUnmounted } from 'vue'
import { Chart, LineController, LineElement, PointElement, LinearScale, TimeScale, CategoryScale, Filler, Tooltip, Legend } from 'chart.js'

Chart.register(LineController, LineElement, PointElement, LinearScale, TimeScale, CategoryScale, Filler, Tooltip, Legend)

const props = defineProps({
  labels: { type: Array, default: () => [] },
  datasets: { type: Array, default: () => [] },
})

const canvas = ref(null)
let chartInstance = null

const COLORS = ['#0ec8e6', '#f59e0b', '#10b981', '#ef4444']

function buildChart() {
  if (!canvas.value) return
  if (chartInstance) chartInstance.destroy()

  const ds = props.datasets.map((d, i) => ({
    label: d.label,
    data: d.data,
    borderColor: d.color || COLORS[i % COLORS.length],
    backgroundColor: (d.color || COLORS[i % COLORS.length]) + '1a',
    fill: true,
    tension: 0.3,
    pointRadius: 2,
    pointHoverRadius: 5,
  }))

  chartInstance = new Chart(canvas.value, {
    type: 'line',
    data: { labels: props.labels, datasets: ds },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: { legend: { position: 'top' } },
      scales: {
        y: { beginAtZero: true, max: 100 },
        x: { ticks: { maxTicksLimit: 10 } },
      },
    },
  })
}

onMounted(buildChart)
watch(() => [props.labels, props.datasets], buildChart, { deep: true })
onUnmounted(() => { if (chartInstance) chartInstance.destroy() })
</script>

<style scoped>
.chart-wrapper { width: 100%; height: 300px; }
</style>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/charts/
git commit -m "feat(frontend): add chart components (TrendChart, MetricGauge)"
```

---

### Task 5: Overview + Servers Pages

**Files:**
- Create: `frontend/src/views/Overview.vue`
- Create: `frontend/src/views/Servers.vue`

- [ ] **Step 1: Create Overview.vue**

```vue
<template>
  <div>
    <h1>总览</h1>
    <div v-if="store.loading && store.list.length === 0">
      <Loading type="skeleton" :count="3" />
    </div>
    <template v-else>
      <div class="summary">
        <div class="stat">🟢 在线: {{ store.onlineCount }}</div>
        <div class="stat">🔴 失联: {{ store.offlineCount }}</div>
        <div class="stat">📊 总数: {{ store.list.length }}</div>
      </div>
      <div v-if="store.error" class="error-banner">{{ store.error }} <button @click="store.fetchServers()">重试</button></div>
      <div v-if="store.list.length === 0">
        <EmptyState message="还没有服务器，添加一台开始监控" actionText="+ 添加服务器" @action="showAddServer = true" />
      </div>
      <div v-else class="card-grid">
        <ServerCard v-for="s in sortedServers" :key="s.name" :server="s" @click="goTrend(s.name)" />
      </div>
    </template>

    <!-- 添加服务器弹窗 -->
    <Modal :visible="showAddServer" title="添加服务器" @close="showAddServer = false" @confirm="addServer">
      <label>服务器名称</label>
      <input v-model="form.name" placeholder="例: web-01" class="modal-input" />
      <label>IP 地址</label>
      <input v-model="form.ip" placeholder="例: 192.168.1.100" class="modal-input" />
      <label>SSH 用户名</label>
      <input v-model="form.user" placeholder="root" class="modal-input" />
      <label>SSH 密码</label>
      <input v-model="form.password" type="password" class="modal-input" />
    </Modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useServersStore } from '../stores/servers'
import api from '../api'
import ServerCard from '../components/common/ServerCard.vue'
import Loading from '../components/common/Loading.vue'
import EmptyState from '../components/common/EmptyState.vue'
import Modal from '../components/common/Modal.vue'

const store = useServersStore()
const router = useRouter()
const showAddServer = ref(false)
const form = ref({ name: '', ip: '', user: '', password: '' })

const sortedServers = computed(() =>
  [...store.list].sort((a, b) => (a.status === 'online' ? -1 : 1))
)

function goTrend(name) { router.push(`/trend/${name}`) }

async function addServer() {
  const f = form.value
  if (!f.name || !f.ip || !f.user || !f.password) return alert('请填写所有字段')
  try {
    await api.addServer(f)
    showAddServer.value = false
    form.value = { name: '', ip: '', user: '', password: '' }
    await store.fetchServers()
  } catch (e) { alert(e.message) }
}

onMounted(() => { store.fetchServers(); store.startAutoRefresh() })
onUnmounted(() => store.stopAutoRefresh())
</script>

<style scoped>
h1 { font-size: 24px; font-weight: 600; margin-bottom: 24px; }
.summary { display: flex; gap: 16px; margin-bottom: 24px; }
.stat {
  background: var(--card-bg); border: 1px solid var(--card-border);
  border-radius: 12px; padding: 20px 28px; box-shadow: var(--shadow);
  font-size: 15px; font-weight: 600; flex: 1;
}
.card-grid { display: flex; flex-wrap: wrap; gap: 16px; }
.error-banner {
  width: 100%; padding: 12px 16px; border-radius: 10px;
  font-size: 14px; font-weight: 600; margin-bottom: 16px;
  background: rgba(239,68,68,0.1); color: #ef4444; border: 1px solid rgba(239,68,68,0.2);
  display: flex; justify-content: space-between; align-items: center;
}
.modal-input {
  width: 100%; padding: 10px 12px; border: 1px solid var(--card-border);
  border-radius: 8px; font-size: 14px; background: var(--bg); color: var(--text);
  outline: none; box-sizing: border-box; margin-bottom: 8px;
}
label { display: block; font-size: 13px; font-weight: 600; color: var(--text-muted); margin: 12px 0 4px; }
label:first-of-type { margin-top: 0; }
</style>
```

- [ ] **Step 2: Create Servers.vue**

```vue
<template>
  <div>
    <h1>服务器列表</h1>
    <Loading v-if="store.loading && store.list.length === 0" type="skeleton" :count="5" :height="40" />
    <div v-else-if="store.error" class="error-banner">{{ store.error }} <button @click="store.fetchServers()">重试</button></div>
    <div v-else-if="store.list.length === 0">
      <EmptyState message="还没有服务器" actionText="+ 添加服务器" @action="showAddServer = true" />
    </div>
    <div v-else style="width:100%;">
      <div class="table-header">
        <span class="table-title">共 {{ store.list.length }} 台服务器</span>
        <button class="add-btn" @click="showAddServer = true">+ 添加服务器</button>
      </div>
      <div class="table-wrapper">
        <table class="server-table">
          <thead>
            <tr>
              <th>名称</th><th>IP</th><th>系统</th><th>状态</th>
              <th>CPU</th><th>内存</th><th>磁盘</th><th>心跳</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in store.list" :key="s.name">
              <td><strong>{{ s.name }}</strong></td>
              <td>{{ s.ip || '-' }}</td>
              <td>{{ s.os || '-' }}</td>
              <td><StatusDot :status="s.status" />{{ s.status === 'online' ? '在线' : '失联' }}</td>
              <td>{{ s.cpu ?? '-' }}%</td>
              <td>{{ s.memory ?? '-' }}%</td>
              <td>{{ s.disk ?? '-' }}%</td>
              <td>{{ s.last_heartbeat ? s.last_heartbeat.slice(5, 16) : '-' }}</td>
              <td><button class="del-btn" @click="deleteServer(s.name)">✕</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <Modal :visible="showAddServer" title="添加服务器" @close="showAddServer = false" @confirm="addServer">
      <label>服务器名称</label>
      <input v-model="form.name" class="modal-input" />
      <label>IP 地址</label>
      <input v-model="form.ip" class="modal-input" />
      <label>SSH 用户名</label>
      <input v-model="form.user" class="modal-input" />
      <label>SSH 密码</label>
      <input v-model="form.password" type="password" class="modal-input" />
    </Modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useServersStore } from '../stores/servers'
import api from '../api'
import StatusDot from '../components/common/StatusDot.vue'
import Loading from '../components/common/Loading.vue'
import EmptyState from '../components/common/EmptyState.vue'
import Modal from '../components/common/Modal.vue'

const store = useServersStore()
const showAddServer = ref(false)
const form = ref({ name: '', ip: '', user: '', password: '' })

async function addServer() {
  if (!form.value.name || !form.value.ip || !form.value.user || !form.value.password) return alert('请填写所有字段')
  try {
    await api.addServer(form.value)
    showAddServer.value = false
    form.value = { name: '', ip: '', user: '', password: '' }
    await store.fetchServers()
  } catch (e) { alert(e.message) }
}

async function deleteServer(name) {
  if (!confirm(`确定删除服务器 ${name}？所有相关数据将被清除。`)) return
  try {
    await api.deleteServer(name)
    await store.fetchServers()
  } catch (e) { alert(e.message) }
}

onMounted(() => store.fetchServers())
</script>

<style scoped>
h1 { font-size: 24px; font-weight: 600; margin-bottom: 24px; }
.table-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.table-title { font-size: 14px; color: var(--text-muted); }
.add-btn { padding: 8px 18px; background: var(--accent); color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; }
.add-btn:hover { background: var(--accent-dim); }
.table-wrapper { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; overflow: hidden; box-shadow: var(--shadow); }
.server-table { width: 100%; border-collapse: collapse; }
.server-table th { padding: 12px 16px; text-align: left; font-size: 12px; font-weight: 600; color: var(--text-muted); background: var(--bg); border-bottom: 1px solid var(--card-border); }
.server-table td { padding: 12px 16px; font-size: 13px; border-bottom: 1px solid var(--card-border); }
.server-table tr:last-child td { border-bottom: none; }
.del-btn { background: none; border: none; cursor: pointer; font-size: 14px; color: var(--text-muted); padding: 4px 8px; border-radius: 4px; }
.del-btn:hover { background: rgba(239,68,68,0.15); color: #ef4444; }
.error-banner {
  padding: 12px 16px; border-radius: 10px; font-size: 14px; font-weight: 600; margin-bottom: 16px;
  background: rgba(239,68,68,0.1); color: #ef4444; border: 1px solid rgba(239,68,68,0.2);
  display: flex; justify-content: space-between; align-items: center;
}
</style>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/Overview.vue frontend/src/views/Servers.vue
git commit -m "feat(frontend): migrate Overview and Servers pages"
```

---

### Task 6: Alerts Page

**Files:**
- Create: `frontend/src/components/alerts/AlertItem.vue`
- Create: `frontend/src/views/Alerts.vue`

- [ ] **Step 1: Create AlertItem.vue**

```vue
<template>
  <div class="alert-item">
    <div class="alert-info">
      <div class="alert-title">
        <span class="alert-badge" :class="'type-' + alert.type">{{ typeText }}</span>
        {{ alert.message }}
        <span v-if="alert.resolved_by_auto" class="auto-badge">🔄 自动</span>
      </div>
      <div class="alert-meta">
        <span>{{ alert.server_name }}</span>
        <span class="alert-status" :class="alert.status">{{ statusText }}</span>
        <span>{{ alert.created_at || '' }}</span>
      </div>
    </div>
    <div v-if="alert.status === 'open' || alert.status === 'acknowledged'" class="alert-actions">
      <button v-if="alert.status === 'open'" @click="$emit('update', 'acknowledged')">确认</button>
      <button @click="$emit('update', 'resolved')">解决</button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  alert: { type: Object, required: true },
})
defineEmits(['update'])

const typeText = computed(() => ({ offline: '离线', cpu: 'CPU', memory: '内存', disk: '磁盘' }[$props.alert.type] || $props.alert.type))
const statusText = computed(() => ({ open: '未处理', acknowledged: '已确认', resolved: '已解决' }[$props.alert.status] || $props.alert.status))
</script>

<style scoped>
.alert-item { padding: 14px 16px; border-bottom: 1px solid var(--card-border); display: flex; justify-content: space-between; align-items: center; }
.alert-item:last-child { border-bottom: none; }
.alert-info { flex: 1; }
.alert-title { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.alert-meta { font-size: 12px; color: var(--text-muted); display: flex; gap: 10px; }
.alert-badge { padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: 600; }
.alert-badge.type-offline { background: rgba(239,68,68,0.15); color: #ef4444; }
.alert-badge.type-cpu { background: rgba(245,158,11,0.15); color: #f59e0b; }
.alert-badge.type-memory { background: rgba(245,158,11,0.15); color: #f59e0b; }
.alert-badge.type-disk { background: rgba(239,68,68,0.15); color: #ef4444; }
.auto-badge { margin-left: 6px; font-size: 11px; color: #10b981; }
.alert-status { padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: 600; }
.alert-status.open { background: rgba(239,68,68,0.15); color: #ef4444; }
.alert-status.acknowledged { background: rgba(245,158,11,0.15); color: #f59e0b; }
.alert-status.resolved { background: rgba(16,185,129,0.15); color: #10b981; }
.alert-actions { display: flex; gap: 6px; }
.alert-actions button { padding: 5px 12px; border: 1px solid var(--card-border); border-radius: 6px; cursor: pointer; font-size: 12px; background: var(--bg); color: var(--text-muted); transition: all 0.2s; }
.alert-actions button:hover { border-color: var(--accent); color: var(--accent); }
</style>
```

- [ ] **Step 2: Create Alerts.vue**

```vue
<template>
  <div>
    <h1>告警</h1>
    <Loading v-if="store.loading && store.list.length === 0" type="skeleton" :count="5" />
    <template v-else>
      <div v-if="store.error" class="error-banner">{{ store.error }} <button @click="store.fetchAlerts()">重试</button></div>
      <div v-if="store.openCount > 0" class="alert-banner">🔴 {{ store.openCount }} 条未处理告警</div>
      <div v-if="store.list.length === 0">
        <EmptyState message="暂无告警" />
      </div>
      <div v-else class="alert-list">
        <AlertItem
          v-for="a in store.list"
          :key="a.id"
          :alert="a"
          @update="(status) => store.updateAlertStatus(a.id, status)"
        />
      </div>
    </template>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useAlertsStore } from '../stores/alerts'
import AlertItem from '../components/alerts/AlertItem.vue'
import Loading from '../components/common/Loading.vue'
import EmptyState from '../components/common/EmptyState.vue'

const store = useAlertsStore()
onMounted(() => store.fetchAlerts())
</script>

<style scoped>
h1 { font-size: 24px; font-weight: 600; margin-bottom: 24px; }
.alert-banner { width: 100%; padding: 12px 16px; border-radius: 10px; font-size: 14px; font-weight: 600; margin-bottom: 16px; background: rgba(239,68,68,0.1); color: #ef4444; border: 1px solid rgba(239,68,68,0.2); }
.alert-list { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; overflow: hidden; box-shadow: var(--shadow); }
.error-banner { padding: 12px 16px; border-radius: 10px; font-size: 14px; font-weight: 600; margin-bottom: 16px; background: rgba(239,68,68,0.1); color: #ef4444; border: 1px solid rgba(239,68,68,0.2); display: flex; justify-content: space-between; align-items: center; }
</style>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/Alerts.vue frontend/src/components/alerts/
git commit -m "feat(frontend): migrate Alerts page with auto-resolve indicator"
```

---

### Task 7: Trend Page

**Files:**
- Create: `frontend/src/views/Trend.vue`

- [ ] **Step 1: Create Trend.vue**

```vue
<template>
  <div>
    <h1>趋势分析</h1>
    <div v-if="serversStore.list.length === 0">
      <EmptyState message="暂无服务器数据" />
      <div v-if="store.loading">
        <Loading type="skeleton" :count="1" :height="300" />
      </div>
    </div>
    <template v-else>
      <div class="controls">
        <span class="label">服务器：</span>
        <select v-model="selectedServer" class="server-select" @change="loadData">
          <option v-for="s in serversStore.list" :key="s.name" :value="s.name">{{ s.name }}</option>
        </select>
        <span class="label" style="margin-left: 16px;">指标：</span>
        <button
          v-for="m in METRICS"
          :key="m.key"
          class="metric-btn"
          :class="{ active: selectedMetrics.includes(m.key) }"
          @click="toggleMetric(m.key)"
        >{{ m.label }}</button>
        <span class="label" style="margin-left: 16px;">时间：</span>
        <button
          v-for="d in DURATIONS"
          :key="d.value"
          class="duration-btn"
          :class="{ active: selectedDuration === d.value }"
          @click="selectedDuration = d.value; loadData()"
        >{{ d.label }}</button>
      </div>

      <div v-if="loading" class="chart-area" style="display:flex;align-items:center;justify-content:center;height:300px;">
        <Loading type="spinner" :loading="true" />
      </div>
      <div v-else-if="error" class="error-banner">{{ error }}</div>
      <div v-else-if="chartData.labels.length === 0" class="chart-area" style="display:flex;align-items:center;justify-content:center;height:300px;">
        <span style="color:var(--text-muted)">暂无数据，采集器启动后自动生成</span>
      </div>
      <div v-else class="chart-area">
        <TrendChart :labels="chartData.labels" :datasets="chartData.datasets" />
      </div>

      <div v-if="currentValues.length" class="current-values">
        <span v-for="v in currentValues" :key="v.label" class="value-item" :style="{ color: v.color }">
          {{ v.label }}: {{ v.value }}
        </span>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useServersStore } from '../stores/servers'
import api from '../api'
import TrendChart from '../components/charts/TrendChart.vue'
import Loading from '../components/common/Loading.vue'
import EmptyState from '../components/common/EmptyState.vue'

const METRICS = [
  { key: 'cpu', label: 'CPU', color: '#0ec8e6' },
  { key: 'memory', label: '内存', color: '#f59e0b' },
  { key: 'disk', label: '磁盘', color: '#10b981' },
]
const DURATIONS = [
  { value: '1h', label: '1 小时' },
  { value: '6h', label: '6 小时' },
  { value: '24h', label: '24 小时' },
]

const route = useRoute()
const serversStore = useServersStore()
const selectedServer = ref('')
const selectedMetrics = ref(['cpu', 'memory'])
const selectedDuration = ref('1h')
const chartData = ref({ labels: [], datasets: [] })
const currentValues = ref([])
const loading = ref(false)
const error = ref('')

function toggleMetric(key) {
  const idx = selectedMetrics.value.indexOf(key)
  if (idx >= 0) selectedMetrics.value.splice(idx, 1)
  else selectedMetrics.value.push(key)
  loadData()
}

async function loadData() {
  if (!selectedServer.value) return
  loading.value = true
  error.value = ''
  try {
    const data = await api.getServerHistory(selectedServer.value)
    if (!data.length) {
      chartData.value = { labels: [], datasets: [] }
      currentValues.value = []
      return
    }
    const labels = data.map(d => d.time)
    const datasets = []
    const vals = []
    if (selectedMetrics.value.includes('cpu')) {
      datasets.push({ label: 'CPU %', data: data.map(d => d.cpu), color: '#0ec8e6' })
      const last = data[data.length - 1]
      vals.push({ label: 'CPU', value: last.cpu != null ? last.cpu + '%' : '-', color: '#0ec8e6' })
    }
    if (selectedMetrics.value.includes('memory')) {
      datasets.push({ label: '内存 %', data: data.map(d => d.memory), color: '#f59e0b' })
      const last = data[data.length - 1]
      vals.push({ label: '内存', value: last.memory != null ? last.memory + '%' : '-', color: '#f59e0b' })
    }
    if (selectedMetrics.value.includes('disk')) {
      datasets.push({ label: '磁盘 %', data: data.map(d => d.disk), color: '#10b981' })
      const last = data[data.length - 1]
      vals.push({ label: '磁盘', value: last.disk != null ? last.disk + '%' : '-', color: '#10b981' })
    }
    chartData.value = { labels, datasets }
    currentValues.value = vals
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await serversStore.fetchServers()
  if (route.params.serverName) {
    selectedServer.value = route.params.serverName
  } else if (serversStore.list.length > 0) {
    selectedServer.value = serversStore.list[0].name
  }
  if (selectedServer.value) loadData()
})

watch(() => route.params.serverName, (name) => {
  if (name && name !== selectedServer.value) {
    selectedServer.value = name
    loadData()
  }
})
</script>

<style scoped>
h1 { font-size: 24px; font-weight: 600; margin-bottom: 24px; }
.controls { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.label { font-size: 14px; color: var(--text-muted); }
.server-select { padding: 8px 12px; border: 1px solid var(--card-border); border-radius: 8px; font-size: 14px; background: var(--card-bg); color: var(--text); outline: none; }
.metric-btn, .duration-btn { padding: 6px 14px; border: 1px solid var(--card-border); border-radius: 6px; cursor: pointer; font-size: 13px; background: var(--card-bg); color: var(--text); transition: all 0.2s; }
.metric-btn:hover, .duration-btn:hover { border-color: var(--accent); }
.metric-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.duration-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.chart-area { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 16px; box-shadow: var(--shadow); margin-top: 16px; }
.current-values { display: flex; gap: 24px; margin-top: 16px; padding: 16px; background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; }
.value-item { font-size: 14px; font-weight: 600; }
.error-banner { margin-top: 16px; padding: 12px; border-radius: 10px; background: rgba(239,68,68,0.1); color: #ef4444; border: 1px solid rgba(239,68,68,0.2); }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/Trend.vue
git commit -m "feat(frontend): migrate Trend page with multi-metric selection"
```

---

### Task 8: Chat Page + RCA Components

**Files:**
- Create: `frontend/src/utils/markdown.js`
- Create: `frontend/src/utils/rca-parser.js`
- Create: `frontend/src/components/chat/ConversationList.vue`
- Create: `frontend/src/components/chat/ChatInput.vue`
- Create: `frontend/src/components/chat/MessageBubble.vue`
- Create: `frontend/src/components/chat/RcaReport.vue`
- Create: `frontend/src/views/Chat.vue`

- [ ] **Step 1: Create src/utils/markdown.js**

```javascript
export function escapeHtml(text) {
  const d = document.createElement('div')
  d.textContent = text
  return d.innerHTML
}

export function renderMarkdown(text) {
  let h = escapeHtml(text)
  h = h.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>')
  h = h.replace(/### (.+)/g, '<h3>$1</h3>')
  h = h.replace(/## (.+)/g, '<h2>$1</h2>')
  h = h.replace(/# (.+)/g, '<h1>$1</h1>')
  h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  h = h.replace(/\n\n/g, '</p><p>')
  h = h.replace(/\n/g, '<br>')
  if (!h.startsWith('<')) h = '<p>' + h + '</p>'
  return h
}
```

- [ ] **Step 2: Create src/utils/rca-parser.js**

```javascript
export function extractRcaReport(text) {
  // Try to match a JSON block within ```json ... ``` markers
  const jsonBlock = text.match(/```json\s*(\{[\s\S]*?"root_cause"[\s\S]*?\})\s*```/)
  if (jsonBlock) {
    try {
      const obj = JSON.parse(jsonBlock[1])
      if (obj.root_cause && obj.recommendation) return obj
    } catch { /* not valid JSON */ }
  }
  // Also try standalone JSON (no code block)
  try {
    const obj = JSON.parse(text)
    if (obj.root_cause && obj.recommendation) return obj
  } catch { /* not valid JSON */ }
  return null
}
```

- [ ] **Step 3: Create ConversationList.vue**

```vue
<template>
  <div>
    <div class="chat-sidebar-header">
      <button @click="$emit('new')">+ 新建对话</button>
    </div>
    <div class="chat-conv-list">
      <Loading v-if="loading" type="skeleton" :count="4" :height="40" />
      <div v-else-if="conversations.length === 0" class="chat-empty">暂无对话，新建一个开始吧</div>
      <div
        v-for="c in conversations"
        :key="c.id"
        class="conv-item"
        :class="{ active: c.id === activeId }"
        @click="$emit('select', c.id)"
      >
        <span class="conv-title">{{ c.summary }}</span>
        <button class="conv-del" @click.stop="$emit('delete', c.id)">✕</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import Loading from '../common/Loading.vue'
defineProps({
  conversations: { type: Array, default: () => [] },
  activeId: { type: Number, default: null },
  loading: { type: Boolean, default: false },
})
defineEmits(['new', 'select', 'delete'])
</script>

<style scoped>
.chat-sidebar-header { padding: 16px; border-bottom: 1px solid var(--card-border); }
.chat-sidebar-header button { width: 100%; padding: 10px; background: var(--accent); color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; }
.chat-sidebar-header button:hover { background: var(--accent-dim); }
.chat-conv-list { flex: 1; overflow-y: auto; padding: 8px; }
.chat-empty { text-align: center; color: var(--text-muted); padding: 40px 20px; font-size: 14px; }
.conv-item { padding: 12px; border-radius: 8px; cursor: pointer; font-size: 13px; color: var(--text); margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center; transition: background 0.2s; }
.conv-item:hover { background: var(--card-border); }
.conv-item.active { background: var(--accent); color: #fff; }
.conv-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.conv-del { display: none; background: none; border: none; cursor: pointer; font-size: 14px; padding: 2px 6px; border-radius: 4px; color: var(--text-muted); line-height: 1; }
.conv-item:hover .conv-del { display: block; }
.conv-del:hover { background: rgba(239,68,68,0.15); color: var(--red); }
.conv-item.active .conv-del:hover { background: rgba(255,255,255,0.2); color: #fff; }
</style>
```

- [ ] **Step 4: Create ChatInput.vue**

```vue
<template>
  <div class="chat-input-area">
    <input
      ref="inputRef"
      v-model="text"
      type="text"
      placeholder="输入你的问题，回车发送"
      @keydown.enter="send"
    />
    <button :disabled="sending || !text.trim()" @click="send">{{ sending ? '发送中...' : '发送' }}</button>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'

const emit = defineEmits(['send'])
const props = defineProps({ sending: { type: Boolean, default: false } })
const text = ref('')
const inputRef = ref(null)

function send() {
  const msg = text.value.trim()
  if (!msg || props.sending) return
  text.value = ''
  emit('send', msg)
  nextTick(() => inputRef.value?.focus())
}

function focus() { nextTick(() => inputRef.value?.focus()) }

defineExpose({ focus })
</script>

<style scoped>
.chat-input-area { padding: 16px 24px; border-top: 1px solid var(--card-border); display: flex; gap: 12px; }
.chat-input-area input { flex: 1; padding: 12px 16px; border: 1px solid var(--card-border); border-radius: 8px; font-size: 14px; outline: none; background: var(--bg); color: var(--text); }
.chat-input-area input:focus { border-color: var(--accent); }
.chat-input-area button { padding: 12px 24px; background: var(--accent); color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; }
.chat-input-area button:hover { background: var(--accent-dim); }
.chat-input-area button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
```

- [ ] **Step 5: Create RcaReport.vue**

```vue
<template>
  <div class="rca-card">
    <div class="rca-header" @click="collapsed = !collapsed">
      <span>⚠️ RCA 诊断报告</span>
      <span class="rca-toggle">{{ collapsed ? '展开' : '收起' }}</span>
    </div>
    <div v-if="!collapsed" class="rca-body">
      <!-- 概要 -->
      <div class="rca-section">
        <div class="rca-section-title">📋 概要</div>
        <div class="rca-section-body">{{ report.summary }}</div>
      </div>

      <!-- 时间线 -->
      <div v-if="report.timeline?.length" class="rca-section">
        <div class="rca-section-title">🕐 时间线</div>
        <div class="rca-timeline">
          <div v-for="(t, i) in report.timeline" :key="i" class="timeline-item">
            <span class="timeline-time">{{ t.time }}</span>
            <span class="timeline-event">{{ t.event }}</span>
            <span class="timeline-source" :class="t.source">{{ t.source }}</span>
          </div>
        </div>
      </div>

      <!-- 根因 -->
      <div v-if="report.root_cause" class="rca-section">
        <div class="rca-section-title">🔍 根因</div>
        <div class="rca-section-body">{{ report.root_cause }}</div>
      </div>

      <!-- 证据 -->
      <div v-if="report.evidence" class="rca-section">
        <div class="rca-section-title">📊 证据</div>
        <div class="evidence-grid">
          <div v-if="report.evidence.log_analysis" class="evidence-item">
            <span class="evidence-label">日志分析</span>
            <span class="evidence-value">{{ report.evidence.log_analysis }}</span>
          </div>
          <div v-if="report.evidence.metric_analysis" class="evidence-item">
            <span class="evidence-label">指标分析</span>
            <span class="evidence-value">{{ report.evidence.metric_analysis }}</span>
          </div>
          <div v-if="report.evidence.knowledge_ref" class="evidence-item">
            <span class="evidence-label">知识库参考</span>
            <span class="evidence-value">{{ report.evidence.knowledge_ref }}</span>
          </div>
        </div>
      </div>

      <!-- 修复建议 -->
      <div v-if="report.recommendation?.length" class="rca-section">
        <div class="rca-section-title">🔧 修复建议</div>
        <ol class="recommendation-list">
          <li v-for="(r, i) in report.recommendation" :key="i">{{ r }}</li>
        </ol>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({ report: { type: Object, required: true } })
const collapsed = ref(false)
</script>

<style scoped>
.rca-card { border: 1px solid var(--accent); border-radius: 12px; overflow: hidden; margin-bottom: 8px; }
.rca-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: rgba(6,182,212,0.08); cursor: pointer; font-weight: 600; font-size: 14px; }
.rca-toggle { font-size: 12px; color: var(--text-muted); }
.rca-body { padding: 16px; }
.rca-section { margin-bottom: 16px; }
.rca-section:last-child { margin-bottom: 0; }
.rca-section-title { font-size: 13px; font-weight: 600; color: var(--accent); margin-bottom: 6px; }
.rca-section-body { font-size: 14px; line-height: 1.6; }
.rca-timeline { display: flex; flex-direction: column; gap: 6px; }
.timeline-item { display: flex; align-items: center; gap: 8px; font-size: 13px; padding: 4px 8px; background: var(--bg); border-radius: 6px; }
.timeline-time { color: var(--text-muted); font-family: monospace; min-width: 50px; }
.timeline-event { flex: 1; }
.timeline-source { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
.timeline-source.loki { background: rgba(6,182,212,0.1); color: #06b6d4; }
.timeline-source.prometheus { background: rgba(245,158,11,0.1); color: #f59e0b; }
.evidence-grid { display: flex; flex-direction: column; gap: 8px; }
.evidence-item { display: flex; gap: 8px; font-size: 13px; padding: 8px; background: var(--bg); border-radius: 6px; }
.evidence-label { font-weight: 600; min-width: 80px; color: var(--text-muted); }
.evidence-value { flex: 1; }
.recommendation-list { margin: 0; padding-left: 20px; }
.recommendation-list li { margin-bottom: 4px; font-size: 14px; line-height: 1.6; }
</style>
```

- [ ] **Step 6: Create MessageBubble.vue**

```vue
<template>
  <div class="message" :class="role">
    <div class="msg-bubble">
      <RcaReport v-if="rca" :report="rca" />
      <div v-else v-html="rendered"></div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { renderMarkdown } from '../utils/markdown'
import { extractRcaReport } from '../utils/rca-parser'
import RcaReport from './RcaReport.vue'

const props = defineProps({ role: { type: String, required: true }, content: { type: String, default: '' } })

const rca = computed(() => props.role === 'ai' ? extractRcaReport(props.content) : null)
const rendered = computed(() => renderMarkdown(props.content))
</script>

<style scoped>
.message { margin-bottom: 20px; max-width: 80%; }
.message.user { margin-left: auto; }
.message.ai { margin-right: auto; }
.msg-bubble { padding: 14px 18px; border-radius: 12px; font-size: 14px; line-height: 1.7; word-break: break-word; }
.message.user .msg-bubble { background: var(--accent); color: #fff; border-bottom-right-radius: 4px; }
.message.ai .msg-bubble { background: var(--bg); color: var(--text); border: 1px solid var(--card-border); border-bottom-left-radius: 4px; }
.message.ai .msg-bubble :deep(pre) { background: rgba(0,0,0,0.05); padding: 12px; border-radius: 8px; overflow-x: auto; margin: 8px 0; }
.message.ai .msg-bubble :deep(code) { background: rgba(0,0,0,0.08); padding: 2px 6px; border-radius: 4px; font-size: 13px; font-family: monospace; }
</style>
```

- [ ] **Step 7: Create Chat.vue**

```vue
<template>
  <div id="chat-page">
    <div class="chat-container">
      <div class="chat-sidebar">
        <ConversationList
          :conversations="store.conversations"
          :active-id="store.currentConvId"
          :loading="store.convLoading"
          @new="handleNew"
          @select="handleSelect"
          @delete="handleDelete"
        />
      </div>
      <div class="chat-main">
        <!-- 欢迎页 -->
        <div v-if="!store.currentConvId" class="chat-welcome">
          <h2>👋 你好，我是 SmartOps AI 助手</h2>
          <p>我可以帮你分析服务器、排查故障、查询日志</p>
          <div class="template-grid">
            <div class="template-btn" @click="quickAsk('检查所有服务器的运行状态')">📊 检查所有服务器状态</div>
            <div class="template-btn" @click="quickAsk('分析最近的错误日志')">🔍 分析最近的错误日志</div>
            <div class="template-btn" @click="quickAsk('总结一下当前的系统资源使用情况')">📈 系统资源使用情况</div>
            <div class="template-btn" @click="quickAsk('最近有没有需要关注的告警')">🚨 当前告警汇总</div>
          </div>
        </div>

        <!-- 消息区 -->
        <div v-show="store.currentConvId" ref="msgContainer" class="chat-messages">
          <Loading v-if="store.loading" type="skeleton" :count="3" :height="50" />
          <div v-else-if="store.messages.length === 0" class="chat-empty">新对话，开始提问吧</div>
          <template v-else>
            <MessageBubble v-for="m in store.messages" :key="m.id || m._key" :role="m.role" :content="m.content" />
            <!-- 打字动画 -->
            <div v-if="store.sending" class="message ai">
              <div class="msg-bubble">
                <div class="typing-dots"><span></span><span></span><span></span></div>
              </div>
            </div>
          </template>
        </div>

        <!-- 输入区 -->
        <ChatInput
          v-show="store.currentConvId"
          ref="chatInput"
          :sending="store.sending"
          @send="handleSend"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'
import { useChatStore } from '../stores/chat'
import ConversationList from '../components/chat/ConversationList.vue'
import ChatInput from '../components/chat/ChatInput.vue'
import MessageBubble from '../components/chat/MessageBubble.vue'
import Loading from '../components/common/Loading.vue'

const store = useChatStore()
const msgContainer = ref(null)
const chatInput = ref(null)

function scrollToBottom() {
  nextTick(() => {
    if (msgContainer.value) {
      msgContainer.value.scrollTop = msgContainer.value.scrollHeight
    }
  })
}

watch(() => store.messages.length, scrollToBottom)
watch(() => store.sending, scrollToBottom)

onMounted(() => store.fetchConversations())

async function handleNew() {
  const conv = await store.createConversation()
  store.currentConvId = conv.id
  nextTick(() => chatInput.value?.focus())
}

async function handleSelect(id) {
  await store.selectConversation(id)
  nextTick(() => chatInput.value?.focus())
}

async function handleDelete(id) {
  await store.deleteConversation(id)
}

async function handleSend(text) {
  await store.sendMessage(text)
  scrollToBottom()
}

async function quickAsk(text) {
  if (!store.currentConvId) {
    const conv = await store.createConversation()
    store.currentConvId = conv.id
  }
  await handleSend(text)
}
</script>

<style scoped>
#chat-page { height: calc(100vh - 120px); }
.chat-container { display: flex; height: 100%; background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; overflow: hidden; box-shadow: var(--shadow); }
.chat-sidebar { width: 260px; min-width: 260px; border-right: 1px solid var(--card-border); display: flex; flex-direction: column; background: var(--bg); }
.chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.chat-welcome { flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 40px; text-align: center; color: var(--text-muted); }
.chat-welcome h2 { font-size: 22px; margin-bottom: 8px; color: var(--text); }
.chat-welcome p { margin-bottom: 24px; font-size: 14px; }
.template-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; max-width: 480px; width: 100%; }
.template-btn { padding: 16px; border: 1px solid var(--card-border); border-radius: 12px; cursor: pointer; font-size: 14px; color: var(--text); background: var(--card-bg); transition: all 0.2s; text-align: center; }
.template-btn:hover { border-color: var(--accent); color: var(--accent); }
.chat-messages { flex: 1; overflow-y: auto; padding: 24px; }
.chat-empty { text-align: center; color: var(--text-muted); padding: 40px 20px; font-size: 14px; }
.typing-dots { display: flex; gap: 4px; align-items: center; padding: 4px 0; }
.typing-dots span { width: 8px; height: 8px; background: var(--text-muted); border-radius: 50%; animation: typing 1.4s infinite; }
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing { 0%, 60%, 100% { opacity: 0.3; transform: translateY(0); } 30% { opacity: 1; transform: translateY(-4px); } }
</style>
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/utils/ frontend/src/components/chat/ frontend/src/views/Chat.vue
git commit -m "feat(frontend): implement Chat page with RCA report rendering"
```

---

### Task 9: LogViewer Page

**Files:**
- Create: `frontend/src/views/LogViewer.vue`

- [ ] **Step 1: Create LogViewer.vue**

```vue
<template>
  <div>
    <h1>🔍 日志查询</h1>

    <!-- 过滤栏 -->
    <div class="filters">
      <span class="label">服务器：</span>
      <select v-model="serverName" class="select" @change="search">
        <option v-for="s in serversStore.list" :key="s.name" :value="s.name">{{ s.name }}</option>
      </select>

      <span class="label">时间：</span>
      <button v-for="d in DURATIONS" :key="d.value" class="btn-filter" :class="{ active: hours === d.value }" @click="hours = d.value; search()">{{ d.label }}</button>

      <span class="label">级别：</span>
      <button v-for="l in LEVELS" :key="l.value" class="btn-filter" :class="{ active: level === l.value }" @click="level = l.value; search()">{{ l.label }}</button>
    </div>

    <div class="keyword-bar">
      <input v-model="keyword" placeholder="关键词过滤..." class="keyword-input" @input="debouncedSearch" />
      <button class="search-btn" @click="search">🔍 查询</button>
    </div>

    <!-- 统计概览 -->
    <Loading v-if="loading" type="bar" :loading="true" />
    <div v-if="stats" class="stats-bar">
      <span class="stat-item" style="color:#ef4444;">🔴 {{ stats.levels?.error || 0 }}</span>
      <span class="stat-item" style="color:#f59e0b;">🟡 {{ stats.levels?.warn || 0 }}</span>
      <span class="stat-item" style="color:#10b981;">🟢 {{ stats.levels?.info || 0 }}</span>
      <span v-if="stats.error_codes && Object.keys(stats.error_codes).length" class="error-codes">
        错误码: {{ Object.entries(stats.error_codes).map(([k, v]) => `${k}=${v}`).join('  ') }}
      </span>
    </div>

    <!-- 错误/空状态 -->
    <div v-if="error" class="error-bar">
      {{ error }}
      <button class="retry-btn" @click="search">重试</button>
    </div>
    <div v-else-if="!loading && logs.length === 0" class="empty-bar">过去 {{ hours }} 小时无日志</div>

    <!-- 日志列表 -->
    <Loading v-if="loading" type="skeleton" :count="8" :height="32" />
    <div v-else-if="logs.length" ref="logContainer" class="log-list" @scroll="onScroll">
      <div v-for="(log, i) in logs" :key="i" class="log-item" :class="getLevel(log)">
        <span class="log-time">{{ log.timestamp?.slice(11, 19) || '' }}</span>
        <span class="log-level" :class="getLevel(log)">{{ getLevel(log).toUpperCase() }}</span>
        <span class="log-content">{{ log.content }}</span>
      </div>
      <div v-if="hasMore" ref="sentinel" class="load-more">加载更多...</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useServersStore } from '../stores/servers'
import api from '../api'
import Loading from '../components/common/Loading.vue'

const DURATIONS = [
  { value: 1, label: '1h' },
  { value: 6, label: '6h' },
  { value: 24, label: '24h' },
]
const LEVELS = [
  { value: '', label: '全部' },
  { value: 'error', label: 'error' },
  { value: 'warn', label: 'warn' },
  { value: 'info', label: 'info' },
]

const serversStore = useServersStore()
const serverName = ref('')
const hours = ref(1)
const level = ref('')
const keyword = ref('')
const logs = ref([])
const stats = ref(null)
const loading = ref(false)
const error = ref('')
const hasMore = ref(true)
let page = 1

function getLevel(log) {
  const c = (log.content || '').toLowerCase()
  if (c.includes('error') || c.includes('fatal')) return 'error'
  if (c.includes('warn')) return 'warn'
  return 'info'
}

async function search(reset = true) {
  if (!serverName.value) return
  if (reset) { logs.value = []; page = 1; hasMore.value = true }
  loading.value = true
  error.value = ''
  try {
    const params = { server_name: serverName.value, hours: hours.value, level: level.value }
    if (keyword.value) params.keywords = [keyword.value]
    const [logData, statsData] = await Promise.all([
      api.queryLogs(params),
      api.analyzeLogs({ server_name: serverName.value, hours: hours.value }),
    ])
    if (typeof logData === 'string') {
      if (reset) logs.value = []
    } else if (Array.isArray(logData)) {
      logs.value = reset ? logData : [...logs.value, ...logData]
      hasMore.value = logData.length >= 100
    }
    stats.value = statsData
  } catch (e) {
    error.value = e.message || 'Loki 连接失败'
  } finally {
    loading.value = false
  }
}

let debounceTimer = null
function debouncedSearch() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => search(true), 300)
}

function onScroll(e) {
  const el = e.target
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 100 && hasMore.value && !loading.value) {
    page++
    search(false)
  }
}

onMounted(async () => {
  await serversStore.fetchServers()
  if (serversStore.list.length) {
    serverName.value = serversStore.list[0].name
    search()
  }
})
</script>

<style scoped>
h1 { font-size: 24px; font-weight: 600; margin-bottom: 24px; }
.filters { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.label { font-size: 13px; color: var(--text-muted); white-space: nowrap; }
.select { padding: 6px 10px; border: 1px solid var(--card-border); border-radius: 6px; font-size: 13px; background: var(--card-bg); color: var(--text); outline: none; }
.btn-filter { padding: 4px 12px; border: 1px solid var(--card-border); border-radius: 6px; cursor: pointer; font-size: 12px; background: var(--card-bg); color: var(--text); transition: all 0.2s; }
.btn-filter:hover { border-color: var(--accent); }
.btn-filter.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.keyword-bar { display: flex; gap: 8px; margin-bottom: 12px; }
.keyword-input { flex: 1; padding: 8px 12px; border: 1px solid var(--card-border); border-radius: 6px; font-size: 13px; background: var(--card-bg); color: var(--text); outline: none; }
.keyword-input:focus { border-color: var(--accent); }
.search-btn { padding: 8px 16px; background: var(--accent); color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; }
.search-btn:hover { background: var(--accent-dim); }
.stats-bar { display: flex; align-items: center; gap: 16px; padding: 12px; background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 8px; margin-bottom: 12px; font-size: 13px; flex-wrap: wrap; }
.stat-item { font-weight: 600; }
.error-codes { font-size: 12px; color: var(--text-muted); }
.error-bar { padding: 12px; background: rgba(239,68,68,0.1); color: #ef4444; border: 1px solid rgba(239,68,68,0.2); border-radius: 8px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }
.empty-bar { padding: 40px; text-align: center; color: var(--text-muted); background: var(--card-bg); border-radius: 8px; }
.log-list { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 8px; overflow-y: auto; max-height: 600px; }
.log-item { padding: 8px 12px; border-bottom: 1px solid var(--card-border); font-size: 13px; display: flex; gap: 8px; font-family: monospace; }
.log-item:last-child { border-bottom: none; }
.log-item:hover { background: rgba(0,0,0,0.02); }
.log-time { color: var(--text-muted); min-width: 70px; }
.log-level { font-weight: 600; min-width: 50px; text-transform: uppercase; }
.log-level.error { color: #ef4444; }
.log-level.warn { color: #f59e0b; }
.log-level.info { color: #10b981; }
.log-content { flex: 1; word-break: break-all; }
.load-more { padding: 12px; text-align: center; color: var(--text-muted); }
.retry-btn { padding: 4px 12px; border: 1px solid currentColor; border-radius: 4px; background: none; cursor: pointer; font-size: 12px; color: inherit; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/LogViewer.vue
git commit -m "feat(frontend): add LogViewer page"
```

---

### Task 10: Backend — New API Endpoints + Alert State Machine

**Files:**
- Modify: `api.py` (add 6 lines for Flask static config + 3 new routes)
- Modify: `collector/scheduler.py` (add auto-resolve logic in `check_heartbeat`)

**Interfaces:**
- Produces: `POST /api/logs/query` — same parameters as `query_logs` tool
- Produces: `POST /api/logs/analyze` — delegates to `analyze_errors`
- Produces: `POST /api/metrics/current` — delegates to `query_metric`

- [ ] **Step 1: Update Flask static config in api.py**

After the `app = Flask(__name__)` line, ensure static folder points to the frontend:

```python
import os
app = Flask(__name__,
            static_folder=os.path.join(os.path.dirname(__file__), 'static'),
            static_url_path='/static')
```

- [ ] **Step 2: Add 3 new API endpoints to api.py**

```python
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


@app.route('/api/metrics/current', methods=['POST'])
def metrics_current():
    """前端直接查 Prometheus 即时指标"""
    data = request.get_json()
    from llm.mcp.prometheus_mcp import query_metric
    return jsonify(query_metric.invoke(data))
```

- [ ] **Step 3: Update collector/scheduler.py — add auto-resolve**

Find `check_heartbeat` function and modify the success branch:

```python
def check_heartbeat(cfg):
    name = cfg["name"]
    session = get_session()
    server = session.query(Server).filter_by(name=name).first()
    was_offline = (server and server.status == "offline")

    try:
        client = SSHClient(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg.get("password"),
        )
        uptime = client.exec("uptime -p")
        client.close()

        if not server:
            server = Server(name=name, ip=cfg['host'], status='online')
            session.add(server)
            session.flush()

        server.last_heartbeat = datetime.now(timezone.utc)
        server.status = "online"
        print(f"[{name}] 心跳正常: {uptime}")

        # ★ 自动恢复：如果之前是离线，关闭 open 的离线告警
        if was_offline:
            existing = session.query(Alert).filter(
                Alert.server_name == name,
                Alert.type == 'offline',
                Alert.status == 'open'
            ).all()
            for alert in existing:
                alert.status = "resolved"
            if existing:
                print(f"[{name}] 服务器恢复在线，自动解决 {len(existing)} 条离线告警")

    except Exception as e:
        print(f"[{name}] 心跳失败: {e}")
        if server and server.status == "online":
            server.status = 'offline'
            existing = session.query(Alert).filter(
                Alert.server_name == name,
                Alert.type == 'offline',
                Alert.status == 'open'
            ).first()
            if not existing:
                alert = Alert(
                    server_name=name,
                    type='offline',
                    message='服务器离线',
                    value=0,
                    status='open'
                )
                session.add(alert)

    session.commit()
    session.close()
```

Key changes:
1. `was_offline` flag at the start: records if server was offline before this check
2. In the success block: if `was_offline`, query all open offline alerts and mark them `resolved`
3. In the failure block: changed from `if server:` to `if server and server.status == "online":` — only create alert if transitioning from online to offline, preventing duplicate alerts on repeated failures

- [ ] **Step 4: Verify the backend changes work**

```bash
# Start Flask and test new endpoints
python api.py &

# Test logs query endpoint (will return empty if no Loki running, but should not crash)
curl -X POST http://localhost:5001/api/logs/query \
  -H 'Content-Type: application/json' \
  -d '{"server_name": "test", "hours": 1}'
```

- [ ] **Step 5: Commit**

```bash
git add api.py collector/scheduler.py
git commit -m "feat(backend): add log/metric API endpoints and alert auto-resolve"
```

---

### Task 11: Flask Serve Vue Build + Integration Test

**Files:**
- Verify: `api.py` Flask serves `templates/index.html`
- Create: `frontend/build` script to copy index.html to templates
- Verify: Full end-to-end — Flask + Vue build

- [ ] **Step 1: Verify Vite builds and output lands in the right places**

```bash
cd frontend
npm run build
# Verify
ls ../static/assets/          # Should have .js and .css files
ls ../templates/              # Should still have dashboard.html (old) — new one created by Vite
```

The Vite build currently doesn't produce `templates/index.html` automatically. We need a post-build script that copies the build output `index.html` into `templates/` with the correct asset paths.

- [ ] **Step 2: Add post-build script to package.json**

```json
"scripts": {
  "dev": "vite",
  "build": "vite build && node postbuild.js",
  "preview": "vite preview"
}
```

Create `frontend/postbuild.js`:

```javascript
import { readFileSync, writeFileSync, copyFileSync, mkdirSync, existsSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')

// Read the built index.html
const htmlPath = resolve(root, 'static', 'index.html')
let html = readFileSync(htmlPath, 'utf-8')

// Wrap in Flask template: assets are served from /static/
html = html.replace(
  '</head>',
  '<meta name="csrf-token" content="{{ csrf_token() if csrf_token else "" }}">\n</head>'
)

// Write to Flask templates dir
const templateDir = resolve(root, 'templates')
if (!existsSync(templateDir)) mkdirSync(templateDir, { recursive: true })
writeFileSync(resolve(templateDir, 'index.html'), html, 'utf-8')

console.log('✅ Built index.html → templates/index.html')
```

- [ ] **Step 3: Update Flask route for index.html**

In `api.py`, the root route served `dashboard.html`. Now it should serve the new `index.html`:

```python
@app.route('/')
def dashboard():
    return render_template('index.html')
```

Keep `dashboard.html` as `templates/dashboard.html.bak` for reference.

- [ ] **Step 4: Full integration test**

```bash
# 1. Build frontend
cd frontend
npm run build

# 2. Start Flask
cd ..
python api.py

# 3. Open http://localhost:5001
# Verify: Vue SPA loads, all 3 pages render, API calls work
```

- [ ] **Step 5: Commit**

```bash
git add frontend/postbuild.js api.py templates/
# Don't delete dashboard.html — just keep it
git rm --cached templates/dashboard.html 2>/dev/null || true
git add -A
git commit -m "feat: Flask serves Vue 3 build, full frontend migration"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ Spec §2 (Deployment) → Task 1 (scaffold) + Task 11 (Flask serve)
- ✅ Spec §3 (Alert state machine) → Task 10 (scheduler.py auto-resolve)
- ✅ Spec §3.4 (Frontend auto-resolve indicator) → Task 6 (AlertItem.vue)
- ✅ Spec §4 (RCA report) → Task 8 (rca-parser.js + RcaReport.vue + MessageBubble.vue)
- ✅ Spec §5 (LogViewer) → Task 9 (LogViewer.vue) + Task 10 (API endpoints)
- ✅ Spec §6 (Metrics enhancement) → Task 4 (MetricGauge.vue) + Task 7 (Trend.vue multi-metric)
- ✅ Spec §7 (Existing page migration) → Tasks 5-7 (Overview, Servers, Alerts, Trend)
- ✅ Spec §8 (Routes) → Task 1 (router/index.js)
- ✅ Spec §9 (Error states) → Tasks 5-9, each view covers loading/empty/error
- ✅ Spec §10 (Backend changes) → Task 10 (3 APIs + alert)
- ✅ Spec §11 (Chat API compatibility) → Task 8 (rca-parser.js handles both RCA and plain text)

**2. Placeholder scan:** No "TBD", "TODO", "implement later" found. All steps contain actual code.

**3. Type consistency:** All component names, store names, and API function calls match across tasks. `api/index.js` method names align with `stores/` usage in views. `query_logs.invoke()` is called with the same parameter names in both Task 9 (LogViewer) and Task 10 (API endpoint).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-05-smartops-frontend-adaptation-plan.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

<template>
  <div>
    <h1>🔍 日志查询</h1>

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

    <Loading v-if="loading" type="bar" :loading="true" />
    <div v-if="stats" class="stats-bar">
      <span class="stat-item" style="color:#ef4444;">🔴 {{ stats.levels?.error || 0 }}</span>
      <span class="stat-item" style="color:#f59e0b;">🟡 {{ stats.levels?.warn || 0 }}</span>
      <span class="stat-item" style="color:#10b981;">🟢 {{ stats.levels?.info || 0 }}</span>
      <span v-if="stats.error_codes && Object.keys(stats.error_codes).length" class="error-codes">
        错误码: {{ Object.entries(stats.error_codes).map(([k, v]) => `${k}=${v}`).join('  ') }}
      </span>
    </div>

    <div v-if="error" class="error-bar">
      {{ error }}
      <button class="retry-btn" @click="search">重试</button>
    </div>
    <div v-else-if="!loading && logs.length === 0" class="empty-bar">过去 {{ hours }} 小时无日志</div>

    <Loading v-if="loading" type="skeleton" :count="8" :height="32" />
    <div v-else-if="logs.length" class="log-list">
      <div v-for="(log, i) in logs" :key="i" class="log-item" :class="getLevel(log)">
        <span class="log-time">{{ log.timestamp?.slice(11, 19) || '' }}</span>
        <span class="log-level" :class="getLevel(log)">{{ getLevel(log).toUpperCase() }}</span>
        <span class="log-content">{{ log.content }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
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

function getLevel(log) {
  if (log.level) return log.level
  const c = (log.content || '').toLowerCase()
  if (c.includes('error') || c.includes('fatal')) return 'error'
  if (c.includes('warn')) return 'warn'
  return 'info'
}

async function search(reset = true) {
  if (!serverName.value) return
  if (reset) { logs.value = [] }
  loading.value = true
  error.value = ''
  try {
    const params = { server_name: serverName.value, hours: hours.value, level: level.value }
    if (keyword.value) params.keywords = [keyword.value]
    const [logData, statsData] = await Promise.all([
      api.queryLogs(params),
      api.analyzeLogs({ server_name: serverName.value, hours: hours.value }),
    ])
    if (Array.isArray(logData)) {
      logs.value = reset ? logData : [...logs.value, ...logData]
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

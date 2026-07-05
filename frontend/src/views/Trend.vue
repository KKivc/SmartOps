<template>
  <div>
    <h1>趋势分析</h1>
    <div v-if="serversStore.list.length === 0">
      <EmptyState message="暂无服务器数据" />
    </div>
    <template v-else>
      <div v-if="serversStore.loading">
        <Loading type="skeleton" :count="1" :height="300" />
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

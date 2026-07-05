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
import { computed } from 'vue'

const props = defineProps({
  alert: { type: Object, required: true },
})
defineEmits(['update'])

const typeText = computed(() => ({ offline: '离线', cpu: 'CPU', memory: '内存', disk: '磁盘' }[props.alert.type] || props.alert.type))
const statusText = computed(() => ({ open: '未处理', acknowledged: '已确认', resolved: '已解决' }[props.alert.status] || props.alert.status))
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

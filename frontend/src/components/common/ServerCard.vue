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
import { computed } from 'vue'
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

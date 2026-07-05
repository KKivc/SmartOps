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

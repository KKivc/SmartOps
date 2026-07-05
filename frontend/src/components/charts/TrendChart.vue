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

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

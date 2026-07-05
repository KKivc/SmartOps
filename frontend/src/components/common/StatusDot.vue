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

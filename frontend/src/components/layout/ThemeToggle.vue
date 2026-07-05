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

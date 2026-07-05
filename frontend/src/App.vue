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

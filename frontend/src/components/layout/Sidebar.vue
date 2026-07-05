<template>
  <aside class="sidebar">
    <div class="sidebar-brand">
      <div class="sidebar-logo"><span>Smart</span>Ops</div>
      <span class="sidebar-subtitle">智能运维平台</span>
    </div>
    <nav class="sidebar-nav">
      <div class="sidebar-label">监控</div>
      <router-link to="/overview" active-class="active">📡 总览</router-link>
      <router-link to="/alerts" active-class="active">🔔 告警</router-link>
      <router-link to="/servers" active-class="active">🖥 服务器</router-link>
      <router-link to="/trend" active-class="active">📈 趋势</router-link>
      <div class="sidebar-label">分析</div>
      <router-link to="/logs" active-class="active">📋 日志查看</router-link>
      <router-link to="/chat" active-class="active">🤖 AI 对话</router-link>
    </nav>
    <div class="sidebar-footer">
      <ThemeToggle />
    </div>
  </aside>
</template>

<script setup>
import ThemeToggle from './ThemeToggle.vue'
</script>

<style scoped>
.sidebar {
  width: 240px; background: #0b1120; color: #e2e8f0;
  display: flex; flex-direction: column; min-height: 100vh;
}
.sidebar-brand { padding: 28px 20px 20px; border-bottom: 1px solid #1a2332; }
.sidebar-logo { font-size: 22px; font-weight: 700; letter-spacing: 2px; }
.sidebar-logo span { color: #0ec8e6; }
.sidebar-subtitle { display: block; font-size: 11px; color: #475569; margin-top: 6px; letter-spacing: 1px; }
.sidebar-nav { flex: 1; padding: 12px 0; }
.sidebar-label { padding: 16px 20px 6px; font-size: 11px; font-weight: 600; color: #475569; letter-spacing: 1px; }
.sidebar-nav a {
  display: block; padding: 10px 20px; margin: 2px 8px;
  border-radius: 8px; cursor: pointer; font-size: 14px;
  color: #94a3b8; text-decoration: none; transition: all 0.2s;
}
.sidebar-nav a:hover { background: #151f31; color: #e2e8f0; }
.sidebar-nav a.active {
  background: rgba(14,200,230,0.08); color: #0ec8e6; font-weight: 600;
  position: relative;
}
.sidebar-nav a.active::before {
  content: ''; position: absolute; left: -8px; top: 50%;
  transform: translateY(-50%); width: 3px; height: 20px;
  background: #0ec8e6; border-radius: 0 3px 3px 0;
}
.sidebar-footer { padding: 16px 20px; border-top: 1px solid #1a2332; }
</style>

<template>
  <aside class="sidebar">
    <div class="sidebar-brand">
      <div class="sidebar-logo"><span>Smart</span>Ops</div>
    </div>
    <nav class="sidebar-nav">
      <router-link to="/overview">📡 总览</router-link>
      <router-link to="/alerts">🔔 告警</router-link>
      <router-link to="/servers">🖥 服务器</router-link>
      <router-link to="/trend">📈 趋势</router-link>
      <router-link to="/logs">📋 日志</router-link>
      <router-link to="/chat">🤖 AI 对话</router-link>
    </nav>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 240px;
  background: #0b1120;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
}
.sidebar-brand { padding: 28px 20px 20px; border-bottom: 1px solid #1a2332; }
.sidebar-logo { font-size: 22px; font-weight: 700; letter-spacing: 2px; }
.sidebar-logo span { color: #0ec8e6; }
.sidebar-nav { flex: 1; padding: 12px 0; }
.sidebar-nav a {
  display: block;
  padding: 10px 20px;
  margin: 2px 8px;
  border-radius: 8px;
  color: #94a3b8;
  text-decoration: none;
  font-size: 14px;
  transition: all 0.2s;
}
.sidebar-nav a:hover { background: #151f31; color: #e2e8f0; }
.sidebar-nav a.router-link-exact-active {
  background: rgba(14,200,230,0.08);
  color: #0ec8e6;
  font-weight: 600;
}
</style>

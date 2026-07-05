<template>
  <div>
    <h1>总览</h1>
    <div v-if="store.loading && store.list.length === 0">
      <Loading type="skeleton" :count="3" />
    </div>
    <template v-else>
      <div class="summary">
        <div class="stat">🟢 在线: {{ store.onlineCount }}</div>
        <div class="stat">🔴 失联: {{ store.offlineCount }}</div>
        <div class="stat">📊 总数: {{ store.list.length }}</div>
      </div>
      <div v-if="store.error" class="error-banner">{{ store.error }} <button @click="store.fetchServers()">重试</button></div>
      <div v-if="store.list.length === 0">
        <EmptyState message="还没有服务器，添加一台开始监控" actionText="+ 添加服务器" @action="showAddServer = true" />
      </div>
      <div v-else class="card-grid">
        <ServerCard v-for="s in sortedServers" :key="s.name" :server="s" @click="goTrend(s.name)" />
      </div>
    </template>

    <Modal :visible="showAddServer" title="添加服务器" @close="showAddServer = false" @confirm="addServer">
      <label>服务器名称</label>
      <input v-model="form.name" placeholder="例: web-01" class="modal-input" />
      <label>IP 地址</label>
      <input v-model="form.ip" placeholder="例: 192.168.1.100" class="modal-input" />
      <label>SSH 用户名</label>
      <input v-model="form.user" placeholder="root" class="modal-input" />
      <label>SSH 密码</label>
      <input v-model="form.password" type="password" class="modal-input" />
    </Modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useServersStore } from '../stores/servers'
import api from '../api'
import ServerCard from '../components/common/ServerCard.vue'
import Loading from '../components/common/Loading.vue'
import EmptyState from '../components/common/EmptyState.vue'
import Modal from '../components/common/Modal.vue'

const store = useServersStore()
const router = useRouter()
const showAddServer = ref(false)
const form = ref({ name: '', ip: '', user: '', password: '' })

const sortedServers = computed(() =>
  [...store.list].sort((a, b) => (a.status === 'online' ? -1 : 1))
)

function goTrend(name) { router.push(`/trend/${name}`) }

async function addServer() {
  const f = form.value
  if (!f.name || !f.ip || !f.user || !f.password) return alert('请填写所有字段')
  try {
    await api.addServer(f)
    showAddServer.value = false
    form.value = { name: '', ip: '', user: '', password: '' }
    await store.fetchServers()
  } catch (e) { alert(e.message) }
}

onMounted(() => { store.fetchServers(); store.startAutoRefresh() })
onUnmounted(() => store.stopAutoRefresh())
</script>

<style scoped>
h1 { font-size: 24px; font-weight: 600; margin-bottom: 24px; }
.summary { display: flex; gap: 16px; margin-bottom: 24px; }
.stat {
  background: var(--card-bg); border: 1px solid var(--card-border);
  border-radius: 12px; padding: 20px 28px; box-shadow: var(--shadow);
  font-size: 15px; font-weight: 600; flex: 1;
}
.card-grid { display: flex; flex-wrap: wrap; gap: 16px; }
.error-banner {
  width: 100%; padding: 12px 16px; border-radius: 10px;
  font-size: 14px; font-weight: 600; margin-bottom: 16px;
  background: rgba(239,68,68,0.1); color: #ef4444; border: 1px solid rgba(239,68,68,0.2);
  display: flex; justify-content: space-between; align-items: center;
}
.modal-input {
  width: 100%; padding: 10px 12px; border: 1px solid var(--card-border);
  border-radius: 8px; font-size: 14px; background: var(--bg); color: var(--text);
  outline: none; box-sizing: border-box; margin-bottom: 8px;
}
label { display: block; font-size: 13px; font-weight: 600; color: var(--text-muted); margin: 12px 0 4px; }
label:first-of-type { margin-top: 0; }
</style>

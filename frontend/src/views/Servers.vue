<template>
  <div>
    <h1>服务器列表</h1>
    <Loading v-if="store.loading && store.list.length === 0" type="skeleton" :count="5" :height="40" />
    <div v-else-if="store.error" class="error-banner">{{ store.error }} <button @click="store.fetchServers()">重试</button></div>
    <div v-else-if="store.list.length === 0">
      <EmptyState message="还没有服务器" actionText="+ 添加服务器" @action="showAddServer = true" />
    </div>
    <div v-else style="width:100%;">
      <div class="table-header">
        <span class="table-title">共 {{ store.list.length }} 台服务器</span>
        <button class="add-btn" @click="showAddServer = true">+ 添加服务器</button>
      </div>
      <div class="table-wrapper">
        <table class="server-table">
          <thead>
            <tr>
              <th>名称</th><th>IP</th><th>系统</th><th>状态</th>
              <th>CPU</th><th>内存</th><th>磁盘</th><th>心跳</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in store.list" :key="s.name">
              <td><strong>{{ s.name }}</strong></td>
              <td>{{ s.ip || '-' }}</td>
              <td>{{ s.os || '-' }}</td>
              <td><StatusDot :status="s.status" />{{ s.status === 'online' ? '在线' : '失联' }}</td>
              <td>{{ s.cpu ?? '-' }}%</td>
              <td>{{ s.memory ?? '-' }}%</td>
              <td>{{ s.disk ?? '-' }}%</td>
              <td>{{ s.last_heartbeat ? s.last_heartbeat.slice(5, 16) : '-' }}</td>
              <td><button class="del-btn" @click="deleteServer(s.name)">✕</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <Modal :visible="showAddServer" title="添加服务器" @close="showAddServer = false" @confirm="addServer">
      <label>服务器名称</label>
      <input v-model="form.name" class="modal-input" />
      <label>IP 地址</label>
      <input v-model="form.ip" class="modal-input" />
      <label>SSH 用户名</label>
      <input v-model="form.user" class="modal-input" />
      <label>SSH 密码</label>
      <input v-model="form.password" type="password" class="modal-input" />
    </Modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useServersStore } from '../stores/servers'
import api from '../api'
import StatusDot from '../components/common/StatusDot.vue'
import Loading from '../components/common/Loading.vue'
import EmptyState from '../components/common/EmptyState.vue'
import Modal from '../components/common/Modal.vue'

const store = useServersStore()
const showAddServer = ref(false)
const form = ref({ name: '', ip: '', user: '', password: '' })

async function addServer() {
  if (!form.value.name || !form.value.ip || !form.value.user || !form.value.password) return alert('请填写所有字段')
  try {
    await api.addServer(form.value)
    showAddServer.value = false
    form.value = { name: '', ip: '', user: '', password: '' }
    await store.fetchServers()
  } catch (e) { alert(e.message) }
}

async function deleteServer(name) {
  if (!confirm(`确定删除服务器 ${name}？所有相关数据将被清除。`)) return
  try {
    await api.deleteServer(name)
    await store.fetchServers()
  } catch (e) { alert(e.message) }
}

onMounted(() => store.fetchServers())
</script>

<style scoped>
h1 { font-size: 24px; font-weight: 600; margin-bottom: 24px; }
.table-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.table-title { font-size: 14px; color: var(--text-muted); }
.add-btn { padding: 8px 18px; background: var(--accent); color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; }
.add-btn:hover { background: var(--accent-dim); }
.table-wrapper { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; overflow: hidden; box-shadow: var(--shadow); }
.server-table { width: 100%; border-collapse: collapse; }
.server-table th { padding: 12px 16px; text-align: left; font-size: 12px; font-weight: 600; color: var(--text-muted); background: var(--bg); border-bottom: 1px solid var(--card-border); }
.server-table td { padding: 12px 16px; font-size: 13px; border-bottom: 1px solid var(--card-border); }
.server-table tr:last-child td { border-bottom: none; }
.del-btn { background: none; border: none; cursor: pointer; font-size: 14px; color: var(--text-muted); padding: 4px 8px; border-radius: 4px; }
.del-btn:hover { background: rgba(239,68,68,0.15); color: #ef4444; }
.error-banner {
  padding: 12px 16px; border-radius: 10px; font-size: 14px; font-weight: 600; margin-bottom: 16px;
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

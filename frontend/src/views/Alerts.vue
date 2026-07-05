<template>
  <div>
    <h1>告警</h1>
    <Loading v-if="store.loading && store.list.length === 0" type="skeleton" :count="5" />
    <template v-else>
      <div v-if="store.error" class="error-banner">{{ store.error }} <button @click="store.fetchAlerts()">重试</button></div>
      <div v-if="store.openCount > 0" class="alert-banner">🔴 {{ store.openCount }} 条未处理告警</div>
      <div v-if="store.list.length === 0">
        <EmptyState message="暂无告警" />
      </div>
      <div v-else class="alert-list">
        <AlertItem
          v-for="a in store.list"
          :key="a.id"
          :alert="a"
          @update="(status) => store.updateAlertStatus(a.id, status)"
        />
      </div>
    </template>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useAlertsStore } from '../stores/alerts'
import AlertItem from '../components/alerts/AlertItem.vue'
import Loading from '../components/common/Loading.vue'
import EmptyState from '../components/common/EmptyState.vue'

const store = useAlertsStore()
onMounted(() => store.fetchAlerts())
</script>

<style scoped>
h1 { font-size: 24px; font-weight: 600; margin-bottom: 24px; }
.alert-banner { width: 100%; padding: 12px 16px; border-radius: 10px; font-size: 14px; font-weight: 600; margin-bottom: 16px; background: rgba(239,68,68,0.1); color: #ef4444; border: 1px solid rgba(239,68,68,0.2); }
.alert-list { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; overflow: hidden; box-shadow: var(--shadow); }
.error-banner { padding: 12px 16px; border-radius: 10px; font-size: 14px; font-weight: 600; margin-bottom: 16px; background: rgba(239,68,68,0.1); color: #ef4444; border: 1px solid rgba(239,68,68,0.2); display: flex; justify-content: space-between; align-items: center; }
</style>

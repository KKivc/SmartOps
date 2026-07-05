import { defineStore } from 'pinia'
import api from '../api'

export const useServersStore = defineStore('servers', {
  state: () => ({
    list: [],
    loading: false,
    error: null,
    refreshTimer: null,
  }),
  getters: {
    onlineCount: (state) => state.list.filter((s) => s.status === 'online').length,
    offlineCount: (state) => state.list.filter((s) => s.status !== 'online').length,
    serverNames: (state) => state.list.map((s) => s.name),
  },
  actions: {
    async fetchServers() {
      this.loading = true
      this.error = null
      try {
        this.list = await api.getServers()
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
    startAutoRefresh(interval = 10000) {
      this.stopAutoRefresh()
      this.refreshTimer = setInterval(() => this.fetchServers(), interval)
    },
    stopAutoRefresh() {
      if (this.refreshTimer) {
        clearInterval(this.refreshTimer)
        this.refreshTimer = null
      }
    },
  },
})

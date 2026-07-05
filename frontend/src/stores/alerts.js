import { defineStore } from 'pinia'
import api from '../api'

export const useAlertsStore = defineStore('alerts', {
  state: () => ({
    list: [],
    loading: false,
    error: null,
  }),
  getters: {
    openCount: (state) => state.list.filter((a) => a.status === 'open').length,
  },
  actions: {
    async fetchAlerts() {
      this.loading = true
      this.error = null
      try {
        this.list = await api.getAlerts()
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
    async updateAlertStatus(id, status) {
      await api.updateAlert(id, status)
      await this.fetchAlerts()
    },
  },
})

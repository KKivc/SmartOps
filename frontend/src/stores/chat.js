import { defineStore } from 'pinia'
import api from '../api'

export const useChatStore = defineStore('chat', {
  state: () => ({
    conversations: [],
    currentConvId: null,
    messages: [],
    loading: false,
    sending: false,
    convLoading: false,
  }),
  actions: {
    async fetchConversations() {
      this.convLoading = true
      try {
        this.conversations = await api.getConversations()
      } finally {
        this.convLoading = false
      }
    },
    async createConversation() {
      const conv = await api.createConversation()
      this.conversations.unshift(conv)
      return conv
    },
    async deleteConversation(id) {
      await api.deleteConversation(id)
      this.conversations = this.conversations.filter((c) => c.id !== id)
      if (this.currentConvId === id) {
        this.currentConvId = null
        this.messages = []
      }
    },
    async selectConversation(id) {
      this.currentConvId = id
      this.loading = true
      try {
        this.messages = await api.getMessages(id)
      } finally {
        this.loading = false
      }
    },
    async sendMessage(text) {
      if (!this.currentConvId) {
        const conv = await this.createConversation()
        this.currentConvId = conv.id
      }
      this.sending = true
      // 追加用户消息到本地
      this.messages.push({ role: 'human', content: text })
      try {
        const data = await api.sendMessage(this.currentConvId, text)
        this.messages.push({ role: 'ai', content: data.reply })
      } finally {
        this.sending = false
      }
    },
  },
})

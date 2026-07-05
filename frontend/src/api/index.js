const BASE = ''

async function request(url, options = {}) {
  const resp = await fetch(BASE + url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(err.error || `HTTP ${resp.status}`)
  }
  return resp.json()
}

export default {
  // 服务器
  getServers: () => request('/api/servers'),
  addServer: (data) =>
    request('/api/servers', { method: 'POST', body: JSON.stringify(data) }),
  deleteServer: (name) =>
    request(`/api/servers/${name}`, { method: 'DELETE' }),
  getServerHistory: (name) =>
    request(`/api/servers/${name}/history`),
  getServerLogs: (name, params = {}) => {
    const q = new URLSearchParams(params).toString()
    return request(`/api/servers/${name}/logs${q ? '?' + q : ''}`)
  },

  // 告警
  getAlerts: () => request('/api/alerts'),
  updateAlert: (id, status) =>
    request(`/api/alerts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

  // 对话
  getConversations: () => request('/api/conversations'),
  createConversation: () =>
    request('/api/conversations', { method: 'POST' }),
  deleteConversation: (id) =>
    request(`/api/conversations/${id}`, { method: 'DELETE' }),
  getMessages: (convId) =>
    request(`/api/conversations/${convId}/messages`),
  sendMessage: (convId, message) =>
    request('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ conversation_id: convId, message }),
    }),

  // 日志（新增 — 直接查 Loki）
  queryLogs: (params) =>
    request('/api/logs/query', { method: 'POST', body: JSON.stringify(params) }),
  analyzeLogs: (params) =>
    request('/api/logs/analyze', { method: 'POST', body: JSON.stringify(params) }),

  // 指标（新增 — 直接查 Prometheus）
  getMetricsCurrent: (params) =>
    request('/api/metrics/current', { method: 'POST', body: JSON.stringify(params) }),
}

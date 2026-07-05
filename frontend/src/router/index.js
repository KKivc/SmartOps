import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/overview' },
  {
    path: '/overview',
    name: 'overview',
    component: () => import('../views/Overview.vue'),
  },
  {
    path: '/servers',
    name: 'servers',
    component: () => import('../views/Servers.vue'),
  },
  {
    path: '/alerts',
    name: 'alerts',
    component: () => import('../views/Alerts.vue'),
  },
  {
    path: '/trend',
    name: 'trend',
    component: () => import('../views/Trend.vue'),
  },
  {
    path: '/trend/:serverName',
    name: 'trend-server',
    component: () => import('../views/Trend.vue'),
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('../views/Chat.vue'),
  },
  {
    path: '/logs',
    name: 'logs',
    component: () => import('../views/LogViewer.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router

import { createRouter, createWebHistory } from 'vue-router'

const DashboardView = () => import('../views/DashboardView.vue')
const AgentsView = () => import('../views/AgentsView.vue')
const ManagementView = () => import('../views/ManagementView.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', name: 'dashboard', component: DashboardView },
    { path: '/agents/:name?', name: 'agents', component: AgentsView },
    { path: '/management', name: 'management', component: ManagementView },
  ],
})

export default router

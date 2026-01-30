import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: 'Dashboard Overview' }
  },
  {
    path: '/dreps',
    name: 'DReps',
    component: () => import('@/views/DRepsView.vue'),
    meta: { title: 'DRep Profiles' }
  },
  {
    path: '/manage',
    name: 'Manage',
    component: () => import('@/views/ManageView.vue'),
    meta: { title: 'Manage DReps' }
  },
  {
    path: '/dreps/:drepId',
    name: 'drep-profile',
    component: () => import('@/views/DRepProfileView.vue'),
    meta: { title: 'DRep Profile' }
  },
  {
    path: '/governance',
    name: 'Governance',
    component: () => import('@/views/GovernanceView.vue'),
    meta: { title: 'Governance Actions' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  document.title = `${to.meta.title || 'DRep Tracker'} | Cardano DRep Tracking`
  next()
})

export default router

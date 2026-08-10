import { createRouter, createWebHistory } from 'vue-router'
import store from '@/store'

// 路由守卫 - 检查认证状态
const requireAuth = (to, from, next) => {
  const isAuthenticated = store.getters['auth/isAuthenticated']
  
  if (!isAuthenticated) {
    // 保存原始目标路由，以便登录后重定向
    next({ 
      name: 'login', 
      query: { redirect: to.fullPath }
    })
  } else {
    next()
  }
}

// 路由守卫 - 检查管理员权限
const requireAdmin = (to, from, next) => {
  const isAuthenticated = store.getters['auth/isAuthenticated']
  const isAdmin = store.getters['auth/isAdmin']
  
  if (!isAuthenticated) {
    next({ 
      name: 'login', 
      query: { redirect: to.fullPath }
    })
  } else if (!isAdmin) {
    next({ name: 'forbidden' })
  } else {
    next()
  }
}

// 路由守卫 - 已登录用户不可访问
const guestOnly = (to, from, next) => {
  const isAuthenticated = store.getters['auth/isAuthenticated']
  
  if (isAuthenticated) {
    next({ name: 'home' })
  } else {
    next()
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/emails',
      name: 'emails',
      component: () => import('@/views/EmailsView.vue'),
      meta: { requiresAuth: true },
      beforeEnter: requireAuth
    },
    {
      path: '/emails/:id',
      name: 'email-detail',
      component: () => import('@/views/EmailDetailView.vue'),
      meta: { requiresAuth: true },
      beforeEnter: requireAuth,
      props: route => ({ id: Number(route.params.id) })
    },
    {
      path: '/import',
      name: 'import',
      component: () => import('@/views/ImportView.vue'),
      meta: { requiresAuth: true },
      beforeEnter: requireAuth
    },
    {
      path: '/search',
      name: 'search',
      component: () => import('@/views/SearchView.vue'),
      meta: { requiresAuth: true },
      beforeEnter: requireAuth
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('@/views/AboutView.vue')
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/auth/LoginView.vue'),
      meta: { guestOnly: true },
      beforeEnter: guestOnly
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/auth/RegisterView.vue'),
      meta: { guestOnly: true },
      beforeEnter: guestOnly
    },
    {
      path: '/account',
      name: 'account',
      component: () => import('@/views/auth/AccountView.vue'),
      meta: { requiresAuth: true },
      beforeEnter: requireAuth
    },
    {
      path: '/admin/users',
      name: 'admin-users',
      component: () => import('@/views/admin/UsersView.vue'),
      meta: { requiresAdmin: true },
      beforeEnter: requireAdmin
    },
    {
      path: '/admin/users-simple',
      name: 'admin-users-simple',
      component: () => import('@/views/admin/SimplifiedUsersView.vue'),
      meta: { requiresAdmin: true },
      beforeEnter: requireAdmin
    },
    {
      path: '/forbidden',
      name: 'forbidden',
      component: () => import('@/views/ForbiddenView.vue')
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue')
    }
  ]
})

// 全局前置守卫
router.beforeEach((to, from, next) => {
  // 检查目标路由是否需要认证
  if (to.matched.some(record => record.meta.requiresAuth)) {
    const isAuthenticated = store.getters['auth/isAuthenticated']
    
    if (!isAuthenticated) {
      next({
        name: 'login',
        query: { redirect: to.fullPath }
      })
    } else {
      next()
    }
  } 
  // 检查目标路由是否需要管理员权限
  else if (to.matched.some(record => record.meta.requiresAdmin)) {
    const isAuthenticated = store.getters['auth/isAuthenticated']
    const isAdmin = store.getters['auth/isAdmin']
    
    if (!isAuthenticated) {
      next({
        name: 'login',
        query: { redirect: to.fullPath }
      })
    } else if (!isAdmin) {
      next({ name: 'forbidden' })
    } else {
      next()
    }
  } 
  // 对于仅限游客访问的路由
  else if (to.matched.some(record => record.meta.guestOnly)) {
    const isAuthenticated = store.getters['auth/isAuthenticated']
    
    if (isAuthenticated) {
      next({ name: 'home' })
    } else {
      next()
    }
  } 
  // 其他路由
  else {
    next()
  }
})

export default router 
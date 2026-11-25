import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: { layout: 'app', auth: true, title: '指挥台', nav: 'home' }
    },
    {
      path: '/emails',
      name: 'emails',
      component: () => import('@/views/EmailsView.vue'),
      meta: { layout: 'app', auth: true, title: '邮箱资产', nav: 'emails' }
    },
    {
      path: '/emails/:id',
      name: 'email-detail',
      component: () => import('@/views/EmailDetailView.vue'),
      meta: { layout: 'app', auth: true, title: '收件箱', nav: 'emails' },
      props: (route) => ({ id: Number(route.params.id) })
    },
    {
      path: '/import',
      name: 'import',
      component: () => import('@/views/ImportView.vue'),
      meta: { layout: 'app', auth: true, title: '批量导入', nav: 'import' }
    },
    {
      path: '/search',
      name: 'search',
      component: () => import('@/views/SearchView.vue'),
      meta: { layout: 'app', auth: true, title: '邮件搜索', nav: 'search' }
    },
    {
      path: '/account',
      name: 'account',
      component: () => import('@/views/auth/AccountView.vue'),
      meta: { layout: 'app', auth: true, title: '账户设置', nav: 'account' }
    },
    {
      path: '/admin/users',
      name: 'admin-users',
      component: () => import('@/views/admin/UsersView.vue'),
      meta: { layout: 'app', auth: true, admin: true, title: '用户管理', nav: 'admin-users' }
    },
    {
      path: '/admin/users-simple',
      redirect: '/admin/users'
    },
    {
      path: '/admin/system',
      name: 'admin-system',
      component: () => import('@/views/admin/SystemView.vue'),
      meta: { layout: 'app', auth: true, admin: true, title: '系统设置', nav: 'admin-system' }
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('@/views/AboutView.vue'),
      meta: { layout: 'app', title: '关于', nav: 'about' }
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/auth/LoginView.vue'),
      meta: { layout: 'auth', guest: true, title: '登录' }
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/auth/RegisterView.vue'),
      meta: { layout: 'auth', guest: true, title: '注册' }
    },
    {
      path: '/forbidden',
      name: 'forbidden',
      component: () => import('@/views/ForbiddenView.vue'),
      meta: { layout: 'blank', title: '禁止访问' }
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
      meta: { layout: 'blank', title: '页面不存在' }
    }
  ]
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.auth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.admin && !auth.isAdmin) {
    return { name: 'forbidden' }
  }
  if (to.meta.guest && auth.isAuthenticated) {
    return { name: 'home' }
  }
  return true
})

router.afterEach((to) => {
  const title = to.meta?.title
  if (typeof document !== 'undefined') {
    document.title = title ? `${title} · FireMail` : 'FireMail'
  }
})

export default router

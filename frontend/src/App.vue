<template>
  <el-config-provider :locale="zhCn">
    <div class="app-container">
      <!-- Mobile Header -->
      <header class="app-header" :class="{ 'scrolled': isScrolled }">
        <div class="header-content">
          <div class="header-left">
            <el-button
              v-if="isAuthenticated"
              class="menu-toggle"
              :icon="Fold"
              @click="drawerVisible = true"
              circle
            />
            <router-link to="/" class="logo-link">
              <div class="logo-icon">
                <el-icon :size="20"><Message /></el-icon>
              </div>
              <span class="logo-text">FireMail</span>
            </router-link>
          </div>

          <div class="header-right">
            <template v-if="!isAuthenticated">
              <router-link to="/login" class="header-btn-link">
                <el-button type="primary" plain round size="small">登录</el-button>
              </router-link>
              <router-link to="/register" class="header-btn-link desktop-only">
                <el-button type="primary" round size="small">注册</el-button>
              </router-link>
            </template>

            <template v-else>
              <el-tag
                :type="websocketConnected ? 'success' : 'danger'"
                effect="dark"
                round
                size="small"
                class="status-tag"
              >
                <el-icon class="status-icon"><Connection /></el-icon>
                <span class="desktop-only">{{ websocketConnected ? '已连接' : '未连接' }}</span>
              </el-tag>

              <el-dropdown @command="handleUserCommand" trigger="click">
                <div class="user-avatar">
                  <el-avatar :size="32" :style="{ background: 'var(--primary-gradient)' }">
                    {{ currentUser?.username?.charAt(0)?.toUpperCase() || 'U' }}
                  </el-avatar>
                </div>
                <template #dropdown>
                  <el-dropdown-menu>
                    <div class="dropdown-header">
                      <strong>{{ currentUser?.username }}</strong>
                      <el-tag v-if="isAdmin" size="small" type="warning">管理员</el-tag>
                    </div>
                    <el-dropdown-item command="account" :icon="User">账户设置</el-dropdown-item>
                    <el-dropdown-item v-if="isAdmin" command="admin" :icon="Setting">用户管理</el-dropdown-item>
                    <el-dropdown-item divided command="logout" :icon="SwitchButton">退出登录</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </div>
        </div>
      </header>

      <!-- Desktop Navigation -->
      <nav v-if="isAuthenticated" class="desktop-nav">
        <el-menu
          mode="horizontal"
          :router="true"
          :default-active="$route.path"
          :ellipsis="false"
        >
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            <span>首页</span>
          </el-menu-item>
          <el-menu-item index="/emails">
            <el-icon><Message /></el-icon>
            <span>邮箱管理</span>
          </el-menu-item>
          <el-menu-item index="/search">
            <el-icon><Search /></el-icon>
            <span>邮件搜索</span>
          </el-menu-item>
          <el-menu-item v-if="isAdmin" index="/admin/users">
            <el-icon><UserFilled /></el-icon>
            <span>用户管理</span>
          </el-menu-item>
          <el-menu-item index="/about">
            <el-icon><InfoFilled /></el-icon>
            <span>关于</span>
          </el-menu-item>
        </el-menu>
      </nav>

      <!-- Mobile Drawer -->
      <el-drawer
        v-model="drawerVisible"
        direction="ltr"
        size="280px"
        :show-close="false"
        class="mobile-drawer"
      >
        <template #header>
          <div class="drawer-header">
            <div class="drawer-logo">
              <div class="logo-icon">
                <el-icon :size="24"><Message /></el-icon>
              </div>
              <span>FireMail</span>
            </div>
            <el-button :icon="Close" circle size="small" @click="drawerVisible = false" />
          </div>
        </template>

        <div class="drawer-user" v-if="currentUser">
          <el-avatar :size="48" :style="{ background: 'var(--primary-gradient)' }">
            {{ currentUser?.username?.charAt(0)?.toUpperCase() }}
          </el-avatar>
          <div class="drawer-user-info">
            <strong>{{ currentUser?.username }}</strong>
            <el-tag v-if="isAdmin" size="small" type="warning">管理员</el-tag>
          </div>
        </div>

        <el-menu
          :router="true"
          :default-active="$route.path"
          @select="drawerVisible = false"
          class="drawer-menu"
        >
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            <span>首页</span>
          </el-menu-item>
          <el-menu-item index="/emails">
            <el-icon><Message /></el-icon>
            <span>邮箱管理</span>
          </el-menu-item>
          <el-menu-item index="/search">
            <el-icon><Search /></el-icon>
            <span>邮件搜索</span>
          </el-menu-item>
          <el-menu-item v-if="isAdmin" index="/admin/users">
            <el-icon><UserFilled /></el-icon>
            <span>用户管理</span>
          </el-menu-item>
          <el-menu-item index="/about">
            <el-icon><InfoFilled /></el-icon>
            <span>关于</span>
          </el-menu-item>
          <el-menu-item index="/account">
            <el-icon><User /></el-icon>
            <span>账户设置</span>
          </el-menu-item>
        </el-menu>

        <template #footer>
          <el-button type="danger" plain round @click="handleLogout" class="logout-btn">
            <el-icon><SwitchButton /></el-icon>
            退出登录
          </el-button>
        </template>
      </el-drawer>

      <!-- Main Content -->
      <main class="app-main">
        <router-view v-slot="{ Component }" v-if="!initializing">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
        <div v-else class="loading-container">
          <el-skeleton :rows="6" animated />
        </div>
      </main>

      <!-- Footer -->
      <footer class="app-footer">
        <span>FireMail 邮箱助手</span>
        <span class="footer-divider">|</span>
        <span>&copy; 2025</span>
      </footer>

      <Notifications />

      <div v-if="showDebugTools" class="debug-tools-container">
        <DebugTools />
      </div>

      <div class="debug-tools-toggle" @click="toggleDebugTools">
        <el-button type="primary" circle size="small" :icon="Setting" />
      </div>
    </div>
  </el-config-provider>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useStore } from 'vuex'
import { ElConfigProvider, ElMessage } from 'element-plus'
import {
  Fold, Close, Search, Message, HomeFilled, InfoFilled,
  UserFilled, Setting, User, SwitchButton, Connection
} from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import websocket from '@/services/websocket'
import Notifications from './components/Notifications.vue'
import DebugTools from './components/DebugTools.vue'

const initializing = ref(true)
const isScrolled = ref(false)
const showDebugTools = ref(false)
const drawerVisible = ref(false)

const store = useStore()
const router = useRouter()

const websocketConnected = computed(() => store.state.websocketConnected)
const isAuthenticated = computed(() => store.getters['auth/isAuthenticated'])
const currentUser = computed(() => store.getters['auth/currentUser'])
const isAdmin = computed(() => store.getters['auth/isAdmin'])

const handleScroll = () => { isScrolled.value = window.scrollY > 10 }
const toggleDebugTools = () => {
  showDebugTools.value = !showDebugTools.value
  localStorage.setItem('show_debug_tools', showDebugTools.value ? 'true' : 'false')
}

const initializeAuth = async () => {
  initializing.value = true
  if (isAuthenticated.value) {
    try {
      await store.dispatch('auth/getCurrentUser')
    } catch (error) {
      console.error('获取用户信息失败:', error)
    }
  }
  initializing.value = false
}

const handleUserCommand = (command) => {
  switch (command) {
    case 'account': router.push('/account'); break
    case 'admin': router.push('/admin/users'); break
    case 'logout': handleLogout(); break
  }
}

const handleLogout = async () => {
  drawerVisible.value = false
  try {
    await store.dispatch('auth/logout')
    router.push('/login')
    ElMessage.success('已成功退出登录')
  } catch (error) {
    ElMessage.error('退出登录失败')
  }
}

const handleConnect = () => store.commit('SET_WEBSOCKET_CONNECTED', true)
const handleDisconnect = () => store.commit('SET_WEBSOCKET_CONNECTED', false)

watch(isAuthenticated, (newValue) => {
  if (newValue) {
    if (!websocket.isConnected) websocket.connect()
  } else {
    websocket.disconnect()
  }
})

onMounted(async () => {
  await initializeAuth()
  websocket.onConnect(handleConnect)
  websocket.onDisconnect(handleDisconnect)
  if (isAuthenticated.value && !websocket.isConnected) websocket.connect()
  window.addEventListener('scroll', handleScroll)
  showDebugTools.value = localStorage.getItem('show_debug_tools') === 'true'
})

onUnmounted(() => {
  websocket.offConnect(handleConnect)
  websocket.offDisconnect(handleDisconnect)
  websocket.disconnect()
  window.removeEventListener('scroll', handleScroll)
})
</script>

<style>
/* 主题变量以 assets/base.css 为准（Claude 卡其/米色），此处不再覆盖主色 */

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: var(--font-sans);
  color: var(--text-color);
  background: var(--neutral-100);
  font-weight: var(--font-weight-normal);
  line-height: 1.55;
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}

.app-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* Header */
.app-header {
  background: var(--card-bg);
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  z-index: 100;
}

.app-header.scrolled { box-shadow: none; border-bottom-color: var(--neutral-200); }

.header-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 1rem;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left { display: flex; align-items: center; gap: 0.75rem; }

.menu-toggle { display: none; }

.logo-link {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
  color: var(--text-color);
}

.logo-icon {
  width: 32px;
  height: 32px;
  background: var(--primary-soft);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-dark);
}

.logo-text {
  font-size: 1.1rem;
  font-weight: var(--font-weight-medium);
  color: var(--primary-text-color);
  letter-spacing: -0.02em;
}

.header-right { display: flex; align-items: center; gap: 0.75rem; }
.header-btn-link { text-decoration: none; }

.status-tag {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0 0.75rem;
}

.status-icon { font-size: 12px; }

.user-avatar { cursor: pointer; }

.dropdown-header {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Desktop Nav：选项与上下分隔线留白，文字/图标垂直居中 */
.desktop-nav {
  background: var(--card-bg);
  border-bottom: 1px solid var(--border-color);
  padding: 8px 0;
}

.desktop-nav .el-menu {
  max-width: 1400px;
  margin: 0 auto;
  border: none !important;
  display: flex;
  justify-content: center;
  align-items: center;
  height: auto !important;
  background: transparent !important;
}

.desktop-nav .el-menu-item {
  height: 36px !important;
  line-height: 1 !important;
  border-radius: 8px !important;
  margin: 0 4px !important;
  padding: 0 14px !important;
  border-bottom: none !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 6px;
  float: none !important;
  box-sizing: border-box;
}

.desktop-nav .el-menu-item .el-icon {
  margin: 0 !important;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.desktop-nav .el-menu-item span {
  line-height: 1;
  display: inline-flex;
  align-items: center;
}

.desktop-nav .el-menu-item:hover,
.desktop-nav .el-menu-item:focus {
  border-bottom: none !important;
  background: var(--neutral-100) !important;
  color: var(--neutral-800) !important;
}

.desktop-nav .el-menu-item.is-active {
  background: var(--primary-soft) !important;
  color: var(--primary-dark) !important;
  border-bottom: none !important;
  font-weight: var(--font-weight-medium);
}

/* Mobile Drawer */
.mobile-drawer .el-drawer__header { padding: 0; margin: 0; }
.mobile-drawer .el-drawer__body { padding: 0; }
.mobile-drawer .el-drawer__footer { padding: 1rem; border-top: 1px solid var(--border-color); }

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem;
  border-bottom: 1px solid var(--border-color);
}

.drawer-logo {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.25rem;
  font-weight: 500;
  color: var(--primary-color);
}

.drawer-user {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1.25rem 1rem;
  background: linear-gradient(135deg, rgba(166,139,91,0.14) 0%, rgba(212,196,168,0.22) 100%);
}

.drawer-user-info { display: flex; flex-direction: column; gap: 0.25rem; }
.drawer-menu { border: none; }
.drawer-menu .el-menu-item { height: 52px; border-radius: var(--radius-md); margin: 0.25rem 0.5rem; }
.logout-btn { width: 100%; }

/* Main */
.app-main {
  flex: 1;
  padding: 1.5rem;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

/* Footer */
.app-footer {
  text-align: center;
  padding: 1.25rem;
  color: var(--text-secondary);
  font-size: 0.875rem;
  background: var(--card-bg);
  border-top: 1px solid var(--border-color);
}

.footer-divider { margin: 0 0.5rem; opacity: 0.5; }

/* Transitions */
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* Debug Tools */
.debug-tools-container {
  position: fixed;
  bottom: 70px;
  right: 1rem;
  width: 380px;
  max-width: calc(100vw - 2rem);
  z-index: 2000;
  background: var(--card-bg);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
}

.debug-tools-toggle {
  position: fixed;
  bottom: 1rem;
  right: 1rem;
  z-index: 2001;
}

/* 细部覆盖见 main.css；此处只保留布局相关 */
.el-tag { border-radius: 9999px; }

/* Desktop Only */
.desktop-only { display: inline-flex; }

/* Mobile Responsive */
@media (max-width: 768px) {
  .desktop-nav { display: none; }
  .menu-toggle { display: inline-flex; }
  .desktop-only { display: none !important; }
  .logo-text { font-size: 1.1rem; }
  .app-main { padding: 1rem; }
  .header-content { padding: 0 0.75rem; }
  .status-tag { padding: 0 0.5rem; }
}

@media (max-width: 480px) {
  .header-content { height: 52px; }
  .logo-icon { width: 32px; height: 32px; }
  .logo-text { display: none; }
  .app-main { padding: 0.75rem; }
  .app-footer { padding: 1rem; font-size: 0.8rem; }
}
</style>

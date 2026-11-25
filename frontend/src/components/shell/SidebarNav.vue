<template>
  <aside class="fm-sidebar" :class="{ 'is-collapsed': isCollapsed }">
    <div class="fm-sidebar__brand">
      <router-link to="/" class="fm-sidebar__logo" @click="emit('navigate')">
        <span class="fm-sidebar__spark" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
            <path
              d="M12.6 2.5C12.9 6.2 16 7.8 16.5 12.2C17.6 11.2 18.2 9.9 18.4 8.6C20.2 10.7 20.8 13.7 19.6 16.6C18.4 19.6 15.5 21.5 12 21.5C7.6 21.5 4.2 18.1 4.2 13.6C4.2 9.5 7.4 6.6 10.6 3.9C11.3 3.3 12 2.8 12.6 2.5Z"
              fill="currentColor"
            />
          </svg>
        </span>
        <span v-if="!isCollapsed" class="fm-sidebar__wordmark">FireMail</span>
      </router-link>
    </div>

    <nav class="fm-sidebar__nav" aria-label="主导航">
      <div class="fm-sidebar__group">
        <el-tooltip
          v-for="item in mainItems"
          :key="item.to"
          :content="item.label"
          placement="right"
          :disabled="!isCollapsed"
        >
          <router-link
            :to="item.to"
            class="fm-nav-item"
            :class="{ 'is-active': route.meta?.nav === item.nav }"
            @click="emit('navigate')"
          >
            <el-icon :size="16" class="fm-nav-item__icon"><component :is="item.icon" /></el-icon>
            <span v-if="!isCollapsed" class="fm-nav-item__label">{{ item.label }}</span>
            <span
              v-if="item.badge && item.badge > 0"
              class="fm-nav-item__badge fm-mono"
              :class="{ 'is-dot': isCollapsed }"
            >
              {{ isCollapsed ? '' : item.badge }}
            </span>
          </router-link>
        </el-tooltip>
      </div>

      <div v-if="auth.isAdmin" class="fm-sidebar__group">
        <div v-if="!isCollapsed" class="fm-sidebar__section-label">管理</div>
        <div v-else class="fm-sidebar__divider" />
        <el-tooltip
          v-for="item in adminItems"
          :key="item.to"
          :content="item.label"
          placement="right"
          :disabled="!isCollapsed"
        >
          <router-link
            :to="item.to"
            class="fm-nav-item"
            :class="{ 'is-active': route.meta?.nav === item.nav }"
            @click="emit('navigate')"
          >
            <el-icon :size="16" class="fm-nav-item__icon"><component :is="item.icon" /></el-icon>
            <span v-if="!isCollapsed" class="fm-nav-item__label">{{ item.label }}</span>
          </router-link>
        </el-tooltip>
      </div>

      <div class="fm-sidebar__group">
        <div class="fm-sidebar__divider" />
        <el-tooltip content="关于" placement="right" :disabled="!isCollapsed">
          <router-link
            to="/about"
            class="fm-nav-item"
            :class="{ 'is-active': route.meta?.nav === 'about' }"
            @click="emit('navigate')"
          >
            <el-icon :size="16" class="fm-nav-item__icon"><InfoFilled /></el-icon>
            <span v-if="!isCollapsed" class="fm-nav-item__label">关于</span>
          </router-link>
        </el-tooltip>
      </div>
    </nav>

    <div class="fm-sidebar__footer">
      <WsStatusDot :collapsed="isCollapsed" />

      <div class="fm-sidebar__controls" :class="{ 'is-collapsed': isCollapsed }">
        <ThemeToggle />
        <el-tooltip
          v-if="!inDrawer"
          :content="isCollapsed ? '展开侧栏' : '折叠侧栏'"
          placement="right"
        >
          <button
            type="button"
            class="fm-collapse-btn"
            :aria-label="isCollapsed ? '展开侧栏' : '折叠侧栏'"
            @click="ui.toggleSidebar()"
          >
            <el-icon :size="15">
              <Expand v-if="isCollapsed" />
              <Fold v-else />
            </el-icon>
          </button>
        </el-tooltip>
      </div>

      <SidebarUserMenu :collapsed="isCollapsed" @navigate="emit('navigate')" />
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  Odometer,
  Message,
  Search,
  Upload,
  User,
  Setting,
  InfoFilled,
  Fold,
  Expand
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useEmailsStore } from '@/stores/emails'
import { useUiStore } from '@/stores/ui'
import WsStatusDot from './WsStatusDot.vue'
import ThemeToggle from './ThemeToggle.vue'
import SidebarUserMenu from './SidebarUserMenu.vue'

const props = defineProps({
  collapsed: { type: Boolean, default: false },
  inDrawer: { type: Boolean, default: false }
})

const emit = defineEmits(['navigate'])

const route = useRoute()
const auth = useAuthStore()
const emails = useEmailsStore()
const ui = useUiStore()

const isCollapsed = computed(() => !props.inDrawer && props.collapsed)

const mainItems = computed(() => [
  { to: '/', nav: 'home', label: '指挥台', icon: Odometer },
  {
    to: '/emails',
    nav: 'emails',
    label: '邮箱资产',
    icon: Message,
    badge: emails.attentionCount
  },
  { to: '/search', nav: 'search', label: '邮件搜索', icon: Search },
  { to: '/import', nav: 'import', label: '批量导入', icon: Upload }
])

const adminItems = [
  { to: '/admin/users', nav: 'admin-users', label: '用户管理', icon: User },
  { to: '/admin/system', nav: 'admin-system', label: '系统设置', icon: Setting }
]
</script>

<style scoped>
.fm-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--fm-bg-subtle);
  padding: var(--fm-space-4) var(--fm-space-3);
  user-select: none;
}

.fm-sidebar.is-collapsed {
  padding: var(--fm-space-4) var(--fm-space-2);
}

.fm-sidebar__brand {
  display: flex;
  align-items: center;
  height: 36px;
  padding: 0 8px;
  margin-bottom: var(--fm-space-4);
}

.fm-sidebar.is-collapsed .fm-sidebar__brand {
  justify-content: center;
  padding: 0;
}

.fm-sidebar__logo {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: var(--fm-text);
}

.fm-sidebar__spark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--fm-accent);
  flex-shrink: 0;
}

.fm-sidebar__wordmark {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--fm-text);
}

.fm-sidebar__nav {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-4);
}

.fm-sidebar__group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.fm-sidebar__section-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--fm-text-3);
  padding: 4px 10px 6px;
}

.fm-sidebar__divider {
  height: 1px;
  background: var(--fm-border);
  margin: 4px 6px 8px;
}

.fm-nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 32px;
  padding: 0 10px;
  border-radius: var(--fm-radius-sm);
  color: var(--fm-text-2);
  font-size: var(--fm-fs-sm);
  font-weight: 500;
  text-decoration: none;
  transition: background var(--fm-dur-fast) var(--fm-ease), color var(--fm-dur-fast) var(--fm-ease);
}

.fm-sidebar.is-collapsed .fm-nav-item {
  justify-content: center;
  padding: 0;
}

.fm-nav-item:hover {
  background: var(--fm-surface-hover);
  color: var(--fm-text);
}

.fm-nav-item.is-active {
  background: var(--fm-surface);
  color: var(--fm-text);
  box-shadow: var(--fm-shadow-xs);
}

.fm-nav-item.is-active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 2px;
  border-radius: 2px;
  background: var(--fm-accent);
}

.fm-nav-item__icon {
  flex-shrink: 0;
}

.fm-nav-item__label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fm-nav-item__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: var(--fm-radius-pill);
  background: var(--fm-danger-soft);
  color: var(--fm-danger);
  border: 1px solid var(--fm-danger-border);
  font-size: 11px;
  font-weight: 600;
}

.fm-nav-item__badge.is-dot {
  position: absolute;
  top: 4px;
  right: 8px;
  min-width: 7px;
  width: 7px;
  height: 7px;
  padding: 0;
  background: var(--fm-danger);
  border: none;
}

.fm-sidebar__footer {
  margin-top: var(--fm-space-4);
  padding-top: var(--fm-space-3);
  border-top: 1px solid var(--fm-border);
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-2);
}

.fm-sidebar__controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--fm-space-2);
  padding: 0 2px;
}

.fm-sidebar__controls.is-collapsed {
  flex-direction: column;
  padding: 0;
}

.fm-collapse-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--fm-border);
  border-radius: var(--fm-radius-sm);
  background: var(--fm-surface);
  color: var(--fm-text-2);
  cursor: pointer;
  transition: background var(--fm-dur-fast) var(--fm-ease), color var(--fm-dur-fast) var(--fm-ease);
}

.fm-collapse-btn:hover {
  background: var(--fm-surface-hover);
  color: var(--fm-text);
}
</style>

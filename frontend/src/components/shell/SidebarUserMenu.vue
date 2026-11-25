<template>
  <el-dropdown trigger="click" placement="top-start" @command="handleCommand">
    <button
      type="button"
      class="fm-user-trigger"
      :class="{ 'is-collapsed': collapsed }"
      :aria-label="`用户菜单：${username}`"
    >
      <span class="fm-user-trigger__avatar" aria-hidden="true">{{ initial }}</span>
      <template v-if="!collapsed">
        <span class="fm-user-trigger__info">
          <span class="fm-user-trigger__name">{{ username }}</span>
          <span class="fm-user-trigger__role">{{ auth.isAdmin ? '管理员' : '普通用户' }}</span>
        </span>
        <el-icon class="fm-user-trigger__caret" :size="12"><ArrowDown /></el-icon>
      </template>
    </button>

    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="account">
          <el-icon><User /></el-icon>
          <span>账户设置</span>
        </el-dropdown-item>
        <el-dropdown-item v-if="auth.isAdmin" command="system">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-dropdown-item>
        <el-dropdown-item command="debug">
          <el-icon><Tools /></el-icon>
          <span>调试工具</span>
        </el-dropdown-item>
        <el-dropdown-item divided command="logout">
          <el-icon><SwitchButton /></el-icon>
          <span>退出登录</span>
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowDown, User, Setting, Tools, SwitchButton } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

defineProps({
  collapsed: { type: Boolean, default: false }
})

const emit = defineEmits(['navigate'])

const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()

const username = computed(() => auth.currentUser?.username || '用户')
const initial = computed(() => username.value.slice(0, 1).toUpperCase())

async function handleCommand(cmd) {
  if (cmd === 'account') {
    router.push('/account')
    emit('navigate')
    return
  }
  if (cmd === 'system') {
    router.push('/admin/system')
    emit('navigate')
    return
  }
  if (cmd === 'debug') {
    ui.setShowDebugTools(true)
    ui.setDebugDrawerOpen(true)
    emit('navigate')
    return
  }
  if (cmd === 'logout') {
    await auth.logout()
    ElMessage.success('已成功退出登录')
    emit('navigate')
    router.push('/login')
  }
}
</script>

<style scoped>
.fm-user-trigger {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 6px 8px;
  border: 1px solid transparent;
  border-radius: var(--fm-radius-md);
  background: transparent;
  color: var(--fm-text);
  cursor: pointer;
  text-align: left;
  transition: background var(--fm-dur-fast) var(--fm-ease), border-color var(--fm-dur-fast) var(--fm-ease);
}

.fm-user-trigger:hover {
  background: var(--fm-surface-hover);
  border-color: var(--fm-border);
}

.fm-user-trigger.is-collapsed {
  justify-content: center;
  padding: 6px;
}

.fm-user-trigger__avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--fm-primary-soft);
  color: var(--fm-text);
  font-size: var(--fm-fs-xs);
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.fm-user-trigger__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}

.fm-user-trigger__name {
  font-size: var(--fm-fs-sm);
  font-weight: 500;
  color: var(--fm-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fm-user-trigger__role {
  font-size: 11px;
  color: var(--fm-text-3);
}

.fm-user-trigger__caret {
  color: var(--fm-text-3);
  flex-shrink: 0;
}
</style>

<template>
  <header class="fm-mobile-topbar">
    <button
      type="button"
      class="fm-mobile-topbar__menu"
      aria-label="打开导航菜单"
      @click="ui.setMobileNavOpen(true)"
    >
      <el-icon :size="18"><Menu /></el-icon>
    </button>

    <span class="fm-mobile-topbar__title">{{ pageTitle }}</span>

    <WsStatusDot compact />
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Menu } from '@element-plus/icons-vue'
import { useUiStore } from '@/stores/ui'
import WsStatusDot from './WsStatusDot.vue'

const route = useRoute()
const ui = useUiStore()

const pageTitle = computed(() => route.meta?.title || 'FireMail')
</script>

<style scoped>
.fm-mobile-topbar {
  position: sticky;
  top: 0;
  z-index: var(--fm-z-topbar);
  height: var(--fm-topbar-h);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--fm-space-3);
  background: var(--fm-surface);
  border-bottom: 1px solid var(--fm-border);
}

.fm-mobile-topbar__menu {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: var(--fm-radius-sm);
  background: transparent;
  color: var(--fm-text);
  cursor: pointer;
}

.fm-mobile-topbar__menu:hover {
  background: var(--fm-surface-hover);
}

.fm-mobile-topbar__title {
  font-size: var(--fm-fs-md);
  font-weight: 600;
  color: var(--fm-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

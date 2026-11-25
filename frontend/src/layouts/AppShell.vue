<template>
  <div class="fm-shell" :class="{ 'is-collapsed': ui.sidebarCollapsed && !isMobile }">
    <div v-if="!isMobile" class="fm-shell__rail">
      <SidebarNav :collapsed="ui.sidebarCollapsed" />
    </div>

    <div class="fm-shell__body">
      <MobileTopbar v-if="isMobile" />

      <main class="fm-shell__main">
        <div class="fm-shell__container">
          <div v-if="showInitSkeleton" class="fm-shell__skeleton">
            <el-skeleton :rows="6" animated />
          </div>
          <slot v-else />
        </div>
      </main>
    </div>

    <el-drawer
      v-if="isMobile"
      v-model="mobileDrawerOpen"
      direction="ltr"
      :with-header="false"
      size="min(84vw, 300px)"
      class="fm-mobile-nav-drawer"
    >
      <SidebarNav in-drawer @navigate="mobileDrawerOpen = false" />
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useUiStore } from '@/stores/ui'
import { useAuthStore } from '@/stores/auth'
import { useEmailsStore } from '@/stores/emails'
import { useBreakpoint } from '@/composables/useBreakpoint'
import SidebarNav from '@/components/shell/SidebarNav.vue'
import MobileTopbar from '@/components/shell/MobileTopbar.vue'

const ui = useUiStore()
const auth = useAuthStore()
const emails = useEmailsStore()
const { isMobile } = useBreakpoint()

const mobileDrawerOpen = computed({
  get: () => ui.mobileNavOpen,
  set: (v) => ui.setMobileNavOpen(v)
})

const showInitSkeleton = computed(() => auth.isAuthenticated && !auth.initialized)

onMounted(() => {
  if (auth.isAuthenticated && !emails.tokenHealth) {
    emails.fetchTokenStatus()
  }
})
</script>

<style scoped>
.fm-shell {
  display: flex;
  min-height: 100vh;
  background: var(--fm-bg);
}

.fm-shell__rail {
  position: sticky;
  top: 0;
  height: 100vh;
  width: var(--fm-sidebar-w);
  flex-shrink: 0;
  border-right: 1px solid var(--fm-border);
  transition: width var(--fm-dur) var(--fm-ease);
  z-index: var(--fm-z-sidebar);
}

.fm-shell.is-collapsed .fm-shell__rail {
  width: var(--fm-sidebar-w-collapsed);
}

.fm-shell__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.fm-shell__main {
  flex: 1;
  min-width: 0;
}

.fm-shell__container {
  width: 100%;
  max-width: var(--fm-content-max);
  margin: 0 auto;
  padding: var(--fm-content-pad);
}

.fm-shell__skeleton {
  padding: var(--fm-space-6);
  background: var(--fm-surface);
  border: 1px solid var(--fm-border);
  border-radius: var(--fm-radius-lg);
}

:deep(.fm-mobile-nav-drawer .el-drawer__body) {
  padding: 0;
}
</style>

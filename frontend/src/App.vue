<template>
  <el-config-provider :locale="zhCn">
    <component :is="activeLayout">
      <router-view v-slot="{ Component, route: currentRoute }">
        <transition name="fm-page" mode="out-in">
          <component :is="Component" :key="currentRoute.name || currentRoute.path" />
        </transition>
      </router-view>
    </component>
    <DebugToolsDrawer />
  </el-config-provider>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { useAuthStore } from '@/stores/auth'
import AppShell from '@/layouts/AppShell.vue'
import AuthLayout from '@/layouts/AuthLayout.vue'
import BlankLayout from '@/layouts/BlankLayout.vue'
import DebugToolsDrawer from '@/components/shell/DebugToolsDrawer.vue'

const route = useRoute()
const auth = useAuthStore()

const LAYOUTS = {
  app: AppShell,
  auth: AuthLayout,
  blank: BlankLayout
}

const activeLayout = computed(() => {
  if (route.name === 'about' && !auth.isAuthenticated) {
    return BlankLayout
  }
  const key = route.meta?.layout || 'blank'
  return LAYOUTS[key] || BlankLayout
})
</script>

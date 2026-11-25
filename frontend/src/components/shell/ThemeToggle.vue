<template>
  <el-tooltip :content="tooltipText" placement="bottom">
    <button
      type="button"
      class="fm-theme-toggle"
      :aria-label="tooltipText"
      @click="toggle"
    >
      <el-icon :size="16">
        <Sunny v-if="theme === 'light'" />
        <Moon v-else-if="theme === 'dark'" />
        <Monitor v-else />
      </el-icon>
    </button>
  </el-tooltip>
</template>

<script setup>
import { computed } from 'vue'
import { Sunny, Moon, Monitor } from '@element-plus/icons-vue'
import { useTheme } from '@/composables/useTheme'

const { theme, toggle } = useTheme()

const LABELS = {
  light: '当前：亮色主题（点击切换）',
  dark: '当前：暗色主题（点击切换）',
  system: '当前：跟随系统（点击切换）'
}

const tooltipText = computed(() => LABELS[theme.value] || LABELS.system)
</script>

<style scoped>
.fm-theme-toggle {
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
  transition: background var(--fm-dur-fast) var(--fm-ease), color var(--fm-dur-fast) var(--fm-ease), border-color var(--fm-dur-fast) var(--fm-ease);
}

.fm-theme-toggle:hover {
  background: var(--fm-surface-hover);
  color: var(--fm-text);
  border-color: var(--fm-border-strong);
}
</style>

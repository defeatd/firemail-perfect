import { computed } from 'vue'
import { useUiStore } from '@/stores/ui'

export function useTheme() {
  const ui = useUiStore()
  const theme = computed(() => ui.theme)
  const isDark = computed(() => ui.isDark)

  return {
    theme,
    isDark,
    setTheme: ui.setTheme,
    toggle: ui.toggleTheme
  }
}

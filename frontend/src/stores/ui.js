import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

const THEME_KEY = 'fm_theme'
const SIDEBAR_KEY = 'fm_sidebar_collapsed'
const DEBUG_KEY = 'show_debug_tools'
const PAPER_KEY = 'fm_mail_paper'
const PAGE_SIZE_KEY = 'fm_emails_page_size'

let mediaQuery = null
let mediaListenerBound = false

function readString(key, fallback) {
  try {
    return localStorage.getItem(key) || fallback
  } catch (_e) {
    return fallback
  }
}

function readBool(key, fallback) {
  try {
    const val = localStorage.getItem(key)
    if (val === null) return fallback
    return val === 'true'
  } catch (_e) {
    return fallback
  }
}

function readInt(key, fallback) {
  try {
    const val = parseInt(localStorage.getItem(key) || '', 10)
    return Number.isFinite(val) && val > 0 ? val : fallback
  } catch (_e) {
    return fallback
  }
}

export const useUiStore = defineStore('ui', () => {
  const theme = ref(readString(THEME_KEY, 'system'))
  const systemDark = ref(
    typeof window !== 'undefined' &&
      Boolean(window.matchMedia?.('(prefers-color-scheme: dark)').matches)
  )
  const sidebarCollapsed = ref(readBool(SIDEBAR_KEY, false))
  const mobileNavOpen = ref(false)
  const showDebugTools = ref(readBool(DEBUG_KEY, false))
  const debugDrawerOpen = ref(false)
  const mailPaperMode = ref(readBool(PAPER_KEY, true))
  const emailsPageSize = ref(readInt(PAGE_SIZE_KEY, 50))

  const isDark = computed(() =>
    theme.value === 'dark' || (theme.value === 'system' && systemDark.value)
  )

  function applyThemeToDom() {
    if (typeof document === 'undefined') return
    const root = document.documentElement
    if (isDark.value) {
      root.classList.add('dark')
      root.style.colorScheme = 'dark'
    } else {
      root.classList.remove('dark')
      root.style.colorScheme = 'light'
    }
  }

  function initTheme() {
    if (typeof window !== 'undefined' && window.matchMedia && !mediaListenerBound) {
      mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      systemDark.value = mediaQuery.matches
      mediaQuery.addEventListener('change', (e) => {
        systemDark.value = e.matches
        applyThemeToDom()
      })
      mediaListenerBound = true
    }
    applyThemeToDom()
  }

  function setTheme(next) {
    if (!['light', 'dark', 'system'].includes(next)) return
    theme.value = next
    try {
      localStorage.setItem(THEME_KEY, next)
    } catch (_e) {
      // ignore storage quota errors
    }
    applyThemeToDom()
  }

  function toggleTheme() {
    const order = ['light', 'dark', 'system']
    const idx = order.indexOf(theme.value)
    setTheme(order[(idx + 1) % order.length])
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
    try {
      localStorage.setItem(SIDEBAR_KEY, String(sidebarCollapsed.value))
    } catch (_e) {
      // ignore
    }
  }

  function setMobileNavOpen(open) {
    mobileNavOpen.value = Boolean(open)
  }

  function setShowDebugTools(enabled) {
    showDebugTools.value = Boolean(enabled)
    try {
      localStorage.setItem(DEBUG_KEY, String(showDebugTools.value))
    } catch (_e) {
      // ignore
    }
    if (showDebugTools.value) {
      debugDrawerOpen.value = true
    }
  }

  function setDebugDrawerOpen(open) {
    debugDrawerOpen.value = Boolean(open)
  }

  function setMailPaperMode(enabled) {
    mailPaperMode.value = Boolean(enabled)
    try {
      localStorage.setItem(PAPER_KEY, String(mailPaperMode.value))
    } catch (_e) {
      // ignore
    }
  }

  function setEmailsPageSize(size) {
    const num = Number(size)
    if (![20, 50, 100].includes(num)) return
    emailsPageSize.value = num
    try {
      localStorage.setItem(PAGE_SIZE_KEY, String(num))
    } catch (_e) {
      // ignore
    }
  }

  return {
    theme,
    isDark,
    sidebarCollapsed,
    mobileNavOpen,
    showDebugTools,
    debugDrawerOpen,
    mailPaperMode,
    emailsPageSize,
    initTheme,
    setTheme,
    toggleTheme,
    toggleSidebar,
    setMobileNavOpen,
    setShowDebugTools,
    setDebugDrawerOpen,
    setMailPaperMode,
    setEmailsPageSize
  }
})

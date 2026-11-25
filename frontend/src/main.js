import { createApp, watch } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import App from './App.vue'
import router from './router'
import { useUiStore } from './stores/ui'
import { useAuthStore } from './stores/auth'
import { useWsStore } from './stores/ws'
import { useEmailsStore } from './stores/emails'
import { safeGetSession, safeSetSession } from './utils/storage'
import './styles/index.css'

const CHUNK_RELOAD_KEY = 'fm_chunk_reload_ts'
const CHUNK_RELOAD_COOLDOWN_MS = 15000

if (typeof window !== 'undefined') {
  window.addEventListener('vite:preloadError', (event) => {
    const lastTs = Number(safeGetSession(CHUNK_RELOAD_KEY, '0')) || 0
    const now = Date.now()
    if (now - lastTs > CHUNK_RELOAD_COOLDOWN_MS) {
      safeSetSession(CHUNK_RELOAD_KEY, String(now))
      event.preventDefault()
      window.location.reload()
    }
  })
}

const app = createApp(App)
const pinia = createPinia()

app.config.errorHandler = (err, _instance, info) => {
  console.error('[FireMail Vue Error]', info, err)
}

app.use(pinia)
app.use(router)
app.use(ElementPlus)

try {
  const ui = useUiStore()
  const auth = useAuthStore()
  const ws = useWsStore()
  const emails = useEmailsStore()

  ui.initTheme()
  ws.init()
  emails.initWebSocketListeners()
  auth.getConfig().catch(() => {})

  watch(
    () => auth.isAuthenticated,
    (authed) => {
      if (authed) {
        ws.connectIfAuthed()
        if (!auth.initialized) {
          auth.fetchCurrentUser().catch(() => {})
        }
      } else {
        ws.disconnect()
      }
    },
    { immediate: true }
  )
} catch (err) {
  console.error('[FireMail Bootstrap Error]', err)
}

app.mount('#app')

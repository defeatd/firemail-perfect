import { reactive, onUnmounted } from 'vue'
import api from '@/services/api'

export function useCredentials() {
  const cache = new Map()
  const loadingMap = reactive({})

  function resolveId(rowOrId) {
    return typeof rowOrId === 'object' && rowOrId !== null ? rowOrId.id : rowOrId
  }

  function getCached(rowOrId) {
    const id = resolveId(rowOrId)
    return cache.get(id) || null
  }

  function isLoading(rowOrId) {
    const id = resolveId(rowOrId)
    return Boolean(loadingMap[id])
  }

  async function ensureCredentials(rowOrId, { force = false } = {}) {
    const id = resolveId(rowOrId)
    if (id === undefined || id === null) return null

    if (!force && cache.has(id)) {
      return cache.get(id)
    }

    loadingMap[id] = true
    try {
      const data = await api.emails.getPassword(id)
      const normalized = {
        password: data?.password ?? '',
        client_id: data?.client_id ?? '',
        refresh_token: data?.refresh_token ?? '',
        mail_type: data?.mail_type ?? ''
      }
      cache.set(id, normalized)
      return normalized
    } finally {
      loadingMap[id] = false
    }
  }

  function clear() {
    cache.clear()
  }

  onUnmounted(() => {
    clear()
  })

  return {
    ensureCredentials,
    getCached,
    isLoading,
    clear
  }
}

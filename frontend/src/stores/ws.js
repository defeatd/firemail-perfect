import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import websocket from '@/services/websocket'
import { safeGetStorage } from '@/utils/storage'

let wsBindingsInitialized = false

export const useWsStore = defineStore('ws', () => {
  const connected = ref(websocket.isConnected)
  const authenticated = ref(websocket.isAuthenticated)
  const connecting = ref(false)

  const status = computed(() => {
    if (connected.value && authenticated.value) return 'connected'
    if (connecting.value || connected.value) return 'connecting'
    return 'disconnected'
  })

  function init() {
    if (wsBindingsInitialized) return
    wsBindingsInitialized = true

    websocket.onConnect(() => {
      connected.value = true
      authenticated.value = websocket.isAuthenticated
      connecting.value = false
    })

    websocket.onAuthSuccess(() => {
      connected.value = true
      authenticated.value = true
      connecting.value = false
    })

    websocket.onDisconnect(() => {
      connected.value = false
      authenticated.value = false
      connecting.value = false
    })
  }

  function connectIfAuthed() {
    init()
    const token = safeGetStorage('token', null)
    if (!token) return
    if (websocket.isConnected && websocket.isAuthenticated) {
      connected.value = true
      authenticated.value = true
      return
    }
    connecting.value = true
    websocket.connect()
  }

  function reconnect() {
    init()
    connecting.value = true
    websocket.reconnect()
  }

  function disconnect() {
    connecting.value = false
    connected.value = false
    authenticated.value = false
    websocket.disconnect()
  }

  return {
    connected,
    authenticated,
    connecting,
    status,
    init,
    connectIfAuthed,
    reconnect,
    disconnect
  }
})

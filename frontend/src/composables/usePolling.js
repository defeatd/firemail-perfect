import { onMounted, onUnmounted } from 'vue'

export function usePolling(fn, intervalMs = 60000) {
  let timer = null

  function clear() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  function start() {
    clear()
    timer = setInterval(() => {
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
      fn()
    }, intervalMs)
  }

  function handleVisibility() {
    if (typeof document === 'undefined') return
    if (document.visibilityState === 'visible') {
      fn()
      start()
    } else {
      clear()
    }
  }

  onMounted(() => {
    start()
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', handleVisibility)
    }
  })

  onUnmounted(() => {
    clear()
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  })

  return { start, stop: clear }
}

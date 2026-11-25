import { reactive, onUnmounted } from 'vue'
import api from '@/services/api'

const MAX_CONSECUTIVE_ERRORS = 10

export function useDeviceCodeFlow() {
  const state = reactive({
    status: 'idle',
    loading: false,
    sessionId: null,
    userCode: '',
    verificationUri: '',
    verificationUriComplete: '',
    message: '',
    error: '',
    interval: 5,
    expiresIn: 0,
    mode: 'add',
    email: '',
    emailId: null,
    clientId: ''
  })

  let pollTimer = null
  let countdownTimer = null
  let lastRequest = null
  let consecutiveErrors = 0
  let runToken = 0

  function clearTimers() {
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
    if (countdownTimer) {
      clearInterval(countdownTimer)
      countdownTimer = null
    }
  }

  function stop() {
    runToken += 1
    clearTimers()
    state.loading = false
  }

  function startCountdown(token) {
    if (countdownTimer) clearInterval(countdownTimer)
    countdownTimer = setInterval(() => {
      if (token !== runToken || state.status !== 'pending') {
        clearTimers()
        return
      }
      if (state.expiresIn > 0) {
        state.expiresIn -= 1
      }
      if (state.expiresIn <= 0) {
        state.status = 'expired'
        state.message = '授权代码已过期'
        clearTimers()
      }
    }, 1000)
  }

  function schedulePoll(token) {
    if (token !== runToken || state.status !== 'pending') return
    const delayMs = Math.max(Number(state.interval) || 5, 2) * 1000
    pollTimer = setTimeout(() => pollOnce(token), delayMs)
  }

  async function pollOnce(token) {
    if (token !== runToken || !state.sessionId || state.status !== 'pending') return
    try {
      const res = await api.pollDeviceCode(state.sessionId)
      if (token !== runToken) return
      const data = res?.data || res || {}
      consecutiveErrors = 0

      if (data.interval) {
        state.interval = Math.max(Number(data.interval) || 5, 2)
      }
      if (data.message) {
        state.message = data.message
      }

      if (data.status === 'success') {
        state.status = 'success'
        clearTimers()
        return
      }
      if (data.status === 'expired') {
        state.status = 'expired'
        clearTimers()
        return
      }
      if (data.status === 'denied') {
        state.status = 'denied'
        clearTimers()
        return
      }
      if (data.status === 'error') {
        state.status = 'error'
        state.error = data.error || data.message || '授权失败'
        clearTimers()
        return
      }
      schedulePoll(token)
    } catch (err) {
      if (token !== runToken) return
      consecutiveErrors += 1
      if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
        state.status = 'error'
        state.error = err?.response?.data?.error || err?.message || '网络连接连续异常，请重试'
        clearTimers()
        return
      }
      schedulePoll(token)
    }
  }

  async function start(request) {
    stop()
    const token = ++runToken
    lastRequest = { ...request }
    consecutiveErrors = 0

    state.mode = request.mode || 'add'
    state.email = request.email || ''
    state.emailId = request.emailId ?? null
    state.clientId = request.clientId || ''
    state.status = 'idle'
    state.loading = true
    state.sessionId = null
    state.userCode = ''
    state.verificationUri = ''
    state.verificationUriComplete = ''
    state.message = ''
    state.error = ''
    state.expiresIn = 0

    try {
      const payload = {}
      if (state.clientId.trim()) {
        payload.client_id = state.clientId.trim()
      }
      const res =
        state.mode === 'add'
          ? await api.startDeviceCodeAdd({ email: state.email.trim(), ...payload })
          : await api.startEmailDeviceCode(state.emailId, payload)

      if (token !== runToken) return false
      const data = res?.data || res || {}
      if (!data.success || !data.session_id) {
        state.status = 'error'
        state.error = data.error || data.message || '发起 Device Code 授权失败'
        return false
      }

      state.sessionId = data.session_id
      state.userCode = data.user_code || ''
      state.verificationUri = data.verification_uri || 'https://microsoft.com/devicelogin'
      state.verificationUriComplete = data.verification_uri_complete || ''
      state.message = data.message || ''
      state.interval = Math.max(Number(data.interval) || 5, 2)
      state.expiresIn = Math.max(Number(data.expires_in) || 900, 1)
      state.status = 'pending'

      startCountdown(token)
      schedulePoll(token)
      return true
    } catch (err) {
      if (token !== runToken) return false
      state.status = 'error'
      state.error = err?.response?.data?.error || err?.response?.data?.message || err?.message || '发起授权失败'
      return false
    } finally {
      if (token === runToken) {
        state.loading = false
      }
    }
  }

  function restart() {
    if (!lastRequest) return Promise.resolve(false)
    return start(lastRequest)
  }

  onUnmounted(() => {
    stop()
  })

  return {
    state,
    start,
    restart,
    stop
  }
}

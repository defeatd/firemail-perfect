import { safeGetStorage } from '@/utils/storage'

export const MessageTypes = {
  AUTHENTICATE: 'authenticate',
  AUTH_RESULT: 'auth_result',
  CONNECTION_ESTABLISHED: 'connection_established',
  GET_ALL_EMAILS: 'get_all_emails',
  CHECK_EMAILS: 'check_emails',
  DELETE_EMAILS: 'delete_emails',
  ADD_EMAIL: 'add_email',
  GET_MAIL_RECORDS: 'get_mail_records',
  IMPORT_EMAILS: 'import_emails',
  EMAILS_LIST: 'emails_list',
  CHECK_PROGRESS: 'check_progress',
  IMPORT_PROGRESS: 'import_progress',
  EMAILS_IMPORTED: 'emails_imported',
  IMPORT_RESULT: 'import_result',
  EMAILS_DELETED: 'emails_deleted',
  EMAIL_ADDED: 'email_added',
  MAIL_RECORDS: 'mail_records',
  INFO: 'info',
  SUCCESS: 'success',
  WARNING: 'warning',
  ERROR: 'error'
}

export class WebSocketService {
  constructor() {
    this.socket = null
    this.isConnected = false
    this.isAuthenticated = false
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.authFailureCount = 0
    this.maxAuthFailures = 3
    this.reconnectTimeoutId = null
    this.connectTimeoutId = null
    this.authTimeoutId = null
    this.baseDelay = 1000
    this.messageHandlers = {}
    this.connectHandlers = new Set()
    this.disconnectHandlers = new Set()
    this.authSuccessHandlers = new Set()
    this.pendingRequests = []
    this.heartbeatInterval = null
    this.heartbeatTimeout = null
    this.lastHeartbeatReceived = 0
    this.url = this.getWebSocketUrl()
  }

  getWebSocketUrl() {
    if (typeof window === 'undefined') return 'ws://127.0.0.1:8765'
    if (window.WS_URL && typeof window.WS_URL === 'string') {
      if (window.WS_URL.startsWith('ws://') || window.WS_URL.startsWith('wss://')) {
        return window.WS_URL
      }
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.port
        ? `${window.location.hostname}:${window.location.port}`
        : window.location.hostname
      return `${protocol}//${host}${window.WS_URL}`
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.hostname}:8765`
  }

  connect() {
    if (
      this.socket &&
      (this.socket.readyState === WebSocket.CONNECTING ||
        this.socket.readyState === WebSocket.OPEN)
    ) {
      return
    }

    this.clearTimers()
    this.isAuthenticated = false

    const token = safeGetStorage('token', null)
    if (!token) return

    this.url = this.getWebSocketUrl()
    try {
      this.socket = new WebSocket(this.url)
      this.connectTimeoutId = setTimeout(() => {
        if (this.socket && this.socket.readyState !== WebSocket.OPEN) {
          this.socket.close()
        }
      }, 10000)

      this.socket.onopen = () => {
        if (this.connectTimeoutId) {
          clearTimeout(this.connectTimeoutId)
          this.connectTimeoutId = null
        }
        this.isConnected = true
        this.reconnectAttempts = 0
        this.sendAuthMessage(token)
        this.startHeartbeat()
      }

      this.socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          if (message.type === 'heartbeat_response') {
            this.handleHeartbeatResponse()
            return
          }
          this.handleMessage(message)
        } catch (err) {
          console.error('WebSocket 消息解析失败:', err)
        }
      }

      this.socket.onclose = (event) => {
        this.clearTimers()
        this.isConnected = false
        this.isAuthenticated = false
        this.notifyDisconnect()
        if (event.code !== 1000 && this.authFailureCount < this.maxAuthFailures) {
          this.scheduleReconnect()
        }
      }

      this.socket.onerror = () => {
        this.isConnected = false
      }
    } catch (err) {
      console.error('创建 WebSocket 连接失败:', err)
    }
  }

  sendAuthMessage(token) {
    if (!this.isConnected || !this.socket || this.socket.readyState !== WebSocket.OPEN) return
    try {
      this.socket.send(
        JSON.stringify({
          type: MessageTypes.AUTHENTICATE,
          token
        })
      )
    } catch (err) {
      console.error('发送 WebSocket 认证消息失败:', err)
    }
  }

  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.dispatchMessage({
        type: MessageTypes.ERROR,
        message: '无法连接到 WebSocket 服务器，请稍后点击重连'
      })
      return
    }
    if (this.reconnectTimeoutId) clearTimeout(this.reconnectTimeoutId)
    const delay = Math.min(this.baseDelay * Math.pow(2, this.reconnectAttempts), 30000)
    this.reconnectTimeoutId = setTimeout(() => {
      this.reconnectAttempts += 1
      this.connect()
    }, delay)
  }

  send(type, data = {}) {
    if (!this.isConnected) {
      if (type !== MessageTypes.AUTHENTICATE) {
        this.pendingRequests.push({ type, data })
      }
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.connect()
      }
      return false
    }

    if (type !== MessageTypes.AUTHENTICATE && !this.isAuthenticated) {
      this.pendingRequests.push({ type, data })
      return false
    }

    return this.doSend(type, data)
  }

  doSend(type, data = {}) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return false
    try {
      this.socket.send(JSON.stringify({ type, ...data }))
      return true
    } catch (err) {
      console.error('发送 WebSocket 消息失败:', err)
      this.isConnected = false
      this.isAuthenticated = false
      this.scheduleReconnect()
      return false
    }
  }

  flushPendingRequests() {
    if (!this.isAuthenticated || !this.isConnected || this.pendingRequests.length === 0) return
    const queue = this.pendingRequests.splice(0, this.pendingRequests.length)
    queue.forEach((req) => {
      this.doSend(req.type, req.data)
    })
  }

  handleMessage(message) {
    const type = message?.type || 'unknown'

    if (type === MessageTypes.AUTH_RESULT) {
      if (message.success) {
        this.isAuthenticated = true
        this.authFailureCount = 0
        this.notifyAuthSuccess()
        this.notifyConnect()
        this.flushPendingRequests()
      } else {
        this.isAuthenticated = false
        this.authFailureCount += 1
        if (this.authFailureCount >= this.maxAuthFailures) {
          this.pendingRequests = []
          this.dispatchMessage({
            type: MessageTypes.ERROR,
            message: message.message || 'WebSocket 认证失败，请重新登录'
          })
          this.disconnect()
          return
        }
        const token = safeGetStorage('token', null)
        if (token) {
          if (this.authTimeoutId) clearTimeout(this.authTimeoutId)
          this.authTimeoutId = setTimeout(() => this.sendAuthMessage(token), 1000)
        } else {
          this.disconnect()
        }
      }
      return
    }

    if (type === MessageTypes.ERROR && message.message === '请先进行认证') {
      if (!this.isAuthenticated && this.authFailureCount < this.maxAuthFailures) {
        this.authFailureCount += 1
        const token = safeGetStorage('token', null)
        if (token) {
          this.sendAuthMessage(token)
          return
        }
      }
      this.isAuthenticated = false
      this.disconnect()
      this.dispatchMessage(message)
      return
    }

    if (type === MessageTypes.CONNECTION_ESTABLISHED) {
      // 仅在 auth_result 成功时触发一次 notifyConnect，避免重复回调
      return
    }

    this.dispatchMessage(message)
  }

  dispatchMessage(message) {
    const type = message?.type
    const set = this.messageHandlers[type]
    if (!set) return
    set.forEach((handler) => {
      try {
        handler(message)
      } catch (err) {
        console.error(`处理 WebSocket 消息 "${type}" 出错:`, err)
      }
    })
  }

  onMessage(type, handler) {
    if (!this.messageHandlers[type]) {
      this.messageHandlers[type] = new Set()
    }
    this.messageHandlers[type].add(handler)
    return () => this.offMessage(type, handler)
  }

  offMessage(type, handler) {
    const set = this.messageHandlers[type]
    if (!set) return
    if (handler) {
      set.delete(handler)
    } else {
      delete this.messageHandlers[type]
    }
  }

  onConnect(handler) {
    this.connectHandlers.add(handler)
    if (this.isConnected && this.isAuthenticated) {
      handler()
    }
    return () => this.offConnect(handler)
  }

  offConnect(handler) {
    this.connectHandlers.delete(handler)
  }

  onDisconnect(handler) {
    this.disconnectHandlers.add(handler)
    return () => this.offDisconnect(handler)
  }

  offDisconnect(handler) {
    this.disconnectHandlers.delete(handler)
  }

  onAuthSuccess(handler) {
    this.authSuccessHandlers.add(handler)
    if (this.isAuthenticated) {
      handler()
    }
    return () => this.offAuthSuccess(handler)
  }

  offAuthSuccess(handler) {
    this.authSuccessHandlers.delete(handler)
  }

  notifyConnect() {
    if (!this.isAuthenticated) return
    this.connectHandlers.forEach((handler) => {
      try {
        handler()
      } catch (err) {
        console.error('执行 WS connect 回调出错:', err)
      }
    })
  }

  notifyDisconnect() {
    this.disconnectHandlers.forEach((handler) => {
      try {
        handler()
      } catch (err) {
        console.error('执行 WS disconnect 回调出错:', err)
      }
    })
  }

  notifyAuthSuccess() {
    this.authSuccessHandlers.forEach((handler) => {
      try {
        handler()
      } catch (err) {
        console.error('执行 WS authSuccess 回调出错:', err)
      }
    })
  }

  getEmails() {
    return this.send(MessageTypes.GET_ALL_EMAILS)
  }

  checkEmails(emailIds) {
    return this.send(MessageTypes.CHECK_EMAILS, { email_ids: emailIds })
  }

  deleteEmails(emailIds) {
    return this.send(MessageTypes.DELETE_EMAILS, { email_ids: emailIds })
  }

  addEmail(emailData) {
    return this.send(MessageTypes.ADD_EMAIL, emailData)
  }

  getMailRecords(emailId) {
    return this.send(MessageTypes.GET_MAIL_RECORDS, { email_id: emailId })
  }

  startHeartbeat() {
    this.lastHeartbeatReceived = Date.now()
    this.heartbeatInterval = setInterval(() => {
      if (!this.isConnected || !this.socket || this.socket.readyState !== WebSocket.OPEN) return
      try {
        this.socket.send(JSON.stringify({ type: 'heartbeat' }))
        if (this.heartbeatTimeout) clearTimeout(this.heartbeatTimeout)
        this.heartbeatTimeout = setTimeout(() => {
          if (Date.now() - this.lastHeartbeatReceived > 30000) {
            this.disconnect()
            this.connect()
          }
        }, 10000)
      } catch (err) {
        console.error('发送心跳失败:', err)
        this.disconnect()
        this.connect()
      }
    }, 20000)
  }

  handleHeartbeatResponse() {
    this.lastHeartbeatReceived = Date.now()
    if (this.heartbeatTimeout) {
      clearTimeout(this.heartbeatTimeout)
      this.heartbeatTimeout = null
    }
  }

  clearTimers() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }
    if (this.heartbeatTimeout) {
      clearTimeout(this.heartbeatTimeout)
      this.heartbeatTimeout = null
    }
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId)
      this.reconnectTimeoutId = null
    }
    if (this.connectTimeoutId) {
      clearTimeout(this.connectTimeoutId)
      this.connectTimeoutId = null
    }
    if (this.authTimeoutId) {
      clearTimeout(this.authTimeoutId)
      this.authTimeoutId = null
    }
  }

  reconnect() {
    this.disconnect()
    this.reconnectAttempts = 0
    this.authFailureCount = 0
    const token = safeGetStorage('token', null)
    if (token) {
      this.connect()
    }
  }

  disconnect() {
    this.clearTimers()
    this.isConnected = false
    this.isAuthenticated = false
    if (this.socket) {
      const sock = this.socket
      this.socket = null
      try {
        sock.close(1000, '正常关闭')
      } catch (err) {
        console.error('关闭 WebSocket 失败:', err)
      }
    }
  }
}

export default new WebSocketService()

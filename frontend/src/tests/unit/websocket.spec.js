import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { WebSocketService, MessageTypes } from '@/services/websocket'

class FakeWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3
  static instances = []

  constructor(url) {
    this.url = url
    this.readyState = FakeWebSocket.CONNECTING
    this.sent = []
    this.closed = false
    FakeWebSocket.instances.push(this)
  }

  open() {
    this.readyState = FakeWebSocket.OPEN
    this.onopen?.()
  }

  send(payload) {
    this.sent.push(JSON.parse(payload))
  }

  receive(obj) {
    this.onmessage?.({ data: JSON.stringify(obj) })
  }

  close(code = 1000) {
    this.readyState = FakeWebSocket.CLOSED
    this.closed = true
    this.onclose?.({ code })
  }
}

describe('WebSocketService', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
    localStorage.setItem('token', 'fake-jwt-token')
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('registers subscription once and supports clean unsubscribe', () => {
    const ws = new WebSocketService()
    const handler = vi.fn()
    const unsub = ws.onMessage(MessageTypes.EMAILS_LIST, handler)
    ws.onMessage(MessageTypes.EMAILS_LIST, handler)

    ws.handleMessage({ type: MessageTypes.EMAILS_LIST, data: [1, 2] })
    expect(handler).toHaveBeenCalledTimes(1)

    unsub()
    ws.handleMessage({ type: MessageTypes.EMAILS_LIST, data: [3] })
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('queues unauthenticated send() and flushes exactly once after auth_result without duplicate timer resend', () => {
    const ws = new WebSocketService()
    ws.connect()
    const sock = FakeWebSocket.instances[0]
    sock.open()

    // Connected but not yet authenticated
    const result = ws.send(MessageTypes.GET_ALL_EMAILS)
    expect(result).toBe(false)

    // Advancing 5 seconds before auth succeeds must NOT resend the queued request
    vi.advanceTimersByTime(5000)
    const beforeAuthMsgs = sock.sent.filter((m) => m.type === MessageTypes.GET_ALL_EMAILS)
    expect(beforeAuthMsgs).toHaveLength(0)

    // Auth succeeds -> flushes queue exactly once
    sock.receive({ type: MessageTypes.AUTH_RESULT, success: true })
    const afterAuthMsgs = sock.sent.filter((m) => m.type === MessageTypes.GET_ALL_EMAILS)
    expect(afterAuthMsgs).toHaveLength(1)
  })

  it('does not double-trigger onConnect when connection_established arrives alongside auth_result', () => {
    const ws = new WebSocketService()
    const onConnect = vi.fn()
    ws.onConnect(onConnect)
    ws.connect()
    const sock = FakeWebSocket.instances[0]
    sock.open()

    sock.receive({ type: MessageTypes.CONNECTION_ESTABLISHED })
    sock.receive({ type: MessageTypes.AUTH_RESULT, success: true })
    expect(onConnect).toHaveBeenCalledTimes(1)
  })

  it('stops retrying after 3 auth failures and resets counter on manual reconnect()', () => {
    const ws = new WebSocketService()
    const errSpy = vi.fn()
    ws.onMessage(MessageTypes.ERROR, errSpy)
    ws.connect()
    const sock = FakeWebSocket.instances[0]
    sock.open()

    sock.receive({ type: MessageTypes.AUTH_RESULT, success: false, message: 'bad token' })
    vi.advanceTimersByTime(1000)
    sock.receive({ type: MessageTypes.AUTH_RESULT, success: false, message: 'bad token' })
    vi.advanceTimersByTime(1000)
    sock.receive({ type: MessageTypes.AUTH_RESULT, success: false, message: 'bad token' })

    expect(ws.authFailureCount).toBe(3)
    expect(sock.closed).toBe(true)
    expect(errSpy).toHaveBeenCalledTimes(1)

    // Manual reconnect resets counters and opens a fresh socket
    ws.reconnect()
    expect(ws.authFailureCount).toBe(0)
    expect(ws.reconnectAttempts).toBe(0)
    expect(FakeWebSocket.instances).toHaveLength(2)
  })
})

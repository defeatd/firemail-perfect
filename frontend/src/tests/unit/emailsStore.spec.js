import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useEmailsStore, isTerminalCheckProgress } from '@/stores/emails'
import api from '@/services/api'

describe('emails store check_progress lifecycle', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    vi.spyOn(api.emails, 'getAll').mockResolvedValue([])
    vi.spyOn(api.emails, 'getRecords').mockResolvedValue([])
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('classifies starting progress=0 as non-terminal and error progress=0 / progress=100 as terminal', () => {
    expect(isTerminalCheckProgress(0, '正在获取访问令牌...')).toBe(false)
    expect(isTerminalCheckProgress(0, '开始收取邮件')).toBe(false)
    expect(isTerminalCheckProgress(0, '连接服务器中...')).toBe(false)
    expect(isTerminalCheckProgress(20, '正在拉取收件箱')).toBe(false)
    expect(isTerminalCheckProgress(0, '认证失败')).toBe(true)
    expect(isTerminalCheckProgress(0, '')).toBe(true)
    expect(isTerminalCheckProgress(100, '检查完成')).toBe(true)
  })

  it('does not clear processing status when start progress=0 is followed by progress=20', () => {
    const store = useEmailsStore()

    store.handleCheckProgress({
      email_id: 42,
      progress: 0,
      message: '正在获取访问令牌...'
    })
    expect(store.getProcessingStatus(42)).toEqual({
      progress: 0,
      message: '正在获取访问令牌...'
    })

    vi.advanceTimersByTime(200)
    store.handleCheckProgress({
      email_id: 42,
      progress: 20,
      message: '正在读取新邮件'
    })

    // 1100ms after the initial progress=0: must STILL remain active
    vi.advanceTimersByTime(900)
    expect(store.getProcessingStatus(42)).toEqual({
      progress: 20,
      message: '正在读取新邮件'
    })
  })

  it('clears processing status after 1000ms on terminal error progress=0 or completion progress=100', () => {
    const store = useEmailsStore()

    store.handleCheckProgress({
      email_id: 7,
      progress: 0,
      message: 'IMAP 登录失败'
    })
    expect(store.getProcessingStatus(7)).not.toBeNull()

    vi.advanceTimersByTime(1000)
    expect(store.getProcessingStatus(7)).toBeNull()

    store.handleCheckProgress({
      email_id: 8,
      progress: 100,
      message: '收取完成'
    })
    expect(store.getProcessingStatus(8)).not.toBeNull()

    vi.advanceTimersByTime(1000)
    expect(store.getProcessingStatus(8)).toBeNull()
  })

  it('cancels a pending clear timer if new progress arrives for the same email_id', () => {
    const store = useEmailsStore()

    store.handleCheckProgress({
      email_id: 9,
      progress: 0,
      message: '临时异常'
    })

    vi.advanceTimersByTime(400)
    store.handleCheckProgress({
      email_id: 9,
      progress: 35,
      message: '重试拉取中'
    })

    vi.advanceTimersByTime(900)
    expect(store.getProcessingStatus(9)).toEqual({
      progress: 35,
      message: '重试拉取中'
    })
  })
})

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { useImportJob } from '@/composables/useImportJob'
import { MessageTypes } from '@/services/websocket'

function createFakeWs() {
  const handlers = new Map()
  return {
    onMessage: vi.fn((type, fn) => {
      if (!handlers.has(type)) handlers.set(type, new Set())
      handlers.get(type).add(fn)
      return () => handlers.get(type)?.delete(fn)
    }),
    emit(type, payload) {
      handlers.get(type)?.forEach((fn) => fn(payload))
    },
    listenerCount(type) {
      return handlers.get(type)?.size || 0
    }
  }
}

describe('useImportJob', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('aggregates multiple jobs via polling and WS import_progress, stops when all finished', async () => {
    const ws = createFakeWs()
    let pollStep = 0
    const apiClient = {
      getImportJob: vi.fn(async (id) => {
        if (id === 'job-1') {
          return {
            data: {
              id: 'job-1',
              total: 10,
              done: pollStep === 0 ? 4 : 10,
              ok: pollStep === 0 ? 3 : 8,
              need_reauth: pollStep === 0 ? 1 : 2,
              banned: 0,
              failed: 0,
              deferred: 0,
              cancelled: false,
              finished: pollStep > 0,
              results: [{ email_id: 1, email: 'a@o.com', status: 'need_reauth', error_code: 'AADSTS70000', hint: '重授' }]
            }
          }
        }
        return {
          data: {
            id: 'job-2',
            total: 5,
            done: 2,
            ok: 2,
            need_reauth: 0,
            banned: 0,
            failed: 0,
            deferred: 0,
            cancelled: false,
            finished: false,
            results: []
          }
        }
      }),
      cancelImportJob: vi.fn(async () => ({ data: { cancelled: true } }))
    }

    const onFinish = vi.fn()
    const job = useImportJob({ apiClient, wsClient: ws, pollIntervalMs: 2000 })
    job.track(['job-1', 'job-2'], { onFinish })

    await vi.advanceTimersByTimeAsync(0)
    expect(job.summary.value.total).toBe(15)
    expect(job.summary.value.done).toBe(6)
    expect(job.summary.value.finished).toBe(false)
    expect(ws.listenerCount(MessageTypes.IMPORT_PROGRESS)).toBe(1)

    // WS 实时推送 job-2 完成
    ws.emit(MessageTypes.IMPORT_PROGRESS, {
      type: MessageTypes.IMPORT_PROGRESS,
      job_id: 'job-2',
      total: 5,
      done: 5,
      ok: 4,
      need_reauth: 0,
      banned: 0,
      failed: 1,
      deferred: 0,
      cancelled: false,
      finished: true,
      results: [{ email_id: 2, email: 'b@o.com', status: 'failed', error_code: 'timeout', hint: '重试' }]
    })
    expect(job.summary.value.done).toBe(9)
    expect(job.summary.value.finished).toBe(false)

    // 下一次 2s 轮询只查尚未完成的 job-1，并触发全部完成
    pollStep = 1
    apiClient.getImportJob.mockClear()
    await vi.advanceTimersByTimeAsync(2000)

    expect(apiClient.getImportJob).toHaveBeenCalledTimes(1)
    expect(apiClient.getImportJob).toHaveBeenCalledWith('job-1')
    expect(job.summary.value.finished).toBe(true)
    expect(job.summary.value.done).toBe(15)
    expect(job.summary.value.ok).toBe(12)
    expect(job.summary.value.results).toHaveLength(2)
    expect(onFinish).toHaveBeenCalledTimes(1)
    expect(ws.listenerCount(MessageTypes.IMPORT_PROGRESS)).toBe(0)

    // 全部结束后不再继续轮询
    apiClient.getImportJob.mockClear()
    await vi.advanceTimersByTimeAsync(6000)
    expect(apiClient.getImportJob).not.toHaveBeenCalled()
  })

  it('cleans up polling timer and WS listener on component unmount', async () => {
    const ws = createFakeWs()
    const apiClient = {
      getImportJob: vi.fn(async (id) => ({
        data: {
          id,
          total: 10,
          done: 1,
          ok: 1,
          need_reauth: 0,
          banned: 0,
          failed: 0,
          deferred: 0,
          cancelled: false,
          finished: false,
          results: []
        }
      })),
      cancelImportJob: vi.fn()
    }

    let exposed = null
    const Comp = defineComponent({
      setup() {
        exposed = useImportJob({ apiClient, wsClient: ws, pollIntervalMs: 2000 })
        exposed.track(['job-u'])
        return () => h('div')
      }
    })

    const wrapper = mount(Comp)
    await vi.advanceTimersByTimeAsync(0)
    expect(ws.listenerCount(MessageTypes.IMPORT_PROGRESS)).toBe(1)

    wrapper.unmount()
    expect(ws.listenerCount(MessageTypes.IMPORT_PROGRESS)).toBe(0)

    apiClient.getImportJob.mockClear()
    await vi.advanceTimersByTimeAsync(6000)
    expect(apiClient.getImportJob).not.toHaveBeenCalled()
  })
})

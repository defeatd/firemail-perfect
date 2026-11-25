import { ref, computed, onUnmounted, getCurrentInstance } from 'vue'
import api from '@/services/api'
import websocket, { MessageTypes } from '@/services/websocket'

const MAX_AGGREGATED_RESULTS = 1000

export function useImportJob(options = {}) {
  const apiClient = options.apiClient || api
  const wsClient = options.wsClient || websocket
  const pollIntervalMs = options.pollIntervalMs ?? 2000

  const trackedIds = ref([])
  const snapshots = ref({})
  const polling = ref(false)
  const cancelling = ref(false)

  let pollTimer = null
  let wsUnsub = null
  let finishCallback = null
  let finishNotified = false

  const summary = computed(() => {
    const ids = trackedIds.value
    if (ids.length === 0) {
      return {
        hasJobs: false,
        total: 0,
        done: 0,
        ok: 0,
        need_reauth: 0,
        banned: 0,
        failed: 0,
        deferred: 0,
        cancelled: false,
        finished: false,
        percent: 0,
        results: []
      }
    }

    let total = 0
    let done = 0
    let ok = 0
    let needReauth = 0
    let banned = 0
    let failed = 0
    let deferred = 0
    let anyCancelled = false
    let allFinished = true
    const results = []

    for (const id of ids) {
      const snap = snapshots.value[id]
      if (!snap) {
        allFinished = false
        continue
      }
      total += Number(snap.total) || 0
      done += Number(snap.done) || 0
      ok += Number(snap.ok) || 0
      needReauth += Number(snap.need_reauth) || 0
      banned += Number(snap.banned) || 0
      failed += Number(snap.failed) || 0
      deferred += Number(snap.deferred) || 0
      if (snap.cancelled) anyCancelled = true
      if (!snap.finished) allFinished = false
      if (Array.isArray(snap.results) && results.length < MAX_AGGREGATED_RESULTS) {
        const remain = MAX_AGGREGATED_RESULTS - results.length
        results.push(...snap.results.slice(0, remain))
      }
    }

    const percent = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : allFinished ? 100 : 0

    return {
      hasJobs: true,
      total,
      done,
      ok,
      need_reauth: needReauth,
      banned,
      failed,
      deferred,
      cancelled: anyCancelled,
      finished: allFinished,
      percent,
      results
    }
  })

  function cleanupListeners() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    if (wsUnsub) {
      wsUnsub()
      wsUnsub = null
    }
    polling.value = false
  }

  function applySnapshot(snap) {
    const id = snap?.job_id || snap?.id
    if (!id || !trackedIds.value.includes(id)) return

    const existing = snapshots.value[id]
    // 防止乱序旧消息覆盖新进度（若已有 finished 或更大 done 则保留最新）
    if (
      existing &&
      (existing.finished || (!snap.finished && (Number(snap.done) || 0) < (Number(existing.done) || 0)))
    ) {
      return
    }

    snapshots.value = {
      ...snapshots.value,
      [id]: snap
    }

    if (summary.value.hasJobs && summary.value.finished) {
      cleanupListeners()
      if (!finishNotified) {
        finishNotified = true
        if (typeof finishCallback === 'function') {
          finishCallback(summary.value)
        }
      }
    }
  }

  async function pollOnce() {
    const pendingIds = trackedIds.value.filter((id) => !snapshots.value[id]?.finished)
    if (pendingIds.length === 0) {
      cleanupListeners()
      return
    }

    await Promise.all(
      pendingIds.map(async (id) => {
        try {
          const res = await apiClient.getImportJob(id)
          const data = res?.data || res
          if (data) {
            applySnapshot({ ...data, id: data.id || id, job_id: data.job_id || id })
          }
        } catch (err) {
          if (err?.response?.status === 404) {
            applySnapshot({
              id,
              job_id: id,
              total: snapshots.value[id]?.total || 0,
              done: snapshots.value[id]?.done || 0,
              ok: snapshots.value[id]?.ok || 0,
              need_reauth: snapshots.value[id]?.need_reauth || 0,
              banned: snapshots.value[id]?.banned || 0,
              failed: snapshots.value[id]?.failed || 0,
              deferred: snapshots.value[id]?.deferred || 0,
              cancelled: false,
              finished: true,
              results: snapshots.value[id]?.results || []
            })
          }
        }
      })
    )
  }

  function track(jobIds, { onFinish } = {}) {
    cleanupListeners()
    const normalized = Array.from(
      new Set((Array.isArray(jobIds) ? jobIds : [jobIds]).filter((id) => Boolean(id)).map(String))
    )
    trackedIds.value = normalized
    snapshots.value = {}
    finishCallback = onFinish || null
    finishNotified = false

    if (normalized.length === 0) return

    polling.value = true
    if (wsClient && typeof wsClient.onMessage === 'function') {
      wsUnsub = wsClient.onMessage(MessageTypes.IMPORT_PROGRESS, (msg) => {
        applySnapshot(msg)
      })
    }

    pollOnce()
    pollTimer = setInterval(() => {
      pollOnce()
    }, pollIntervalMs)
  }

  async function cancelAll() {
    const pendingIds = trackedIds.value.filter((id) => !snapshots.value[id]?.finished)
    if (pendingIds.length === 0) return false
    cancelling.value = true
    try {
      await Promise.all(
        pendingIds.map((id) => apiClient.cancelImportJob(id).catch(() => null))
      )
      await pollOnce()
      return true
    } finally {
      cancelling.value = false
    }
  }

  function reset() {
    cleanupListeners()
    trackedIds.value = []
    snapshots.value = {}
    finishCallback = null
    finishNotified = false
  }

  if (getCurrentInstance()) {
    onUnmounted(() => {
      cleanupListeners()
    })
  }

  return {
    trackedIds,
    snapshots,
    summary,
    polling,
    cancelling,
    track,
    pollOnce,
    cancelAll,
    reset
  }
}

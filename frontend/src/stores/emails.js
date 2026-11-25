import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { ElNotification } from 'element-plus'
import api from '@/services/api'
import websocket, { MessageTypes } from '@/services/websocket'
import { parseServerUtc } from '@/utils/time'

let wsListenersInitialized = false
const finishTimers = new Map()
const START_PROGRESS_RE = /^(正在|开始|连接)/

export function isTerminalCheckProgress(progress, message) {
  if (progress >= 100) return true
  if (progress === 0) {
    return !START_PROGRESS_RE.test(String(message || '').trim())
  }
  return false
}

function normalizeMailRecords(records) {
  const list = (Array.isArray(records) ? records : []).map((record) => ({
    ...record,
    id: record.id,
    subject: record.subject || '(无主题)',
    sender: record.sender || '(未知发件人)',
    received_time: record.received_time || '',
    content: record.content ?? '(无内容)',
    folder: record.folder || 'INBOX',
    has_attachments: Boolean(record.has_attachments)
  }))

  list.sort((a, b) => {
    const ta = parseServerUtc(a.received_time)?.valueOf() ?? 0
    const tb = parseServerUtc(b.received_time)?.valueOf() ?? 0
    return tb - ta
  })
  return list
}

export const useEmailsStore = defineStore('emails', () => {
  const emails = ref([])
  const loading = ref(false)
  const recordsLoading = ref(false)
  const error = ref(null)
  const selectedEmails = ref([])
  const processingEmails = ref({})
  const currentMailRecords = ref([])
  const currentEmailId = ref(null)
  const tokenHealth = ref(null)
  const tokenKeeper = ref(null)
  const loadedOnce = ref(false)

  const hasSelectedEmails = computed(() => selectedEmails.value.length > 0)
  const selectedEmailsCount = computed(() => selectedEmails.value.length)
  const attentionCount = computed(() => {
    const h = tokenHealth.value
    if (!h) return 0
    return (Number(h.need_reauth) || 0) + (Number(h.expiring_7d) || 0)
  })

  function getEmailById(id) {
    const num = Number(id)
    return emails.value.find((item) => Number(item.id) === num) || null
  }

  function getProcessingStatus(id) {
    return processingEmails.value[id] || null
  }

  function clearProcessingStatus(id) {
    if (finishTimers.has(id)) {
      clearTimeout(finishTimers.get(id))
      finishTimers.delete(id)
    }
    const next = { ...processingEmails.value }
    delete next[id]
    processingEmails.value = next
  }

  function handleCheckProgress(msg) {
    const { email_id: eid, progress, message } = msg || {}
    if (eid === undefined || eid === null) return

    if (finishTimers.has(eid)) {
      clearTimeout(finishTimers.get(eid))
      finishTimers.delete(eid)
    }

    processingEmails.value = {
      ...processingEmails.value,
      [eid]: { progress, message }
    }

    if (isTerminalCheckProgress(progress, message)) {
      const timerId = setTimeout(() => {
        finishTimers.delete(eid)
        clearProcessingStatus(eid)
        fetchEmails().catch(() => {})
        if (Number(currentEmailId.value) === Number(eid)) {
          fetchMailRecords(eid).catch(() => {})
        }
      }, 1000)
      finishTimers.set(eid, timerId)
    }
  }

  function initWebSocketListeners() {
    if (wsListenersInitialized) return
    wsListenersInitialized = true

    websocket.onConnect(() => {
      fetchEmails()
      fetchTokenStatus()
    })

    websocket.onMessage(MessageTypes.EMAILS_LIST, (msg) => {
      if (Array.isArray(msg.data)) {
        emails.value = msg.data
        loadedOnce.value = true
        loading.value = false
      }
    })

    websocket.onMessage(MessageTypes.EMAIL_ADDED, (msg) => {
      ElNotification({
        title: '邮箱添加成功',
        message: msg.message || '新邮箱已添加',
        type: 'success',
        duration: 4000
      })
      refreshAll()
    })

    websocket.onMessage(MessageTypes.EMAILS_DELETED, (msg) => {
      if (Array.isArray(msg.email_ids)) {
        const delSet = new Set(msg.email_ids)
        emails.value = emails.value.filter((item) => !delSet.has(item.id))
        selectedEmails.value = selectedEmails.value.filter((id) => !delSet.has(id))
      }
      fetchTokenStatus()
    })

    websocket.onMessage(MessageTypes.EMAILS_IMPORTED, (msg) => {
      ElNotification({
        title: '批量导入完成',
        message: `成功导入 ${msg.success || 0} 个，失败 ${msg.failed || 0} 个`,
        type: (msg.failed || 0) > 0 ? 'warning' : 'success',
        duration: 5000
      })
      refreshAll()
    })

    websocket.onMessage(MessageTypes.CHECK_PROGRESS, (msg) => {
      handleCheckProgress(msg)
    })

    websocket.onMessage(MessageTypes.MAIL_RECORDS, (msg) => {
      if (Number(msg.email_id) === Number(currentEmailId.value)) {
        currentMailRecords.value = normalizeMailRecords(msg.data)
        recordsLoading.value = false
      }
    })

    const passthrough = [
      [MessageTypes.ERROR, 'error', '系统错误'],
      [MessageTypes.WARNING, 'warning', '提示'],
      [MessageTypes.SUCCESS, 'success', '操作成功'],
      [MessageTypes.INFO, 'info', '通知']
    ]
    passthrough.forEach(([type, level, title]) => {
      websocket.onMessage(type, (msg) => {
        if (!msg?.message) return
        if (type === MessageTypes.ERROR) {
          error.value = msg.message
        }
        ElNotification({
          title,
          message: msg.message,
          type: level,
          duration: type === MessageTypes.ERROR ? 6000 : 4000
        })
      })
    })
  }

  let emailsInflight = null
  let tokenStatusInflight = null

  async function fetchEmails() {
    if (emailsInflight) return emailsInflight
    loading.value = true
    error.value = null
    emailsInflight = api.emails
      .getAll()
      .then((data) => {
        emails.value = Array.isArray(data) ? data : []
        loadedOnce.value = true
        return emails.value
      })
      .catch((err) => {
        error.value = '获取邮箱列表失败'
        throw err
      })
      .finally(() => {
        loading.value = false
        emailsInflight = null
      })
    return emailsInflight
  }

  async function ensureEmailsLoaded() {
    if (!loadedOnce.value || emails.value.length === 0) {
      await fetchEmails()
    }
  }

  async function fetchTokenStatus() {
    if (tokenStatusInflight) return tokenStatusInflight
    tokenStatusInflight = api
      .getTokenKeeperStatus()
      .then((res) => {
        const data = res?.data || res
        if (data?.health) {
          tokenHealth.value = data.health
          tokenKeeper.value = data.keeper || null
        }
        return data
      })
      .catch((err) => {
        console.warn('获取保活状态失败:', err?.message)
        return null
      })
      .finally(() => {
        tokenStatusInflight = null
      })
    return tokenStatusInflight
  }

  async function refreshAll() {
    const [list] = await Promise.all([fetchEmails(), fetchTokenStatus()])
    return list
  }

  async function addEmail(emailData) {
    const response = await api.emails.add(emailData)
    await refreshAll()
    return response.data
  }

  async function updateEmail(id, payload) {
    const clean = { ...payload }
    if (clean.mail_type === 'imap' && 'use_ssl' in clean) {
      clean.use_ssl = Boolean(clean.use_ssl)
    }
    const response = await api.emails.update(id, clean)
    await refreshAll()
    return response.data
  }

  async function toggleRealtime(id, enable) {
    const target = getEmailById(id)
    const prev = target ? Boolean(target.enable_realtime_check) : !enable
    if (target) {
      target.enable_realtime_check = enable ? 1 : 0
    }
    try {
      const response = await api.emails.toggleRealtime(id, enable)
      return response.data
    } catch (err) {
      if (target) {
        target.enable_realtime_check = prev ? 1 : 0
      }
      throw err
    }
  }

  async function deleteEmail(emailId) {
    await api.emails.delete([emailId])
    emails.value = emails.value.filter((item) => item.id !== emailId)
    selectedEmails.value = selectedEmails.value.filter((id) => id !== emailId)
    fetchTokenStatus()
  }

  async function deleteEmails(emailIds) {
    if (!Array.isArray(emailIds) || emailIds.length === 0) return
    await api.emails.delete(emailIds)
    const delSet = new Set(emailIds)
    emails.value = emails.value.filter((item) => !delSet.has(item.id))
    selectedEmails.value = selectedEmails.value.filter((id) => !delSet.has(id))
    fetchTokenStatus()
  }

  async function checkEmail(emailId) {
    try {
      const response = await api.emails.check([emailId])
      if (response.status === 409) {
        return { success: false, message: response.data?.message, status: 'processing' }
      }
      return response.data || { success: true }
    } catch (err) {
      if (err?.response?.status === 409) {
        return { success: false, message: err.response.data?.message, status: 'processing' }
      }
      throw err
    }
  }

  async function checkEmails(emailIds) {
    if (!Array.isArray(emailIds) || emailIds.length === 0) return null
    const response = await api.emails.check(emailIds)
    return response.data
  }

  async function fetchMailRecords(emailId) {
    recordsLoading.value = true
    currentEmailId.value = Number(emailId)
    try {
      const data = await api.emails.getRecords(emailId)
      currentMailRecords.value = normalizeMailRecords(data)
      return currentMailRecords.value
    } catch (err) {
      error.value = '获取邮件记录失败'
      throw err
    } finally {
      recordsLoading.value = false
    }
  }

  async function importEmails({
    data,
    mailType = 'outlook',
    separator = 'auto',
    onDuplicate = 'skip',
    verify = true
  }) {
    const response = await api.importEmails({
      data,
      mail_type: mailType,
      separator,
      on_duplicate: onDuplicate,
      verify
    })
    const result = response.data || response
    const written = (Number(result?.added) || 0) + (Number(result?.updated) || 0)
    if (written > 0 || (Number(result?.success) || 0) > 0) {
      await refreshAll()
    }
    return result
  }

  return {
    emails,
    loading,
    recordsLoading,
    error,
    selectedEmails,
    processingEmails,
    currentMailRecords,
    currentEmailId,
    tokenHealth,
    tokenKeeper,
    hasSelectedEmails,
    selectedEmailsCount,
    attentionCount,
    getEmailById,
    getProcessingStatus,
    handleCheckProgress,
    initWebSocketListeners,
    fetchEmails,
    ensureEmailsLoaded,
    fetchTokenStatus,
    refreshAll,
    addEmail,
    updateEmail,
    toggleRealtime,
    deleteEmail,
    deleteEmails,
    checkEmail,
    checkEmails,
    fetchMailRecords,
    importEmails
  }
})

import { reactive } from 'vue'
import api from '@/services/api'
import { fileKind } from '@/utils/file'

export function useAttachments() {
  const byMailId = reactive({})
  const loadingById = reactive({})
  const errorById = reactive({})

  async function list(mailId, { force = false } = {}) {
    if (!mailId) return []
    if (!force && Array.isArray(byMailId[mailId])) {
      return byMailId[mailId]
    }
    loadingById[mailId] = true
    errorById[mailId] = null
    try {
      const data = await api.mail.attachments(mailId)
      const items = Array.isArray(data) ? data : []
      byMailId[mailId] = items
      return items
    } catch (err) {
      errorById[mailId] = err?.response?.data?.error || '获取附件列表失败'
      throw err
    } finally {
      loadingById[mailId] = false
    }
  }

  async function download(att) {
    const { blob, filename } = await api.mail.downloadAttachment(att.id)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = att.filename || filename || 'attachment'
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  async function preview(att) {
    const { blob, filename } = await api.mail.downloadAttachment(att.id)
    const kind = fileKind(att)
    const resolvedName = att.filename || filename || 'attachment'

    if (kind === 'text') {
      const textContent = await blob.text()
      return {
        kind,
        filename: resolvedName,
        url: null,
        textContent,
        cleanup: () => {}
      }
    }

    const url = URL.createObjectURL(blob)
    return {
      kind,
      filename: resolvedName,
      url,
      textContent: '',
      cleanup: () => URL.revokeObjectURL(url)
    }
  }

  return {
    byMailId,
    loadingById,
    errorById,
    list,
    download,
    preview
  }
}

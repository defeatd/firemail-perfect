import { ElLoading, ElMessage } from 'element-plus'
import api from '@/services/api'

const CONCURRENCY = 4

function formatTimestamp(date = new Date()) {
  const pad = (n) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}_` +
    `${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`
  )
}

function cleanField(value) {
  if (!value || value === '******') return ''
  return String(value).replace(/[\r\n]+/g, '')
}

export function useEmailExport() {
  async function exportTxt(rows) {
    if (!Array.isArray(rows) || rows.length === 0) {
      ElMessage.warning('没有可导出的邮箱')
      return false
    }

    const total = rows.length
    let completed = 0
    const lines = new Array(total)
    const loader = ElLoading.service({
      lock: true,
      text: `正在准备导出 0/${total}`,
      background: 'rgba(0, 0, 0, 0.45)'
    })

    try {
      let cursor = 0
      const worker = async () => {
        while (cursor < total) {
          const idx = cursor++
          const row = rows[idx]
          let creds = null
          try {
            creds = await api.emails.getPassword(row.id)
          } catch (_err) {
            creds = null
          }
          const email = cleanField(row.email)
          const password = cleanField(creds?.password ?? row.password)
          const clientId = cleanField(creds?.client_id ?? row.client_id)
          const refreshToken = cleanField(creds?.refresh_token ?? row.refresh_token)
          lines[idx] = `${email}----${password}----${clientId}----${refreshToken}`
          completed += 1
          loader.setText(`正在准备导出 ${completed}/${total}`)
        }
      }

      const workers = Array.from({ length: Math.min(CONCURRENCY, total) }, () => worker())
      await Promise.all(workers)

      const content = `${lines.join('\n')}\n`
      const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `emails_export_${formatTimestamp()}.txt`
      document.body.appendChild(anchor)
      anchor.click()
      document.body.removeChild(anchor)
      setTimeout(() => URL.revokeObjectURL(url), 1000)

      ElMessage.success(`成功导出 ${total} 个邮箱`)
      return true
    } catch (err) {
      console.error('导出邮箱失败:', err?.message)
      ElMessage.error('导出失败，请稍后重试')
      return false
    } finally {
      loader.close()
    }
  }

  return {
    exportTxt
  }
}

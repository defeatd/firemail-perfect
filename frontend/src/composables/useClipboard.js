import { ElMessage } from 'element-plus'

async function writeClipboard(text, fallbackEl = null) {
  if (!text) return false

  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch (_e) {
      // fall through
    }
  }

  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.setAttribute('readonly', '')
    ta.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;padding:0;border:none;opacity:0;'
    document.body.appendChild(ta)
    ta.focus()
    ta.select()
    ta.setSelectionRange(0, text.length)
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    if (ok) return true
  } catch (_e) {
    // fall through
  }

  if (fallbackEl && window.getSelection && document.createRange) {
    try {
      const range = document.createRange()
      range.selectNodeContents(fallbackEl)
      const sel = window.getSelection()
      sel.removeAllRanges()
      sel.addRange(range)
    } catch (_e) {
      // ignore
    }
  }
  return false
}

export function useClipboard() {
  async function copy(text, label = '', fallbackEl = null) {
    const value = String(text || '')
    if (!value) {
      ElMessage.warning('暂无可复制内容')
      return false
    }
    const ok = await writeClipboard(value, fallbackEl)
    if (ok) {
      ElMessage.success(label ? `已复制${label}` : '已复制到剪贴板')
    } else {
      ElMessage.warning('自动复制失败，请手动复制')
    }
    return ok
  }

  return { copy }
}

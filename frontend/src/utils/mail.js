import DOMPurify from 'dompurify'

const PURIFY_CONFIG = {
  WHOLE_DOCUMENT: false,
  FORBID_TAGS: [
    'script',
    'iframe',
    'object',
    'embed',
    'form',
    'input',
    'button',
    'meta',
    'link',
    'base'
  ],
  FORBID_ATTR: ['srcdoc', 'formaction'],
  ALLOW_DATA_ATTR: false
}

const HTML_HINT_RE = /<(?:html|body|div|p|table|tr|td|img|a|br|span|h[1-6]|ul|ol|li|strong|style)\b/i
const URL_SPLIT_RE = /(https?:\/\/[^\s<>"'`)\]]+)/gi

/**
 * 全仓唯一 DOMPurify 清洗入口。
 * 额外移除任何内联 on* 事件属性与 javascript: 协议链接。
 */
export function sanitizeMailHtml(html) {
  if (!html || typeof html !== 'string') return ''
  return DOMPurify.sanitize(html, PURIFY_CONFIG)
}

/**
 * 将后端多种形态的邮件 content 统一解析为 { html, text }。
 */
export function parseMailContent(mail) {
  if (!mail) return { html: null, text: null }
  let raw = mail.content
  if (raw == null) return { html: null, text: null }

  if (typeof raw === 'string') {
    const trimmed = raw.trim()
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      try {
        const parsed = JSON.parse(trimmed)
        if (parsed && typeof parsed === 'object') {
          raw = parsed
        }
      } catch (_e) {
        // 非 JSON 普通正文
      }
    }
  }

  if (typeof raw === 'object' && raw !== null) {
    const htmlPart =
      typeof raw.html === 'string' && raw.html.trim()
        ? raw.html
        : raw.has_html || raw.content_type === 'text/html'
          ? String(raw.content || '')
          : null
    const textPart =
      typeof raw.text === 'string' && raw.text.trim()
        ? raw.text
        : !htmlPart && raw.content
          ? String(raw.content)
          : null
    return {
      html: htmlPart && htmlPart.trim() ? htmlPart : null,
      text: textPart && textPart.trim() ? textPart : null
    }
  }

  const str = String(raw)
  if (!str.trim()) return { html: null, text: null }
  if (HTML_HINT_RE.test(str)) {
    return { html: str, text: null }
  }
  return { html: null, text: str }
}

/**
 * 基于 DOMParser 安全提取 HTML 纯文本（不执行脚本）。
 */
export function htmlToText(html) {
  if (!html || typeof html !== 'string') return ''
  try {
    const parser = new DOMParser()
    const doc = parser.parseFromString(html, 'text/html')
    doc.querySelectorAll('script, style, noscript').forEach((el) => el.remove())
    return (doc.body?.textContent || '').replace(/\r\n/g, '\n').trim()
  } catch (_e) {
    return html.replace(/<[^>]+>/g, ' ').trim()
  }
}

/**
 * 安全纯文本 URL 分词（供 Vue 模板安全渲染，绝不写 innerHTML / v-html）。
 */
export function tokenizeTextLinks(text) {
  if (!text) return []
  const parts = String(text).split(URL_SPLIT_RE)
  return parts
    .filter((part) => part !== '')
    .map((part) => ({
      text: part,
      isLink: /^https?:\/\//i.test(part)
    }))
}

/**
 * 解析发件人显示名与邮箱地址。
 */
export function parseSender(sender) {
  const raw = String(sender || '').trim()
  if (!raw) return { name: '未知发件人', address: '' }
  const angleMatch = raw.match(/^"?([^"<]+?)"?\s*<([^>]+)>$/)
  if (angleMatch) {
    return {
      name: angleMatch[1].trim() || angleMatch[2].trim(),
      address: angleMatch[2].trim()
    }
  }
  return { name: raw, address: raw.includes('@') ? raw : '' }
}

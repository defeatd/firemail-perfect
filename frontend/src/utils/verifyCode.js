import { htmlToText } from './mail'

const KEYWORD_RE =
  /验证码|校验码|动态码|确认码|安全码|安全代码|一次性|激活码|驗證碼|verification|verify|passcode|security\s+code|one-time|\b(?:code|otp|pin)\b/i

const YEAR_CONTEXT_RE = /年|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december)\b/i
const MONEY_CONTEXT_RE = /[¥$€£￥]|元|\b(?:USD|CNY|RMB|EUR|GBP)\b/i
const ORDER_PREFIX_RE = /(?:订单号?|单号|order(?:\s*(?:id|no\.?|number|#))?|no\.)\s*[:#：]?\s*$/i
const PHONE_CONTEXT_RE = /(?:\+86|tel|phone|手机|电话|热线)\s*[:：-]?\s*$/i

const URL_RE = /https?:\/\/[^\s<>"'`]+|www\.[^\s<>"'`]+/gi
const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g
const HEX_COLOR_RE = /#[0-9a-fA-F]{3,8}\b/g

function cleanForScan(raw) {
  return String(raw || '')
    .replace(URL_RE, ' ')
    .replace(EMAIL_RE, ' ')
    .replace(HEX_COLOR_RE, ' ')
    .replace(/[ \t]+/g, ' ')
}

function collectEmphasizedTokens(html) {
  const emphasized = new Set()
  if (!html || typeof html !== 'string') return emphasized
  try {
    const parser = new DOMParser()
    const doc = parser.parseFromString(html, 'text/html')
    const nodes = doc.querySelectorAll('strong, b, h1, h2, h3, td')
    nodes.forEach((node) => {
      const txt = (node.textContent || '').trim()
      if (!txt || txt.length > 40) return
      const compact = txt.replace(/[ -]/g, '')
      if (/^[A-Z0-9]{4,10}$/.test(compact)) {
        emphasized.add(compact)
      }
      const matches = txt.match(/\b[A-Z0-9]{4,10}\b/g) || []
      matches.forEach((m) => emphasized.add(m))
    })
  } catch (_e) {
    // ignore DOMParser errors
  }
  return emphasized
}

function extractCandidates(cleaned) {
  const found = []
  const pushMatch = (normalized, raw, index) => {
    found.push({ code: normalized, raw, index })
  }

  // (c) 分组 6 位码：123 456 / 123-456
  const groupedRe = /(?<!\d|\d\.|\d-)(\d{3})[ -](\d{3})(?!\d|\.\d|-\d)/g
  let m
  const groupedSpans = []
  while ((m = groupedRe.exec(cleaned)) !== null) {
    pushMatch(`${m[1]}${m[2]}`, m[0], m.index)
    groupedSpans.push([m.index, m.index + m[0].length])
  }

  const insideGrouped = (idx, len) =>
    groupedSpans.some(([s, e]) => idx >= s && idx + len <= e)

  // (a) 4-8 位纯数字（排除小数/连字符编号/超长数字，允许句末标点如 "908172."）
  const digitsRe = /(?<!\d|\d\.|\d-)\d{4,8}(?!\d|\.\d|-\d)/g
  while ((m = digitsRe.exec(cleaned)) !== null) {
    if (!insideGrouped(m.index, m[0].length)) {
      pushMatch(m[0], m[0], m.index)
    }
  }

  // (b) 6-10 位大写字母+数字混合（至少含 1 数字与 1 大写字母）
  const alnumRe = /\b(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{6,10}\b/g
  while ((m = alnumRe.exec(cleaned)) !== null) {
    pushMatch(m[0], m[0], m.index)
  }

  return found
}

function isStandaloneLine(text, index, length) {
  const lineStart = text.lastIndexOf('\n', index) + 1
  const nextNl = text.indexOf('\n', index + length)
  const lineEnd = nextNl === -1 ? text.length : nextNl
  const line = text.slice(lineStart, lineEnd).trim()
  return line.length <= length + 4
}

function scoreCandidate(item, cleaned, subjectHasKw, emphasized, freqMap) {
  const { code, raw, index } = item
  const before = cleaned.slice(Math.max(0, index - 48), index)
  const after = cleaned.slice(index + raw.length, Math.min(cleaned.length, index + raw.length + 48))
  const nearby = `${before}${raw}${after}`
  const shortBefore = cleaned.slice(Math.max(0, index - 16), index)
  const shortAfter = cleaned.slice(index + raw.length, Math.min(cleaned.length, index + raw.length + 10))

  let score = 0
  if (KEYWORD_RE.test(nearby)) score += 6
  if (subjectHasKw) score += 2

  if (/^\d+$/.test(code)) {
    if (code.length === 6) score += 2
    else if (code.length === 4 || code.length === 8) score += 1
  }

  if (emphasized.has(code) || isStandaloneLine(cleaned, index, raw.length)) {
    score += 2
  }

  // 疑似年份 (1900-2099)
  if (/^(?:19|20)\d{2}$/.test(code)) {
    const nearYear = `${shortBefore}${raw}${shortAfter}`
    if (YEAR_CONTEXT_RE.test(nearYear) || /[-/]\s*$/.test(shortBefore) || /^\s*[-/]/.test(shortAfter)) {
      score -= 6
    }
  }

  // 疑似时间（仅当冒号另一侧也是数字，如 10:45，避免误伤 "code: XK7P9Q2M"）
  if (/^\s*:\s*\d/.test(shortAfter) || /\d\s*:\s*$/.test(shortBefore)) {
    score -= 5
  }

  // 疑似金额
  if (MONEY_CONTEXT_RE.test(`${shortBefore.slice(-6)}${shortAfter.slice(0, 6)}`)) {
    score -= 5
  }

  // 疑似电话
  if (PHONE_CONTEXT_RE.test(shortBefore)) {
    score -= 5
  }

  // 疑似订单号
  if (ORDER_PREFIX_RE.test(shortBefore)) {
    score -= 5
  }

  if ((freqMap.get(code) || 0) > 3) {
    score -= 2
  }

  const ctxStart = Math.max(0, index - 24)
  const ctxEnd = Math.min(cleaned.length, index + raw.length + 24)
  const context = cleaned.slice(ctxStart, ctxEnd).replace(/\s+/g, ' ').trim()

  return { code, score, context, index }
}

/**
 * 智能提取邮件中的验证码候选，返回得分 >= 5 的前 3 项。
 */
export function extractVerifyCodes({ subject = '', html = '', text = '' } = {}) {
  const bodyText = html ? htmlToText(html) : String(text || '')
  const combined = `${String(subject || '')}\n${bodyText}`
  const cleaned = cleanForScan(combined)
  if (!cleaned.trim()) return []

  const candidates = extractCandidates(cleaned)
  if (candidates.length === 0) return []

  const subjectHasKw = KEYWORD_RE.test(String(subject || ''))
  const emphasized = collectEmphasizedTokens(html)
  const freqMap = new Map()
  candidates.forEach((c) => {
    freqMap.set(c.code, (freqMap.get(c.code) || 0) + 1)
  })

  const scored = candidates
    .map((c) => scoreCandidate(c, cleaned, subjectHasKw, emphasized, freqMap))
    .filter((c) => c.score >= 5)

  // 同 code 保留最高分与首次出现位置
  const bestByCode = new Map()
  scored.forEach((item) => {
    const prev = bestByCode.get(item.code)
    if (!prev || item.score > prev.score) {
      bestByCode.set(item.code, {
        code: item.code,
        score: item.score,
        context: item.context,
        firstIndex: prev ? Math.min(prev.firstIndex, item.index) : item.index
      })
    }
  })

  return Array.from(bestByCode.values())
    .sort((a, b) => (b.score !== a.score ? b.score - a.score : a.firstIndex - b.firstIndex))
    .slice(0, 3)
    .map(({ code, score, context }) => ({ code, score, context }))
}

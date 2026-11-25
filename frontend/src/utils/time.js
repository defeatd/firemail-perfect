import dayjs from 'dayjs'

/**
 * 解析服务端返回的时间字符串。
 * 后端 SQLite CURRENT_TIMESTAMP 与 token 生命周期字段均为 UTC naive 格式（'YYYY-MM-DD HH:mm:ss'），
 * 缺少时区后缀时按 UTC 解析，再交由 dayjs 转为本地时间展示。
 */
export function parseServerUtc(value) {
  if (!value) return null
  if (value instanceof Date) {
    const d = dayjs(value)
    return d.isValid() ? d : null
  }
  const str = String(value).trim()
  if (!str) return null
  const hasTz = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(str)
  const iso = hasTz ? str : `${str.replace(' ', 'T')}Z`
  const d = dayjs(iso)
  return d.isValid() ? d : null
}

export function formatAbs(value, fmt = 'YYYY-MM-DD HH:mm:ss') {
  const d = parseServerUtc(value)
  return d ? d.format(fmt) : ''
}

export function formatRelative(value, nowMs = Date.now()) {
  const d = parseServerUtc(value)
  if (!d) return ''

  const diffMs = nowMs - d.valueOf()
  if (diffMs < 0) {
    return d.format('YYYY-MM-DD HH:mm')
  }
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return '刚刚'

  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} 分钟前`

  const now = dayjs(nowMs)
  if (d.isSame(now, 'day')) {
    return `今天 ${d.format('HH:mm')}`
  }
  if (d.isSame(now.subtract(1, 'day'), 'day')) {
    return `昨天 ${d.format('HH:mm')}`
  }
  if (d.isSame(now, 'year')) {
    return d.format('MM-DD')
  }
  return d.format('YYYY-MM-DD')
}

export function daysUntil(value, nowMs = Date.now()) {
  const d = parseServerUtc(value)
  if (!d) return null
  return Math.floor((d.valueOf() - nowMs) / 86400000)
}

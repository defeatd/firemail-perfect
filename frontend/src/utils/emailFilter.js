import { daysUntil, parseServerUtc } from './time'

export function countByMailType(list) {
  const counts = { all: list.length, outlook: 0, imap: 0, gmail: 0, qq: 0 }
  list.forEach((row) => {
    if (row.mail_type in counts) counts[row.mail_type] += 1
  })
  return counts
}

export function matchesAuthFilter(row, filter) {
  if (filter === 'all') return true
  if (row.mail_type !== 'outlook') return false
  const status = row.auth_status || 'ok'
  const days = daysUntil(row.refresh_token_expires_at)

  if (filter === 'attention') {
    return ['need_reauth', 'banned', 'error'].includes(status) || (days !== null && days < 15)
  }
  if (filter === 'need_reauth') return status === 'need_reauth'
  if (filter === 'banned') return status === 'banned'
  if (filter === 'error') return status === 'error'
  if (filter === 'pending') return status === 'pending'
  if (filter === 'unverified') return !row.refresh_token_expires_at && status === 'ok'
  if (filter === 'expiring_7d') return status === 'ok' && days !== null && days < 7
  if (filter === 'expiring_15d') return status === 'ok' && days !== null && days < 15
  if (filter === 'ok') {
    return status === 'ok' && Boolean(row.refresh_token_expires_at) && (days === null || days >= 15)
  }
  return true
}

export function filterAndSortEmails(list, { query, typeFilter, authFilter, sort }) {
  const q = String(query || '').trim().toLowerCase()
  const filtered = list.filter((row) => {
    if (typeFilter !== 'all' && row.mail_type !== typeFilter) return false
    if (!matchesAuthFilter(row, authFilter)) return false
    if (q && !String(row.email || '').toLowerCase().includes(q)) return false
    return true
  })

  const { prop, order } = sort || {}
  if (!prop || !order) return filtered
  const dir = order === 'descending' ? -1 : 1

  return [...filtered].sort((a, b) => {
    if (prop === 'email') {
      return (
        String(a.email || '').localeCompare(String(b.email || ''), 'en', { sensitivity: 'base' }) *
        dir
      )
    }
    if (prop === 'last_check_time') {
      const ta = parseServerUtc(a.last_check_time)?.valueOf()
      const tb = parseServerUtc(b.last_check_time)?.valueOf()
      if (!ta && !tb) return 0
      if (!ta) return 1
      if (!tb) return -1
      return (ta - tb) * dir
    }
    if (prop === 'rt_days') {
      const da = a.mail_type === 'outlook' ? daysUntil(a.refresh_token_expires_at) : null
      const db = b.mail_type === 'outlook' ? daysUntil(b.refresh_token_expires_at) : null
      if (da === null && db === null) return 0
      if (da === null) return 1
      if (db === null) return -1
      return (da - db) * dir
    }
    return 0
  })
}

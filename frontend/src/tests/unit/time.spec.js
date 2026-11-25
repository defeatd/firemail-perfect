import { describe, it, expect } from 'vitest'
import { parseServerUtc, formatAbs, formatRelative, daysUntil } from '@/utils/time'

describe('time utils', () => {
  it('parses naive SQLite timestamp as UTC', () => {
    const d = parseServerUtc('2026-05-01 12:30:00')
    expect(d).not.toBeNull()
    expect(d.toISOString()).toBe('2026-05-01T12:30:00.000Z')
  })

  it('preserves explicit timezone offsets and Z suffix', () => {
    const z = parseServerUtc('2026-05-01T12:30:00Z')
    const offset = parseServerUtc('2026-05-01T20:30:00+08:00')
    expect(z.valueOf()).toBe(offset.valueOf())
  })

  it('returns null for empty or invalid input', () => {
    expect(parseServerUtc('')).toBeNull()
    expect(parseServerUtc(null)).toBeNull()
    expect(parseServerUtc('not-a-date')).toBeNull()
  })

  it('formats absolute timestamps with custom format', () => {
    const formatted = formatAbs('2026-05-01T00:00:00Z', 'YYYY')
    expect(formatted).toBe('2026')
    expect(formatAbs(null)).toBe('')
  })

  it('formats relative timestamps across ranges', () => {
    const now = Date.UTC(2026, 4, 10, 12, 0, 0)
    expect(formatRelative(new Date(now - 20 * 1000), now)).toBe('刚刚')
    expect(formatRelative(new Date(now - 15 * 60 * 1000), now)).toBe('15 分钟前')
    expect(formatRelative(new Date(now - 3 * 3600 * 1000), now)).toMatch(/^今天 \d{2}:\d{2}$/)
    expect(formatRelative(new Date(now - 24 * 3600 * 1000), now)).toMatch(/^昨天 \d{2}:\d{2}$/)
    expect(formatRelative(new Date(Date.UTC(2026, 1, 5, 12, 0, 0)), now)).toBe('02-05')
    expect(formatRelative(new Date(Date.UTC(2024, 10, 2, 12, 0, 0)), now)).toBe('2024-11-02')
  })

  it('computes floored daysUntil accurately', () => {
    const now = Date.UTC(2026, 4, 10, 0, 0, 0)
    const in10d = '2026-05-20 12:00:00'
    const past2d = '2026-05-08 12:00:00'
    expect(daysUntil(in10d, now)).toBe(10)
    expect(daysUntil(past2d, now)).toBe(-2)
    expect(daysUntil(null, now)).toBeNull()
  })
})

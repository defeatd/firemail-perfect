import { parseServerUtc, formatAbs, formatRelative, daysUntil } from '@/utils/time'

export function useServerTime() {
  return {
    parseServerUtc,
    formatAbs,
    formatRelative,
    daysUntil
  }
}

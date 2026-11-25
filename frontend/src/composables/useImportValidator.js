import { MAX_IMPORT_ROWS, parseImportText } from '@/utils/importParser'

export function validateImportLines(text, options = {}) {
  const separator = options.separator ?? 'auto'
  const maxRows = options.maxRows ?? MAX_IMPORT_ROWS
  const parsed = parseImportText(text, { separator, maxRows })

  const errors = parsed.invalid.map((item) => ({
    line: item.line,
    email: item.email,
    message: item.error
  }))

  const warnings = parsed.tokenConflicts.map((item) => ({
    line: item.line,
    email: item.email,
    message: '不同邮箱共用同一授权码（疑似复制错位），将跳过'
  }))

  const duplicates = parsed.duplicatesInBatch.map((item) => ({
    line: item.line,
    email: item.email,
    message: '批内重复邮箱，将保留最后一条'
  }))

  const validCount = parsed.rows.length
  return {
    ok: !parsed.overLimit && validCount > 0,
    total: parsed.totalNonEmpty,
    validCount,
    overLimit: parsed.overLimit,
    maxRows,
    errors,
    warnings,
    duplicates
  }
}

export function useImportValidator() {
  return {
    validateLines: validateImportLines
  }
}

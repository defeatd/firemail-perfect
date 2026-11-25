/**
 * 批量导入文本解析器（与 backend/utils/email/import_parser.py 逐条对齐）。
 *
 * 规则：
 * 1. 去除 UTF-8 BOM 与 CR，跳过空行
 * 2. 分隔符：显式指定（非 auto）时直接使用；否则按 ---- -> Tab -> | 取第一个切出 >=3 段的
 * 3. parts[0] 必须是合法邮箱（转小写）
 * 4. 在 parts[1:] 中找第一个 GUID 作为 client_id（位置 g）
 * 5. password：g==1 为空；g==2 为 parts[1]；g>2 用 sep 拼回 parts[1:g]
 * 6. tail = parts[g+1:]：若 len>=2 且 tail[1] 是邮箱，按 5/6 段解析辅助邮箱/密码；否则去尾空段后拼回作为 token
 * 7. 若 g 之后无有效段且 g>=2 且 parts[g-1] 长度>=50，按 token/client_id 对调处理
 * 8. 校验 token != client_id 且 token.length >= 50
 * 9. 批内邮箱去重保留最后一条；不同邮箱共用同一 token 记入 tokenConflicts（不入库）
 * 10. 非空行超过 maxRows 时设 overLimit = true
 */

export const GUID_RE = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/
export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
export const AUTO_SEPARATORS = ['----', '\t', '|']
export const MAX_IMPORT_ROWS = 5000
export const MIN_TOKEN_LEN = 50

export function detectSeparator(line, preferred = null) {
  if (preferred !== null && preferred !== undefined) {
    const pref = String(preferred)
    if (pref && pref.toLowerCase() !== 'auto') {
      return pref
    }
  }
  for (const sep of AUTO_SEPARATORS) {
    if (line.split(sep).length >= 3) {
      return sep
    }
  }
  return ''
}

export function parseImportLine(raw, lineNo, separator = null) {
  const cleaned = String(raw || '')
    .replace(/\ufeff/g, '')
    .replace(/\r/g, '')
    .trim()

  const base = {
    line: lineNo,
    email: '',
    password: '',
    clientId: '',
    refreshToken: '',
    recoveryEmail: '',
    recoveryPassword: '',
    separator: '',
    error: ''
  }

  if (!cleaned) {
    return { ...base, error: '空行' }
  }

  const sep = detectSeparator(cleaned, separator)
  if (!sep) {
    return {
      ...base,
      error: '格式错误：未识别到有效分隔符（至少需要 3 段，默认支持 ---- / Tab / |）'
    }
  }

  const parts = cleaned.split(sep)
  const emailRaw = parts[0].trim().toLowerCase()
  if (!EMAIL_RE.test(emailRaw)) {
    return {
      ...base,
      email: emailRaw,
      separator: sep,
      error: '邮箱格式非法'
    }
  }

  let g = -1
  for (let idx = 1; idx < parts.length; idx += 1) {
    if (GUID_RE.test(parts[idx].trim())) {
      g = idx
      break
    }
  }

  if (g < 0) {
    return {
      ...base,
      email: emailRaw,
      separator: sep,
      error: '未找到合法的 client_id(GUID)'
    }
  }

  const clientId = parts[g].trim()
  let password = ''
  if (g === 1) {
    password = ''
  } else if (g === 2) {
    password = parts[1].trim()
  } else {
    password = parts.slice(1, g).join(sep).trim()
  }

  const tail = parts.slice(g + 1)
  let recoveryEmail = ''
  let recoveryPassword = ''

  const trimmedTail = tail.slice()
  while (trimmedTail.length > 0 && trimmedTail[trimmedTail.length - 1].trim() === '') {
    trimmedTail.pop()
  }

  let token = ''
  if (tail.length >= 2 && EMAIL_RE.test(tail[1].trim())) {
    token = tail[0].trim()
    recoveryEmail = tail[1].trim().toLowerCase()
    recoveryPassword = tail.slice(2).join(sep).trim()
  } else if (trimmedTail.length > 0) {
    token = trimmedTail.join(sep).trim()
  } else if (g >= 2 && parts[g - 1].trim().length >= MIN_TOKEN_LEN) {
    token = parts[g - 1].trim()
    password = parts.slice(1, g - 1).join(sep).trim()
  }

  if (token && token.toLowerCase() === clientId.toLowerCase()) {
    return {
      ...base,
      email: emailRaw,
      password,
      clientId,
      separator: sep,
      error: '授权码不能与 client_id 相同'
    }
  }

  if (token.length < MIN_TOKEN_LEN) {
    return {
      ...base,
      email: emailRaw,
      password,
      clientId,
      separator: sep,
      error: `授权码长度不足 ${MIN_TOKEN_LEN}（实际 ${token.length}）`
    }
  }

  return {
    line: lineNo,
    email: emailRaw,
    password,
    clientId,
    refreshToken: token,
    recoveryEmail,
    recoveryPassword,
    separator: sep,
    error: ''
  }
}

export function parseImportText(text, separatorOrOpts = 'auto', maxRowsArg = MAX_IMPORT_ROWS) {
  let separator = 'auto'
  let maxRows = maxRowsArg
  if (separatorOrOpts && typeof separatorOrOpts === 'object') {
    separator = separatorOrOpts.separator ?? 'auto'
    maxRows = separatorOrOpts.maxRows ?? MAX_IMPORT_ROWS
  } else if (separatorOrOpts !== undefined && separatorOrOpts !== null) {
    separator = separatorOrOpts
  }

  const rawLines = String(text || '').split('\n')
  const nonEmpty = []
  for (let i = 0; i < rawLines.length; i += 1) {
    const cleaned = rawLines[i].replace(/\ufeff/g, '').replace(/\r/g, '').trim()
    if (!cleaned) continue
    nonEmpty.push({ lineNo: i + 1, cleaned })
  }

  const totalNonEmpty = nonEmpty.length
  if (totalNonEmpty > maxRows) {
    return {
      rows: [],
      invalid: [],
      duplicatesInBatch: [],
      tokenConflicts: [],
      totalNonEmpty,
      overLimit: true
    }
  }

  const invalid = []
  const validLines = []
  for (const item of nonEmpty) {
    const parsed = parseImportLine(item.cleaned, item.lineNo, separator)
    if (parsed.error) {
      invalid.push(parsed)
    } else {
      validLines.push(parsed)
    }
  }

  // 批内去重：同一邮箱保留最后一条
  const lastIndexByEmail = new Map()
  validLines.forEach((item, pos) => {
    lastIndexByEmail.set(item.email, pos)
  })

  const duplicatesInBatch = []
  const deduped = []
  validLines.forEach((item, pos) => {
    if (lastIndexByEmail.get(item.email) !== pos) {
      duplicatesInBatch.push(item)
    } else {
      deduped.push(item)
    }
  })

  // 跨邮箱 Token 冲突检测
  const emailsByToken = new Map()
  for (const item of deduped) {
    if (!emailsByToken.has(item.refreshToken)) {
      emailsByToken.set(item.refreshToken, new Set())
    }
    emailsByToken.get(item.refreshToken).add(item.email)
  }

  const tokenConflicts = []
  const rows = []
  for (const item of deduped) {
    if (emailsByToken.get(item.refreshToken).size > 1) {
      tokenConflicts.push(item)
    } else {
      rows.push(item)
    }
  }

  return {
    rows,
    invalid,
    duplicatesInBatch,
    tokenConflicts,
    totalNonEmpty,
    overLimit: false
  }
}

export function buildImportChunks(text, chunkSize = 2000) {
  const lines = String(text || '').split('\n')
  const chunks = []
  let startIdx = 0
  let nonEmptyInChunk = 0

  for (let i = 0; i < lines.length; i += 1) {
    if (lines[i].replace(/\ufeff/g, '').replace(/\r/g, '').trim()) {
      nonEmptyInChunk += 1
    }
    if (nonEmptyInChunk >= chunkSize) {
      chunks.push({
        lineOffset: startIdx,
        text: lines.slice(startIdx, i + 1).join('\n')
      })
      startIdx = i + 1
      nonEmptyInChunk = 0
    }
  }
  if (startIdx < lines.length) {
    const tailText = lines.slice(startIdx).join('\n')
    if (tailText.replace(/\ufeff/g, '').replace(/\r/g, '').trim()) {
      chunks.push({ lineOffset: startIdx, text: tailText })
    }
  }
  return chunks
}

export function createImportAggregate(rawText = '') {
  return {
    job_id: null,
    job_ids: [],
    total: 0,
    added: 0,
    updated: 0,
    skipped: 0,
    invalid: 0,
    warned: 0,
    success: 0,
    failed: 0,
    rows: [],
    rows_truncated: false,
    failed_details: [],
    success_emails: [],
    message: '',
    rawText
  }
}

export function mergeImportChunkResult(agg, res, lineOffset = 0) {
  if (res?.job_id) agg.job_ids.push(res.job_id)
  agg.total += Number(res?.total) || 0
  agg.added += Number(res?.added) || 0
  agg.updated += Number(res?.updated) || 0
  agg.skipped += Number(res?.skipped) || 0
  agg.invalid += Number(res?.invalid) || 0
  agg.warned += Number(res?.warned) || 0
  agg.success += Number(res?.success) || 0
  agg.failed += Number(res?.failed) || 0
  if (res?.rows_truncated) agg.rows_truncated = true

  if (Array.isArray(res?.rows)) {
    for (const row of res.rows) {
      if (agg.rows.length < 1000) {
        agg.rows.push({
          ...row,
          line: row.line ? Number(row.line) + lineOffset : row.line
        })
      } else {
        agg.rows_truncated = true
      }
    }
  }
  if (Array.isArray(res?.failed_details)) {
    for (const item of res.failed_details) {
      if (agg.failed_details.length < 1000) {
        agg.failed_details.push({
          ...item,
          line: item.line ? Number(item.line) + lineOffset : item.line
        })
      }
    }
  }
  if (Array.isArray(res?.success_emails) && agg.success_emails.length < 1000) {
    agg.success_emails.push(...res.success_emails.slice(0, 1000 - agg.success_emails.length))
  }
  agg.job_id = agg.job_ids[0] || null
  agg.message =
    agg.job_ids.length > 0
      ? `入库完成：新增 ${agg.added}，更新 ${agg.updated}，跳过 ${agg.skipped}，无效 ${agg.invalid}，冲突 ${agg.warned}；后台首验已启动`
      : `入库完成：新增 ${agg.added}，更新 ${agg.updated}，跳过 ${agg.skipped}，无效 ${agg.invalid}，冲突 ${agg.warned}`
  return agg
}

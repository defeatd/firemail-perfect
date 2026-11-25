// @vitest-environment node
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect } from 'vitest'
import {
  MAX_IMPORT_ROWS,
  parseImportLine,
  parseImportText
} from '@/utils/importParser'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const fixturePath = path.resolve(
  __dirname,
  '../../../../backend/tests/fixtures/import_parse_cases.json'
)
const fixtures = JSON.parse(fs.readFileSync(fixturePath, 'utf-8'))

describe('importParser shared fixture parity with backend', () => {
  for (const c of fixtures.line_cases) {
    it(`line case: ${c.name}`, () => {
      const parsed = parseImportLine(c.raw, c.line_no, c.separator)
      const exp = c.expect
      if ('error_contains' in exp) {
        expect(parsed.error).toBeTruthy()
        expect(parsed.error).toContain(exp.error_contains)
        expect(parsed.error).not.toContain('M.C512')
      } else {
        expect(parsed.error).toBe(exp.error)
        expect(parsed.email).toBe(exp.email)
        expect(parsed.password).toBe(exp.password)
        expect(parsed.clientId).toBe(exp.client_id)
        expect(parsed.refreshToken).toBe(exp.refresh_token)
        expect(parsed.recoveryEmail).toBe(exp.recovery_email)
        expect(parsed.recoveryPassword).toBe(exp.recovery_password)
        expect(parsed.separator).toBe(exp.separator)
      }
    })
  }

  for (const c of fixtures.text_cases) {
    it(`text case: ${c.name}`, () => {
      const res = parseImportText(c.text, {
        separator: c.separator,
        maxRows: c.max_rows ?? MAX_IMPORT_ROWS
      })
      const exp = c.expect
      expect(res.totalNonEmpty).toBe(exp.total_non_empty)
      expect(res.overLimit).toBe(exp.over_limit)
      if (!exp.over_limit) {
        expect(res.rows.map((r) => r.email)).toEqual(exp.rows_emails)
        expect(res.rows.map((r) => r.line)).toEqual(exp.rows_lines)
        expect(res.invalid.map((r) => r.line)).toEqual(exp.invalid_lines)
        expect(res.duplicatesInBatch.map((r) => r.line)).toEqual(exp.duplicates_lines)
        expect(res.tokenConflicts.map((r) => r.line)).toEqual(exp.conflict_lines)
        if (exp.last_row_password !== undefined) {
          expect(res.rows[res.rows.length - 1].password).toBe(exp.last_row_password)
        }
      }
    })
  }
})

import { describe, it, expect } from 'vitest'
import { validateImportLines } from '@/composables/useImportValidator'

const GUID = '9e5f94bc-e8a4-4e73-b8be-63364c29d753'
const TOK1 = 'M.C512_BAY.0.U.-VALID_TOKEN_ONE_0123456789ABCDEFGHIJKLMNOPQ'
const TOK2 = 'M.C512_BAY.0.U.-VALID_TOKEN_TWO_0123456789ABCDEFGHIJKLMNOPQ'

describe('validateImportLines', () => {
  it('accepts valid 4-part and 3-part lines and ignores blank lines', () => {
    const input = [
      `alice@outlook.com----Pass123----${GUID}----${TOK1}`,
      '',
      '   ',
      `bob@hotmail.com----${GUID}----${TOK2}`
    ].join('\n')

    const res = validateImportLines(input)
    expect(res.ok).toBe(true)
    expect(res.total).toBe(2)
    expect(res.validCount).toBe(2)
    expect(res.errors).toEqual([])
    expect(res.warnings).toEqual([])
    expect(res.duplicates).toEqual([])
  })

  it('allows partial submit (ok=true) when at least one valid line exists', () => {
    const input = [
      `alice@outlook.com----Pass123----${GUID}----${TOK1}`,
      'broken-line-only-two----parts'
    ].join('\n')

    const res = validateImportLines(input)
    expect(res.ok).toBe(true)
    expect(res.total).toBe(2)
    expect(res.validCount).toBe(1)
    expect(res.errors).toHaveLength(1)
    expect(res.errors[0].line).toBe(2)
  })

  it('flags invalid email addresses and missing GUID', () => {
    const res1 = validateImportLines(`not-an-email----Pass123----${GUID}----${TOK1}`)
    expect(res1.ok).toBe(false)
    expect(res1.errors[0].message).toContain('邮箱格式非法')

    const res2 = validateImportLines(`alice@outlook.com----Pass123----not-a-guid----${TOK1}`)
    expect(res2.ok).toBe(false)
    expect(res2.errors[0].message).toContain('GUID')
  })

  it('reports token conflicts as warnings and duplicates in batch', () => {
    const input = [
      `dup@outlook.com----Old----${GUID}----${TOK1}`,
      `dup@outlook.com----New----${GUID}----${TOK1}`,
      `c1@outlook.com----P1----${GUID}----${TOK2}`,
      `c2@outlook.com----P2----${GUID}----${TOK2}`
    ].join('\n')

    const res = validateImportLines(input)
    expect(res.ok).toBe(true)
    expect(res.validCount).toBe(1)
    expect(res.duplicates).toHaveLength(1)
    expect(res.warnings).toHaveLength(2)
  })

  it('returns ok=false for empty input', () => {
    const res = validateImportLines('   \n\n ')
    expect(res.ok).toBe(false)
    expect(res.total).toBe(0)
  })
})

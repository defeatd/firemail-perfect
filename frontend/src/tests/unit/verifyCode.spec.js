import { describe, it, expect } from 'vitest'
import { extractVerifyCodes } from '@/utils/verifyCode'

describe('extractVerifyCodes', () => {
  it('extracts Microsoft Chinese security code', () => {
    const res = extractVerifyCodes({
      subject: 'Microsoft 帐户安全代码',
      text: '请使用以下安全代码验证您的账户：123456。如果您未请求此代码，请忽略。'
    })
    expect(res.length).toBeGreaterThan(0)
    expect(res[0].code).toBe('123456')
  })

  it('extracts GitHub English verification code', () => {
    const res = extractVerifyCodes({
      subject: '[GitHub] Please verify your device',
      text: 'Your verification code: 845273\nEnter this code to continue signing in.'
    })
    expect(res[0].code).toBe('845273')
  })

  it('extracts Chinese 4-digit verification code', () => {
    const res = extractVerifyCodes({
      subject: '登录确认',
      text: '您的验证码为 4821，5 分钟内有效，请勿泄露给他人。'
    })
    expect(res[0].code).toBe('4821')
  })

  it('extracts Notion alphanumeric uppercase code', () => {
    const res = extractVerifyCodes({
      subject: 'Notion login code',
      text: 'Copy and paste this temporary login code: XK7P9Q2M'
    })
    expect(res[0].code).toBe('XK7P9Q2M')
  })

  it('extracts and normalizes grouped 3+3 code', () => {
    const res = extractVerifyCodes({
      subject: 'Your one-time passcode',
      text: 'Enter verification code 123 456 to finish sign-in.'
    })
    expect(res[0].code).toBe('123456')
  })

  it('extracts hyphen-grouped 3-3 code', () => {
    const res = extractVerifyCodes({
      subject: '安全校验码',
      text: '您的动态码为 654-321，请在页面输入。'
    })
    expect(res[0].code).toBe('654321')
  })

  it('does not misclassify order numbers as verification codes', () => {
    const res = extractVerifyCodes({
      subject: '您的订单已发货',
      text: '感谢购买！您的订单号 20251124001 已由快递揽收，另一子单号 884512 正在配货。'
    })
    expect(res).toEqual([])
  })

  it('does not misclassify dates and years', () => {
    const res = extractVerifyCodes({
      subject: '会议通知',
      text: '会议定于 2025 年 11 月 24 日举行，请准时参加。'
    })
    expect(res).toEqual([])
  })

  it('does not misclassify currency amounts', () => {
    const res = extractVerifyCodes({
      subject: '账单明细',
      text: '本期应付金额 ¥1999，另含服务费 $2500 USD。'
    })
    expect(res).toEqual([])
  })

  it('does not misclassify 11-digit phone numbers', () => {
    const res = extractVerifyCodes({
      subject: '联系客服',
      text: '如有疑问请致电 +86 13800138000 联系客服人员。'
    })
    expect(res).toEqual([])
  })

  it('does not misclassify clock times', () => {
    const res = extractVerifyCodes({
      subject: '提醒',
      text: '系统将于 10:45 进行例行维护，预计耗时 30 分钟。'
    })
    expect(res).toEqual([])
  })

  it('returns empty array for emails with no verification code', () => {
    const res = extractVerifyCodes({
      subject: '本周产品更新摘要',
      text: '欢迎阅读本周通讯，我们上线了新的工作台界面与暗色主题。'
    })
    expect(res).toEqual([])
  })

  it('prioritizes code emphasized inside HTML <strong> over plain text candidate', () => {
    const res = extractVerifyCodes({
      subject: 'Security verification code',
      html: '<p>Request ID 445511 received.</p><p>Your verification code is <strong>908172</strong>.</p>'
    })
    expect(res.length).toBeGreaterThanOrEqual(1)
    expect(res[0].code).toBe('908172')
  })

  it('strips URLs, email addresses and hex colors before scanning and caps at 3 deduped results', () => {
    const res = extractVerifyCodes({
      subject: 'OTP verification',
      text: 'See https://example.com/verify/999888 color #123456 mail user1234@example.com. Code 112233, backup code 223344, alt code 334455, extra code 445566, repeat 112233.'
    })
    const codes = res.map((r) => r.code)
    expect(codes).not.toContain('999888')
    expect(codes).not.toContain('123456')
    expect(codes.length).toBeLessThanOrEqual(3)
    expect(new Set(codes).size).toBe(codes.length)
  })
})

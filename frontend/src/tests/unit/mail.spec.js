import { describe, it, expect } from 'vitest'
import {
  sanitizeMailHtml,
  parseMailContent,
  htmlToText,
  tokenizeTextLinks,
  parseSender
} from '@/utils/mail'

describe('mail utils', () => {
  it('strips script, iframe, form, on* handlers, srcdoc and javascript URLs', () => {
    const dirty = [
      '<div onclick="alert(1)" style="color:red">Hello</div>',
      '<script>alert("xss")</script>',
      '<iframe src="https://evil.test" srcdoc="<script>1</script>"></iframe>',
      '<img src="x" onerror="alert(2)">',
      '<a href="javascript:alert(3)">click</a>',
      '<form action="/steal"><input name="p"><button formaction="/x">Go</button></form>'
    ].join('')

    const clean = sanitizeMailHtml(dirty)
    expect(clean).toContain('Hello')
    expect(clean.toLowerCase()).not.toContain('<script')
    expect(clean.toLowerCase()).not.toContain('<iframe')
    expect(clean.toLowerCase()).not.toContain('<form')
    expect(clean.toLowerCase()).not.toContain('onclick')
    expect(clean.toLowerCase()).not.toContain('onerror')
    expect(clean.toLowerCase()).not.toContain('srcdoc')
    expect(clean.toLowerCase()).not.toContain('javascript:')
  })

  it('parses plain text, HTML string, JSON string and object mail content', () => {
    expect(parseMailContent({ content: 'Plain hello world' })).toEqual({
      html: null,
      text: 'Plain hello world'
    })

    expect(parseMailContent({ content: '<p>Hello <b>HTML</b></p>' })).toEqual({
      html: '<p>Hello <b>HTML</b></p>',
      text: null
    })

    expect(
      parseMailContent({ content: JSON.stringify({ html: '<div>Hi</div>', text: 'Hi' }) })
    ).toEqual({
      html: '<div>Hi</div>',
      text: 'Hi'
    })

    expect(
      parseMailContent({ content: { has_html: true, content: '<table><tr><td>1</td></tr></table>' } })
    ).toEqual({
      html: '<table><tr><td>1</td></tr></table>',
      text: null
    })
  })

  it('converts HTML to plain text stripping script and style blocks', () => {
    const text = htmlToText('<style>.a{color:red}</style><script>x()</script><p>Hello <b>World</b></p>')
    expect(text).toBe('Hello World')
  })

  it('tokenizes URLs in plain text without producing raw HTML', () => {
    const tokens = tokenizeTextLinks('Visit https://example.com/a?b=1 now!')
    expect(tokens).toEqual([
      { text: 'Visit ', isLink: false },
      { text: 'https://example.com/a?b=1', isLink: true },
      { text: ' now!', isLink: false }
    ])
  })

  it('parses sender display name and address', () => {
    expect(parseSender('"GitHub" <noreply@github.com>')).toEqual({
      name: 'GitHub',
      address: 'noreply@github.com'
    })
    expect(parseSender('ops@outlook.com')).toEqual({
      name: 'ops@outlook.com',
      address: 'ops@outlook.com'
    })
  })
})

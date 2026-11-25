export const MAIL_TYPES = [
  { value: 'outlook', label: 'Outlook / Hotmail' },
  { value: 'imap', label: 'IMAP' },
  { value: 'gmail', label: 'Gmail' },
  { value: 'qq', label: 'QQ 邮箱' }
]

export function getMailTypeLabel(type) {
  const found = MAIL_TYPES.find((item) => item.value === (type || 'outlook'))
  return found ? found.label : String(type || 'outlook')
}

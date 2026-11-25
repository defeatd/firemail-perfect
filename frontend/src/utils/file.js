export function formatFileSize(bytes) {
  if (bytes == null || Number.isNaN(Number(bytes))) return '—'
  const num = Number(bytes)
  if (num <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const idx = Math.min(Math.floor(Math.log(num) / Math.log(1024)), units.length - 1)
  return `${parseFloat((num / Math.pow(1024, idx)).toFixed(2))} ${units[idx]}`
}

const EXT_KIND_MAP = {
  image: ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico', 'avif'],
  pdf: ['pdf'],
  text: ['txt', 'md', 'json', 'csv', 'xml', 'log', 'yaml', 'yml', 'ini', 'html', 'htm', 'eml'],
  audio: ['mp3', 'wav', 'ogg', 'm4a', 'flac', 'aac'],
  video: ['mp4', 'webm', 'mov', 'mkv', 'avi'],
  archive: ['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz'],
  office: ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods']
}

export function fileKind(att) {
  const ct = String(att?.content_type || '').toLowerCase()
  if (ct.startsWith('image/')) return 'image'
  if (ct === 'application/pdf') return 'pdf'
  if (ct.startsWith('text/') || ct === 'application/json' || ct === 'application/xml') return 'text'
  if (ct.startsWith('audio/')) return 'audio'
  if (ct.startsWith('video/')) return 'video'

  const name = String(att?.filename || '').toLowerCase()
  const ext = name.includes('.') ? name.split('.').pop() : ''
  for (const [kind, exts] of Object.entries(EXT_KIND_MAP)) {
    if (exts.includes(ext)) return kind
  }
  return 'other'
}

export function isPreviewableKind(kind) {
  return ['image', 'pdf', 'text', 'audio', 'video'].includes(kind)
}

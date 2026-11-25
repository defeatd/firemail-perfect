<template>
  <div class="fm-mail-body" :class="{ 'fm-mail-body--paper': paper && Boolean(html) }">
    <iframe
      v-if="html"
      ref="iframeRef"
      class="fm-mail-body__iframe"
      title="邮件正文"
      sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
      referrerpolicy="no-referrer"
      :srcdoc="iframeSrcdoc"
      :style="{ height: `${iframeHeight}px` }"
      @load="handleIframeLoad"
    />

    <pre v-else-if="text" class="fm-mail-body__text"><template v-for="(seg, idx) in textSegments" :key="idx"><a
      v-if="seg.isLink"
      :href="seg.text"
      target="_blank"
      rel="noopener noreferrer"
      class="fm-mail-body__link"
    >{{ seg.text }}</a><template v-else>{{ seg.text }}</template></template></pre>

    <div v-else class="fm-mail-body__empty">(无正文内容)</div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { sanitizeMailHtml, tokenizeTextLinks } from '@/utils/mail'
import { useTheme } from '@/composables/useTheme'

const props = defineProps({
  html: { type: String, default: null },
  text: { type: String, default: null },
  paper: { type: Boolean, default: true }
})

const { isDark } = useTheme()
const iframeRef = ref(null)
const iframeHeight = ref(240)
let resizeObserver = null

const sanitizedHtml = computed(() => sanitizeMailHtml(props.html || ''))
const textSegments = computed(() => tokenizeTextLinks(props.text || ''))

function readCssVar(name, fallback) {
  if (typeof window === 'undefined') return fallback
  const val = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return val || fallback
}

const iframeSrcdoc = computed(() => {
  // Touch isDark so theme switches recompute theme-following iframe colors
  const darkFlag = isDark.value
  let bodyColors
  let schemeMeta
  if (props.paper) {
    /* MailBody paper mode hex colors explicitly permitted per Contract §8.3 */
    bodyColors = 'background:#ffffff;color:#1a1a1a;'
    schemeMeta = 'light'
  } else {
    const surfaceCol = readCssVar('--fm-surface', darkFlag ? 'rgb(20,22,26)' : 'rgb(255,255,255)')
    const textCol = readCssVar('--fm-text', darkFlag ? 'rgb(237,237,239)' : 'rgb(24,24,27)')
    bodyColors = `background:${surfaceCol};color:${textCol};`
    schemeMeta = darkFlag ? 'dark' : 'light'
  }
  const linkCol = readCssVar('--fm-accent', 'rgb(234,88,12)')
  const fontStack = readCssVar('--fm-font-sans', 'sans-serif')

  return [
    '<!doctype html>',
    `<html><head><meta charset="utf-8"><meta name="color-scheme" content="${schemeMeta}"><base target="_blank">`,
    '<style>',
    `html,body{margin:0;padding:0;${bodyColors}font-family:${fontStack};font-size:14px;line-height:1.65;overflow-wrap:break-word;}`,
    'img{max-width:100%;height:auto;}',
    `a{color:${linkCol};}`,
    'pre,code{white-space:pre-wrap;word-break:break-word;max-width:100%;}',
    'blockquote{margin:12px 0;padding-left:12px;border-left:2px solid currentColor;opacity:0.78;}',
    '</style></head><body>',
    sanitizedHtml.value,
    '</body></html>'
  ].join('')
})

function disconnectObserver() {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
}

function measureIframe() {
  const el = iframeRef.value
  const doc = el?.contentDocument
  if (!doc) return
  const docHeight = Math.max(
    doc.documentElement?.scrollHeight || 0,
    doc.body?.scrollHeight || 0,
    120
  )
  iframeHeight.value = docHeight + 8
}

function handleIframeLoad() {
  disconnectObserver()
  measureIframe()
  const docEl = iframeRef.value?.contentDocument?.documentElement
  if (docEl && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => measureIframe())
    resizeObserver.observe(docEl)
  }
}

watch(
  () => props.html,
  () => {
    iframeHeight.value = 240
  }
)

onUnmounted(() => {
  disconnectObserver()
})
</script>

<style scoped>
.fm-mail-body {
  width: 100%;
  min-width: 0;
}

.fm-mail-body--paper {
  background: var(--fm-paper);
  color: var(--fm-paper-text);
  border: 1px solid var(--fm-border);
  border-radius: var(--fm-radius-lg);
  box-shadow: var(--fm-shadow-sm);
  padding: var(--fm-space-6);
}

.fm-mail-body__iframe {
  display: block;
  width: 100%;
  border: none;
  background: transparent;
}

.fm-mail-body__text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--fm-font-sans);
  font-size: var(--fm-fs-md);
  line-height: 1.68;
  color: var(--fm-text);
}

.fm-mail-body__link {
  color: var(--fm-accent);
  text-decoration: underline;
  word-break: break-all;
}

.fm-mail-body__empty {
  color: var(--fm-text-3);
  font-size: var(--fm-fs-sm);
  padding: var(--fm-space-4) 0;
}
</style>

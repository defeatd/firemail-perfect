<template>
  <article
    class="fm-mail-item"
    :class="{ 'is-selected': selected }"
    role="option"
    :aria-selected="selected"
    @click="$emit('select', mail)"
  >
    <div class="fm-mail-item__top">
      <span class="fm-mail-item__sender">{{ senderInfo.name }}</span>
      <span class="fm-mail-item__time fm-mono">
        {{ formatRelative(mail.received_time) || '—' }}
      </span>
    </div>

    <div class="fm-mail-item__subject">
      <template v-for="(seg, idx) in subjectSegments" :key="idx">
        <mark v-if="seg.match" class="fm-hl">{{ seg.text }}</mark>
        <span v-else>{{ seg.text }}</span>
      </template>
    </div>

    <div class="fm-mail-item__bottom">
      <p class="fm-mail-item__snippet">
        <template v-for="(seg, idx) in snippetSegments" :key="idx">
          <mark v-if="seg.match" class="fm-hl">{{ seg.text }}</mark>
          <span v-else>{{ seg.text }}</span>
        </template>
      </p>
      <div class="fm-mail-item__badges">
        <el-icon v-if="mail.has_attachments" :size="13" class="fm-mail-item__attach" title="包含附件">
          <Paperclip />
        </el-icon>
        <VerifyCodeChips
          mini
          :subject="mail.subject"
          :html="parsed.html || ''"
          :text="parsed.text || ''"
        />
      </div>
    </div>

    <div v-if="showEmailBadge" class="fm-mail-item__meta-row">
      <button
        v-if="mail.email_address"
        type="button"
        class="fm-mail-item__chip fm-mono"
        title="跳转到此邮箱"
        @click.stop="$emit('click-email', mail)"
      >
        {{ mail.email_address }}
      </button>
      <button
        v-if="senderInfo.address"
        type="button"
        class="fm-mail-item__chip"
        title="按此发件人搜索"
        @click.stop="$emit('click-sender', senderInfo.address)"
      >
        搜发件人
      </button>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { Paperclip } from '@element-plus/icons-vue'
import { formatRelative } from '@/utils/time'
import { parseMailContent, htmlToText, parseSender } from '@/utils/mail'
import VerifyCodeChips from './VerifyCodeChips.vue'

const props = defineProps({
  mail: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  highlightQuery: { type: String, default: '' },
  showEmailBadge: { type: Boolean, default: false }
})

defineEmits(['select', 'click-sender', 'click-email'])

const parsed = computed(() => parseMailContent(props.mail))
const senderInfo = computed(() => parseSender(props.mail.sender))

const snippetText = computed(() => {
  const plain = parsed.value.text || htmlToText(parsed.value.html || '')
  const collapsed = plain.replace(/\s+/g, ' ').trim()
  if (!collapsed) return '(无正文预览)'
  return collapsed.length > 90 ? `${collapsed.slice(0, 90)}…` : collapsed
})

function splitHighlight(text, query) {
  const source = String(text || '')
  const q = String(query || '').trim()
  if (!q) return [{ text: source, match: false }]
  const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp(`(${escaped})`, 'gi')
  return source
    .split(re)
    .filter((p) => p !== '')
    .map((p) => ({ text: p, match: p.toLowerCase() === q.toLowerCase() }))
}

const subjectSegments = computed(() =>
  splitHighlight(props.mail.subject || '(无主题)', props.highlightQuery)
)

const snippetSegments = computed(() =>
  splitHighlight(snippetText.value, props.highlightQuery)
)
</script>

<style scoped>
.fm-mail-item {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--fm-border);
  cursor: pointer;
  transition: background var(--fm-dur-fast) var(--fm-ease);
}

.fm-mail-item:hover {
  background: var(--fm-surface-hover);
}

.fm-mail-item.is-selected {
  background: var(--fm-surface-active);
}

.fm-mail-item.is-selected::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--fm-accent);
}

.fm-mail-item__top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--fm-space-2);
}

.fm-mail-item__sender {
  font-size: var(--fm-fs-sm);
  font-weight: 600;
  color: var(--fm-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fm-mail-item__time {
  font-size: 11px;
  color: var(--fm-text-3);
  white-space: nowrap;
  flex-shrink: 0;
}

.fm-mail-item__subject {
  font-size: var(--fm-fs-sm);
  color: var(--fm-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fm-mail-item__bottom {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 8px;
}

.fm-mail-item__snippet {
  margin: 0;
  flex: 1;
  min-width: 0;
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.fm-mail-item__badges {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
}

.fm-mail-item__attach {
  color: var(--fm-text-3);
}

.fm-mail-item__meta-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

.fm-mail-item__chip {
  padding: 2px 6px;
  border-radius: var(--fm-radius-xs);
  border: 1px solid var(--fm-border);
  background: var(--fm-bg-subtle);
  color: var(--fm-text-2);
  font-size: 11px;
  cursor: pointer;
}

.fm-mail-item__chip:hover {
  border-color: var(--fm-border-strong);
  color: var(--fm-text);
}

.fm-hl {
  background: var(--fm-accent-soft);
  color: var(--fm-accent);
  border-radius: 2px;
  padding: 0 2px;
}
</style>

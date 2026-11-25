<template>
  <section v-if="mail" class="fm-reader">
    <header class="fm-reader__header">
      <div class="fm-reader__top-row">
        <el-button
          v-if="showBack"
          size="small"
          @click="$emit('back')"
        >
          <el-icon><ArrowLeft /></el-icon>
          <span>返回列表</span>
        </el-button>

        <div class="fm-reader__toolbar">
          <el-tooltip
            v-if="parsed.html"
            :content="ui.mailPaperMode ? '当前：白纸阅读模式（点击跟随主题）' : '当前：跟随主题模式（点击切换白纸）'"
            placement="top"
          >
            <el-button
              size="small"
              :aria-label="ui.mailPaperMode ? '切换跟随主题' : '切换纸张模式'"
              @click="ui.setMailPaperMode(!ui.mailPaperMode)"
            >
              <span>{{ ui.mailPaperMode ? '☀ 纸张' : '◐ 跟随主题' }}</span>
            </el-button>
          </el-tooltip>

          <el-tooltip v-if="parsed.html" content="在新窗口打开清洗后的正文" placement="top">
            <el-button
              size="small"
              aria-label="新窗口打开"
              @click="openInNewTab"
            >
              <el-icon><Link /></el-icon>
              <span>新窗口</span>
            </el-button>
          </el-tooltip>

          <el-tooltip content="复制正文纯文本" placement="top">
            <el-button
              size="small"
              aria-label="复制纯文本"
              @click="copyPlainText"
            >
              <el-icon><CopyDocument /></el-icon>
              <span>复制文本</span>
            </el-button>
          </el-tooltip>
        </div>
      </div>

      <h2 class="fm-reader__subject">{{ mail.subject || '(无主题)' }}</h2>

      <div class="fm-reader__sender-row">
        <span class="fm-reader__avatar" aria-hidden="true">{{ senderInitial }}</span>
        <div class="fm-reader__sender-info">
          <div class="fm-reader__sender-main">
            <span class="fm-reader__sender-name">{{ senderInfo.name }}</span>
            <button
              v-if="showSearchLinks && senderInfo.address"
              type="button"
              class="fm-reader__link-chip fm-mono"
              title="按此发件人搜索"
              @click="$emit('click-sender', senderInfo.address)"
            >
              &lt;{{ senderInfo.address }}&gt;
            </button>
            <span v-else-if="senderInfo.address" class="fm-reader__sender-addr fm-mono">
              &lt;{{ senderInfo.address }}&gt;
            </span>
          </div>

          <div class="fm-reader__meta">
            <el-tooltip
              v-if="mail.received_time"
              :content="formatRelative(mail.received_time)"
              placement="top"
            >
              <span class="fm-mono">{{ formatAbs(mail.received_time) }}</span>
            </el-tooltip>

            <StatusPill
              v-if="mail.folder && mail.folder.toUpperCase() !== 'INBOX'"
              tone="muted"
              :dot="false"
            >
              {{ mail.folder }}
            </StatusPill>

            <button
              v-if="showSearchLinks && mail.email_address"
              type="button"
              class="fm-reader__link-chip fm-mono"
              title="打开所属邮箱"
              @click="$emit('click-email', mail)"
            >
              所属邮箱：{{ mail.email_address }} →
            </button>

            <button
              v-if="hasRecipientDetails"
              type="button"
              class="fm-reader__toggle-rcpt"
              @click="showRecipients = !showRecipients"
            >
              {{ showRecipients ? '收起收件人' : '显示收件人' }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="showRecipients && hasRecipientDetails" class="fm-reader__recipients">
        <div v-if="mail.recipient" class="fm-reader__rcpt-row">
          <span class="fm-reader__rcpt-label">收件人</span>
          <span class="fm-mono">{{ mail.recipient }}</span>
        </div>
        <div v-if="mail.cc" class="fm-reader__rcpt-row">
          <span class="fm-reader__rcpt-label">抄送</span>
          <span class="fm-mono">{{ mail.cc }}</span>
        </div>
      </div>

      <VerifyCodeChips
        :subject="mail.subject || ''"
        :html="parsed.html || ''"
        :text="parsed.text || ''"
      />
    </header>

    <div class="fm-reader__body">
      <MailBody
        :html="parsed.html"
        :text="parsed.text"
        :paper="ui.mailPaperMode"
      />

      <AttachmentList
        v-if="mail.has_attachments"
        :mail-id="mail.id"
        :has-attachments="Boolean(mail.has_attachments)"
      />
    </div>
  </section>

  <div v-else class="fm-reader-empty">
    <EmptyState
      :icon="Message"
      title="选择一封邮件开始阅读"
      description="点击左侧邮件列表中的任意项查看正文、验证码与附件。"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ArrowLeft, Link, CopyDocument, Message } from '@element-plus/icons-vue'
import { formatAbs, formatRelative } from '@/utils/time'
import { parseMailContent, parseSender, htmlToText, sanitizeMailHtml } from '@/utils/mail'
import { useUiStore } from '@/stores/ui'
import { useClipboard } from '@/composables/useClipboard'
import StatusPill from '@/components/common/StatusPill.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import VerifyCodeChips from './VerifyCodeChips.vue'
import MailBody from './MailBody.vue'
import AttachmentList from './AttachmentList.vue'

const props = defineProps({
  mail: { type: Object, default: null },
  emailId: { type: [Number, String], default: null },
  showBack: { type: Boolean, default: false },
  showSearchLinks: { type: Boolean, default: false }
})

defineEmits(['back', 'click-sender', 'click-email'])

const ui = useUiStore()
const { copy } = useClipboard()
const showRecipients = ref(false)

const parsed = computed(() => parseMailContent(props.mail))
const senderInfo = computed(() => parseSender(props.mail?.sender))
const senderInitial = computed(() => (senderInfo.value.name || '?').slice(0, 1).toUpperCase())
const hasRecipientDetails = computed(() => Boolean(props.mail?.recipient || props.mail?.cc))

watch(
  () => props.mail?.id,
  () => {
    showRecipients.value = false
  }
)

function copyPlainText() {
  const plain = parsed.value.text || htmlToText(parsed.value.html || '')
  copy(plain || '', '邮件纯文本')
}

function openInNewTab() {
  if (!parsed.value.html) return
  const clean = sanitizeMailHtml(parsed.value.html)
  const doc = `<!doctype html><html><head><meta charset="utf-8"><title>${(props.mail?.subject || '邮件').replace(/</g, '&lt;')}</title><style>body{font-family:sans-serif;max-width:860px;margin:24px auto;padding:0 16px;line-height:1.65;}img{max-width:100%;height:auto;}</style></head><body>${clean}</body></html>`
  const blob = new Blob([doc], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  window.open(url, '_blank', 'noopener,noreferrer')
  setTimeout(() => URL.revokeObjectURL(url), 15000)
}
</script>

<style scoped>
.fm-reader {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--fm-surface);
}

.fm-reader__header {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-3);
  padding: var(--fm-space-5) var(--fm-space-6);
  border-bottom: 1px solid var(--fm-border);
  flex-shrink: 0;
}

.fm-reader__top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--fm-space-2);
  flex-wrap: wrap;
}

.fm-reader__toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-left: auto;
}

.fm-reader__subject {
  margin: 0;
  font-size: var(--fm-fs-xl);
  font-weight: 600;
  line-height: 1.35;
  color: var(--fm-text);
  word-break: break-word;
}

.fm-reader__sender-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.fm-reader__avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--fm-primary-soft);
  color: var(--fm-text);
  font-size: var(--fm-fs-sm);
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.fm-reader__sender-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.fm-reader__sender-main {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 6px;
}

.fm-reader__sender-name {
  font-size: var(--fm-fs-sm);
  font-weight: 600;
  color: var(--fm-text);
}

.fm-reader__sender-addr {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
  word-break: break-all;
}

.fm-reader__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--fm-space-2);
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
}

.fm-reader__link-chip {
  padding: 2px 6px;
  border: 1px solid var(--fm-border);
  border-radius: var(--fm-radius-xs);
  background: var(--fm-bg-subtle);
  color: var(--fm-accent);
  font-size: var(--fm-fs-xs);
  cursor: pointer;
}

.fm-reader__link-chip:hover {
  border-color: var(--fm-accent);
}

.fm-reader__toggle-rcpt {
  border: none;
  background: transparent;
  color: var(--fm-text-2);
  font-size: var(--fm-fs-xs);
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
}

.fm-reader__recipients {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 12px;
  border-radius: var(--fm-radius-md);
  background: var(--fm-bg-subtle);
  border: 1px solid var(--fm-border);
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-2);
}

.fm-reader__rcpt-row {
  display: flex;
  gap: 8px;
}

.fm-reader__rcpt-label {
  color: var(--fm-text-3);
  flex-shrink: 0;
}

.fm-reader__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--fm-space-5) var(--fm-space-6);
}

.fm-reader-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--fm-surface);
}

@media (max-width: 767.98px) {
  .fm-reader__header,
  .fm-reader__body {
    padding: var(--fm-space-4);
  }
}
</style>

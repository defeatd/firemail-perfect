<template>
  <span v-if="row.mail_type !== 'outlook'" class="fm-auth-na">—</span>

  <el-tooltip v-else placement="top" :show-after="200">
    <template #content>
      <div class="fm-auth-tip">
        <p
          v-if="row.auth_status === 'pending'"
          class="fm-auth-tip__note"
        >
          账号已入库，后台正在限速首验并自动识别收信通道
        </p>
        <p
          v-else-if="!row.refresh_token_expires_at && row.auth_status !== 'need_reauth' && row.auth_status !== 'banned' && !row.last_refresh_error_code"
          class="fm-auth-tip__note"
        >
          RT 尚未验证，待首次保活建立基线
        </p>
        <KeyValueList v-else :items="tooltipItems" dense />
      </div>
    </template>

    <div class="fm-auth-cell" :class="{ 'fm-auth-cell--compact': compact }">
      <div class="fm-auth-cell__pills">
        <StatusPill :tone="pillMeta.tone" size="sm">{{ pillMeta.label }}</StatusPill>
        <span v-if="channelLabel" class="fm-channel-badge fm-mono">{{ channelLabel }}</span>
      </div>
      <RtLifeBar
        :expires-at="row.refresh_token_expires_at"
        :status="row.auth_status || 'ok'"
      />
    </div>
  </el-tooltip>
</template>

<script setup>
import { computed } from 'vue'
import { daysUntil, formatAbs } from '@/utils/time'
import StatusPill from '@/components/common/StatusPill.vue'
import RtLifeBar from '@/components/common/RtLifeBar.vue'
import KeyValueList from '@/components/common/KeyValueList.vue'

const props = defineProps({
  row: { type: Object, required: true },
  compact: { type: Boolean, default: false }
})

const remainingDays = computed(() => daysUntil(props.row.refresh_token_expires_at))

const channelLabel = computed(() => {
  const ch = String(props.row.mail_channel || '').toLowerCase()
  if (ch === 'graph') return 'Graph'
  if (ch === 'imap') return 'IMAP'
  return ''
})

const pillMeta = computed(() => {
  const status = props.row.auth_status
  if (status === 'pending') return { tone: 'info', label: '首验中' }
  if (status === 'need_reauth') return { tone: 'danger', label: '需重授' }
  if (status === 'banned') return { tone: 'solid-muted', label: '已封禁' }
  if (status === 'error') return { tone: 'warning', label: '异常' }
  if (!props.row.refresh_token_expires_at) return { tone: 'info', label: '待验证' }
  if (remainingDays.value !== null && remainingDays.value < 7) {
    return { tone: 'danger', label: '即将到期' }
  }
  if (remainingDays.value !== null && remainingDays.value < 15) {
    return { tone: 'warning', label: '临近到期' }
  }
  return { tone: 'success', label: '正常' }
})

const tooltipItems = computed(() => {
  const items = []
  if (channelLabel.value) {
    items.push({ label: '收信通道', value: channelLabel.value, mono: true })
  }
  if (props.row.refresh_token_expires_at) {
    const dateStr = formatAbs(props.row.refresh_token_expires_at, 'YYYY-MM-DD')
    const d = remainingDays.value
    const suffix = d === null ? '' : d < 0 ? `（已超期 ${Math.abs(d)} 天）` : `（剩 ${d} 天）`
    items.push({ label: 'RT 预计到期', value: `${dateStr}${suffix}`, mono: true })
  }
  if (props.row.next_rotate_at) {
    items.push({
      label: '下次保活',
      value: formatAbs(props.row.next_rotate_at, 'YYYY-MM-DD HH:mm'),
      mono: true
    })
  }
  if (props.row.last_refresh_error_code) {
    items.push({ label: '最近错误', value: props.row.last_refresh_error_code, mono: true })
  }
  if (props.row.last_refresh_error_hint) {
    items.push({ label: '处理建议', value: props.row.last_refresh_error_hint })
  }
  if (props.row.rotate_fail_count) {
    items.push({ label: '失败次数', value: String(props.row.rotate_fail_count), mono: true })
  }
  if (items.length === 0) {
    items.push({ label: '授权状态', value: pillMeta.value.label })
  }
  return items
})
</script>

<style scoped>
.fm-auth-na {
  color: var(--fm-text-3);
}

.fm-auth-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  min-width: 150px;
}

.fm-auth-cell__pills {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.fm-channel-badge {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 6px;
  border-radius: var(--fm-radius-xs);
  border: 1px solid var(--fm-border-strong);
  background: var(--fm-bg-subtle);
  color: var(--fm-text-2);
  font-size: 11px;
  font-weight: 500;
  line-height: 1;
}

.fm-auth-cell--compact {
  min-width: 0;
  width: 100%;
}

.fm-auth-cell :deep(.fm-rt-bar) {
  width: 100%;
}

.fm-auth-tip {
  min-width: 220px;
  max-width: 300px;
}

.fm-auth-tip__note {
  margin: 0;
  font-size: var(--fm-fs-xs);
}
</style>

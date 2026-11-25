<template>
  <div v-if="result" class="fm-import-result">
    <section class="fm-import-result__section">
      <div class="fm-import-result__sec-head">
        <h4 class="fm-import-result__heading">① 入库汇总</h4>
        <el-button
          v-if="downloadableLines.length > 0"
          size="small"
          @click="downloadFailedLines"
        >
          下载失败行（{{ downloadableLines.length }}）
        </el-button>
      </div>

      <div class="fm-import-result__stats">
        <StatCard label="新增入库" :value="addedCount" tone="success" />
        <StatCard label="覆盖更新" :value="updatedCount" tone="info" />
        <StatCard label="已跳过" :value="skippedCount" />
        <StatCard
          label="无效 / 冲突"
          :value="problemCount"
          :tone="problemCount > 0 ? 'danger' : 'default'"
        />
      </div>

      <el-alert
        :title="alertTitle"
        :type="alertType"
        :closable="false"
        show-icon
      />

      <div v-if="ingestProblemRows.length > 0" class="fm-import-result__block">
        <h5 class="fm-import-result__subhead">
          入库问题明细（{{ ingestProblemRows.length }}<template v-if="result.rows_truncated">，仅展示前 1000 条</template>）
        </h5>
        <el-table :data="ingestProblemRows" max-height="300" size="small">
          <el-table-column prop="line" label="行号" width="72">
            <template #default="{ row }">
              <span class="fm-mono">{{ row.line ?? '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="email" label="邮箱" min-width="180">
            <template #default="{ row }">
              <span class="fm-mono">{{ row.email || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="actionLabel" label="分类" width="84" />
          <el-table-column prop="reason" label="原因" min-width="220" />
        </el-table>
      </div>
    </section>

    <section v-if="jobSummary?.hasJobs" class="fm-import-result__section fm-import-result__verify">
      <div class="fm-import-result__sec-head">
        <div class="fm-import-result__verify-title">
          <h4 class="fm-import-result__heading">② 后台首验进度</h4>
          <StatusPill :tone="verifyPill.tone" size="sm">{{ verifyPill.label }}</StatusPill>
        </div>
        <el-button
          v-if="!jobSummary.finished"
          size="small"
          type="warning"
          plain
          :loading="cancelling"
          @click="$emit('cancel-job')"
        >
          取消首验
        </el-button>
      </div>

      <div class="fm-import-result__progress-row">
        <el-progress
          :percentage="jobSummary.percent"
          :status="progressBarStatus"
          :stroke-width="10"
          class="fm-import-result__progress"
        />
        <span class="fm-mono fm-import-result__ratio">
          {{ jobSummary.done }} / {{ jobSummary.total }}
        </span>
      </div>

      <div class="fm-import-result__verify-chips fm-mono">
        <span class="is-ok">可用 {{ jobSummary.ok }}</span>
        <span class="is-danger">需重授 {{ jobSummary.need_reauth }}</span>
        <span v-if="jobSummary.banned > 0" class="is-muted">封禁 {{ jobSummary.banned }}</span>
        <span class="is-warn">失败 {{ jobSummary.failed }}</span>
        <span v-if="jobSummary.deferred > 0" class="is-info">熔断延后 {{ jobSummary.deferred }}</span>
      </div>

      <div v-if="jobSummary.results.length > 0" class="fm-import-result__block">
        <h5 class="fm-import-result__subhead">
          首验未通过明细（{{ jobSummary.results.length }}）
        </h5>
        <el-table :data="jobSummary.results" max-height="320" size="small">
          <el-table-column prop="email" label="邮箱" min-width="180">
            <template #default="{ row }">
              <span class="fm-mono">{{ row.email || `#${row.email_id}` }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="96">
            <template #default="{ row }">
              <StatusPill :tone="verifyRowTone(row.status)" size="sm">
                {{ verifyRowLabel(row.status) }}
              </StatusPill>
            </template>
          </el-table-column>
          <el-table-column prop="error_code" label="错误码" width="144">
            <template #default="{ row }">
              <span class="fm-mono">{{ row.error_code || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="hint" label="处理建议" min-width="240" />
        </el-table>
      </div>
    </section>

    <div v-if="!compact" class="fm-import-result__actions">
      <el-button type="primary" @click="$emit('view-emails')">查看邮箱列表</el-button>
      <el-button @click="$emit('continue')">继续导入</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import StatCard from '@/components/common/StatCard.vue'
import StatusPill from '@/components/common/StatusPill.vue'

const ACTION_LABELS = {
  invalid: '格式错误',
  warned: 'Token 冲突',
  skipped: '已跳过'
}

const VERIFY_STATUS_META = {
  need_reauth: { label: '需重授', tone: 'danger' },
  banned: { label: '已封禁', tone: 'solid-muted' },
  deferred: { label: '熔断延后', tone: 'info' },
  failed: { label: '临时失败', tone: 'warning' }
}

const props = defineProps({
  result: { type: Object, default: null },
  jobSummary: { type: Object, default: null },
  cancelling: { type: Boolean, default: false },
  rawText: { type: String, default: '' },
  compact: { type: Boolean, default: false }
})

defineEmits(['view-emails', 'continue', 'cancel-job'])

const addedCount = computed(() => Number(props.result?.added ?? props.result?.success) || 0)
const updatedCount = computed(() => Number(props.result?.updated) || 0)
const skippedCount = computed(() => Number(props.result?.skipped) || 0)
const invalidCount = computed(() => Number(props.result?.invalid) || 0)
const warnedCount = computed(() => Number(props.result?.warned) || 0)
const problemCount = computed(() => {
  const nw = invalidCount.value + warnedCount.value
  if (nw > 0) return nw
  return Number(props.result?.failed) || 0
})

const ingestedCount = computed(() => addedCount.value + updatedCount.value)

const alertType = computed(() => {
  if (ingestedCount.value > 0 && problemCount.value === 0) return 'success'
  if (ingestedCount.value > 0 && problemCount.value > 0) return 'warning'
  if (skippedCount.value > 0 && problemCount.value === 0) return 'info'
  return 'error'
})

const alertTitle = computed(() => {
  if (props.result?.message) return props.result.message
  if (ingestedCount.value > 0) {
    return `已入库 ${ingestedCount.value} 个邮箱（新增 ${addedCount.value}，更新 ${updatedCount.value}），后台首验将自动更新授权状态`
  }
  return '未新增任何邮箱，请检查下方明细'
})

const ingestProblemRows = computed(() => {
  if (Array.isArray(props.result?.rows) && props.result.rows.length > 0) {
    return props.result.rows.map((item, idx) => ({
      line: item.line ?? idx + 1,
      email: item.email || '',
      action: item.action || 'invalid',
      actionLabel: ACTION_LABELS[item.action] || '异常',
      reason: item.reason || '未入库'
    }))
  }
  const legacy = props.result?.failed_details || props.result?.errors || []
  return Array.isArray(legacy)
    ? legacy.map((item, idx) => ({
        line: item.line ?? item.line_number ?? idx + 1,
        email: item.email || '',
        action: 'invalid',
        actionLabel: '失败',
        reason: item.reason || item.error || item.message || '导入失败'
      }))
    : []
})

const downloadableLines = computed(() => {
  const source = props.rawText || props.result?.rawText || ''
  if (!source) return []
  const rawLines = source.split('\n')
  const lineNums = new Set()
  for (const row of ingestProblemRows.value) {
    if ((row.action === 'invalid' || row.action === 'warned') && Number(row.line) > 0) {
      lineNums.add(Number(row.line))
    }
  }
  return Array.from(lineNums)
    .sort((a, b) => a - b)
    .map((num) => rawLines[num - 1])
    .filter((line) => typeof line === 'string' && line.length > 0)
})

const verifyPill = computed(() => {
  const j = props.jobSummary
  if (!j?.hasJobs) return { tone: 'muted', label: '未启动' }
  if (!j.finished) return { tone: 'info', label: '首验进行中' }
  if (j.cancelled) return { tone: 'warning', label: '已取消（其余待保活）' }
  if (j.ok === j.total && j.total > 0) return { tone: 'success', label: '全部可用' }
  return { tone: 'warning', label: '首验完成' }
})

const progressBarStatus = computed(() => {
  const j = props.jobSummary
  if (!j?.finished) return ''
  if (j.cancelled) return 'warning'
  if (j.ok === j.total && j.total > 0) return 'success'
  return j.ok > 0 ? 'warning' : 'exception'
})

function verifyRowTone(status) {
  return VERIFY_STATUS_META[status]?.tone || 'warning'
}

function verifyRowLabel(status) {
  return VERIFY_STATUS_META[status]?.label || status || '失败'
}

function downloadFailedLines() {
  if (downloadableLines.value.length === 0) {
    ElMessage.info('当前没有可下载的原始失败行')
    return
  }
  const blob = new Blob([downloadableLines.value.join('\n')], {
    type: 'text/plain;charset=utf-8'
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `firemail_failed_lines_${Date.now()}.txt`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.fm-import-result {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-5);
}

.fm-import-result__section {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-3);
}

.fm-import-result__verify {
  padding-top: var(--fm-space-4);
  border-top: 1px solid var(--fm-border);
}

.fm-import-result__sec-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--fm-space-2);
}

.fm-import-result__verify-title {
  display: inline-flex;
  align-items: center;
  gap: var(--fm-space-2);
}

.fm-import-result__heading {
  margin: 0;
  font-size: var(--fm-fs-sm);
  font-weight: 600;
  color: var(--fm-text);
}

.fm-import-result__subhead {
  margin: 0;
  font-size: var(--fm-fs-xs);
  font-weight: 600;
  color: var(--fm-text-2);
}

.fm-import-result__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--fm-space-3);
}

.fm-import-result__block {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-2);
}

.fm-import-result__progress-row {
  display: flex;
  align-items: center;
  gap: var(--fm-space-3);
}

.fm-import-result__progress {
  flex: 1;
}

.fm-import-result__ratio {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-2);
  white-space: nowrap;
}

.fm-import-result__verify-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--fm-space-4);
  font-size: var(--fm-fs-xs);
}

.fm-import-result__verify-chips .is-ok {
  color: var(--fm-success);
  font-weight: 600;
}

.fm-import-result__verify-chips .is-danger {
  color: var(--fm-danger);
  font-weight: 600;
}

.fm-import-result__verify-chips .is-warn {
  color: var(--fm-warning);
  font-weight: 600;
}

.fm-import-result__verify-chips .is-info {
  color: var(--fm-info);
  font-weight: 600;
}

.fm-import-result__verify-chips .is-muted {
  color: var(--fm-text-3);
  font-weight: 600;
}

.fm-import-result__actions {
  display: flex;
  align-items: center;
  gap: var(--fm-space-2);
}

@media (max-width: 767.98px) {
  .fm-import-result__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

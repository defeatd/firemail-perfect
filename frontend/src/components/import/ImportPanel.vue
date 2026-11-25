<template>
  <div class="fm-import-panel" :class="{ 'fm-import-panel--compact': compact }">
    <div class="fm-import-panel__top">
      <div class="fm-import-panel__controls">
        <div class="fm-import-panel__field">
          <label class="fm-import-panel__label" for="fm-import-type">邮箱类型</label>
          <el-select id="fm-import-type" v-model="mailType" style="width: 164px">
            <el-option value="outlook" label="Outlook / Hotmail" />
          </el-select>
        </div>

        <div class="fm-import-panel__field">
          <label class="fm-import-panel__label" for="fm-import-sep">分隔符</label>
          <el-select id="fm-import-sep" v-model="separator" style="width: 146px">
            <el-option value="auto" label="自动识别" />
            <el-option value="----" label="----（四连字符）" />
            <el-option value="	" label="Tab 制表符" />
            <el-option value="|" label="|（竖线）" />
            <el-option value=":" label=":（冒号）" />
          </el-select>
        </div>

        <div class="fm-import-panel__field">
          <label class="fm-import-panel__label" for="fm-import-dup">重复邮箱</label>
          <el-select id="fm-import-dup" v-model="onDuplicate" style="width: 146px">
            <el-option value="skip" label="跳过已存在" />
            <el-option value="update" label="覆盖更新 Token" />
          </el-select>
        </div>
      </div>

      <div
        class="fm-import-panel__drop"
        :class="{ 'is-dragging': isDragging }"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="handleFileDrop"
      >
        <input
          ref="fileInputRef"
          type="file"
          accept=".txt,text/plain"
          class="fm-import-panel__file-input"
          @change="handleFileSelect"
        />
        <el-button size="small" @click="triggerFilePicker">
          <el-icon><Upload /></el-icon>
          <span>选择 .txt 文件</span>
        </el-button>
        <span class="fm-import-panel__drop-hint">支持拖放读取（单次最多 5000 行）</span>
      </div>
    </div>

    <div v-if="isLargeFileMode" class="fm-import-panel__large-card">
      <div class="fm-import-panel__large-head">
        <div>
          <div class="fm-import-panel__large-title">
            大文件模式{{ loadedFileName ? `：${loadedFileName}` : '' }}
          </div>
          <div class="fm-import-panel__large-sub fm-mono">
            文本体积 {{ formattedSize }} · 非空 {{ validation.total }} 行（已免渲染文本框防止卡顿）
          </div>
        </div>
        <el-button size="small" :disabled="submitting" @click="reset">清空重选</el-button>
      </div>
      <div class="fm-import-panel__large-metrics fm-mono">
        <span>可入库 <strong>{{ validation.validCount }}</strong></span>
        <span>无效 <strong>{{ validation.errors.length }}</strong></span>
        <span>冲突 <strong>{{ validation.warnings.length }}</strong></span>
        <span>批内重复 <strong>{{ validation.duplicates.length }}</strong></span>
      </div>
    </div>

    <div v-else class="fm-import-panel__editor-wrap">
      <div class="fm-import-panel__gutter fm-mono" aria-hidden="true">
        <span v-for="n in lineCount" :key="n" class="fm-import-panel__line-num" />
      </div>
      <textarea
        v-model="rawText"
        class="fm-import-panel__textarea fm-mono"
        :rows="compact ? 8 : 12"
        spellcheck="false"
        placeholder="每行一条：邮箱----密码----client_id----refresh_token（自动兼容 3/4/5/6 段与 Tab / |）"
      />
    </div>

    <div class="fm-import-panel__status">
      <span class="fm-mono fm-import-panel__counter">
        共 {{ validation.total }} 行 · 可入库 {{ validation.validCount }} 行
        <template v-if="skippedPreviewCount > 0">
          · <span class="is-warn">将跳过 {{ skippedPreviewCount }} 行</span>
        </template>
        <template v-if="validation.duplicates.length > 0">
          · 批内去重 {{ validation.duplicates.length }} 行
        </template>
      </span>
      <span v-if="validation.overLimit" class="fm-import-panel__err-text">
        超出单次上限 {{ MAX_IMPORT_ROWS }} 行，请分批导入
      </span>
      <span v-else-if="validation.ok && skippedPreviewCount === 0" class="fm-import-panel__ok">
        校验通过，点击开始入库
      </span>
      <span v-else-if="validation.ok" class="fm-import-panel__warn-text">
        将跳过 {{ skippedPreviewCount }} 行无效/冲突记录，其余正常入库
      </span>
    </div>

    <div v-if="previewIssues.length > 0" class="fm-import-panel__errors">
      <div
        v-for="issue in previewIssues.slice(0, 12)"
        :key="`${issue.kind}-${issue.line}`"
        class="fm-import-panel__error-row"
      >
        <span class="fm-mono fm-import-panel__error-line">第 {{ issue.line }} 行</span>
        <span>{{ issue.message }}</span>
      </div>
      <div v-if="previewIssues.length > 12" class="fm-import-panel__error-more">
        另有 {{ previewIssues.length - 12 }} 条无效或冲突行，入库后可在结果中一键下载失败行
      </div>
    </div>

    <div v-if="chunkProgressText" class="fm-import-panel__chunk-bar fm-mono">
      {{ chunkProgressText }}
    </div>

    <div v-if="!hideActions" class="fm-import-panel__actions">
      <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submit">
        {{ submitButtonLabel }}
      </el-button>
      <el-button :disabled="submitting || !rawText" @click="reset">重置</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import {
  MAX_IMPORT_ROWS,
  buildImportChunks,
  createImportAggregate,
  mergeImportChunkResult
} from '@/utils/importParser'
import { useEmailsStore } from '@/stores/emails'
import { useImportValidator } from '@/composables/useImportValidator'

const CHUNK_SIZE = 2000
const LARGE_FILE_BYTES = 512 * 1024
const LARGE_FILE_LINES = 2000

const props = defineProps({
  compact: { type: Boolean, default: false },
  hideActions: { type: Boolean, default: false }
})

const emit = defineEmits(['imported', 'submitting'])
const emails = useEmailsStore()
const { validateLines } = useImportValidator()

const mailType = ref('outlook')
const separator = ref('auto')
const onDuplicate = ref('skip')
const rawText = ref('')
const loadedFileName = ref('')
const submitting = ref(false)
const isDragging = ref(false)
const fileInputRef = ref(null)
const chunkProgressText = ref('')
const validation = ref(validateLines('', { separator: 'auto' }))
let debounceTimer = null

function runValidationNow() {
  if (debounceTimer) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
  validation.value = validateLines(rawText.value, {
    separator: separator.value,
    maxRows: MAX_IMPORT_ROWS
  })
}

watch([rawText, separator], () => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    debounceTimer = null
    validation.value = validateLines(rawText.value, {
      separator: separator.value,
      maxRows: MAX_IMPORT_ROWS
    })
  }, 250)
})

onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
})

const rawLineCount = computed(() => (rawText.value ? rawText.value.split('\n').length : 0))
const isLargeFileMode = computed(
  () => rawText.value.length > LARGE_FILE_BYTES || rawLineCount.value > LARGE_FILE_LINES
)
const formattedSize = computed(() => {
  const bytes = new Blob([rawText.value]).size
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(2)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`
})
const skippedPreviewCount = computed(
  () => validation.value.errors.length + validation.value.warnings.length
)
const previewIssues = computed(() => [
  ...validation.value.errors.map((e) => ({ ...e, kind: 'err' })),
  ...validation.value.warnings.map((w) => ({ ...w, kind: 'warn' }))
])
const canSubmit = computed(() => validation.value.ok && !submitting.value)
const submitButtonLabel = computed(() => {
  if (submitting.value) return '正在入库…'
  if (validation.value.validCount > 0 && skippedPreviewCount.value > 0) {
    return `入库 ${validation.value.validCount} 条（跳过 ${skippedPreviewCount.value} 条）`
  }
  return '开始导入'
})
const lineCount = computed(() => {
  const minLines = props.compact ? 8 : 12
  return Math.max(minLines, Math.min(rawLineCount.value, LARGE_FILE_LINES))
})

function triggerFilePicker() {
  fileInputRef.value?.click()
}

function readTxtFile(file) {
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.txt') && file.type && !file.type.startsWith('text/')) {
    ElMessage.warning('请选择 .txt 文本文件')
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    loadedFileName.value = file.name
    rawText.value = String(reader.result || '')
    runValidationNow()
    ElMessage.success(`已读取文件：${file.name}`)
  }
  reader.onerror = () => ElMessage.error('读取文件失败')
  reader.readAsText(file, 'utf-8')
}

function handleFileSelect(event) {
  readTxtFile(event.target?.files?.[0])
  if (event.target) event.target.value = ''
}

function handleFileDrop(event) {
  isDragging.value = false
  readTxtFile(event.dataTransfer?.files?.[0])
}

function reset() {
  rawText.value = ''
  loadedFileName.value = ''
  chunkProgressText.value = ''
  runValidationNow()
}

async function submit() {
  runValidationNow()
  if (!rawText.value.trim()) {
    ElMessage.warning('请输入要导入的邮箱数据')
    return null
  }
  if (validation.value.overLimit) {
    ElMessage.warning(`单次导入上限为 ${MAX_IMPORT_ROWS} 行，请分批导入`)
    return null
  }
  if (!validation.value.ok) {
    ElMessage.warning('没有可入库的有效邮箱行，请检查格式或分隔符设置')
    return null
  }

  const chunks = buildImportChunks(rawText.value, CHUNK_SIZE)
  if (chunks.length === 0) return null

  submitting.value = true
  emit('submitting', true)
  ElMessage.info(
    skippedPreviewCount.value > 0
      ? `正在入库…（将跳过 ${skippedPreviewCount.value} 行无效/冲突记录）`
      : '正在入库…'
  )

  const aggregated = createImportAggregate(rawText.value)
  try {
    for (let idx = 0; idx < chunks.length; idx += 1) {
      if (chunks.length > 1) {
        chunkProgressText.value = `正在提交第 ${idx + 1} / ${chunks.length} 片…`
      }
      const res = await emails.importEmails({
        data: chunks[idx].text,
        mailType: mailType.value,
        separator: separator.value,
        onDuplicate: onDuplicate.value,
        verify: true
      })
      mergeImportChunkResult(aggregated, res, chunks[idx].lineOffset)
    }
    emit('imported', aggregated)
    return aggregated
  } catch (err) {
    const msg =
      err?.response?.data?.error || err?.response?.data?.message || err?.message || '导入失败'
    ElMessage.error(msg)
    throw err
  } finally {
    chunkProgressText.value = ''
    submitting.value = false
    emit('submitting', false)
  }
}

defineExpose({ submit, reset, canSubmit, submitting })
</script>

<style scoped>
.fm-import-panel { display: flex; flex-direction: column; gap: var(--fm-space-4); }
.fm-import-panel__top { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--fm-space-3); }
.fm-import-panel__controls { display: flex; align-items: center; flex-wrap: wrap; gap: var(--fm-space-3); }
.fm-import-panel__field { display: flex; align-items: center; gap: var(--fm-space-2); }
.fm-import-panel__label { font-size: var(--fm-fs-sm); font-weight: 500; color: var(--fm-text-2); white-space: nowrap; }
.fm-import-panel__drop {
  display: inline-flex; align-items: center; gap: var(--fm-space-2); padding: 6px 10px;
  border: 1px dashed var(--fm-border-strong); border-radius: var(--fm-radius-md); background: var(--fm-bg-subtle);
  transition: border-color var(--fm-dur-fast) var(--fm-ease), background var(--fm-dur-fast) var(--fm-ease);
}
.fm-import-panel__drop.is-dragging { border-color: var(--fm-accent); background: var(--fm-accent-soft); }
.fm-import-panel__file-input { display: none; }
.fm-import-panel__drop-hint { font-size: var(--fm-fs-xs); color: var(--fm-text-3); }
.fm-import-panel__large-card {
  border: 1px solid var(--fm-border-strong); border-radius: var(--fm-radius-md);
  background: var(--fm-bg-subtle); padding: var(--fm-space-4); display: flex; flex-direction: column; gap: var(--fm-space-3);
}
.fm-import-panel__large-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--fm-space-3); }
.fm-import-panel__large-title { font-size: var(--fm-fs-sm); font-weight: 600; color: var(--fm-text); }
.fm-import-panel__large-sub { margin-top: 2px; font-size: var(--fm-fs-xs); color: var(--fm-text-3); }
.fm-import-panel__large-metrics { display: flex; flex-wrap: wrap; gap: var(--fm-space-4); font-size: var(--fm-fs-xs); color: var(--fm-text-2); }
.fm-import-panel__editor-wrap {
  display: flex; border: 1px solid var(--fm-border); border-radius: var(--fm-radius-md);
  background: var(--fm-surface); overflow: hidden; max-height: 360px;
}
.fm-import-panel__editor-wrap:focus-within { border-color: var(--fm-accent); box-shadow: var(--fm-focus-ring); }
.fm-import-panel__gutter {
  counter-reset: import-line; padding: 10px 8px; background: var(--fm-bg-subtle); border-right: 1px solid var(--fm-border);
  color: var(--fm-text-3); font-size: 12px; line-height: 22px; text-align: right; min-width: 36px; user-select: none; overflow: hidden;
}
.fm-import-panel__line-num { display: block; counter-increment: import-line; }
.fm-import-panel__line-num::before { content: counter(import-line); }
.fm-import-panel__textarea {
  flex: 1; min-width: 0; border: none; outline: none; resize: vertical; padding: 10px 12px;
  background: transparent; color: var(--fm-text); font-size: 12px; line-height: 22px; white-space: pre; overflow: auto;
}
.fm-import-panel__status { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--fm-space-2); font-size: var(--fm-fs-xs); color: var(--fm-text-2); }
.fm-import-panel__counter .is-warn, .fm-import-panel__warn-text { color: var(--fm-warning); font-weight: 600; }
.fm-import-panel__ok { color: var(--fm-success); font-weight: 500; }
.fm-import-panel__err-text { color: var(--fm-danger); font-weight: 600; }
.fm-import-panel__errors {
  border: 1px solid var(--fm-warning-border); background: var(--fm-warning-soft); border-radius: var(--fm-radius-md);
  padding: var(--fm-space-3); display: flex; flex-direction: column; gap: 4px; font-size: var(--fm-fs-xs); color: var(--fm-text);
  max-height: 150px; overflow-y: auto;
}
.fm-import-panel__error-row { display: flex; gap: var(--fm-space-2); }
.fm-import-panel__error-line { font-weight: 600; white-space: nowrap; color: var(--fm-warning); }
.fm-import-panel__error-more { margin-top: 2px; color: var(--fm-text-2); }
.fm-import-panel__chunk-bar { font-size: var(--fm-fs-xs); color: var(--fm-info); }
.fm-import-panel__actions { display: flex; align-items: center; gap: var(--fm-space-2); }
</style>

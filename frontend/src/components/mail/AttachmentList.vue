<template>
  <section v-if="hasAttachments" class="fm-attachments">
    <div class="fm-attachments__head">
      <span class="fm-attachments__title">
        <el-icon><Paperclip /></el-icon>
        <span>附件</span>
        <span v-if="items.length > 0" class="fm-mono">({{ items.length }})</span>
      </span>
    </div>

    <div v-if="isLoading" class="fm-attachments__loading">
      <el-skeleton :rows="1" animated />
    </div>

    <div v-else-if="items.length > 0" class="fm-attachments__grid">
      <div v-for="att in items" :key="att.id" class="fm-att-card">
        <div class="fm-att-card__icon">
          <el-icon :size="18"><component :is="kindIcon(att)" /></el-icon>
        </div>
        <div class="fm-att-card__info">
          <div class="fm-att-card__name" :title="att.filename">{{ att.filename || '未命名附件' }}</div>
          <div class="fm-att-card__size fm-mono">{{ formatFileSize(att.size) }}</div>
        </div>
        <div class="fm-att-card__actions">
          <el-tooltip v-if="canPreview(att)" content="预览" placement="top">
            <button
              type="button"
              class="fm-att-card__btn"
              :disabled="busyId === att.id"
              aria-label="预览附件"
              @click="handlePreview(att)"
            >
              <el-icon :size="14"><View /></el-icon>
            </button>
          </el-tooltip>
          <el-tooltip content="下载" placement="top">
            <button
              type="button"
              class="fm-att-card__btn"
              :disabled="busyId === att.id"
              aria-label="下载附件"
              @click="handleDownload(att)"
            >
              <el-icon :size="14"><Download /></el-icon>
            </button>
          </el-tooltip>
        </div>
      </div>
    </div>

    <AttachmentPreviewDialog
      v-model="previewOpen"
      :preview-data="previewData"
      :attachment="previewAttachment"
      @download="handleDownload"
    />
  </section>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Paperclip,
  Document,
  Picture,
  VideoCamera,
  Headset,
  Folder,
  View,
  Download
} from '@element-plus/icons-vue'
import { formatFileSize, fileKind, isPreviewableKind } from '@/utils/file'
import { useAttachments } from '@/composables/useAttachments'
import AttachmentPreviewDialog from './AttachmentPreviewDialog.vue'

const props = defineProps({
  mailId: { type: [Number, String], required: true },
  hasAttachments: { type: Boolean, default: false }
})

const { byMailId, loadingById, list, download, preview } = useAttachments()

const busyId = ref(null)
const previewOpen = ref(false)
const previewData = ref(null)
const previewAttachment = ref(null)

const items = computed(() => byMailId[props.mailId] || [])
const isLoading = computed(() => Boolean(loadingById[props.mailId]))

watch(
  () => [props.mailId, props.hasAttachments],
  async ([id, has]) => {
    if (!id || !has) return
    try {
      await list(id)
    } catch (_err) {
      ElMessage.error('获取附件列表失败')
    }
  },
  { immediate: true }
)

function kindIcon(att) {
  const kind = fileKind(att)
  if (kind === 'image') return Picture
  if (kind === 'video') return VideoCamera
  if (kind === 'audio') return Headset
  if (kind === 'archive') return Folder
  return Document
}

function canPreview(att) {
  return isPreviewableKind(fileKind(att))
}

async function handleDownload(att) {
  if (!att) return
  busyId.value = att.id
  try {
    await download(att)
  } catch (_err) {
    ElMessage.error('下载附件失败')
  } finally {
    busyId.value = null
  }
}

async function handlePreview(att) {
  busyId.value = att.id
  try {
    previewAttachment.value = att
    previewData.value = await preview(att)
    previewOpen.value = true
  } catch (_err) {
    ElMessage.error('加载附件预览失败')
  } finally {
    busyId.value = null
  }
}
</script>

<style scoped>
.fm-attachments {
  margin-top: var(--fm-space-5);
  padding-top: var(--fm-space-4);
  border-top: 1px solid var(--fm-border);
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-3);
}

.fm-attachments__title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fm-fs-sm);
  font-weight: 600;
  color: var(--fm-text);
}

.fm-attachments__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--fm-space-3);
}

.fm-att-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--fm-radius-md);
  background: var(--fm-surface-2);
  border: 1px solid var(--fm-border);
  min-width: 0;
}

.fm-att-card__icon {
  color: var(--fm-text-2);
  display: inline-flex;
  flex-shrink: 0;
}

.fm-att-card__info {
  flex: 1;
  min-width: 0;
}

.fm-att-card__name {
  font-size: var(--fm-fs-xs);
  font-weight: 500;
  color: var(--fm-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fm-att-card__size {
  font-size: 11px;
  color: var(--fm-text-3);
}

.fm-att-card__actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.fm-att-card__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: var(--fm-radius-xs);
  background: transparent;
  color: var(--fm-text-2);
  cursor: pointer;
}

.fm-att-card__btn:hover:not(:disabled) {
  background: var(--fm-surface-hover);
  color: var(--fm-text);
}
</style>

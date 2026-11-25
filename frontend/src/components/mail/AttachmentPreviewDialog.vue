<template>
  <el-dialog
    :model-value="modelValue"
    :title="previewData?.filename || attachment?.filename || '附件预览'"
    :width="isMobile ? '94vw' : '760px'"
    destroy-on-close
    @update:model-value="handleVisibleChange"
  >
    <div v-if="previewData" class="fm-att-preview">
      <img
        v-if="previewData.kind === 'image'"
        :src="previewData.url"
        :alt="previewData.filename"
        class="fm-att-preview__img"
      />

      <iframe
        v-else-if="previewData.kind === 'pdf'"
        :src="previewData.url"
        title="PDF 附件预览"
        sandbox="allow-same-origin"
        class="fm-att-preview__pdf"
      />

      <pre v-else-if="previewData.kind === 'text'" class="fm-att-preview__text fm-mono">{{ previewData.textContent }}</pre>

      <audio
        v-else-if="previewData.kind === 'audio'"
        :src="previewData.url"
        controls
        class="fm-att-preview__media"
      />

      <video
        v-else-if="previewData.kind === 'video'"
        :src="previewData.url"
        controls
        class="fm-att-preview__video"
      />

      <div v-else class="fm-att-preview__fallback">
        <p>无法预览此类型的附件，请下载后查看。</p>
        <el-button type="primary" @click="$emit('download', attachment)">下载附件</el-button>
      </div>
    </div>

    <template #footer>
      <el-button @click="handleVisibleChange(false)">关闭</el-button>
      <el-button v-if="attachment" type="primary" @click="$emit('download', attachment)">
        下载
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { watch, onUnmounted } from 'vue'
import { useBreakpoint } from '@/composables/useBreakpoint'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  previewData: { type: Object, default: null },
  attachment: { type: Object, default: null }
})

const emit = defineEmits(['update:modelValue', 'download'])

const { isMobile } = useBreakpoint()

function cleanupCurrent(data) {
  if (typeof data?.cleanup === 'function') {
    data.cleanup()
  }
}

watch(
  () => props.previewData,
  (_next, prev) => {
    if (prev) cleanupCurrent(prev)
  }
)

watch(
  () => props.modelValue,
  (open) => {
    if (!open && props.previewData) {
      cleanupCurrent(props.previewData)
    }
  }
)

onUnmounted(() => {
  cleanupCurrent(props.previewData)
})

function handleVisibleChange(val) {
  if (!val) cleanupCurrent(props.previewData)
  emit('update:modelValue', val)
}
</script>

<style scoped>
.fm-att-preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 220px;
}

.fm-att-preview__img {
  max-width: 100%;
  max-height: 68vh;
  border-radius: var(--fm-radius-md);
  object-fit: contain;
}

.fm-att-preview__pdf {
  width: 100%;
  height: 68vh;
  border: 1px solid var(--fm-border);
  border-radius: var(--fm-radius-md);
}

.fm-att-preview__text {
  width: 100%;
  max-height: 65vh;
  overflow: auto;
  margin: 0;
  padding: var(--fm-space-4);
  border-radius: var(--fm-radius-md);
  background: var(--fm-bg-subtle);
  border: 1px solid var(--fm-border);
  font-size: var(--fm-fs-xs);
  white-space: pre-wrap;
  word-break: break-word;
}

.fm-att-preview__media {
  width: 100%;
}

.fm-att-preview__video {
  max-width: 100%;
  max-height: 65vh;
  border-radius: var(--fm-radius-md);
}

.fm-att-preview__fallback {
  text-align: center;
  padding: var(--fm-space-6);
  color: var(--fm-text-2);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--fm-space-3);
}
</style>

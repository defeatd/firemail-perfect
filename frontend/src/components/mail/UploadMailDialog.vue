<template>
  <el-dialog
    :model-value="modelValue"
    title="上传邮件文件"
    :width="isMobile ? '94vw' : '480px'"
    :close-on-click-modal="false"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="fm-upload-dialog">
      <el-upload
        ref="uploadRef"
        drag
        action=""
        :auto-upload="false"
        :limit="1"
        accept=".eml,.txt,.msg,.mbox,.emlx"
        :on-change="handleChange"
        :on-remove="handleRemove"
        :on-exceed="handleExceed"
      >
        <el-icon class="fm-upload-dialog__icon" :size="36"><UploadFilled /></el-icon>
        <div class="fm-upload-dialog__text">
          将邮件文件拖到此处，或<em>点击选择</em>
        </div>
        <template #tip>
          <div class="fm-upload-dialog__tip">
            支持格式：.eml / .txt / .msg / .mbox / .emlx，每次仅限上传 1 个文件
          </div>
        </template>
      </el-upload>
    </div>

    <template #footer>
      <div class="fm-upload-dialog__footer">
        <el-button @click="$emit('update:modelValue', false)">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">
          开始上传
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import api from '@/services/api'
import { useBreakpoint } from '@/composables/useBreakpoint'

const ALLOWED_EXTS = ['.eml', '.txt', '.msg', '.mbox', '.emlx']

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  emailId: { type: [Number, String], required: true }
})

const emit = defineEmits(['update:modelValue', 'uploaded'])

const { isMobile } = useBreakpoint()
const uploadRef = ref(null)
const selectedFile = ref(null)
const uploading = ref(false)

watch(
  () => props.modelValue,
  (open) => {
    if (!open) {
      selectedFile.value = null
      uploadRef.value?.clearFiles()
    }
  }
)

function handleChange(file) {
  const raw = file?.raw
  if (!raw) return
  const name = raw.name.toLowerCase()
  const ok = ALLOWED_EXTS.some((ext) => name.endsWith(ext))
  if (!ok) {
    ElMessage.warning('仅支持 .eml / .txt / .msg / .mbox / .emlx 格式的邮件文件')
    uploadRef.value?.clearFiles()
    selectedFile.value = null
    return
  }
  selectedFile.value = raw
}

function handleRemove() {
  selectedFile.value = null
}

function handleExceed() {
  ElMessage.warning('只能上传一个文件')
}

async function handleUpload() {
  if (!selectedFile.value) {
    ElMessage.warning('请选择要上传的文件')
    return
  }
  uploading.value = true
  try {
    await api.emails.uploadMailFile(props.emailId, selectedFile.value)
    ElMessage.success('邮件文件上传成功')
    emit('update:modelValue', false)
    emit('uploaded')
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || err?.message || '上传失败')
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.fm-upload-dialog__icon {
  color: var(--fm-text-3);
  margin-bottom: var(--fm-space-2);
}

.fm-upload-dialog__text {
  font-size: var(--fm-fs-sm);
  color: var(--fm-text-2);
}

.fm-upload-dialog__text em {
  color: var(--fm-accent);
  font-style: normal;
  font-weight: 500;
}

.fm-upload-dialog__tip {
  margin-top: var(--fm-space-2);
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
}

.fm-upload-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--fm-space-2);
}
</style>

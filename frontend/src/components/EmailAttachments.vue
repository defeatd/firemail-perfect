<template>
  <div class="email-attachments-component">
    <div v-if="hasAttachments" class="attachments-container">
      <div class="attachments-header">
        <el-icon><Paperclip /></el-icon>
        <span>附件 ({{ attachmentsCount }})</span>
      </div>

      <div class="attachments-loading" v-if="loading">
        <el-skeleton :rows="1" animated />
      </div>

      <div v-else class="attachments-grid">
        <div v-for="attachment in attachments" :key="attachment.id" class="attachment-card">
          <div class="attachment-icon">
            <el-icon v-if="isImageAttachment(attachment)"><Picture /></el-icon>
            <el-icon v-else-if="isPdfAttachment(attachment)"><Document /></el-icon>
            <el-icon v-else-if="isTextAttachment(attachment)"><Reading /></el-icon>
            <el-icon v-else-if="isArchiveAttachment(attachment)"><Files /></el-icon>
            <el-icon v-else-if="isAudioAttachment(attachment)"><Headset /></el-icon>
            <el-icon v-else-if="isVideoAttachment(attachment)"><VideoPlay /></el-icon>
            <el-icon v-else-if="isExcelAttachment(attachment)"><Grid /></el-icon>
            <el-icon v-else-if="isWordAttachment(attachment)"><Reading /></el-icon>
            <el-icon v-else-if="isPowerPointAttachment(attachment)"><PieChart /></el-icon>
            <el-icon v-else><Document /></el-icon>
          </div>

          <div class="attachment-info">
            <div class="attachment-name" :title="attachment.filename">{{ attachment.filename }}</div>
            <div class="attachment-size">{{ formatFileSize(attachment.size) }}</div>
          </div>

          <div class="attachment-actions">
            <el-tooltip content="下载附件" placement="top">
              <el-button size="small" type="primary" circle @click="downloadAttachment(attachment.id, attachment.filename)">
                <el-icon><Download /></el-icon>
              </el-button>
            </el-tooltip>

            <el-tooltip v-if="canPreviewAttachment(attachment)" content="预览" placement="top">
              <el-button size="small" type="success" circle @click="previewAttachment(attachment)">
                <el-icon><View /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>
      </div>
    </div>

    <!-- 附件预览对话框 -->
    <el-dialog
      v-model="previewDialogVisible"
      :title="previewingAttachment ? previewingAttachment.filename : '附件预览'"
      width="70%"
      destroy-on-close
      class="attachment-preview-dialog"
    >
      <div v-if="previewingAttachment" class="attachment-preview">
        <div v-if="isImageAttachment(previewingAttachment)" class="image-preview">
          <img :src="previewUrl" :alt="previewingAttachment.filename" />
        </div>
        <div v-else-if="isTextAttachment(previewingAttachment)" class="text-preview">
          <pre>{{ previewContent }}</pre>
        </div>
        <div v-else-if="isPdfAttachment(previewingAttachment)" class="pdf-preview">
          <iframe :src="previewUrl" width="100%" height="500"></iframe>
        </div>
        <div v-else-if="isAudioAttachment(previewingAttachment)" class="audio-preview">
          <audio controls :src="previewUrl" style="width: 100%"></audio>
        </div>
        <div v-else-if="isVideoAttachment(previewingAttachment)" class="video-preview">
          <video controls :src="previewUrl" style="max-width: 100%; max-height: 500px"></video>
        </div>
        <div v-else class="unsupported-preview">
          <p>无法预览此类型的附件，请下载后查看。</p>
          <el-button type="primary" @click="downloadAttachment(previewingAttachment.id, previewingAttachment.filename)">
            <el-icon><Download /></el-icon> 下载附件
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import {
  Document, Download, View, Picture, Files,
  Paperclip, Headset, VideoPlay, Grid, Reading, PieChart
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  attachments: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

// 附件预览相关
const previewDialogVisible = ref(false)
const previewingAttachment = ref(null)
const previewUrl = ref('')
const previewContent = ref('')

// 计算属性
const hasAttachments = computed(() => {
  return props.attachments && props.attachments.length > 0
})

const attachmentsCount = computed(() => {
  return props.attachments ? props.attachments.length : 0
})

// 附件类型判断方法
const isImageAttachment = (attachment) => {
  if (!attachment || !attachment.content_type) return false
  return attachment.content_type.startsWith('image/')
}

const isPdfAttachment = (attachment) => {
  if (!attachment || !attachment.content_type) return false
  return attachment.content_type === 'application/pdf'
}

const isTextAttachment = (attachment) => {
  if (!attachment || !attachment.content_type) return false
  return attachment.content_type.startsWith('text/') ||
         attachment.filename.endsWith('.txt') ||
         attachment.filename.endsWith('.log') ||
         attachment.filename.endsWith('.md') ||
         attachment.filename.endsWith('.json') ||
         attachment.filename.endsWith('.csv')
}

const isArchiveAttachment = (attachment) => {
  if (!attachment || !attachment.filename) return false
  const filename = attachment.filename.toLowerCase()
  return filename.endsWith('.zip') ||
         filename.endsWith('.rar') ||
         filename.endsWith('.7z') ||
         filename.endsWith('.tar') ||
         filename.endsWith('.gz')
}

const isAudioAttachment = (attachment) => {
  if (!attachment || !attachment.content_type) return false
  return attachment.content_type.startsWith('audio/')
}

const isVideoAttachment = (attachment) => {
  if (!attachment || !attachment.content_type) return false
  return attachment.content_type.startsWith('video/')
}

const isExcelAttachment = (attachment) => {
  if (!attachment || !attachment.filename) return false
  const filename = attachment.filename.toLowerCase()
  return filename.endsWith('.xls') ||
         filename.endsWith('.xlsx') ||
         filename.endsWith('.csv') ||
         attachment.content_type === 'application/vnd.ms-excel' ||
         attachment.content_type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
}

const isWordAttachment = (attachment) => {
  if (!attachment || !attachment.filename) return false
  const filename = attachment.filename.toLowerCase()
  return filename.endsWith('.doc') ||
         filename.endsWith('.docx') ||
         attachment.content_type === 'application/msword' ||
         attachment.content_type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}

const isPowerPointAttachment = (attachment) => {
  if (!attachment || !attachment.filename) return false
  const filename = attachment.filename.toLowerCase()
  return filename.endsWith('.ppt') ||
         filename.endsWith('.pptx') ||
         attachment.content_type === 'application/vnd.ms-powerpoint' ||
         attachment.content_type === 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
}

const canPreviewAttachment = (attachment) => {
  return isImageAttachment(attachment) ||
         isPdfAttachment(attachment) ||
         isTextAttachment(attachment) ||
         isAudioAttachment(attachment) ||
         isVideoAttachment(attachment)
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'

  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 下载附件
const downloadAttachment = (attachmentId, filename) => {
  const token = localStorage.getItem('token')
  const downloadUrl = `/api/attachments/${attachmentId}/download`

  // 创建一个隐藏的a标签用于下载
  const link = document.createElement('a')
  link.href = downloadUrl
  link.setAttribute('download', filename)
  link.setAttribute('target', '_blank')

  // 添加认证头
  fetch(downloadUrl, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })
  .then(response => response.blob())
  .then(blob => {
    const url = window.URL.createObjectURL(blob)
    link.href = url
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  })
  .catch(error => {
    console.error('下载附件失败:', error)
    ElMessage.error('下载附件失败')
  })
}

// 预览附件
const previewAttachment = (attachment) => {
  previewingAttachment.value = attachment
  previewDialogVisible.value = true

  if (isImageAttachment(attachment) || isPdfAttachment(attachment) || isAudioAttachment(attachment) || isVideoAttachment(attachment)) {
    const token = localStorage.getItem('token')
    const downloadUrl = `/api/attachments/${attachment.id}/download`

    fetch(downloadUrl, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    .then(response => response.blob())
    .then(blob => {
      previewUrl.value = URL.createObjectURL(blob)
    })
    .catch(error => {
      console.error('获取附件预览失败:', error)
      ElMessage.error('获取附件预览失败')
    })
  } else if (isTextAttachment(attachment)) {
    const token = localStorage.getItem('token')
    const downloadUrl = `/api/attachments/${attachment.id}/download`

    fetch(downloadUrl, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    .then(response => response.text())
    .then(text => {
      previewContent.value = text
    })
    .catch(error => {
      console.error('获取附件预览失败:', error)
      ElMessage.error('获取附件预览失败')
    })
  }
}
</script>

<style scoped>
.email-attachments-component {
  width: 100%;
}

.attachments-container {
  padding: 16px;
  background-color: #f0f9eb;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.attachments-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-weight: 500;
  color: #67c23a;
  font-size: 16px;
}

.attachments-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 12px;
}

.attachment-card {
  display: flex;
  align-items: center;
  padding: 12px;
  background-color: #fff;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  transition: all 0.3s;
}

.attachment-card:hover {
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.attachment-icon {
  margin-right: 12px;
  font-size: 24px;
  color: #909399;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  background-color: #f5f7fa;
  border-radius: 6px;
}

.attachment-info {
  flex: 1;
  min-width: 0;
}

.attachment-name {
  font-weight: 500;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.attachment-size {
  font-size: 12px;
  color: #909399;
}

.attachment-actions {
  display: flex;
  gap: 8px;
}

.attachment-preview {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
}

.image-preview img {
  max-width: 100%;
  max-height: 70vh;
}

.text-preview {
  width: 100%;
  max-height: 70vh;
  overflow: auto;
  background-color: #f8f9fa;
  padding: 16px;
  border-radius: 4px;
}

.text-preview pre {
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  font-family: monospace;
}

.unsupported-preview {
  text-align: center;
  padding: 32px;
}

@media (max-width: 768px) {
  .attachments-grid {
    grid-template-columns: 1fr;
  }
}
</style>

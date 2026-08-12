<template>
  <div class="email-detail-container">
    <div class="header-section">
      <el-page-header @back="goBack" :title="'返回邮箱列表'">
        <template #content>
          <span class="email-title">{{ email ? email.email : '加载中...' }}</span>
        </template>
      </el-page-header>

      <div class="actions" v-if="email">
        <el-button type="primary" @click="checkEmail" :disabled="isProcessing" :loading="loading">
          <el-icon><Download /></el-icon> 收取邮件
        </el-button>
        <el-button type="success" @click="showUploadDialog" :disabled="isProcessing">
          <el-icon><Upload /></el-icon> 上传邮件文件
        </el-button>
        <el-button type="danger" @click="confirmDelete" :disabled="isProcessing">
          <el-icon><Delete /></el-icon> 删除邮箱
        </el-button>
      </div>
    </div>

    <div class="email-info" v-if="email">
      <el-descriptions title="邮箱信息" :column="1" border>
        <el-descriptions-item label="邮箱地址">{{ email.email }}</el-descriptions-item>
        <el-descriptions-item label="最后检查时间">{{ formatDate(email.last_check_time) }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDate(email.created_at) }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="mail-records" v-loading="loading">
      <el-card class="mail-card">
        <template #header>
          <div class="mail-header">
            <span>邮件列表</span>
            <el-input
              v-model="searchQuery"
              placeholder="搜索邮件主题或内容"
              clearable
              class="search-input"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>
        </template>

        <div v-if="filteredMailRecords.length === 0" class="no-mails">
          <el-empty description="暂无邮件记录" />
        </div>

        <div v-else>
          <el-collapse accordion @change="handleCollapseChange">
            <el-collapse-item v-for="mail in filteredMailRecords" :key="mail.id" :name="mail.id">
              <template #title>
                <div class="mail-title">
                  <span class="subject">{{ mail.subject || '(无主题)' }}</span>
                  <span class="date">{{ formatDate(mail.received_time) }}</span>
                  <el-tag v-if="mail.has_attachments" size="small" type="success" class="attachment-tag">
                    <el-icon><Document /></el-icon> 附件
                  </el-tag>
                </div>
              </template>

              <div class="mail-content">
                <!-- 使用EmailContentViewer组件 -->
                <EmailContentViewer
                  :mail="mail"
                  :attachments="mailAttachments[mail.id] || []"
                  :loading-attachments="loadingAttachments"
                />
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </el-card>
    </div>
  </div>

  <!-- 上传邮件文件对话框 -->
  <el-dialog
    v-model="uploadDialogVisible"
    title="上传邮件文件"
    width="500px"
  >
    <el-form>
      <el-form-item label="选择邮件文件">
        <el-upload
          ref="uploadRef"
          class="upload-demo"
          drag
          action="#"
          :auto-upload="false"
          :limit="1"
          :on-change="handleFileChange"
          :on-exceed="handleExceed"
          :file-list="fileList"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            拖拽文件到此处或 <em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              支持 .eml 格式的邮件文件
            </div>
          </template>
        </el-upload>
      </el-form-item>
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="uploadEmailFile" :loading="uploading">
          上传
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Download, Delete, Search, Upload, UploadFilled, Document } from '@element-plus/icons-vue'
import { useEmailsStore } from '@/store/emails'
import dayjs from 'dayjs'
import DOMPurify from 'dompurify'
import axios from 'axios'
import EmailContentViewer from '@/components/EmailContentViewer.vue'
import EmailAttachments from '@/components/EmailAttachments.vue'
import EmailQuoteFormatter from '@/components/EmailQuoteFormatter.vue'

const route = useRoute()
const router = useRouter()
const emailsStore = useEmailsStore()
const searchQuery = ref('')
const mailAttachments = ref({}) // 存储邮件附件信息
const loadingAttachments = ref(false)

// 上传邮件文件相关
const uploadDialogVisible = ref(false)
const uploadRef = ref(null)
const fileList = ref([])
const uploading = ref(false)

// 邮箱ID
const emailId = computed(() => parseInt(route.params.id))

// 邮箱信息
const email = computed(() => emailsStore.getEmailById(emailId.value))

// 处理状态
const loading = computed(() => emailsStore.loading)
const isProcessing = computed(() => {
  const status = getProcessingStatus(emailId.value)
  return status && status.progress > 0 && status.progress < 100
})

// 邮件记录（按接收时间由新到旧）
const mailRecords = computed(() => {
  const list = Array.isArray(emailsStore.currentMailRecords)
    ? [...emailsStore.currentMailRecords]
    : []
  return list.sort((a, b) => {
    const ta = a?.received_time ? dayjs(a.received_time).valueOf() : 0
    const tb = b?.received_time ? dayjs(b.received_time).valueOf() : 0
    if (Number.isNaN(ta) && Number.isNaN(tb)) return 0
    if (Number.isNaN(ta)) return 1
    if (Number.isNaN(tb)) return -1
    return tb - ta
  })
})

// 过滤的邮件记录
const filteredMailRecords = computed(() => {
  if (!searchQuery.value) return mailRecords.value

  const query = searchQuery.value.toLowerCase()
  return mailRecords.value.filter(mail => {
    return (mail.subject && mail.subject.toLowerCase().includes(query)) ||
           (mail.content && mail.content.toLowerCase().includes(query))
  })
})

// 获取处理状态
const getProcessingStatus = (id) => {
  return emailsStore.getProcessingStatus(id)
}

// 格式化日期
const formatDate = (dateString) => {
  if (!dateString) return '无'
  return dayjs(dateString).format('YYYY-MM-DD HH:mm:ss')
}

// 返回
const goBack = () => {
  router.push('/emails')
}

// 检查邮件内容是否为HTML格式
const isHtmlContent = (mail) => {
  if (!mail || !mail.content) return false;

  // 兼容新旧格式
  if (typeof mail.content === 'object') {
    return mail.content.has_html === true || mail.content.content_type === 'text/html';
  }

  // 旧格式，检查内容是否包含HTML标签
  const content = String(mail.content);
  return content.includes('<html') || content.includes('<body') ||
         content.includes('<div') || content.includes('<p>') ||
         content.includes('<table') || content.includes('<img');
}

// 获取邮件内容
const getMailContent = (mail) => {
  if (!mail) return '';

  // 兼容新旧格式
  if (typeof mail.content === 'object' && mail.content !== null) {
    return mail.content.content || '';
  }

  return mail.content || '';
}

// 净化HTML内容，防止XSS攻击
const sanitizeHtml = (html) => {
  if (!html) return '';
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'a', 'b', 'br', 'div', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'i', 'img', 'li', 'ol', 'p', 'span', 'strong', 'table', 'tbody',
      'td', 'th', 'thead', 'tr', 'u', 'ul', 'font', 'blockquote', 'hr',
      'pre', 'code', 'col', 'colgroup', 'section', 'header', 'footer',
      'nav', 'article', 'aside', 'figure', 'figcaption', 'address', 'main',
      'caption', 'center', 'cite', 'dd', 'dl', 'dt', 'mark', 's', 'small',
      'strike', 'sub', 'sup'
    ],
    ALLOWED_ATTR: [
      'href', 'target', 'src', 'alt', 'style', 'class', 'id', 'width', 'height',
      'align', 'valign', 'bgcolor', 'border', 'cellpadding', 'cellspacing',
      'color', 'colspan', 'dir', 'face', 'frame', 'frameborder', 'headers',
      'hspace', 'lang', 'marginheight', 'marginwidth', 'nowrap', 'rel',
      'rev', 'rowspan', 'scrolling', 'shape', 'span', 'summary', 'title',
      'usemap', 'vspace', 'start', 'type', 'value', 'size', 'data-*'
    ]
  });
}

// 加载邮件附件
const loadMailAttachments = async (mailId) => {
  if (mailAttachments.value[mailId]) {
    return // 已加载过，不重复加载
  }

  loadingAttachments.value = true
  try {
    const response = await axios.get(`/api/mail_records/${mailId}/attachments`, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })

    if (response.status === 200) {
      mailAttachments.value[mailId] = response.data
    } else {
      ElMessage.error('获取附件列表失败')
    }
  } catch (error) {
    console.error('获取附件列表失败:', error)
    ElMessage.error('获取附件列表失败')
  } finally {
    loadingAttachments.value = false
  }
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

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B'

  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 收取邮件
const checkEmail = () => {
  emailsStore.checkEmail(emailId.value)
  ElMessage.success('开始收取邮件')
}

// 确认删除邮箱
const confirmDelete = () => {
  if (!email.value) return

  ElMessageBox.confirm(
    `确定要删除邮箱 ${email.value.email} 吗？所有相关的邮件记录也将被删除。`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    emailsStore.deleteEmail(emailId.value)
    ElMessage.success('删除成功')
    router.push('/emails')
  }).catch(() => {
    // 取消删除
  })
}

// 监听邮箱ID变化，获取邮件记录
watch(emailId, (newId) => {
  if (newId) {
    emailsStore.fetchMailRecords(newId)
  }
})

// 处理折叠面板变化
const handleCollapseChange = (activeNames) => {
  if (activeNames && typeof activeNames === 'number') {
    // 获取当前展开的邮件
    const mail = mailRecords.value.find(m => m.id === activeNames)
    if (mail && mail.has_attachments) {
      // 加载附件
      loadMailAttachments(mail.id)
    }
  }
}

// 显示上传对话框
const showUploadDialog = () => {
  uploadDialogVisible.value = true
  fileList.value = []
}

// 处理文件变化
const handleFileChange = (file) => {
  fileList.value = [file]
}

// 处理超出文件数量限制
const handleExceed = () => {
  ElMessage.warning('只能上传一个文件')
}

// 上传邮件文件
const uploadEmailFile = async () => {
  if (fileList.value.length === 0) {
    ElMessage.warning('请选择要上传的文件')
    return
  }

  const file = fileList.value[0].raw

  // 检查文件扩展名
  const fileName = file.name
  const fileExt = fileName.substring(fileName.lastIndexOf('.')).toLowerCase()
  const allowedExtensions = ['.eml', '.txt', '.msg', '.mbox', '.emlx']
  if (!allowedExtensions.includes(fileExt)) {
    ElMessage.error(`只支持${allowedExtensions.join('、')}格式的邮件文件`)
    return
  }

  // 创建FormData对象
  const formData = new FormData()
  formData.append('file', file)

  uploading.value = true
  try {
    const response = await axios.post(
      `/api/emails/${emailId.value}/upload_email_file`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      }
    )

    if (response.data.success) {
      ElMessage.success('邮件文件上传成功')
      uploadDialogVisible.value = false
      // 刷新邮件列表
      emailsStore.fetchMailRecords(emailId.value)
    } else {
      ElMessage.error(response.data.error || '上传失败')
    }
  } catch (error) {
    console.error('上传邮件文件失败:', error)
    ElMessage.error(error.response?.data?.error || '上传失败')
  } finally {
    uploading.value = false
  }
}

// 组件挂载时获取邮件记录
onMounted(() => {
  if (emailId.value) {
    emailsStore.fetchMailRecords(emailId.value)
  }
})
</script>

<style scoped>
.email-detail-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 20px;
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.email-title {
  font-size: 18px;
  font-weight: bold;
  color: var(--primary-color);
}

.status-section {
  margin-bottom: 20px;
}

.progress-bar {
  margin-top: 10px;
}

.email-info {
  margin-bottom: 20px;
}

.mail-card {
  margin-bottom: 20px;
}

.mail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-input {
  max-width: 300px;
}

.no-mails {
  padding: 40px 0;
}

.mail-title {
  display: flex;
  justify-content: space-between;
  width: 100%;
  padding-right: 20px;
}

.subject {
  font-weight: bold;
  margin-right: 10px;
}

.date {
  color: #909399;
  font-size: 0.9em;
}

.mail-content {
  padding: 10px;
  background-color: #f8f9fa;
  border-radius: 4px;
}

.mail-info {
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #ebeef5;
}

.mail-body {
  white-space: pre-line;
  word-break: break-word;
}

.mail-attachments {
  margin: 10px 0;
  padding: 10px;
  background-color: #f0f9eb;
  border-radius: 4px;
  border-left: 3px solid #67c23a;
}

.attachments-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
}

.attachment-item {
  margin-bottom: 5px;
}

.attachment-tag {
  margin-left: 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.html-content {
  max-width: 100%;
  overflow-x: auto;
  padding: 10px;
  background-color: #f8f9fa;
  border-radius: 4px;
  line-height: 1.5;
}

.html-content img {
  max-width: 100%;
  height: auto;
}

.html-content a {
  color: var(--primary-color);
  text-decoration: underline;
}

.html-content table {
  border-collapse: collapse;
  margin: 10px 0;
}

.html-content th,
.html-content td {
  border: 1px solid #ddd;
  padding: 8px;
}

@media (max-width: 768px) {
  .header-section {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .actions {
    width: 100%;
    display: flex;
    justify-content: space-between;
  }

  .mail-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .search-input {
    max-width: 100%;
    width: 100%;
  }

  .mail-title {
    flex-direction: column;
    gap: 5px;
  }
}
</style>
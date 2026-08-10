<template>
  <div class="import-container">
    <h1 class="page-title">批量导入邮箱</h1>

    <el-card class="import-card">
      <div class="import-form">
        <el-alert
          type="info"
          title="导入格式说明"
          :closable="false"
          show-icon
        >
          <p>请选择邮箱类型，然后按照相应格式输入邮箱信息，每行一个：</p>
          <p v-if="formData.mailType === 'outlook'">
            <code>邮箱地址----密码----客户端ID----RefreshToken</code>
          </p>
          <p>
            示例：example@outlook.com----password123----9e5f94bc-e8a4-4e73-b8be-63364c29d753----M.C511_BL2...
          </p>
          <p class="hint-warn">
            导入时会自动校验 Outlook Token：无效账号<strong>不会入库</strong>，并在下方列出失败原因。
          </p>
        </el-alert>

        <el-form :model="formData" ref="formRef" :rules="rules" label-position="top">
          <el-form-item label="选择邮箱类型" prop="mailType">
            <el-select v-model="formData.mailType" placeholder="请选择邮箱类型">
              <el-option label="Outlook/Hotmail" value="outlook" />
            </el-select>
          </el-form-item>

          <el-form-item label="批量邮箱数据" prop="importData">
            <el-input
              v-model="formData.importData"
              type="textarea"
              :rows="10"
              placeholder="请输入需要批量导入的邮箱数据，每行一个"
            />
          </el-form-item>

          <el-form-item>
            <el-button type="primary" @click="submitForm" :loading="loading">
              <el-icon><Upload /></el-icon> 开始导入
            </el-button>
            <el-button @click="resetForm" :disabled="loading">
              <el-icon><RefreshRight /></el-icon> 重置
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <div class="import-result" v-if="importResult">
        <el-divider>导入结果</el-divider>

        <el-alert
          :type="resultAlertType"
          :title="getResultTitle()"
          :description="getResultSubtitle()"
          show-icon
          :closable="false"
          class="result-alert"
        />

        <div class="result-stats">
          <el-tag type="info">合计 {{ importResult.total || 0 }}</el-tag>
          <el-tag type="success">成功 {{ importResult.success || 0 }}</el-tag>
          <el-tag type="danger">失败 {{ importResult.failed || 0 }}</el-tag>
        </div>

        <div class="result-actions">
          <el-button type="primary" @click="navigateToEmails">查看邮箱列表</el-button>
          <el-button @click="resetForm">继续导入</el-button>
        </div>

        <template v-if="importResult.failed > 0 && importResult.failed_details?.length">
          <h3 class="fail-title">
            <el-icon color="#F56C6C"><WarningFilled /></el-icon>
            失败详情（这些账号未写入系统）
          </h3>
          <el-table
            :data="importResult.failed_details"
            stripe
            border
            style="width: 100%"
            max-height="420"
          >
            <el-table-column prop="line" label="行号" width="72" />
            <el-table-column prop="email" label="邮箱" min-width="160" show-overflow-tooltip />
            <el-table-column prop="reason" label="失败原因" min-width="280" show-overflow-tooltip />
            <el-table-column prop="content" label="原始内容（已脱敏）" min-width="180" show-overflow-tooltip />
          </el-table>
        </template>

        <template v-if="importResult.success_emails?.length">
          <h3 class="ok-title">成功导入的邮箱</h3>
          <el-tag
            v-for="addr in importResult.success_emails"
            :key="addr"
            type="success"
            class="ok-tag"
            effect="plain"
          >
            {{ addr }}
          </el-tag>
        </template>
      </div>
    </el-card>

    <el-card class="guide-card">
      <template #header>
        <div class="card-header">
          <span>如何获取 RefreshToken</span>
        </div>
      </template>

      <div class="guide-content" v-if="formData.mailType === 'outlook'">
        <p>获取 RefreshToken 的步骤：</p>
        <ol>
          <li>登录您的 Microsoft 账户</li>
          <li>访问 Microsoft Azure 门户</li>
          <li>注册应用并获取客户端 ID</li>
          <li>设置 API 权限和回调 URL</li>
          <li>使用 OAuth 流程获取初始 RefreshToken</li>
        </ol>
        <p>
          详细说明可参考：
          <a
            href="https://learn.microsoft.com/zh-cn/azure/active-directory/develop/v2-oauth2-auth-code-flow"
            target="_blank"
            rel="noopener"
          >Microsoft OAuth 2.0 授权代码流</a>
        </p>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElNotification } from 'element-plus'
import { Upload, RefreshRight, WarningFilled } from '@element-plus/icons-vue'
import { useEmailsStore } from '@/store/emails'
import api from '@/services/api'

const router = useRouter()
const emailsStore = useEmailsStore()
const formRef = ref(null)
const loading = ref(false)
const importResult = ref(null)

const formData = reactive({
  mailType: 'outlook',
  importData: ''
})

const rules = {
  mailType: [
    { required: true, message: '请选择邮箱类型', trigger: 'change' }
  ],
  importData: [
    { required: true, message: '请输入邮箱数据', trigger: 'blur' },
    { validator: validateImportData, trigger: 'blur' }
  ]
}

function validateImportData(rule, value, callback) {
  if (!value) {
    callback()
    return
  }

  const lines = value.trim().split('\n')
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line) continue

    if (formData.mailType === 'outlook') {
      const parts = line.split('----')
      if (parts.length !== 4) {
        callback(new Error(`第 ${i + 1} 行格式错误，请使用 "----" 分隔四个字段`))
        return
      }
      if (!parts[0] || !parts[1] || !parts[2] || !parts[3]) {
        callback(new Error(`第 ${i + 1} 行有空白字段，所有字段都必须填写`))
        return
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(parts[0])) {
        callback(new Error(`第 ${i + 1} 行邮箱格式不正确`))
        return
      }
    }
  }
  callback()
}

const resultAlertType = computed(() => {
  if (!importResult.value) return 'info'
  const { success = 0, failed = 0 } = importResult.value
  if (success > 0 && failed > 0) return 'warning'
  if (success > 0) return 'success'
  return 'error'
})

function applyImportResult(result) {
  importResult.value = result
  loading.value = false

  const ok = result.success || 0
  const fail = result.failed || 0

  if (ok > 0 && fail === 0) {
    ElMessage.success(`全部成功：已导入 ${ok} 个邮箱`)
  } else if (ok > 0 && fail > 0) {
    ElNotification({
      title: '部分导入成功',
      message: `成功 ${ok} 个，失败 ${fail} 个。失败账号未写入，请查看下方详情。`,
      type: 'warning',
      duration: 8000
    })
  } else {
    ElNotification({
      title: '导入失败',
      message: fail > 0
        ? `全部 ${fail} 个均失败，未写入任何账号。请查看失败原因。`
        : '没有成功导入任何邮箱',
      type: 'error',
      duration: 8000
    })
  }

  if (ok > 0) {
    emailsStore.fetchEmails?.()
  }
}

async function submitForm() {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
    loading.value = true
    importResult.value = null

    ElMessage.info('正在校验 Token 并导入，请稍候…')

    // 统一走 HTTP API，保证返回结构化 failed_details（校验可能较慢）
    const response = await api.importEmails(
      formData.importData.trim(),
      formData.mailType
    )
    applyImportResult(response.data || response)
  } catch (error) {
    loading.value = false
    const msg =
      error?.response?.data?.error ||
      error?.message ||
      '导入失败'
    ElMessage.error(msg)
  }
}

function resetForm() {
  if (formRef.value) {
    formRef.value.resetFields()
  }
  formData.mailType = 'outlook'
  formData.importData = ''
  importResult.value = null
}

function getResultTitle() {
  if (!importResult.value) return ''
  const { success = 0, failed = 0 } = importResult.value
  if (success > 0 && failed > 0) {
    return `部分成功：导入 ${success} 个，失败 ${failed} 个`
  }
  if (success > 0) return `成功导入 ${success} 个邮箱`
  return '导入失败：无效账号均未写入'
}

function getResultSubtitle() {
  if (!importResult.value) return ''
  const { total = 0, success = 0, failed = 0, message } = importResult.value
  if (message) return message
  return `共处理 ${total} 条有效记录，成功 ${success}，失败 ${failed}`
}

function navigateToEmails() {
  router.push('/emails')
}
</script>

<style scoped>
.import-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 20px;
}

.page-title {
  font-size: 24px;
  margin-bottom: 20px;
  color: var(--neutral-800);
}

.import-card {
  margin-bottom: 20px;
}

.import-form {
  margin-bottom: 20px;
}

.hint-warn {
  margin-top: 8px;
  color: #e6a23c;
}

.import-result {
  margin-top: 20px;
}

.result-alert {
  margin-bottom: 16px;
}

.result-stats {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.result-actions {
  margin-bottom: 20px;
}

.fail-title,
.ok-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 16px 0 10px;
  font-size: 16px;
}

.ok-tag {
  margin: 0 8px 8px 0;
}

.guide-card {
  margin-bottom: 20px;
}

.guide-content {
  line-height: 1.6;
}

.guide-content ol {
  padding-left: 20px;
  margin-bottom: 20px;
}

.guide-content li {
  margin-bottom: 10px;
}

.guide-content a {
  color: var(--neutral-800);
  text-decoration: none;
}
</style>

<template>
  <div class="page-container">
    <div class="emails-container">
      <el-card class="email-list-card shadow">
        <template #header>
          <div class="card-header flex-between">
            <h2 class="page-title">邮箱列表</h2>
            <div class="actions flex gap-md">
              <el-button @click="refreshEmails" :icon="Refresh">
                刷新列表
              </el-button>
              <el-button type="primary" @click="showAddEmailDialog" :icon="Plus">
                添加邮箱
              </el-button>
            </div>
          </div>
        </template>

        <div class="toolbar flex gap-md mb-4">
          <el-button
            :disabled="!hasSelectedEmails"
            @click="handleBatchDelete"
            :icon="Delete"
          >
            批量删除
          </el-button>
          <el-button
            type="primary"
            plain
            :disabled="!hasSelectedEmails"
            @click="handleBatchCheck"
            :icon="Download"
          >
            批量收信
          </el-button>
          <el-button
            :disabled="sortedEmails.length === 0"
            @click="handleExportTxt"
            :icon="Document"
          >
            导出TXT
          </el-button>
        </div>

        <el-table
          v-loading="loading"
          :data="sortedEmails"
          :row-key="row => row.id"
          @selection-change="handleSelectionChange"
          @sort-change="handleSortChange"
          style="width: 100%"
          stripe
          border
          highlight-current-row
          class="email-table desktop-table"
          :fit="true"
        >
          <el-table-column
            type="selection"
            width="48"
            :selectable="row => row"
            reserve-selection
            class-name="selection-column"
          />
          <el-table-column prop="email" label="邮箱地址" min-width="220" show-overflow-tooltip sortable="custom">
            <template #default="scope">
              <div class="email-cell">
                <div class="email-avatar">
                  <span>{{ scope.row.email.charAt(0).toUpperCase() }}</span>
                </div>
                <div class="email-main">
                  <span class="email-text">{{ scope.row.email }}</span>
                  <el-tag
                    v-if="(scope.row.mail_type || 'outlook') === 'outlook'"
                    size="small"
                    class="auth-inline-tag"
                    :class="authStatusClass(scope.row)"
                  >
                    {{ authStatusLabel(scope.row) }}
                  </el-tag>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="mail_type" label="类型" width="120" show-overflow-tooltip sortable="custom">
            <template #default="scope">
              <el-tag size="small" class="mail-type-tag" effect="plain">
                {{ getMailTypeName(scope.row.mail_type || 'outlook') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="password" label="密码" width="168" class-name="password-column">
            <template #default="scope">
              <div class="password-field">
                <code class="password-text" :title="scope.row.showPassword ? scope.row.password : ''">
                  {{ scope.row.showPassword ? scope.row.password : '••••••••' }}
                </code>
                <el-button
                  link
                  type="primary"
                  :icon="scope.row.showPassword ? Hide : View"
                  @click.stop="togglePasswordVisibility(scope.row)"
                  :loading="scope.row.passwordLoading"
                  class="password-toggle-btn"
                  :title="scope.row.showPassword ? '隐藏密码' : '显示密码'"
                />
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="last_check_time" label="最后检查" width="158" sortable="custom">
            <template #default="scope">
              <span class="time-field">{{ formatDate(scope.row.last_check_time) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="授权" width="96" align="center">
            <template #default="scope">
              <el-tag
                v-if="(scope.row.mail_type || 'outlook') === 'outlook'"
                size="small"
                class="auth-status-tag"
                :class="authStatusClass(scope.row)"
              >
                {{ authStatusLabel(scope.row) }}
              </el-tag>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" width="340" class-name="ops-column">
            <template #default="scope">
              <div class="action-buttons">
                <el-button
                  type="primary"
                  size="small"
                  class="btn-check"
                  :disabled="isEmailProcessing(scope.row)"
                  @click="handleCheck(scope.row)"
                >
                  {{ getEmailActionText(scope.row) }}
                </el-button>
                <el-button
                  v-if="(scope.row.mail_type || 'outlook') === 'outlook'"
                  size="small"
                  class="btn-reauth"
                  @click="openDeviceReauth(scope.row)"
                >
                  重新授权
                </el-button>
                <el-button size="small" @click="handleViewMails(scope.row)">
                  查看
                </el-button>
                <el-button size="small" @click="handleEdit(scope.row)">
                  编辑
                </el-button>
                <el-button size="small" type="danger" plain @click="handleDelete(scope.row)">
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <!-- 移动端卡片列表 -->
        <div v-if="isMobile" class="mobile-email-list" v-loading="loading">
          <div
            v-for="email in sortedEmails"
            :key="email.id"
            class="email-card"
            :class="{ 'selected': emailsStore.selectedEmails.includes(email.id) }"
          >
            <div class="email-card-header">
              <el-checkbox
                :model-value="emailsStore.selectedEmails.includes(email.id)"
                @change="toggleEmailSelection(email)"
              />
              <el-tag
                :type="getMailTypeColor(email.mail_type || 'outlook')"
                effect="plain"
                size="small"
              >
                {{ getMailTypeName(email.mail_type || 'outlook') }}
              </el-tag>
            </div>

            <div class="email-card-body">
              <div class="email-address">{{ email.email }}</div>
              <div class="email-meta">
                <span class="meta-label">最后检查:</span>
                <span class="meta-value">{{ formatDate(email.last_check_time) }}</span>
                <el-tag
                  v-if="(email.mail_type || 'outlook') === 'outlook'"
                  size="small"
                  class="auth-status-tag"
                  :class="authStatusClass(email)"
                >
                  {{ authStatusLabel(email) }}
                </el-tag>
              </div>
            </div>

            <div class="email-card-actions">
              <el-button
                type="primary"
                size="small"
                :disabled="isEmailProcessing(email)"
                @click="handleCheck(email)"
              >
                {{ getEmailActionText(email) }}
              </el-button>
              <el-button
                v-if="(email.mail_type || 'outlook') === 'outlook'"
                size="small"
                @click="openDeviceReauth(email)"
              >
                重新授权
              </el-button>
              <el-button size="small" @click="handleViewMails(email)">查看</el-button>
              <el-button size="small" @click="handleEdit(email)">编辑</el-button>
              <el-button size="small" type="danger" plain @click="handleDelete(email)">删除</el-button>
            </div>
          </div>

          <el-empty v-if="sortedEmails.length === 0" description="暂无邮箱" />
        </div>
      </el-card>

      <!-- 添加邮箱对话框 -->
      <el-dialog
        v-model="addEmailDialogVisible"
        title="添加邮箱"
        :width="dialogWidth"
        :close-on-click-modal="false"
        class="add-email-dialog responsive-dialog"
        destroy-on-close
      >
        <el-tabs v-model="addEmailActiveTab">
          <el-tab-pane label="Device Code 授权添加" name="device">
            <el-alert
              type="success"
              :closable="false"
              show-icon
              class="mb-3"
              title="无需事先准备 Refresh Token：填写邮箱后跳转微软登录，授权成功自动入库"
            />
            <el-form label-width="120px">
              <el-form-item label="邮箱地址" required>
                <el-input
                  v-model="deviceAddEmail"
                  placeholder="例如 name@outlook.com / hotmail.com"
                />
              </el-form-item>
              <el-form-item label="Client ID">
                <el-input
                  v-model="deviceAddClientId"
                  placeholder="可留空，使用系统默认 Client ID"
                />
              </el-form-item>
              <el-button type="warning" :loading="deviceReauthStarting" @click="startDeviceAdd">
                开始 Device Code 授权
              </el-button>
            </el-form>
          </el-tab-pane>
          <el-tab-pane label="单个添加" name="single">
            <el-form
              ref="addEmailFormRef"
              :model="addEmailForm"
              :rules="addEmailRules"
              label-width="120px"
              class="add-email-form"
            >
              <el-form-item label="邮箱类型" prop="mail_type">
                <el-select v-model="addEmailForm.mail_type" placeholder="请选择邮箱类型" class="w-full">
                  <el-option
                    v-for="(config, type) in mailTypes"
                    :key="type"
                    :label="config.name"
                    :value="type"
                  />
                </el-select>
              </el-form-item>

              <el-form-item label="邮箱地址" prop="email">
                <el-input v-model="addEmailForm.email" placeholder="请输入邮箱地址" />
              </el-form-item>

              <el-form-item label="密码" prop="password">
                <el-input
                  v-model="addEmailForm.password"
                  type="password"
                  placeholder="请输入密码"
                  show-password
                />
              </el-form-item>

              <template v-if="addEmailForm.mail_type === 'outlook'">
                <el-form-item label="Client ID" prop="client_id">
                  <el-input v-model="addEmailForm.client_id" placeholder="请输入Client ID" />
                </el-form-item>

                <el-form-item label="Refresh Token" prop="refresh_token">
                  <el-input v-model="addEmailForm.refresh_token" placeholder="请输入Refresh Token" />
                </el-form-item>
              </template>

              <template v-if="addEmailForm.mail_type === 'imap'">
                <el-form-item label="服务器" prop="server">
                  <el-input v-model="addEmailForm.server" placeholder="请输入IMAP服务器地址" />
                </el-form-item>

                <el-form-item label="端口" prop="port">
                  <el-input-number v-model="addEmailForm.port" :min="1" :max="65535" />
                </el-form-item>

                <el-form-item label="使用SSL" prop="use_ssl">
                  <el-switch v-model="addEmailForm.use_ssl" />
                </el-form-item>
              </template>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="批量添加" name="batch">
            <p class="import-help">请按照以下格式输入邮箱信息，每行一个：<br/>邮箱地址----密码----客户端ID----刷新令牌</p>
            <el-form :model="batchImport" label-width="120px" :rules="batchImportRules" ref="batchImportFormRef">
              <el-form-item label="邮箱类型">
                <el-select v-model="batchImport.mailType" placeholder="请选择邮箱类型">
                  <el-option
                    label="Outlook/Hotmail"
                    value="outlook"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="批量数据" prop="data">
                <el-input
                  v-model="batchImport.data"
                  type="textarea"
                  :rows="10"
                  placeholder="例如: example@outlook.com----password----clientid----refreshtoken"
                />
              </el-form-item>
            </el-form>
          </el-tab-pane>
        </el-tabs>

        <template #footer>
          <span class="dialog-footer">
            <el-button @click="addEmailDialogVisible = false">取消</el-button>
            <el-button type="primary" @click="handleAddOrImport" :loading="addingEmail || importing">
              确定
            </el-button>
          </span>
        </template>
      </el-dialog>

      <!-- 邮件列表对话框 -->
      <el-dialog
        v-model="mailListDialogVisible"
        title="邮件列表"
        :width="windowWidth < 768 ? '95%' : '90%'"
        top="5vh"
        class="mail-list-dialog responsive-dialog"
        destroy-on-close
      >
        <div v-if="currentEmail" class="mail-dialog-header flex-between mb-4">
          <h3 class="email-title">
            <span class="text-primary">{{ currentEmail.email }}</span> 的邮件
          </h3>
          <el-button
            type="primary"
            size="small"
            @click="handleCheck(currentEmail)"
            :disabled="isEmailProcessing(currentEmail)"
            :icon="Refresh"
            class="refresh-btn hover-scale"
          >
            刷新邮件
          </el-button>
        </div>

        <el-table
          v-loading="loadingMails"
          :data="mailRecords"
          style="width: 100%"
          stripe
          border
          max-height="60vh"
          class="mail-list-table"
        >
          <el-table-column prop="subject" label="主题" min-width="250" show-overflow-tooltip>
            <template #default="scope">
              <div class="subject-cell">
                <span>{{ scope.row.subject }}</span>
                <el-tag v-if="scope.row.has_attachments" size="small" type="success" class="attachment-tag">
                  <el-icon><Document /></el-icon> 附件
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="sender" label="发件人" min-width="200" show-overflow-tooltip />
          <el-table-column prop="received_time" label="接收时间" width="180">
            <template #default="scope">
              <span class="time-field">{{ formatDate(scope.row.received_time) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="scope">
              <el-button
                type="primary"
                size="small"
                @click="viewMailContent(scope.row)"
                :icon="Document"
                class="view-btn"
              >
                查看
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-dialog>

      <!-- 邮件内容查看对话框 -->
      <el-dialog
        v-model="mailContentDialogVisible"
        :title="selectedMail ? selectedMail.subject : '邮件详情'"
        :width="windowWidth < 480 ? '98%' : (windowWidth < 768 ? '95%' : '90%')"
        :top="windowWidth < 768 ? '1vh' : '2vh'"
        class="mail-content-dialog responsive-dialog"
        :fullscreen="windowWidth < 480"
      >
        <div v-if="selectedMail" class="mail-detail">
          <!-- 使用EmailContentViewer组件 -->
          <EmailContentViewer
            :mail="selectedMail"
            :attachments="selectedMail.attachments || []"
            :loading-attachments="false"
          />
        </div>
      </el-dialog>

      <!-- 编辑邮箱对话框 -->
      <el-dialog
        v-model="editDialogVisible"
        title="编辑邮箱"
        :width="dialogWidth"
        class="responsive-dialog"
        @close="resetEditForm"
      >
        <el-form
          ref="editFormRef"
          :model="editForm"
          :rules="editRules"
          label-width="100px"
        >
          <el-form-item label="邮箱地址" prop="email">
            <el-input v-model="editForm.email" />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="editForm.password"
              type="password"
              show-password
              @input="checkPasswordStrength"
            >
              <template #append>
                <el-tooltip
                  content="密码应包含大小写字母、数字和特殊字符,长度至少8位"
                  placement="top"
                >
                  <el-icon><InfoFilled /></el-icon>
                </el-tooltip>
              </template>
            </el-input>
            <div class="password-strength" v-if="editForm.password">
              <span>密码强度:</span>
              <el-progress
                :percentage="passwordStrength"
                :color="passwordStrengthColor"
                :format="passwordStrengthText"
              />
            </div>
          </el-form-item>
          <!-- 显示邮箱类型但不能修改 -->
          <el-form-item label="邮箱类型">
            <el-tag :type="getMailTypeColor(editForm.mail_type)">
              {{ getMailTypeName(editForm.mail_type) }}
            </el-tag>
            <div class="form-tips">邮箱类型创建后不可修改</div>
          </el-form-item>
          <template v-if="editForm.mail_type === 'imap'">
            <div class="imap-tips">
              <h4>常用IMAP服务器配置:</h4>
              <p>Gmail: <code>imap.gmail.com</code> 端口: <code>993</code> SSL: 开启</p>
              <p>Outlook: <code>outlook.office365.com</code> 端口: <code>993</code> SSL: 开启</p>
              <p>QQ邮箱: <code>imap.qq.com</code> 端口: <code>993</code> SSL: 开启</p>
              <p>163邮箱: <code>imap.163.com</code> 端口: <code>993</code> SSL: 开启</p>
            </div>
            <el-form-item
              label="服务器"
              prop="server"
            >
              <el-input v-model="editForm.server">
                <template #append>
                  <el-tooltip content="IMAP服务器地址,如: imap.gmail.com" placement="top">
                    <el-icon><InfoFilled /></el-icon>
                  </el-tooltip>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item
              label="端口"
              prop="port"
            >
              <el-input-number
                v-model="editForm.port"
                :min="1"
                :max="65535"
                controls-position="right"
              />
              <div class="form-tips">常用端口: SSL-993, 非SSL-143</div>
            </el-form-item>
            <el-form-item label="使用SSL" prop="use_ssl">
              <el-switch v-model="editForm.use_ssl" />
            </el-form-item>
          </template>
          <template v-if="editForm.mail_type === 'outlook'">
            <el-form-item label="Client ID" prop="client_id">
              <el-input v-model="editForm.client_id" />
            </el-form-item>
            <el-form-item label="Refresh Token" prop="refresh_token">
              <el-input v-model="editForm.refresh_token" />
            </el-form-item>
          </template>
        </el-form>
        <template #footer>
          <span class="dialog-footer">
            <el-button
              v-if="editForm.mail_type === 'outlook'"
              type="warning"
              @click="openDeviceReauthFromEdit"
            >
              Device Code 重新授权
            </el-button>
            <el-button @click="editDialogVisible = false">取消</el-button>
            <el-button type="primary" @click="submitEditForm">确定</el-button>
          </span>
        </template>
      </el-dialog>

      <!-- Device Code 重新授权对话框 -->
      <el-dialog
        v-model="deviceReauthVisible"
        :title="deviceReauthTitle"
        width="520px"
        :close-on-click-modal="false"
        @closed="stopDevicePoll"
        class="responsive-dialog"
      >
        <div v-loading="deviceReauthStarting" class="device-reauth-body">
          <el-alert
            type="info"
            :closable="false"
            show-icon
            title="按下面步骤完成微软登录授权"
            class="mb-3"
          />
          <p v-if="deviceReauth.email" class="device-email">
            目标邮箱：<strong>{{ deviceReauth.email }}</strong>
          </p>
          <ol class="device-steps">
            <li>
              打开验证页面：
              <a
                v-if="deviceReauth.verification_uri"
                :href="deviceReauth.verification_uri"
                target="_blank"
                rel="noopener"
              >{{ deviceReauth.verification_uri }}</a>
              <span v-else>—</span>
            </li>
            <li class="device-code-row">
              输入代码：
              <code
                ref="userCodeEl"
                class="user-code"
                @click.stop="copyUserCode"
              >{{ deviceReauth.user_code || '……' }}</code>
              <el-button
                type="primary"
                size="small"
                class="copy-code-btn"
                :disabled="!deviceReauth.user_code"
                @click.stop="copyUserCode"
              >
                复制
              </el-button>
            </li>
            <li>使用<strong>该邮箱对应的 Microsoft 账号</strong>登录并同意权限</li>
            <li>本页会自动检测结果，成功后 Token 自动写回</li>
          </ol>

          <div class="device-status-box" :class="'status-' + deviceReauth.status">
            <template v-if="deviceReauth.status === 'pending'">
              <el-icon class="is-loading"><Refresh /></el-icon>
              等待登录中… 剩余约 {{ deviceReauth.expires_in || 0 }} 秒
            </template>
            <template v-else-if="deviceReauth.status === 'success'">
              ✅ 授权成功，Token 已保存
            </template>
            <template v-else-if="deviceReauth.status === 'expired'">
              ⏰ 代码已过期，请关闭后重新发起
            </template>
            <template v-else-if="deviceReauth.status === 'denied'">
              ❌ 用户拒绝了授权
            </template>
            <template v-else-if="deviceReauth.status === 'error'">
              ❌ {{ deviceReauth.error || '授权失败' }}
            </template>
            <template v-else>
              准备中…
            </template>
          </div>

          <p v-if="deviceReauth.message" class="device-msg">{{ deviceReauth.message }}</p>
        </div>
        <template #footer>
          <el-button @click="deviceReauthVisible = false">
            {{ deviceReauth.status === 'success' ? '完成' : '关闭' }}
          </el-button>
          <el-button
            v-if="deviceReauth.status === 'expired' || deviceReauth.status === 'error' || deviceReauth.status === 'denied'"
            type="primary"
            @click="restartDeviceReauth"
          >
            重新发起
          </el-button>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive, onUnmounted } from 'vue'
import { useEmailsStore } from '@/store/emails'
import { ElMessage, ElMessageBox, ElLoading, ElNotification } from 'element-plus'
import {
  Delete,
  Refresh,
  Plus,
  Download,
  Document,
  Message,
  View,
  Hide,
  InfoFilled
} from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import DOMPurify from 'dompurify'
import EmailContentViewer from '@/components/EmailContentViewer.vue'
import EmailAttachments from '@/components/EmailAttachments.vue'
import EmailQuoteFormatter from '@/components/EmailQuoteFormatter.vue'
import api from '@/services/api'

const emailsStore = useEmailsStore()

// 响应式对话框宽度
const windowWidth = ref(window.innerWidth)
const dialogWidth = computed(() => {
  if (windowWidth.value < 480) return '95%'
  if (windowWidth.value < 768) return '90%'
  return '600px'
})

const handleResize = () => {
  windowWidth.value = window.innerWidth
}

// 判断是否移动端
const isMobile = computed(() => windowWidth.value < 768)

// 移动端单个邮箱选择切换
const toggleEmailSelection = (email) => {
  const idx = emailsStore.selectedEmails.indexOf(email.id)
  if (idx === -1) {
    emailsStore.selectedEmails.push(email.id)
  } else {
    emailsStore.selectedEmails.splice(idx, 1)
  }
}

// 状态
const loadingMails = ref(false)
const addEmailDialogVisible = ref(false)
const addEmailActiveTab = ref('single')
const mailContentDialogVisible = ref(false)
const mailListDialogVisible = ref(false)
const addingEmail = ref(false)
const importing = ref(false)

// 添加邮箱表单引用
const addEmailFormRef = ref(null)
const batchImportFormRef = ref(null)

// 邮箱类型配置
const mailTypes = {
  outlook: {
    name: 'Outlook/Hotmail',
    color: 'primary'
  },
  imap: {
    name: 'IMAP邮箱',
    color: 'info'
  },
  gmail: {
    name: 'Gmail',
    color: 'danger'
  },
  qq: {
    name: 'QQ邮箱',
    color: 'success'
  }
}

// 获取邮箱类型名称
const getMailTypeName = (type) => {
  return mailTypes[type]?.name || type
}

// 获取邮箱类型颜色
const getMailTypeColor = (type) => {
  return mailTypes[type]?.color || 'default'
}

// 添加邮箱表单
const addEmailForm = ref({
  mail_type: 'outlook',
  email: '',
  password: '',
  client_id: '',
  refresh_token: '',
  server: '',
  port: 993,
  use_ssl: true
})

// 批量导入数据
const batchImport = reactive({
  data: '',
  mailType: 'outlook'
})

// 批量导入验证规则
const batchImportRules = {
  data: [
    { required: true, message: '导入数据不能为空', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (!value) {
          callback()
          return
        }

        const lines = value.trim().split('\n')
        let hasError = false

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i].trim()
          if (!line) continue

          // 根据不同邮箱类型进行不同的验证
          if (batchImport.mailType === 'outlook') {
            const parts = line.split('----')
            if (parts.length !== 4) {
              hasError = true
              callback(new Error(`第 ${i + 1} 行格式错误，请使用"----"分隔邮箱、密码、客户端ID和RefreshToken`))
              break
            }

            if (!parts[0] || !parts[1] || !parts[2] || !parts[3]) {
              hasError = true
              callback(new Error(`第 ${i + 1} 行有空白字段，所有字段都必须填写`))
              break
            }

            // 简单的邮箱格式检查
            if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(parts[0])) {
              hasError = true
              callback(new Error(`第 ${i + 1} 行邮箱格式不正确`))
              break
            }
          }
        }

        if (!hasError) {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

// 添加邮箱表单验证规则
const addEmailRules = {
  mail_type: [{ required: true, message: '请选择邮箱类型', trigger: 'change' }],
  email: [{ required: true, message: '请输入邮箱地址', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  client_id: [{ required: true, message: '请输入Client ID', trigger: 'blur', validator: (rule, value, callback) => {
    if (addEmailForm.value.mail_type === 'outlook' && !value) {
      callback(new Error('请输入Client ID'))
    } else {
      callback()
    }
  }}],
  refresh_token: [{ required: true, message: '请输入Refresh Token', trigger: 'blur', validator: (rule, value, callback) => {
    if (addEmailForm.value.mail_type === 'outlook' && !value) {
      callback(new Error('请输入Refresh Token'))
    } else {
      callback()
    }
  }}],
  server: [{ required: true, message: '请输入服务器地址', trigger: 'blur', validator: (rule, value, callback) => {
    if (addEmailForm.value.mail_type === 'imap' && !value) {
      callback(new Error('请输入服务器地址'))
    } else {
      callback()
    }
  }}],
  port: [{ required: true, message: '请输入端口号', trigger: 'blur' }]
}

const selectedMail = ref(null)

// 计算属性
const emails = computed(() => emailsStore.emails)
const loading = computed(() => emailsStore.loading)
const currentEmail = computed(() => emailsStore.getEmailById(emailsStore.currentEmailId))
const mailRecords = computed(() => emailsStore.currentMailRecords)
const hasSelectedEmails = computed(() => emailsStore.hasSelectedEmails)

// 排序状态（Element Plus: 'ascending' | 'descending' | null）
const sortProp = ref('')
const sortOrder = ref('')

const handleSortChange = ({ prop, order }) => {
  sortProp.value = prop || ''
  sortOrder.value = order || ''
}

const sortedEmails = computed(() => {
  const list = Array.isArray(emails.value) ? [...emails.value] : []

  if (!sortProp.value || !sortOrder.value) {
    return list
  }

  const direction = sortOrder.value === 'ascending' ? 1 : -1
  const prop = sortProp.value

  const toComparableString = (value) => String(value ?? '').toLowerCase()

  const compareString = (a, b) => {
    const as = toComparableString(a)
    const bs = toComparableString(b)
    return as.localeCompare(bs, 'en', { sensitivity: 'base' })
  }

  const compareDate = (a, b) => {
    const at = a ? dayjs(a).valueOf() : null
    const bt = b ? dayjs(b).valueOf() : null

    const aValid = Number.isFinite(at)
    const bValid = Number.isFinite(bt)

    // 空值/无效值始终排到最后（无论升序/降序）
    if (!aValid && !bValid) return 0
    if (!aValid) return 1
    if (!bValid) return -1

    if (at === bt) return 0
    return at > bt ? 1 : -1
  }

  list.sort((a, b) => {
    let result = 0

    if (prop === 'last_check_time') {
      result = compareDate(a?.last_check_time, b?.last_check_time)
    } else if (prop === 'mail_type') {
      result = compareString(a?.mail_type, b?.mail_type)
    } else {
      result = compareString(a?.[prop], b?.[prop])
    }

    return result * direction
  })

  return list
})

// 方法
const refreshEmails = async () => {
  try {
    await emailsStore.fetchEmails()
    ElMessage.success('刷新成功')
  } catch (error) {
    console.error('获取邮箱列表失败:', error)
    ElMessage.error('获取邮箱列表失败，请检查网络连接')
  }
}

const handleSelectionChange = (selection) => {
  if (Array.isArray(selection)) {
    emailsStore.selectedEmails = selection.map(item => item.id)
  } else {
    emailsStore.selectedEmails = []
  }
}

const handleDelete = (row) => {
  ElMessageBox.confirm(
    `确定要删除邮箱 ${row.email} 吗？`,
    '提示',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await emailsStore.deleteEmail(row.id)
      ElMessage.success('删除成功')
    } catch (error) {
      console.error('删除邮箱失败:', error)
      ElMessage.error('删除邮箱失败: ' + (error.message || '未知错误'))
    }
  }).catch(() => {
    // 取消删除，不做任何操作
  })
}

const handleBatchDelete = () => {
  if (!hasSelectedEmails.value) {
    ElMessage.warning('请先选择要删除的邮箱')
    return
  }

  const count = emailsStore.selectedEmailsCount
  // 确保是数组并且创建副本
  const emailIds = Array.isArray(emailsStore.selectedEmails) ?
    [...emailsStore.selectedEmails] : []

  if (emailIds.length === 0) {
    ElMessage.warning('没有选中有效的邮箱')
    return
  }

  ElMessageBox.confirm(
    `确定要删除选中的 ${count} 个邮箱吗？`,
    '批量删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await emailsStore.deleteEmails(emailIds)
      ElMessage.success(`已成功删除 ${count} 个邮箱`)
    } catch (error) {
      console.error('批量删除邮箱失败:', error)
      ElMessage.error('批量删除邮箱失败: ' + (error.message || '未知错误'))
    }
  }).catch(() => {
    // 取消删除，不做任何操作
  })
}

const handleCheck = async (row) => {
  try {
    const result = await emailsStore.checkEmail(row.id)

    // 检查结果，确定是否显示正在处理中的消息
    if (result && result.status === 'processing') {
      ElMessage.warning(result.message || '邮箱正在处理中，请稍候...')
    } else {
      ElMessage.info(`正在检查邮箱 ${row.email} 的邮件，请稍候...`)
    }
  } catch (error) {
    console.error('检查邮箱失败:', error)
    ElMessage.error('检查邮箱失败: ' + (error.message || '未知错误'))
  }
}

const handleBatchCheck = async () => {
  if (!hasSelectedEmails.value) {
    ElMessage.warning('请先选择要检查的邮箱')
    return
  }

  const count = emailsStore.selectedEmailsCount
  // 确保是数组并且创建副本
  const emailIds = Array.isArray(emailsStore.selectedEmails) ?
    [...emailsStore.selectedEmails] : []

  if (emailIds.length === 0) {
    ElMessage.warning('没有选中有效的邮箱')
    return
  }

  try {
    await emailsStore.checkEmails(emailIds)
    ElMessage.info(`正在检查 ${count} 个邮箱的邮件，请稍候...`)
  } catch (error) {
    console.error('批量检查邮箱失败:', error)
    ElMessage.error('批量检查邮箱失败: ' + (error.message || '未知错误'))
  }
}

const getEmailsForExport = () => {
  const list = Array.isArray(sortedEmails.value) ? sortedEmails.value : []

  if (hasSelectedEmails.value) {
    const selectedIds = new Set(Array.isArray(emailsStore.selectedEmails) ? emailsStore.selectedEmails : [])
    return list.filter(row => selectedIds.has(row.id))
  }

  return list
}

const getExportPassword = async (row) => {
  if (row?.password && row.password !== '******') {
    return String(row.password)
  }

  try {
    const result = await emailsStore.getEmailPassword(row.id)
    return result?.password ? String(result.password) : ''
  } catch (error) {
    console.warn('获取邮箱密码失败（将导出为空）:', error)
    return ''
  }
}

const formatOutlook4PartLine = async (row) => {
  const email = String(row?.email ?? '')
  const password = await getExportPassword(row)

  const isOutlook = row?.mail_type === 'outlook'
  const clientId = isOutlook ? String(row?.client_id ?? '') : ''
  const refreshToken = isOutlook ? String(row?.refresh_token ?? '') : ''

  return [email, password, clientId, refreshToken].join('----')
}

const downloadTextFile = (filename, content) => {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)

  const link = document.createElement('a')
  link.href = url
  link.download = filename

  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)

  URL.revokeObjectURL(url)
}

const handleExportTxt = async () => {
  const exportRows = getEmailsForExport()

  if (exportRows.length === 0) {
    ElMessage.warning('没有可导出的邮箱')
    return
  }

  const lines = []
  for (const row of exportRows) {
    // 统一按Outlook 4段格式输出，非Outlook的client_id/refresh_token留空
    // 内容使用LF换行（\n），避免CRLF
    lines.push(await formatOutlook4PartLine(row))
  }

  const content = lines.join('\n') + '\n'
  const filename = `emails_export_${dayjs().format('YYYYMMDD_HHmmss')}.txt`
  downloadTextFile(filename, content)

  const scopeText = hasSelectedEmails.value ? '已选中' : '全部'
  ElMessage.success(`导出成功（${scopeText} ${exportRows.length} 条）`)
}

const handleViewMails = async (row) => {
  loadingMails.value = true
  try {
    emailsStore.currentEmailId = row.id
    await emailsStore.fetchMailRecords(row.id)
    mailListDialogVisible.value = true
  } catch (error) {
    console.error('获取邮件记录失败:', error)
    ElMessage.error('获取邮件记录失败: ' + (error.message || '未知错误'))
  } finally {
    loadingMails.value = false
  }
}

const viewMailContent = (mail) => {
  // 增加防护检查，确保mail对象及其必要字段存在
  if (!mail) {
    ElMessage.warning('邮件数据不存在或格式错误');
    return;
  }

  // 创建一个格式化后的副本，防止直接修改原始数据
  const formattedMail = {
    ...mail,
    subject: mail.subject || '(无主题)',
    sender: mail.sender || '(未知发件人)',
    received_time: mail.received_time || new Date().toISOString(),
    content: mail.content || '(无内容)'
  };

  selectedMail.value = formattedMail;
  mailContentDialogVisible.value = true;
}

const showAddEmailDialog = () => {
  resetAddEmailForm()
  addEmailDialogVisible.value = true
  addEmailActiveTab.value = 'single'
}

const deviceAddEmail = ref('')
const deviceAddClientId = ref('')

async function startDeviceAdd() {
  const email = deviceAddEmail.value.trim()
  if (!email || !email.includes('@')) {
    ElMessage.warning('请填写有效邮箱地址')
    return
  }
  addEmailDialogVisible.value = false
  deviceReauthTarget.value = {
    mode: 'add',
    email,
    client_id: deviceAddClientId.value.trim() || undefined
  }
  deviceReauthVisible.value = true
  await startDeviceSession()
}

const handleAddOrImport = async () => {
  if (addEmailActiveTab.value === 'device') {
    await startDeviceAdd()
    return
  }
  if (addEmailActiveTab.value === 'single') {
    await handleAddEmail()
  } else {
    await handleImport()
  }
}

const handleAddEmail = async () => {
  if (!addEmailFormRef.value) return

  try {
    // 表单验证
    await addEmailFormRef.value.validate()

    addingEmail.value = true
    const loading = ElLoading.service({
      lock: true,
      text: '正在添加邮箱...',
      background: 'rgba(0, 0, 0, 0.7)'
    })

    const formData = {
      email: addEmailForm.value.email,
      password: addEmailForm.value.password,
      mail_type: addEmailForm.value.mail_type
    }

    if (addEmailForm.value.mail_type === 'outlook') {
      formData.client_id = addEmailForm.value.client_id
      formData.refresh_token = addEmailForm.value.refresh_token
    } else if (addEmailForm.value.mail_type === 'imap') {
      formData.server = addEmailForm.value.server
      formData.port = addEmailForm.value.port
      formData.use_ssl = addEmailForm.value.use_ssl
    }

    await emailsStore.addEmail(formData)
    addEmailDialogVisible.value = false
    ElMessage.success('添加邮箱成功')

    // 刷新邮箱列表
    await refreshEmails()
  } catch (error) {
    console.error('添加邮箱失败:', error)
    ElMessage.error('添加邮箱失败: ' + (error.message || '未知错误'))
  } finally {
    addingEmail.value = false
    ElLoading.service().close()
  }
}

const handleImport = async () => {
  if (!batchImportFormRef.value) return

  try {
    await batchImportFormRef.value.validate()

    importing.value = true
    ElMessage.info('正在校验 Token 并导入，无效账号不会写入…')

    const importData = {
      data: batchImport.data.trim(),
      mail_type: batchImport.mailType
    }

    const result = await emailsStore.importEmails(importData)
    const ok = result?.success || 0
    const fail = result?.failed || 0

    if (ok > 0 && fail === 0) {
      ElMessage.success(`全部成功：已导入 ${ok} 个邮箱`)
      addEmailDialogVisible.value = false
    } else if (ok > 0 && fail > 0) {
      const details = (result.failed_details || [])
        .slice(0, 5)
        .map(d => `${d.email || '第' + d.line + '行'}: ${d.reason}`)
        .join('\n')
      ElNotification({
        title: `部分成功（成功 ${ok} / 失败 ${fail}）`,
        message: details || result.message || '部分账号 Token 无效，未写入',
        type: 'warning',
        duration: 12000,
        dangerouslyUseHTMLString: false
      })
      // 保留对话框，方便对照失败原因；仍刷新列表
    } else {
      const details = (result.failed_details || [])
        .slice(0, 8)
        .map(d => `${d.email || '第' + d.line + '行'}: ${d.reason}`)
        .join('\n')
      ElNotification({
        title: '导入失败（全部未写入）',
        message: details || result?.message || '全部账号校验失败',
        type: 'error',
        duration: 12000
      })
    }

    await refreshEmails()
  } catch (error) {
    console.error('导入邮箱失败:', error)
    ElMessage.error(
      '导入邮箱失败: ' +
        (error?.response?.data?.error || error.message || '未知错误')
    )
  } finally {
    importing.value = false
  }
}

const resetAddEmailForm = () => {
  addEmailForm.value = {
    mail_type: 'outlook',
    email: '',
    password: '',
    client_id: '',
    refresh_token: '',
    server: '',
    port: 993,
    use_ssl: true
  }
}

// ---------- Device Code 重新授权 ----------
const deviceReauthVisible = ref(false)
const deviceReauthStarting = ref(false)
const devicePollTimer = ref(null)
const deviceReauthTarget = ref(null) // { id?, email, client_id?, mode: 'reauth'|'add' }
const deviceReauth = reactive({
  session_id: '',
  user_code: '',
  verification_uri: '',
  message: '',
  status: '',
  interval: 5,
  expires_in: 0,
  email: '',
  error: '',
  email_id: null
})

const deviceReauthTitle = computed(() => {
  if (deviceReauthTarget.value?.mode === 'add') return 'Device Code 添加 Outlook'
  return 'Device Code 重新授权'
})

function authStatusLabel(row) {
  const s = row?.auth_status || 'ok'
  if (s === 'need_reauth') return '需重授'
  if (s === 'error') return '异常'
  return '正常'
}

function authStatusClass(row) {
  const s = row?.auth_status || 'ok'
  if (s === 'need_reauth') return 'auth-need'
  if (s === 'error') return 'auth-error'
  return 'auth-ok'
}

function stopDevicePoll() {
  if (devicePollTimer.value) {
    clearTimeout(devicePollTimer.value)
    devicePollTimer.value = null
  }
}

const userCodeEl = ref(null)

/** 兼容 HTTP / 非 secure context / 权限受限 的剪贴板写入 */
async function copyTextToClipboard(text) {
  if (!text) return false

  // 1) 现代 Clipboard API（仅 HTTPS / localhost 等 secure context 可靠）
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch (_) {
      // fall through
    }
  }

  // 2) 传统 execCommand 回退（HTTP / iframe 等场景）
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.setAttribute('readonly', '')
    ta.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;padding:0;border:none;opacity:0;'
    document.body.appendChild(ta)
    ta.focus()
    ta.select()
    ta.setSelectionRange(0, text.length)
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    if (ok) return true
  } catch (_) {
    // fall through
  }

  // 3) 选中页面上的代码节点，方便用户 Ctrl/Cmd+C
  try {
    const el = userCodeEl.value
    if (el && window.getSelection && document.createRange) {
      const range = document.createRange()
      range.selectNodeContents(el)
      const sel = window.getSelection()
      sel.removeAllRanges()
      sel.addRange(range)
    }
  } catch (_) {
    // ignore
  }
  return false
}

async function copyUserCode() {
  const code = deviceReauth.user_code
  if (!code) {
    ElMessage.warning('暂无授权代码可复制')
    return
  }
  const ok = await copyTextToClipboard(code)
  if (ok) {
    ElMessage.success('已复制授权代码')
  } else {
    ElMessage.warning(`自动复制失败，请手动复制：${code}`)
  }
}

async function openDeviceReauth(row) {
  deviceReauthTarget.value = {
    mode: 'reauth',
    id: row.id,
    email: row.email,
    client_id: row.client_id
  }
  deviceReauthVisible.value = true
  await startDeviceSession()
}

function openDeviceReauthFromEdit() {
  const f = editForm.value
  if (!f?.id) {
    ElMessage.warning('请先保存邮箱后再重新授权，或从列表点击「重新授权」')
    return
  }
  editDialogVisible.value = false
  openDeviceReauth({
    id: f.id,
    email: f.email,
    client_id: f.client_id,
    mail_type: 'outlook'
  })
}

async function restartDeviceReauth() {
  await startDeviceSession()
}

async function startDeviceSession() {
  stopDevicePoll()
  deviceReauthStarting.value = true
  deviceReauth.status = ''
  deviceReauth.error = ''
  deviceReauth.user_code = ''
  deviceReauth.session_id = ''

  const target = deviceReauthTarget.value
  if (!target) {
    deviceReauthStarting.value = false
    return
  }

  try {
    let res
    if (target.mode === 'add') {
      res = await api.startDeviceCodeAdd({
        email: target.email,
        client_id: target.client_id || undefined,
        password: target.password || '[OAUTH]'
      })
    } else {
      res = await api.startEmailDeviceCode(target.id, {
        client_id: target.client_id || undefined
      })
    }
    const data = res.data || res
    if (!data.success) {
      throw new Error(data.error || data.message || '发起授权失败')
    }
    deviceReauth.session_id = data.session_id
    deviceReauth.user_code = data.user_code
    deviceReauth.verification_uri = data.verification_uri
    deviceReauth.message = data.message
    deviceReauth.interval = data.interval || 5
    deviceReauth.expires_in = data.expires_in || 900
    deviceReauth.email = data.email_address || target.email
    deviceReauth.email_id = data.email_id || target.id
    deviceReauth.status = 'pending'
    scheduleDevicePoll(deviceReauth.interval)
  } catch (e) {
    deviceReauth.status = 'error'
    deviceReauth.error =
      e?.response?.data?.error || e?.message || '发起 Device Code 失败'
    ElMessage.error(deviceReauth.error)
  } finally {
    deviceReauthStarting.value = false
  }
}

function scheduleDevicePoll(seconds) {
  stopDevicePoll()
  const wait = Math.max(Number(seconds) || 5, 2) * 1000
  devicePollTimer.value = setTimeout(pollDeviceOnce, wait)
}

async function pollDeviceOnce() {
  if (!deviceReauth.session_id || !deviceReauthVisible.value) return
  try {
    const res = await api.pollDeviceCode(deviceReauth.session_id)
    const data = res.data || res
    deviceReauth.status = data.status || deviceReauth.status
    deviceReauth.message = data.message || deviceReauth.message
    deviceReauth.expires_in = data.expires_in ?? deviceReauth.expires_in
    deviceReauth.error = data.error || ''
    if (data.interval) deviceReauth.interval = data.interval

    if (data.status === 'pending') {
      scheduleDevicePoll(data.interval || deviceReauth.interval)
      return
    }

    stopDevicePoll()
    if (data.status === 'success') {
      ElNotification({
        title: '重新授权成功',
        message: `${deviceReauth.email || '邮箱'} 的 Token 已更新`,
        type: 'success',
        duration: 5000
      })
      await refreshEmails()
    } else if (data.status === 'expired') {
      ElMessage.warning('授权代码已过期，请重新发起')
    } else if (data.status === 'denied') {
      ElMessage.error('用户拒绝了授权')
    } else if (data.status === 'error') {
      ElMessage.error(data.error || '授权失败')
    }
  } catch (e) {
    // 网络抖动：继续轮询
    scheduleDevicePoll(deviceReauth.interval || 5)
  }
}

// 格式化日期
const formatDate = (dateString) => {
  if (!dateString) return '无';
  return dayjs(dateString).format('YYYY-MM-DD HH:mm:ss');
};

// 判断邮箱是否正在处理中
const isEmailProcessing = (email) => {
  const status = emailsStore.getProcessingStatus(email.id)
  return status && status.progress >= 0 && status.progress < 100
}

// 获取邮箱操作文本
const getEmailActionText = (email) => {
  return isEmailProcessing(email) ? '检查中...' : '检查邮件'
}

const togglePasswordVisibility = async (row) => {
  // 如果已经显示密码，则隐藏
  if (row.showPassword) {
    row.showPassword = false;
    return;
  }

  // 否则，从后端获取密码
  if (!row.password || row.password === '******') {
    row.passwordLoading = true;
    try {
      const response = await emailsStore.getEmailPassword(row.id);
      if (response && response.password) {
        row.password = response.password;
      }
    } catch (error) {
      console.error('获取密码失败:', error);
      ElMessage.error('获取密码失败: ' + (error.message || '未知错误'));
    } finally {
      row.passwordLoading = false;
    }
  }

  // 显示密码
  row.showPassword = true;
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

// 截断内容
const truncateContent = (content) => {
  if (!content) return content;

  const maxLength = 1000; // 设置最大长度
  if (content.length > maxLength) {
    return content.slice(0, maxLength) + '...';
  }
  return content;
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

// 添加编辑按钮的处理函数
const handleEdit = (email) => {
  // 确保use_ssl是布尔值
  const emailData = { ...email }
  if (emailData.mail_type === 'imap') {
    emailData.use_ssl = Boolean(emailData.use_ssl)
  }
  editForm.value = emailData
  editDialogVisible.value = true
}

// 引用和定义编辑对话框相关变量
const editDialogVisible = ref(false)
const editFormRef = ref(null)
const editForm = ref({
  id: null,
  email: '',
  password: '',
  mail_type: 'outlook',
  server: '',
  port: 993,
  use_ssl: true,
  client_id: '',
  refresh_token: ''
})

// 密码强度相关
const passwordStrength = ref(0)
const passwordStrengthColor = computed(() => {
  if (passwordStrength.value < 40) return '#F56C6C'
  if (passwordStrength.value < 80) return '#E6A23C'
  return '#67C23A'
})

const passwordStrengthText = (percentage) => {
  if (percentage < 40) return '弱'
  if (percentage < 80) return '中'
  return '强'
}

const checkPasswordStrength = (password) => {
  if (!password) {
    passwordStrength.value = 0
    return
  }

  let strength = 0
  // 检查长度
  if (password.length >= 8) strength += 20
  // 检查是否包含数字
  if (/\d/.test(password)) strength += 20
  // 检查是否包含小写字母
  if (/[a-z]/.test(password)) strength += 20
  // 检查是否包含大写字母
  if (/[A-Z]/.test(password)) strength += 20
  // 检查是否包含特殊字符
  if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) strength += 20

  passwordStrength.value = strength
}

// 编辑表单的规则
const editRules = {
  email: [
    { required: true, message: '邮箱地址不能为空', trigger: 'blur' },
    { type: 'email', message: '邮箱地址格式不正确', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '密码不能为空', trigger: 'blur' },
    { min: 6, message: '密码长度不能小于6位', trigger: 'blur' }
  ],
  server: [
    { required: true, message: 'IMAP服务器地址不能为空', trigger: 'blur',
      // 仅当类型为imap时验证
      validator: (rule, value, callback) => {
        if (editForm.value.mail_type === 'imap' && !value) {
          callback(new Error('IMAP服务器地址不能为空'));
        } else {
          callback();
        }
      }
    }
  ],
  port: [
    {
      required: true,
      message: '端口号不能为空',
      trigger: 'blur',
      // 仅当类型为imap时验证
      validator: (rule, value, callback) => {
        if (editForm.value.mail_type === 'imap' && (!value || isNaN(value))) {
          callback(new Error('端口号必须是有效数字'));
        } else {
          callback();
        }
      }
    }
  ],
  client_id: [
    {
      required: true,
      message: 'Client ID不能为空',
      trigger: 'blur',
      // 仅当类型为outlook时验证
      validator: (rule, value, callback) => {
        if (editForm.value.mail_type === 'outlook' && !value) {
          callback(new Error('Client ID不能为空'));
        } else {
          callback();
        }
      }
    }
  ],
  refresh_token: [
    {
      required: true,
      message: 'Refresh Token不能为空',
      trigger: 'blur',
      // 仅当类型为outlook时验证
      validator: (rule, value, callback) => {
        if (editForm.value.mail_type === 'outlook' && !value) {
          callback(new Error('Refresh Token不能为空'));
        } else {
          callback();
        }
      }
    }
  ],
}

// 重置编辑表单
const resetEditForm = () => {
  editForm.value = {
    id: null,
    email: '',
    password: '******',  // 默认显示星号，实际修改时会获取真实密码
    mail_type: 'outlook',
    client_id: '',
    refresh_token: '',
    server: '',
    port: 993,
    use_ssl: true
  }
}

// 提交编辑表单
const submitEditForm = async () => {
  if (!editFormRef.value) return

  try {
    await editFormRef.value.validate()

    // 准备提交的数据
    const formData = { ...editForm.value }

    // 如果密码仍然是默认的星号，则不发送密码更新
    if (formData.password === '******') {
      delete formData.password
    }

    const loading = ElLoading.service({
      lock: true,
      text: '正在更新邮箱...',
      background: 'rgba(0, 0, 0, 0.7)'
    })

    await emailsStore.updateEmail(formData.id, formData)
    editDialogVisible.value = false

    // 刷新邮箱列表
    await refreshEmails()

    ElMessage.success('邮箱更新成功')
  } catch (error) {
    console.error('更新邮箱失败:', error)
    ElMessage.error('更新邮箱失败: ' + (error.message || '未知错误'))
  } finally {
    ElLoading.service().close()
  }
}

// 生命周期钩子
onMounted(() => {
  emailsStore.initWebSocketListeners()
  refreshEmails()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  stopDevicePoll()
})
</script>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: var(--bg-color);
  overflow-x: hidden;
}

.emails-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
  max-width: 100%;
  margin: 0 auto;
  width: 100%;
}

.email-list-card {
  margin-bottom: 20px;
  transition: all var(--transition-normal);
}

.card-header {
  width: 100%;
}

.page-title {
  font-size: 1.5rem;
  color: var(--primary-color);
  margin: 0;
  position: relative;
  display: inline-block;
}

.page-title::after {
  content: '';
  position: absolute;
  bottom: -5px;
  left: 0;
  width: 40px;
  height: 3px;
  background-color: var(--primary-color);
  border-radius: 999px;
}

.email-table {
  border-radius: 0.75rem;
  overflow: hidden;
  border: none !important;
}

/* 表格整体美化 */
.email-table :deep(.el-table__inner-wrapper) {
  border-radius: 0.75rem;
}

.email-table :deep(.el-table__header-wrapper) {
  border-radius: 0.75rem 0.75rem 0 0;
}

/* 增强表格样式 */
.email-table :deep(.el-table__header) {
  background: linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%);
}

.email-table :deep(.el-table__header th) {
  background: transparent;
  font-weight: 600;
  color: #475569;
  padding: 14px 12px;
  border-bottom: 2px solid #E2E8F0;
}

.email-table :deep(.el-table__header th .cell) {
  font-size: 0.875rem;
  letter-spacing: 0.025em;
}

.email-table :deep(.el-table__body td) {
  padding: 12px;
  border-bottom: 1px solid #F1F5F9;
}

.email-table :deep(.el-table__row) {
  transition: all 0.2s ease;
}

.email-table :deep(.el-table__row:hover) {
  background-color: rgba(99, 102, 241, 0.04) !important;
}

.email-table :deep(.el-table__row:hover td) {
  background-color: transparent !important;
}

.email-table :deep(.el-table__row.current-row) {
  background-color: rgba(99, 102, 241, 0.08);
}

/* 选择框列样式 */
.email-table :deep(.selection-column .cell) {
  padding-left: 14px;
  padding-right: 8px;
}

/* 邮箱地址单元格样式 */
.email-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.email-avatar {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--primary-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: none;
}

.email-avatar span {
  color: white;
  font-weight: 600;
  font-size: 0.95rem;
  text-transform: uppercase;
}

.email-text {
  font-weight: 500;
  color: #1E293B;
  font-size: 0.9rem;
}

/* 增强按钮样式 */
.toolbar .el-button {
  font-weight: 500;
  border-radius: 0.5rem;
}

.action-btn {
  border-radius: 0.375rem;
  font-weight: 500;
}

.mail-type-tag {
  font-weight: 500;
  white-space: nowrap;
  padding: 4px 12px;
  font-size: 0.8rem;
}

/* 密码列：避免 el-table .cell overflow 裁切显示/隐藏按钮 */
.email-table :deep(.password-column .cell) {
  overflow: visible;
  display: flex;
  align-items: center;
}

.password-field {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  min-width: 0;
}

.password-text {
  flex: 1 1 auto;
  min-width: 0;
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  background: linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%);
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 0.85rem;
  color: #475569;
  letter-spacing: 0.05em;
  box-sizing: border-box;
}

.password-toggle-btn {
  flex: 0 0 auto;
  padding: 4px 6px !important;
  margin: 0 !important;
  height: 28px;
  min-width: 28px;
  z-index: 2;
  position: relative;
  transition: all 0.2s ease;
}

.password-toggle-btn:hover {
  transform: none;
  color: var(--primary-dark);
}

.time-field {
  color: var(--secondary-text-color);
  font-size: 0.9rem;
}

.progress-container {
  width: 100%;
  padding: 0 5px;
}

.progress-message {
  font-size: 0.8rem;
  margin-top: 4px;
}

.action-buttons {
  display: flex;
  flex-wrap: nowrap;
  gap: 6px;
  justify-content: flex-start;
  align-items: center;
  white-space: nowrap;
}

.action-buttons .el-button {
  margin: 0 !important;
  padding: 5px 10px !important;
  height: 28px !important;
  font-size: 12px !important;
  font-weight: 560 !important;
}

.action-buttons .btn-check {
  background: var(--primary-color) !important;
  border-color: var(--primary-color) !important;
  color: #fff !important;
  min-width: 72px;
}

.action-buttons .btn-check:hover:not(:disabled) {
  background: var(--primary-light) !important;
  border-color: var(--primary-light) !important;
  color: #fff !important;
}

.action-buttons .btn-check.is-disabled,
.action-buttons .btn-check:disabled {
  opacity: 0.55;
  color: #fff !important;
}

.action-buttons .btn-reauth {
  background: var(--primary-soft) !important;
  border-color: var(--primary-muted) !important;
  color: var(--primary-dark) !important;
}

.auth-status-tag,
.auth-inline-tag {
  border: 1px solid transparent !important;
  font-weight: 560 !important;
  height: 22px !important;
  line-height: 20px !important;
  padding: 0 8px !important;
}

.auth-ok {
  background: #E8F0E9 !important;
  color: #5A7A5E !important;
  border-color: #C9D9CB !important;
}

.auth-need {
  background: #F8EBE7 !important;
  color: #A65A4A !important;
  border-color: #E8C9C0 !important;
}

.auth-error {
  background: #F3EDE0 !important;
  color: #8B7345 !important;
  border-color: #E0D5BC !important;
}

.email-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.email-main .email-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.auth-inline-tag {
  width: fit-content;
  max-width: 100%;
}

/* 固定操作列不要把前一列压没 */
.email-table :deep(.ops-column) {
  background: var(--card-bg) !important;
}

.email-table :deep(.el-table__fixed-right) {
  box-shadow: -4px 0 8px rgba(44, 42, 36, 0.04) !important;
}

.email-table :deep(.el-table__fixed-right-patch) {
  background: var(--card-bg) !important;
}

.mail-dialog-header {
  padding: 0 0 10px 0;
  border-bottom: 1px solid var(--border-color-light);
}

.email-title {
  font-size: 1.2rem;
  margin: 0;
}

.mail-list-table {
  border-radius: var(--border-radius);
  overflow: hidden;
}

.subject-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.attachment-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.mail-detail {
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 88vh;
  overflow-y: auto;
}

.mail-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.info-item {
  width: 100%;
}

.label {
  font-weight: 500;
  margin-right: 10px;
}

.mail-content {
  max-height: 400px;
  overflow-y: auto;
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

.mail-content-text {
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: break-word;
  max-width: 100%;
  font-family: monospace;
  font-size: 0.9rem;
  line-height: 1.5;
  padding: 10px;
  background-color: var(--bg-light);
  border-radius: var(--border-radius);
}

.html-content {
  max-width: 100%;
  overflow-x: auto;
  padding: 10px;
  background-color: var(--bg-light);
  border-radius: var(--border-radius);
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

.add-email-form {
  padding: 20px;
}

.w-full {
  width: 100%;
}

.import-help {
  margin-bottom: 20px;
  padding: 10px;
  background-color: var(--bg-light);
  border-radius: var(--border-radius);
  font-size: 0.9rem;
  line-height: 1.5;
}

.server-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.8rem;
  background: #F8FAFC;
  padding: 8px 10px;
  border-radius: 6px;
}

.server-field, .port-field {
  color: #64748B;
}

.server-field strong, .port-field strong {
  color: #475569;
  margin-right: 4px;
}

.config-info {
  font-size: 0.8rem;
  color: #64748B;
  background: linear-gradient(135deg, #F0FDF4 0%, #DCFCE7 100%);
  padding: 6px 12px;
  border-radius: 6px;
  display: inline-block;
}

.flex {
  display: flex;
  align-items: center;
}

.flex-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.gap-sm {
  gap: 8px;
}

.gap-md {
  gap: 16px;
}

.mb-4 {
  margin-bottom: 16px;
}

.text-center {
  text-align: center;
}

.text-primary {
  color: var(--primary-color);
}

.hover-scale {
  transition: transform 0.2s;
}

.hover-scale:hover:not(:disabled) { transform: none !important;
  transform: none;
}

/* Modern Card Styles */
.email-list-card {
  border-radius: 1rem;
  border: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.email-list-card :deep(.el-card__header) {
  border-bottom: 1px solid #E2E8F0;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.05) 0%, rgba(139, 92, 246, 0.05) 100%);
  border-radius: 1rem 1rem 0 0;
}

/* 移动端卡片列表样式 */
.mobile-email-list {
  display: none;
}

.email-card {
  background: #fff;
  border-radius: 0.75rem;
  border: 1px solid #E2E8F0;
  padding: 1rem;
  margin-bottom: 0.75rem;
  transition: all 0.2s ease;
}

.email-card:hover {
  box-shadow: none;
  border-color: var(--primary-muted);
}

.email-card.selected {
  border-color: var(--primary-color);
  background: rgba(99, 102, 241, 0.05);
}

.email-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.email-card-body {
  margin-bottom: 0.75rem;
}

.email-address {
  font-weight: 600;
  color: #1E293B;
  font-size: 0.95rem;
  word-break: break-all;
  margin-bottom: 0.5rem;
}

.email-meta {
  font-size: 0.8rem;
  color: #64748B;
}

.meta-label {
  margin-right: 0.25rem;
}

.email-card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.email-card-actions .el-button {
  flex: 1;
  min-width: calc(50% - 0.25rem);
}

/* Mobile Responsive Styles */
@media (max-width: 768px) {
  .emails-container {
    padding: 0.75rem;
  }

  /* 隐藏桌面表格，显示移动端卡片 */
  .desktop-table {
    display: none !important;
  }

  .mobile-email-list {
    display: block;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 1rem;
  }

  .card-header .actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .card-header .actions .el-button {
    flex: 1;
    min-width: 45%;
  }

  .toolbar {
    flex-wrap: wrap;
  }

  .toolbar .el-button {
    flex: 1;
    min-width: 30%;
    font-size: 0.8rem;
    padding: 8px 12px;
  }

  .email-table :deep(.el-table__header-wrapper) {
    display: none;
  }

  .email-table :deep(.el-table__body-wrapper) {
    overflow-x: auto;
  }

  .action-buttons {
    flex-direction: column;
    width: 100%;
  }

  .action-btn {
    width: 100%;
    min-width: unset;
  }

  /* 响应式对话框样式 */
  .responsive-dialog :deep(.el-dialog) {
    margin: 1rem auto !important;
    max-height: 90vh;
  }

  .responsive-dialog :deep(.el-dialog__body) {
    max-height: calc(90vh - 120px);
    overflow-y: auto;
    padding: 1rem;
  }

  .add-email-form {
    padding: 0.5rem;
  }

  .add-email-form :deep(.el-form-item) {
    margin-bottom: 1rem;
  }

  .add-email-form :deep(.el-form-item__label) {
    width: 100% !important;
    text-align: left;
    padding-bottom: 0.5rem;
    float: none;
  }

  .add-email-form :deep(.el-form-item__content) {
    margin-left: 0 !important;
  }

  .page-title {
    font-size: 1.25rem;
  }

  .mail-detail {
    height: auto;
    max-height: 80vh;
  }
}

@media (max-width: 480px) {
  .emails-container {
    padding: 0.5rem;
  }

  .card-header .actions .el-button {
    min-width: 100%;
  }

  .toolbar .el-button {
    min-width: 48%;
    font-size: 0.75rem;
  }

  .page-title {
    font-size: 1.1rem;
  }

  .email-list-card :deep(.el-card__body) {
    padding: 0.75rem;
  }

  /* 超小屏对话框优化 */
  .responsive-dialog :deep(.el-dialog__header) {
    padding: 0.75rem 1rem;
  }

  .responsive-dialog :deep(.el-dialog__title) {
    font-size: 1rem;
  }

  .responsive-dialog :deep(.el-dialog__body) {
    padding: 0.75rem;
  }

  .responsive-dialog :deep(.el-dialog__footer) {
    padding: 0.75rem 1rem;
  }

  .add-email-form :deep(.el-input),
  .add-email-form :deep(.el-select),
  .add-email-form :deep(.el-textarea__inner) {
    font-size: 16px; /* 防止iOS缩放 */
  }

  /* 批量导入文本框优化 */
  .import-help {
    font-size: 0.8rem;
    padding: 0.75rem;
  }
}

.device-reauth-body {
  line-height: 1.6;
}
.device-email {
  margin: 8px 0 12px;
}
.device-steps {
  padding-left: 1.25rem;
  margin: 0 0 16px;
}
.device-steps li {
  margin-bottom: 8px;
}
.device-code-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.user-code {
  display: inline-block;
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  padding: 4px 10px;
  background: #fef3c7;
  color: #92400e;
  border-radius: 6px;
  cursor: pointer;
  user-select: all;
  -webkit-user-select: all;
}
.copy-code-btn {
  flex-shrink: 0;
}
.device-status-box {
  padding: 12px 14px;
  border-radius: 8px;
  background: #f1f5f9;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.device-status-box.status-pending {
  background: #eff6ff;
  color: #1d4ed8;
}
.device-status-box.status-success {
  background: #ecfdf5;
  color: #047857;
}
.device-status-box.status-error,
.device-status-box.status-denied,
.device-status-box.status-expired {
  background: #fef2f2;
  color: #b91c1c;
}
.device-msg {
  color: #64748b;
  font-size: 0.9rem;
}
.mb-3 {
  margin-bottom: 12px;
}
</style>

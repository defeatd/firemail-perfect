<template>
  <div class="email-list">
    <!-- 邮箱列表 -->
    <el-table :data="emails" style="width: 100%">
      <el-table-column prop="email" label="邮箱地址" />
      <el-table-column prop="mail_type" label="类型" width="100">
        <template #default="scope">
          {{ scope.row.mail_type === 'outlook' ? 'Outlook' : 'IMAP' }}
        </template>
      </el-table-column>
      <el-table-column prop="last_check_time" label="最后检查时间" width="180" />
      <el-table-column label="操作" width="300" align="center">
        <template #default="scope">
          <div class="action-buttons flex gap-sm">
            <el-button
              type="primary"
              size="small"
              @click="checkEmail(scope.row.id)"
              class="action-btn"
            >
              检查邮件
            </el-button>
            <el-button
              type="success"
              size="small"
              @click="viewEmails(scope.row.id)"
              class="action-btn"
            >
              查看邮件
            </el-button>
            <el-button
              type="danger"
              size="small"
              @click="deleteEmail(scope.row.id)"
              class="action-btn"
            >
              删除
            </el-button>
            <el-button
              type="warning"
              size="small"
              @click="editEmail(scope.row)"
              class="action-btn"
            >
              编辑
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑邮箱"
      width="500px"
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
        <el-form-item label="邮箱类型" prop="mail_type">
          <el-select v-model="editForm.mail_type" style="width: 100%">
            <el-option label="Outlook" value="outlook" />
            <el-option label="IMAP" value="imap" />
          </el-select>
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
            :rules="[
              { required: true, message: '请输入IMAP服务器地址', trigger: 'blur' },
              { type: 'string', pattern: /^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/, message: '请输入有效的服务器地址', trigger: 'blur' }
            ]"
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
            :rules="[
              { required: true, message: '请输入端口号', trigger: 'blur' },
              { type: 'number', min: 1, max: 65535, message: '端口号范围: 1-65535', trigger: 'blur' }
            ]"
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
        <el-form-item v-if="editForm.mail_type === 'imap'">
          <el-button type="primary" @click="testConnection" :loading="testing">
            测试连接
          </el-button>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="editDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitEditForm">确定</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import { InfoFilled, Search, Edit, Delete, Message as View } from '@element-plus/icons-vue'

const store = useStore()
const router = useRouter()
const emails = ref([])
const editDialogVisible = ref(false)
const editFormRef = ref(null)
const editForm = ref({
  id: null,
  email: '',
  password: '',
  mail_type: 'imap',
  server: '',
  port: 993,
  use_ssl: true,
  client_id: '',
  refresh_token: ''
})

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

const editRules = {
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码长度至少为8位', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value && passwordStrength.value < 60) {
          callback(new Error('密码强度不足'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ],
  mail_type: [
    { required: true, message: '请选择邮箱类型', trigger: 'change' }
  ],
  server: [
    { required: true, message: '请输入服务器地址', trigger: 'blur' }
  ],
  port: [
    { required: true, message: '请输入端口号', trigger: 'blur' }
  ],
  client_id: [
    { required: true, message: '请输入Client ID', trigger: 'blur' }
  ],
  refresh_token: [
    { required: true, message: '请输入Refresh Token', trigger: 'blur' }
  ]
}

const testing = ref(false)

// 获取邮箱列表
const fetchEmails = async () => {
  try {
    const response = await fetch('/api/emails', {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })
    if (response.ok) {
      emails.value = await response.json()
    } else {
      ElMessage.error('获取邮箱列表失败')
    }
  } catch (error) {
    console.error('获取邮箱列表失败:', error)
    ElMessage.error('获取邮箱列表失败')
  }
}

// 检查邮件
const checkEmail = async (emailId) => {
  try {
    const response = await fetch(`/api/emails/${emailId}/check`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })
    if (response.ok) {
      ElMessage.success('开始检查邮件')
    } else {
      ElMessage.error('检查邮件失败')
    }
  } catch (error) {
    console.error('检查邮件失败:', error)
    ElMessage.error('检查邮件失败')
  }
}

// 删除邮箱
const deleteEmail = async (emailId) => {
  try {
    await ElMessageBox.confirm('确定要删除这个邮箱吗？', '提示', {
      type: 'warning'
    })

    const response = await fetch(`/api/emails/${emailId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })

    if (response.ok) {
      ElMessage.success('删除成功')
      fetchEmails()
    } else {
      ElMessage.error('删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除邮箱失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

// 编辑邮箱
const editEmail = (email) => {
  // 确保use_ssl是布尔值
  const emailData = { ...email }
  if (emailData.mail_type === 'imap') {
    emailData.use_ssl = Boolean(emailData.use_ssl)
  }
  editForm.value = emailData
  editDialogVisible.value = true
}

// 提交编辑表单
const submitEditForm = async () => {
  if (!editFormRef.value) return

  try {
    await editFormRef.value.validate()

    // 确保use_ssl是布尔值
    if (editForm.value.mail_type === 'imap') {
      editForm.value.use_ssl = Boolean(editForm.value.use_ssl)
    }

    const response = await fetch(`/api/emails/${editForm.value.id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify(editForm.value)
    })

    if (response.ok) {
      ElMessage.success('更新成功')
      editDialogVisible.value = false
      fetchEmails()
    } else {
      ElMessage.error('更新失败')
    }
  } catch (error) {
    console.error('更新邮箱失败:', error)
    ElMessage.error('更新失败')
  }
}

// 重置编辑表单
const resetEditForm = () => {
  if (editFormRef.value) {
    editFormRef.value.resetFields()
  }
  editForm.value = {
    id: null,
    email: '',
    password: '',
    mail_type: 'imap',
    server: '',
    port: 993,
    use_ssl: true,
    client_id: '',
    refresh_token: ''
  }
}

// 测试IMAP连接
const testConnection = async () => {
  if (!editFormRef.value) return

  try {
    await editFormRef.value.validate(['email', 'password', 'server', 'port'])
    testing.value = true

    const response = await fetch('/api/emails/test-connection', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({
        email: editForm.value.email,
        password: editForm.value.password,
        server: editForm.value.server,
        port: editForm.value.port,
        use_ssl: editForm.value.use_ssl
      })
    })

    if (response.ok) {
      ElMessage.success('连接测试成功')
    } else {
      const data = await response.json()
      ElMessage.error(`连接测试失败: ${data.message || '未知错误'}`)
    }
  } catch (error) {
    console.error('连接测试失败:', error)
    ElMessage.error('连接测试失败')
  } finally {
    testing.value = false
  }
}

// 查看邮件
const viewEmails = (emailId) => {
  router.push(`/emails/${emailId}/messages`)
}

onMounted(() => {
  fetchEmails()
})
</script>

<style scoped>
.email-list {
  padding: 20px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.password-strength {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.password-strength span {
  font-size: 12px;
  color: #606266;
}

:deep(.el-progress) {
  width: 120px;
  margin-right: 10px;
}

:deep(.el-form-item__content) {
  position: relative;
}

:deep(.el-tooltip) {
  cursor: help;
}

:deep(.el-input-group__append .el-icon) {
  margin: 0 5px;
  cursor: help;
}

.form-tips {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}

.imap-tips {
  background-color: #f4f4f5;
  border-radius: 4px;
  padding: 12px;
  margin: 10px 0;
}

.imap-tips h4 {
  margin: 0 0 8px;
  color: #606266;
}

.imap-tips p {
  margin: 4px 0;
  color: #909399;
  font-size: 13px;
}

.imap-tips code {
  background-color: #e9e9eb;
  padding: 2px 4px;
  border-radius: 3px;
  font-family: monospace;
}

.action-buttons {
  display: flex;
  justify-content: center;
  flex-wrap: nowrap;
  gap: 8px;
  width: 100%;
  overflow-x: auto;
  padding: 4px 0;
  scrollbar-width: thin;
  -webkit-overflow-scrolling: touch; /* 增强iOS滚动体验 */
}

.action-buttons::-webkit-scrollbar {
  height: 4px;
}

.action-buttons::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 2px;
}

.action-buttons::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 2px;
}

.action-buttons::-webkit-scrollbar-thumb:hover {
  background: #555;
}

.action-btn {
  margin: 0;
  min-width: 80px;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: transform 0.2s;
}

.action-btn:hover {
  transform: translateY(-2px);
}

:deep(.el-table .el-table__cell) {
  padding: 10px 0;
}
</style>
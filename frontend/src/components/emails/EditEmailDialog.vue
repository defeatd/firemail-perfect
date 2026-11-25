<template>
  <el-dialog
    :model-value="modelValue"
    title="编辑邮箱"
    :width="isMobile ? '100%' : '560px'"
    :fullscreen="isMobile"
    :close-on-click-modal="false"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div v-loading="hydrating" class="fm-edit-dialog">
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
      >
        <el-form-item label="邮箱类型">
          <div class="fm-edit-dialog__type">
            <StatusPill tone="muted" :dot="false">{{ getMailTypeLabel(form.mail_type) }}</StatusPill>
            <span class="fm-edit-dialog__hint">邮箱类型创建后不可修改</span>
          </div>
        </el-form-item>

        <el-form-item label="邮箱地址" prop="email">
          <el-input v-model="form.email" />
        </el-form-item>

        <el-form-item label="密码 / 授权码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="请输入密码"
          />
          <div v-if="passwordStrength.label" class="fm-pwd-strength">
            <div class="fm-pwd-strength__bar">
              <div
                class="fm-pwd-strength__fill"
                :class="`is-${passwordStrength.tone}`"
                :style="{ width: `${passwordStrength.percent}%` }"
              />
            </div>
            <span class="fm-pwd-strength__text" :class="`is-${passwordStrength.tone}`">
              强度：{{ passwordStrength.label }}
            </span>
          </div>
        </el-form-item>

        <template v-if="form.mail_type === 'outlook'">
          <el-form-item label="Client ID" prop="client_id">
            <el-input v-model="form.client_id" class="fm-mono" />
          </el-form-item>
          <el-form-item label="Refresh Token" prop="refresh_token">
            <el-input
              v-model="form.refresh_token"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 6 }"
              class="fm-mono"
            />
          </el-form-item>
        </template>

        <template v-else-if="form.mail_type === 'imap'">
          <div class="fm-imap-hints">
            <div class="fm-imap-hints__title">常用 IMAP 服务器参考</div>
            <div class="fm-imap-hints__grid fm-mono">
              <span>Gmail: imap.gmail.com</span>
              <span>Outlook: outlook.office365.com</span>
              <span>QQ: imap.qq.com</span>
              <span>163: imap.163.com</span>
            </div>
          </div>

          <el-form-item label="IMAP 服务器" prop="server">
            <el-input v-model="form.server" />
          </el-form-item>

          <div class="fm-edit-dialog__row">
            <el-form-item label="端口" prop="port" style="flex: 1">
              <el-input-number
                v-model="form.port"
                :min="1"
                :max="65535"
                controls-position="right"
                style="width: 100%"
              />
              <div class="fm-edit-dialog__hint">常用端口: SSL-993, 非SSL-143</div>
            </el-form-item>

            <el-form-item label="启用 SSL" prop="use_ssl">
              <el-switch v-model="form.use_ssl" />
            </el-form-item>
          </div>
        </template>
      </el-form>
    </div>

    <template #footer>
      <div class="fm-edit-dialog__footer">
        <el-button
          v-if="form.mail_type === 'outlook'"
          @click="triggerReauth"
        >
          Device Code 重新授权
        </el-button>
        <div class="fm-edit-dialog__footer-right">
          <el-button @click="$emit('update:modelValue', false)">取消</el-button>
          <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getMailTypeLabel } from '@/utils/mailTypes'
import { useEmailsStore } from '@/stores/emails'
import { useCredentials } from '@/composables/useCredentials'
import { useBreakpoint } from '@/composables/useBreakpoint'
import StatusPill from '@/components/common/StatusPill.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  email: { type: Object, default: null }
})

const emit = defineEmits(['update:modelValue', 'saved', 'start-device'])

const emails = useEmailsStore()
const { ensureCredentials } = useCredentials()
const { isMobile } = useBreakpoint()

const formRef = ref(null)
const hydrating = ref(false)
const saving = ref(false)

const form = reactive({
  id: null,
  mail_type: 'outlook',
  email: '',
  password: '',
  client_id: '',
  refresh_token: '',
  server: '',
  port: 993,
  use_ssl: true
})

const rules = computed(() => ({
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  client_id:
    form.mail_type === 'outlook'
      ? [{ required: true, message: '请输入 Client ID', trigger: 'blur' }]
      : [],
  refresh_token:
    form.mail_type === 'outlook'
      ? [{ required: true, message: '请输入 Refresh Token', trigger: 'blur' }]
      : [],
  server:
    form.mail_type === 'imap'
      ? [{ required: true, message: '请输入 IMAP 服务器', trigger: 'blur' }]
      : []
}))

const passwordStrength = computed(() => {
  const pwd = form.password || ''
  if (!pwd || pwd === '******') return { label: '', tone: 'muted', percent: 0 }
  let score = 0
  if (pwd.length >= 6) score += 1
  if (pwd.length >= 10) score += 1
  if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score += 1
  if (/\d/.test(pwd)) score += 1
  if (/[^a-zA-Z0-9]/.test(pwd)) score += 1
  if (score <= 2) return { label: '较弱', tone: 'danger', percent: 33 }
  if (score <= 3) return { label: '中等', tone: 'warning', percent: 66 }
  return { label: '较强', tone: 'success', percent: 100 }
})

async function hydrateForm() {
  if (!props.email) return
  form.id = props.email.id
  form.mail_type = props.email.mail_type || 'outlook'
  form.email = props.email.email || ''
  form.password = ''
  form.client_id = props.email.client_id || ''
  form.refresh_token = ''
  form.server = props.email.server || ''
  form.port = Number(props.email.port) || 993
  form.use_ssl = props.email.use_ssl !== 0 && props.email.use_ssl !== false

  hydrating.value = true
  try {
    const creds = await ensureCredentials(props.email, { force: true })
    if (creds) {
      form.password = creds.password === '******' ? '' : creds.password || ''
      form.client_id = creds.client_id || form.client_id
      form.refresh_token = creds.refresh_token === '******' ? '' : creds.refresh_token || ''
    }
  } catch (_err) {
    ElMessage.warning('加载邮箱敏感信息失败，请手动填写需要修改的字段')
    form.password = ''
    form.refresh_token = ''
  } finally {
    hydrating.value = false
  }
}

watch(
  () => [props.modelValue, props.email?.id],
  ([open]) => {
    if (open && props.email) {
      hydrateForm()
    }
  },
  { immediate: true }
)

function triggerReauth() {
  emit('update:modelValue', false)
  emit('start-device', {
    mode: 'reauth',
    emailId: form.id,
    email: form.email,
    clientId: form.client_id
  })
}

async function handleSave() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return

  saving.value = true
  try {
    const payload = {
      email: form.email.trim(),
      mail_type: form.mail_type
    }
    if (form.password && form.password !== '******') {
      payload.password = form.password
    }
    if (form.mail_type === 'outlook') {
      if (form.client_id.trim()) payload.client_id = form.client_id.trim()
      if (form.refresh_token && form.refresh_token !== '******') {
        payload.refresh_token = form.refresh_token.trim()
      }
    } else if (form.mail_type === 'imap') {
      payload.server = form.server.trim()
      payload.port = Number(form.port) || 993
      payload.use_ssl = Boolean(form.use_ssl)
    }

    await emails.updateEmail(form.id, payload)
    ElMessage.success('邮箱信息更新成功')
    emit('update:modelValue', false)
    emit('saved')
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || err?.message || '更新邮箱信息失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.fm-edit-dialog__type {
  display: flex;
  align-items: center;
  gap: var(--fm-space-3);
}

.fm-edit-dialog__hint {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
  margin-top: 4px;
}

.fm-edit-dialog__row {
  display: flex;
  align-items: flex-start;
  gap: var(--fm-space-4);
}

.fm-pwd-strength {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--fm-space-2);
  margin-top: 6px;
}

.fm-pwd-strength__bar {
  flex: 1;
  height: 4px;
  border-radius: var(--fm-radius-pill);
  background: var(--fm-bg-subtle);
  overflow: hidden;
}

.fm-pwd-strength__fill {
  height: 100%;
  transition: width var(--fm-dur) var(--fm-ease);
}

.fm-pwd-strength__fill.is-danger {
  background: var(--fm-danger);
}

.fm-pwd-strength__fill.is-warning {
  background: var(--fm-warning);
}

.fm-pwd-strength__fill.is-success {
  background: var(--fm-success);
}

.fm-pwd-strength__text {
  font-size: var(--fm-fs-xs);
}

.fm-pwd-strength__text.is-danger {
  color: var(--fm-danger);
}

.fm-pwd-strength__text.is-warning {
  color: var(--fm-warning);
}

.fm-pwd-strength__text.is-success {
  color: var(--fm-success);
}

.fm-imap-hints {
  padding: var(--fm-space-3);
  border-radius: var(--fm-radius-md);
  background: var(--fm-bg-subtle);
  border: 1px solid var(--fm-border);
  margin-bottom: var(--fm-space-4);
}

.fm-imap-hints__title {
  font-size: var(--fm-fs-xs);
  font-weight: 600;
  color: var(--fm-text-2);
  margin-bottom: 6px;
}

.fm-imap-hints__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px 12px;
  font-size: 11px;
  color: var(--fm-text-3);
}

.fm-edit-dialog__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--fm-space-2);
}

.fm-edit-dialog__footer-right {
  display: flex;
  align-items: center;
  gap: var(--fm-space-2);
  margin-left: auto;
}
</style>

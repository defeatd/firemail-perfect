<template>
  <el-dialog
    :model-value="modelValue"
    title="添加邮箱"
    :width="isMobile ? '100%' : '560px'"
    :fullscreen="isMobile"
    :close-on-click-modal="false"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="fm-add-dialog">
      <SegmentedFilter v-model="activeTab" :options="TAB_OPTIONS" />

      <div v-if="activeTab === 'device'" class="fm-add-dialog__pane">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="通过微软官方设备码流程授权添加 Outlook 邮箱，无需手动准备 Refresh Token。"
        />
        <el-form
          ref="deviceFormRef"
          :model="deviceForm"
          :rules="deviceRules"
          label-position="top"
          @submit.prevent="submitDevice"
        >
          <el-form-item label="Outlook 邮箱地址" prop="email">
            <el-input
              v-model="deviceForm.email"
              placeholder="name@outlook.com"
              autocomplete="off"
            />
          </el-form-item>
          <el-form-item label="Client ID（可选）" prop="clientId">
            <el-input
              v-model="deviceForm.clientId"
              placeholder="留空使用系统默认"
              class="fm-mono"
            />
          </el-form-item>
        </el-form>
      </div>

      <div v-else-if="activeTab === 'single'" class="fm-add-dialog__pane">
        <el-form
          ref="singleFormRef"
          :model="singleForm"
          :rules="singleRules"
          label-position="top"
        >
          <el-form-item label="邮箱类型" prop="mail_type">
            <el-select v-model="singleForm.mail_type" style="width: 100%">
              <el-option
                v-for="item in MAIL_TYPES"
                :key="item.value"
                :value="item.value"
                :label="item.label"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="邮箱地址" prop="email">
            <el-input v-model="singleForm.email" placeholder="example@outlook.com" />
          </el-form-item>

          <el-form-item label="密码 / 授权码" prop="password">
            <el-input
              v-model="singleForm.password"
              type="password"
              show-password
              placeholder="请输入邮箱密码或应用授权码"
            />
          </el-form-item>

          <template v-if="singleForm.mail_type === 'outlook'">
            <el-form-item label="Client ID" prop="client_id">
              <el-input v-model="singleForm.client_id" placeholder="Microsoft App Client ID" />
            </el-form-item>
            <el-form-item label="Refresh Token" prop="refresh_token">
              <el-input
                v-model="singleForm.refresh_token"
                type="textarea"
                :autosize="{ minRows: 3, maxRows: 6 }"
                placeholder="粘贴完整的 Refresh Token"
                class="fm-mono"
              />
            </el-form-item>
          </template>

          <template v-else-if="singleForm.mail_type === 'imap'">
            <el-form-item label="IMAP 服务器" prop="server">
              <el-input v-model="singleForm.server" placeholder="imap.example.com" />
            </el-form-item>
            <div class="fm-add-dialog__row">
              <el-form-item label="端口" prop="port" style="flex: 1">
                <el-input-number
                  v-model="singleForm.port"
                  :min="1"
                  :max="65535"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
              <el-form-item label="启用 SSL" prop="use_ssl">
                <el-switch v-model="singleForm.use_ssl" />
              </el-form-item>
            </div>
          </template>
        </el-form>
      </div>

      <div v-else class="fm-add-dialog__pane">
        <ImportPanel
          ref="importPanelRef"
          compact
          hide-actions
          @imported="handleBatchImported"
          @submitting="batchSubmitting = $event"
        />
        <ImportResult
          v-if="batchResult"
          :result="batchResult"
          :job-summary="importJob.summary.value"
          :cancelling="importJob.cancelling.value"
          :raw-text="batchRawText"
          compact
          @cancel-job="importJob.cancelAll()"
        />
      </div>
    </div>

    <template #footer>
      <div class="fm-dialog-footer">
        <el-button @click="$emit('update:modelValue', false)">取消</el-button>
        <el-button
          type="primary"
          :loading="activeLoading"
          @click="handleConfirm"
        >
          {{ confirmLabel }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import { MAIL_TYPES } from '@/utils/mailTypes'
import { useEmailsStore } from '@/stores/emails'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { useImportJob } from '@/composables/useImportJob'
import SegmentedFilter from '@/components/common/SegmentedFilter.vue'
import ImportPanel from '@/components/import/ImportPanel.vue'
import ImportResult from '@/components/import/ImportResult.vue'

const TAB_OPTIONS = [
  { value: 'device', label: 'Device Code 授权' },
  { value: 'single', label: '单个添加' },
  { value: 'batch', label: '批量添加' }
]

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  defaultTab: { type: String, default: 'single' }
})

const emit = defineEmits(['update:modelValue', 'added', 'start-device'])

const emails = useEmailsStore()
const { isMobile } = useBreakpoint()
const importJob = useImportJob()

const activeTab = ref(props.defaultTab || 'single')
const singleFormRef = ref(null)
const deviceFormRef = ref(null)
const importPanelRef = ref(null)
const singleSubmitting = ref(false)
const batchSubmitting = ref(false)
const batchResult = ref(null)
const batchRawText = ref('')

const deviceForm = reactive({
  email: '',
  clientId: ''
})

const singleForm = reactive({
  mail_type: 'outlook',
  email: '',
  password: '',
  client_id: '',
  refresh_token: '',
  server: '',
  port: 993,
  use_ssl: true
})

const deviceRules = {
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    {
      validator: (_rule, val, cb) => {
        if (!val || !val.includes('@')) cb(new Error('请输入有效的邮箱地址'))
        else cb()
      },
      trigger: 'blur'
    }
  ]
}

const singleRules = computed(() => ({
  mail_type: [{ required: true, message: '请选择邮箱类型', trigger: 'change' }],
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  client_id:
    singleForm.mail_type === 'outlook'
      ? [{ required: true, message: '请输入 Client ID', trigger: 'blur' }]
      : [],
  refresh_token:
    singleForm.mail_type === 'outlook'
      ? [{ required: true, message: '请输入 Refresh Token', trigger: 'blur' }]
      : [],
  server:
    singleForm.mail_type === 'imap'
      ? [{ required: true, message: '请输入 IMAP 服务器地址', trigger: 'blur' }]
      : []
}))

const activeLoading = computed(() =>
  activeTab.value === 'single' ? singleSubmitting.value : activeTab.value === 'batch' ? batchSubmitting.value : false
)

const confirmLabel = computed(() => {
  if (activeTab.value === 'device') return '发起授权'
  if (activeTab.value === 'batch') return '开始导入'
  return '确定'
})

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      activeTab.value = props.defaultTab || 'single'
      batchResult.value = null
      batchRawText.value = ''
      importJob.reset()
      deviceForm.email = ''
      deviceForm.clientId = ''
      singleForm.mail_type = 'outlook'
      singleForm.email = ''
      singleForm.password = ''
      singleForm.client_id = ''
      singleForm.refresh_token = ''
      singleForm.server = ''
      singleForm.port = 993
      singleForm.use_ssl = true
    } else {
      importJob.reset()
    }
  }
)

async function submitDevice() {
  const ok = await deviceFormRef.value?.validate().catch(() => false)
  if (!ok) return
  emit('update:modelValue', false)
  emit('start-device', {
    mode: 'add',
    email: deviceForm.email.trim(),
    clientId: deviceForm.clientId.trim()
  })
}

async function submitSingle() {
  const ok = await singleFormRef.value?.validate().catch(() => false)
  if (!ok) return
  singleSubmitting.value = true
  try {
    const payload = {
      mail_type: singleForm.mail_type,
      email: singleForm.email.trim(),
      password: singleForm.password
    }
    if (singleForm.mail_type === 'outlook') {
      payload.client_id = singleForm.client_id.trim()
      payload.refresh_token = singleForm.refresh_token.trim()
    } else if (singleForm.mail_type === 'imap') {
      payload.server = singleForm.server.trim()
      payload.port = Number(singleForm.port) || 993
      payload.use_ssl = Boolean(singleForm.use_ssl)
    }
    await emails.addEmail(payload)
    ElMessage.success('添加邮箱成功')
    emit('update:modelValue', false)
    emit('added')
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || err?.message || '添加邮箱失败')
  } finally {
    singleSubmitting.value = false
  }
}

function handleBatchImported(result) {
  batchResult.value = result
  batchRawText.value = result?.rawText || ''
  const added = Number(result?.added) || 0
  const updated = Number(result?.updated) || 0
  const success = added + updated || Number(result?.success) || 0
  const failed = (Number(result?.invalid) || 0) + (Number(result?.warned) || 0) || Number(result?.failed) || 0
  const ids = Array.isArray(result?.job_ids)
    ? result.job_ids
    : result?.job_id
      ? [result.job_id]
      : []

  if (ids.length > 0) {
    importJob.track(ids, {
      onFinish: () => {
        emails.refreshAll().catch(() => {})
      }
    })
  } else {
    importJob.reset()
  }

  if (success > 0) {
    ElMessage.success(
      ids.length > 0
        ? `已入库 ${success} 个邮箱，后台首验进行中`
        : `成功导入 ${success} 个邮箱`
    )
    emit('added')
    if (failed === 0 && ids.length === 0) {
      emit('update:modelValue', false)
    }
    return
  }

  const failedItems = (result?.rows || result?.failed_details || result?.errors || []).filter(
    (item) => item && item.success !== true
  )
  const summary = failedItems
    .slice(0, 6)
    .map((item) => `${item.email || `第${item.line || '?'}行`}: ${item.reason || item.error || '失败'}`)
    .join('；')
  ElNotification({
    title: failed > 0 ? `未入库（问题 ${failed} 条）` : '未新增任何邮箱',
    message: summary || result?.message || '请检查导入格式或重复邮箱策略',
    type: failed > 0 ? 'error' : 'info',
    duration: 10000
  })
}

async function handleConfirm() {
  if (activeTab.value === 'device') {
    await submitDevice()
  } else if (activeTab.value === 'single') {
    await submitSingle()
  } else {
    await importPanelRef.value?.submit().catch(() => {})
  }
}
</script>

<style scoped>
.fm-add-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-4);
}

.fm-add-dialog__pane {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-4);
}

.fm-add-dialog__row {
  display: flex;
  align-items: flex-start;
  gap: var(--fm-space-4);
}

.fm-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--fm-space-2);
}
</style>

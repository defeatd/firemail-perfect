<template>
  <div class="fm-inbox-view">
    <PageHeader back-to="/emails" back-label="邮箱资产">
      <template #title>
        <BrandIcon v-if="emailInfo" :type="emailInfo.mail_type" :size="20" />
        <span class="fm-mono fm-inbox-view__addr">{{ emailInfo?.email || `邮箱 #${emailId}` }}</span>
      </template>

      <template #meta>
        <span v-if="emailInfo?.last_check_time">
          最后检查：{{ formatRelative(emailInfo.last_check_time) }}
        </span>
        <span v-else>尚未检查</span>
        <span v-if="emailInfo?.created_at" class="fm-mono">
          创建于 {{ formatAbs(emailInfo.created_at, 'YYYY-MM-DD') }}
        </span>
        <AuthStatusCell v-if="emailInfo?.mail_type === 'outlook'" :row="emailInfo" />
      </template>

      <template #actions>
        <el-button
          type="primary"
          :disabled="Boolean(processingStatus)"
          :loading="checking"
          @click="handleCheckMail"
        >
          <el-icon v-if="!processingStatus"><Download /></el-icon>
          <span>{{ checkButtonLabel }}</span>
        </el-button>

        <el-button @click="uploadOpen = true">
          <el-icon><Upload /></el-icon>
          <span>上传邮件</span>
        </el-button>

        <el-dropdown trigger="click" placement="bottom-end" @command="handleMoreCommand">
          <el-button :icon="MoreFilled" aria-label="更多操作" />
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-if="emailInfo?.mail_type === 'outlook'" command="keepalive">
                <el-icon><RefreshRight /></el-icon>
                <span>立即保活</span>
              </el-dropdown-item>
              <el-dropdown-item v-if="emailInfo?.mail_type === 'outlook'" command="reauth">
                <el-icon><Key /></el-icon>
                <span>重新授权</span>
              </el-dropdown-item>
              <el-dropdown-item command="edit">
                <el-icon><Edit /></el-icon>
                <span>编辑邮箱</span>
              </el-dropdown-item>
              <el-dropdown-item divided command="delete" class="fm-dropdown-danger">
                <el-icon><Delete /></el-icon>
                <span>删除邮箱</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
    </PageHeader>

    <div class="fm-inbox-pane" :class="{ 'is-narrow': isNarrow }">
      <div v-if="!isMobile || !selectedMail" class="fm-inbox-pane__list">
        <MailList
          :records="emails.currentMailRecords"
          :selected-id="selectedMailId"
          :loading="emails.recordsLoading"
          @select="selectMail"
          @check-mail="handleCheckMail"
        />
      </div>

      <div v-if="!isMobile" class="fm-inbox-pane__reader">
        <MailReader :mail="selectedMail" :email-id="emailId" />
      </div>
    </div>

    <div v-if="isMobile && selectedMail" class="fm-mobile-reader-overlay">
      <MailReader
        :mail="selectedMail"
        :email-id="emailId"
        show-back
        @back="closeMobileReader"
      />
    </div>

    <UploadMailDialog
      v-model="uploadOpen"
      :email-id="emailId"
      @uploaded="reloadRecords"
    />

    <EditEmailDialog
      v-model="editOpen"
      :email="emailInfo"
      @saved="emails.refreshAll()"
      @start-device="openDeviceDialog"
    />

    <DeviceCodeDialog
      v-model="deviceOpen"
      :request="deviceRequest"
      @success="emails.refreshAll()"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Download,
  Upload,
  MoreFilled,
  RefreshRight,
  Key,
  Edit,
  Delete
} from '@element-plus/icons-vue'
import api from '@/services/api'
import { formatAbs, formatRelative } from '@/utils/time'
import { useEmailsStore } from '@/stores/emails'
import { useBreakpoint } from '@/composables/useBreakpoint'
import PageHeader from '@/components/common/PageHeader.vue'
import BrandIcon from '@/components/common/BrandIcon.vue'
import AuthStatusCell from '@/components/emails/AuthStatusCell.vue'
import EditEmailDialog from '@/components/emails/EditEmailDialog.vue'
import DeviceCodeDialog from '@/components/emails/DeviceCodeDialog.vue'
import MailList from '@/components/mail/MailList.vue'
import MailReader from '@/components/mail/MailReader.vue'
import UploadMailDialog from '@/components/mail/UploadMailDialog.vue'

const route = useRoute()
const router = useRouter()
const emails = useEmailsStore()
const { isMobile, isNarrow } = useBreakpoint()

const checking = ref(false)
const uploadOpen = ref(false)
const editOpen = ref(false)
const deviceOpen = ref(false)
const deviceRequest = ref(null)

const emailId = computed(() => Number(route.params.id))
const emailInfo = computed(() => emails.getEmailById(emailId.value))
const processingStatus = computed(() => emails.getProcessingStatus(emailId.value))

const checkButtonLabel = computed(() => {
  if (!processingStatus.value) return '收取邮件'
  const pct = Number(processingStatus.value.progress)
  return Number.isFinite(pct) && pct > 0 ? `收信中 ${Math.round(pct)}%` : '收信中…'
})

const selectedMailId = computed(() => {
  const fromQuery = route.query.mail ? Number(route.query.mail) : null
  if (fromQuery) return fromQuery
  if (!isMobile.value && emails.currentMailRecords.length > 0) {
    return emails.currentMailRecords[0].id
  }
  return null
})

const selectedMail = computed(() => {
  if (!selectedMailId.value) return null
  return emails.currentMailRecords.find((m) => Number(m.id) === Number(selectedMailId.value)) || null
})

async function loadMailbox(id) {
  if (!id || Number.isNaN(id)) return
  try {
    await emails.ensureEmailsLoaded()
    await emails.fetchMailRecords(id)
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || '加载邮件记录失败')
  }
}

watch(
  emailId,
  (id) => {
    loadMailbox(id)
  },
  { immediate: true }
)

function reloadRecords() {
  emails.fetchMailRecords(emailId.value).catch(() => {})
}

function selectMail(mail) {
  router.replace({ query: { ...route.query, mail: String(mail.id) } })
}

function closeMobileReader() {
  const nextQuery = { ...route.query }
  delete nextQuery.mail
  router.replace({ query: nextQuery })
}

async function handleCheckMail() {
  checking.value = true
  try {
    const res = await emails.checkEmail(emailId.value)
    if (res?.status === 'processing') {
      ElMessage.warning(res.message || '邮箱正在处理中，请稍候...')
    } else {
      ElMessage.success('开始收取邮件')
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || '收取邮件失败')
  } finally {
    checking.value = false
  }
}

function openDeviceDialog(req) {
  deviceRequest.value = req
  deviceOpen.value = true
}

async function handleKeepalive() {
  if (!emailInfo.value) return
  try {
    const res = await api.refreshEmailToken(emailInfo.value.id)
    const data = res?.data || {}
    if (data.success) {
      const rotMsg = data.refresh_rotated ? '（Refresh Token 已轮换续期）' : ''
      ElMessage.success(`${emailInfo.value.email} 保活成功${rotMsg}`)
    } else if (data.need_reauth) {
      ElMessage.warning(`${emailInfo.value.email} 需要重新授权：${data.error || ''}`)
    } else {
      ElMessage.error(`${emailInfo.value.email} 保活失败：${data.error || ''}`)
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || '保活失败')
  } finally {
    await emails.refreshAll().catch(() => {})
  }
}

async function handleDeleteEmail() {
  const label = emailInfo.value?.email || `#${emailId.value}`
  try {
    await ElMessageBox.confirm(
      `确定要删除邮箱 ${label} 吗？所有相关的邮件记录也将被删除。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', confirmButtonClass: 'el-button--danger' }
    )
    await emails.deleteEmail(emailId.value)
    ElMessage.success('邮箱已删除')
    router.push('/emails')
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err?.response?.data?.error || '删除邮箱失败')
  }
}

function handleMoreCommand(cmd) {
  if (cmd === 'keepalive') handleKeepalive()
  else if (cmd === 'edit') editOpen.value = true
  else if (cmd === 'reauth' && emailInfo.value) {
    openDeviceDialog({
      mode: 'reauth',
      emailId: emailInfo.value.id,
      email: emailInfo.value.email,
      clientId: emailInfo.value.client_id || ''
    })
  } else if (cmd === 'delete') handleDeleteEmail()
}
</script>

<style scoped>
.fm-inbox-view__addr {
  word-break: break-all;
}

.fm-inbox-pane {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  height: calc(100vh - 210px);
  min-height: 540px;
  border: 1px solid var(--fm-border);
  border-radius: var(--fm-radius-lg);
  overflow: hidden;
  background: var(--fm-surface);
  box-shadow: var(--fm-shadow-xs);
}

.fm-inbox-pane.is-narrow {
  grid-template-columns: 300px minmax(0, 1fr);
}

.fm-inbox-pane__list {
  border-right: 1px solid var(--fm-border);
  min-height: 0;
  overflow: hidden;
}

.fm-inbox-pane__reader {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.fm-mobile-reader-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  background: var(--fm-surface);
  display: flex;
  flex-direction: column;
}

@media (max-width: 767.98px) {
  .fm-inbox-pane {
    grid-template-columns: 1fr;
    height: calc(100vh - 230px);
    min-height: 440px;
  }

  .fm-inbox-pane__list {
    border-right: none;
  }
}
</style>

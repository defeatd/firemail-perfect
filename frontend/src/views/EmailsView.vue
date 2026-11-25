<template>
  <div class="fm-emails-view">
    <PageHeader title="邮箱资产" :count="emails.emails.length">
      <template #actions>
        <el-tooltip content="刷新列表" placement="bottom">
          <el-button
            :icon="Refresh"
            :loading="refreshingList"
            aria-label="刷新列表"
            @click="handleRefreshList"
          />
        </el-tooltip>
        <el-button @click="router.push('/import')">
          <el-icon><Upload /></el-icon>
          <span>导入</span>
        </el-button>
        <el-button type="primary" @click="openAddDialog('single')">
          <el-icon><Plus /></el-icon>
          <span>添加邮箱</span>
        </el-button>
      </template>
    </PageHeader>

    <TokenHealthStrip
      :health="emails.tokenHealth"
      :keeper="emails.tokenKeeper"
      :active-auth="authFilter"
      @select-filter="authFilter = $event"
    />

    <EmailFilters
      v-model:query="query"
      v-model:type="typeFilter"
      v-model:auth="authFilter"
      :type-counts="typeCounts"
    />

    <BatchActionBar
      :selected-rows="selectedRows"
      :filtered-count="filteredRows.length"
      :checking="batchChecking"
      :refreshing="batchRefreshing"
      :deleting="batchDeleting"
      :exporting="exporting"
      @batch-check="handleBatchCheck"
      @batch-refresh="handleBatchRefresh"
      @export="handleExport"
      @batch-delete="handleBatchDelete"
      @clear="selectedIds = []"
    />

    <EmailTable
      v-if="!isMobile"
      :rows="pagedRows"
      :total-count="filteredRows.length"
      :loading="emails.loading"
      :selected-ids="selectedIds"
      :processing="emails.processingEmails"
      :refreshing-ids="refreshingIds"
      :revealed-passwords="revealedPasswords"
      :password-loading="passwordLoading"
      :page="page"
      :page-size="ui.emailsPageSize"
      @update:selected-ids="selectedIds = $event"
      @update:page="page = $event"
      @update:page-size="handlePageSizeChange"
      @sort-change="sort = $event"
      @check="handleSingleCheck"
      @view="handleViewMail"
      @keepalive="handleSingleKeepalive"
      @edit="openEditDialog"
      @reauth="openReauthDevice"
      @credentials="openCredentialsDialog"
      @delete="handleSingleDelete"
      @toggle-realtime="handleToggleRealtime"
      @reveal-password="handleRevealPassword"
    />

    <EmailCardList
      v-else
      :rows="pagedRows"
      :total-count="filteredRows.length"
      :loading="emails.loading"
      :selected-ids="selectedIds"
      :processing="emails.processingEmails"
      :refreshing-ids="refreshingIds"
      :sort="sort"
      :page="page"
      :page-size="ui.emailsPageSize"
      @update:selected-ids="selectedIds = $event"
      @update:page="page = $event"
      @sort-change="sort = $event"
      @add="openAddDialog('single')"
      @check="handleSingleCheck"
      @view="handleViewMail"
      @keepalive="handleSingleKeepalive"
      @edit="openEditDialog"
      @reauth="openReauthDevice"
      @credentials="openCredentialsDialog"
      @delete="handleSingleDelete"
      @toggle-realtime="handleToggleRealtime"
    />

    <AddEmailDialog
      v-model="addDialogOpen"
      :default-tab="addDefaultTab"
      @added="emails.refreshAll()"
      @start-device="openDeviceDialog"
    />

    <EditEmailDialog
      v-model="editDialogOpen"
      :email="activeEmail"
      @saved="emails.refreshAll()"
      @start-device="openDeviceDialog"
    />

    <DeviceCodeDialog
      v-model="deviceDialogOpen"
      :request="deviceRequest"
      @success="emails.refreshAll()"
    />

    <CredentialsDialog v-model="credsDialogOpen" :email="activeEmail" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Upload, Plus } from '@element-plus/icons-vue'
import api from '@/services/api'
import { countByMailType, filterAndSortEmails } from '@/utils/emailFilter'
import { useEmailsStore } from '@/stores/emails'
import { useUiStore } from '@/stores/ui'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { useCredentials } from '@/composables/useCredentials'
import { useEmailExport } from '@/composables/useEmailExport'
import { usePolling } from '@/composables/usePolling'
import PageHeader from '@/components/common/PageHeader.vue'
import TokenHealthStrip from '@/components/emails/TokenHealthStrip.vue'
import EmailFilters from '@/components/emails/EmailFilters.vue'
import BatchActionBar from '@/components/emails/BatchActionBar.vue'
import EmailTable from '@/components/emails/EmailTable.vue'
import EmailCardList from '@/components/emails/EmailCardList.vue'
import AddEmailDialog from '@/components/emails/AddEmailDialog.vue'
import EditEmailDialog from '@/components/emails/EditEmailDialog.vue'
import DeviceCodeDialog from '@/components/emails/DeviceCodeDialog.vue'
import CredentialsDialog from '@/components/emails/CredentialsDialog.vue'

const route = useRoute()
const router = useRouter()
const emails = useEmailsStore()
const ui = useUiStore()
const { isMobile } = useBreakpoint()
const { ensureCredentials } = useCredentials()
const { exportTxt } = useEmailExport()

const query = ref(String(route.query.q || ''))
const typeFilter = ref(String(route.query.type || 'all'))
const authFilter = ref(
  String(route.query.auth || (route.query.filter === 'attention' ? 'attention' : 'all'))
)
const page = ref(1)
const sort = ref({ prop: '', order: null })
const selectedIds = ref([])
const refreshingList = ref(false)
const batchChecking = ref(false)
const batchRefreshing = ref(false)
const batchDeleting = ref(false)
const exporting = ref(false)
const refreshingIds = reactive({})
const revealedPasswords = reactive({})
const passwordLoading = reactive({})

const addDialogOpen = ref(false)
const addDefaultTab = ref('single')
const editDialogOpen = ref(false)
const credsDialogOpen = ref(false)
const deviceDialogOpen = ref(false)
const activeEmail = ref(null)
const deviceRequest = ref(null)

const typeCounts = computed(() => countByMailType(emails.emails))

const filteredRows = computed(() =>
  filterAndSortEmails(emails.emails, {
    query: query.value,
    typeFilter: typeFilter.value,
    authFilter: authFilter.value,
    sort: sort.value
  })
)

const pagedRows = computed(() => {
  const start = (page.value - 1) * ui.emailsPageSize
  return filteredRows.value.slice(start, start + ui.emailsPageSize)
})

const selectedRows = computed(() => {
  const set = new Set(selectedIds.value)
  return emails.emails.filter((row) => set.has(row.id))
})

watch([query, typeFilter, authFilter], ([q, t, a]) => {
  page.value = 1
  const nextQuery = {}
  if (q.trim()) nextQuery.q = q.trim()
  if (t !== 'all') nextQuery.type = t
  if (a !== 'all') nextQuery.auth = a
  router.replace({ query: nextQuery })
})

usePolling(() => emails.fetchTokenStatus(), 60000)

onMounted(async () => {
  await emails.refreshAll().catch(() => {})
  if (route.query.action === 'add') {
    openAddDialog(route.query.tab === 'device' ? 'device' : 'single')
  } else if (route.query.action === 'export') {
    handleExport()
  }
})

const openAddDialog = (tab = 'single') => {
  addDefaultTab.value = tab
  addDialogOpen.value = true
}
const openEditDialog = (row) => {
  activeEmail.value = row
  editDialogOpen.value = true
}
const openCredentialsDialog = (row) => {
  activeEmail.value = row
  credsDialogOpen.value = true
}
const openDeviceDialog = (req) => {
  deviceRequest.value = req
  deviceDialogOpen.value = true
}
const openReauthDevice = (row) =>
  openDeviceDialog({
    mode: 'reauth',
    emailId: row.id,
    email: row.email,
    clientId: row.client_id || ''
  })

function handlePageSizeChange(size) {
  ui.setEmailsPageSize(size)
  page.value = 1
}

async function handleRefreshList() {
  refreshingList.value = true
  try {
    await emails.refreshAll()
    ElMessage.success('刷新成功')
  } catch (_err) {
    ElMessage.error('刷新失败，请稍后重试')
  } finally {
    refreshingList.value = false
  }
}

async function handleRevealPassword(row) {
  if (revealedPasswords[row.id] !== undefined) {
    delete revealedPasswords[row.id]
    return
  }
  passwordLoading[row.id] = true
  try {
    const creds = await ensureCredentials(row)
    const pwd = creds?.password
    if (!pwd || pwd === '******') {
      ElMessage.warning('该邮箱未保存密码，或返回为空')
      return
    }
    revealedPasswords[row.id] = pwd
  } catch (_err) {
    ElMessage.error('获取密码失败')
  } finally {
    passwordLoading[row.id] = false
  }
}

async function handleToggleRealtime(row, enable) {
  try {
    const res = await emails.toggleRealtime(row.id, enable)
    ElMessage.success(res?.message || (enable ? '已开启实时收信' : '已关闭实时收信'))
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || '切换实时收信状态失败')
  }
}

async function handleSingleCheck(row) {
  try {
    const res = await emails.checkEmail(row.id)
    if (res?.status === 'processing') {
      ElMessage.warning(res.message || '邮箱正在处理中，请稍候...')
    } else {
      ElMessage.info(`正在检查邮箱 ${row.email} 的邮件，请稍候...`)
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || '检查邮件失败')
  }
}

const handleViewMail = (row) => router.push({ name: 'email-detail', params: { id: row.id } })

async function handleSingleKeepalive(row) {
  refreshingIds[row.id] = true
  try {
    const res = await api.refreshEmailToken(row.id)
    const data = res?.data || {}
    if (data.success) {
      const rotMsg = data.refresh_rotated ? '（Refresh Token 已轮换续期）' : ''
      ElMessage.success(`${row.email} 保活成功${rotMsg}`)
    } else if (data.need_reauth) ElMessage.warning(`${row.email} 需要重新授权：${data.error || data.message || ''}`)
    else ElMessage.error(`${row.email} 保活失败：${data.error || data.message || ''}`)
  } catch (err) {
    const data = err?.response?.data || {}
    if (data.need_reauth) ElMessage.warning(`${row.email} 需要重新授权：${data.error || data.message || ''}`)
    else ElMessage.error(`${row.email} 保活失败：${data.error || err?.message || ''}`)
  } finally {
    refreshingIds[row.id] = false
    await emails.refreshAll().catch(() => {})
  }
}

async function handleBatchCheck() {
  batchChecking.value = true
  try {
    await emails.checkEmails(selectedIds.value)
    ElMessage.info(`正在检查选中的 ${selectedIds.value.length} 个邮箱，请稍候...`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || '批量检查失败')
  } finally {
    batchChecking.value = false
  }
}

async function handleBatchRefresh() {
  const outlookIds = selectedRows.value.filter((r) => r.mail_type === 'outlook').map((r) => r.id)
  if (outlookIds.length === 0) return
  batchRefreshing.value = true
  try {
    const res = await api.batchRefreshTokens(outlookIds)
    ElMessage.success(`已提交 ${res?.data?.queued ?? outlookIds.length} 个 Outlook 邮箱进入后台保活队列`)
    setTimeout(() => emails.refreshAll().catch(() => {}), 3000)
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || '批量保活提交失败')
  } finally {
    batchRefreshing.value = false
  }
}

async function handleExport() {
  exporting.value = true
  try {
    await exportTxt(selectedRows.value.length > 0 ? selectedRows.value : filteredRows.value)
  } finally {
    exporting.value = false
  }
}

async function handleSingleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定要删除邮箱 ${row.email} 吗？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      confirmButtonClass: 'el-button--danger'
    })
    await emails.deleteEmail(row.id)
    selectedIds.value = selectedIds.value.filter((id) => id !== row.id)
    ElMessage.success('邮箱已删除')
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err?.response?.data?.error || '删除邮箱失败')
  }
}

async function handleBatchDelete() {
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedIds.value.length} 个邮箱吗？`, '确认批量删除', {
      type: 'warning',
      confirmButtonText: '删除',
      confirmButtonClass: 'el-button--danger'
    })
    batchDeleting.value = true
    await emails.deleteEmails(selectedIds.value)
    selectedIds.value = []
    ElMessage.success('批量删除成功')
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(err?.response?.data?.error || '批量删除失败')
  } finally {
    batchDeleting.value = false
  }
}
</script>

<template>
  <div class="fm-home-view">
    <PageHeader title="指挥台" :subtitle="greetingSubtitle">
      <template #actions>
        <el-button @click="router.push('/import')">
          <el-icon><Upload /></el-icon>
          <span>批量导入</span>
        </el-button>
        <el-button type="primary" @click="router.push('/emails?action=add')">
          <el-icon><Plus /></el-icon>
          <span>添加邮箱</span>
        </el-button>
      </template>
    </PageHeader>

    <section class="fm-home-stats" aria-label="核心指标">
      <StatCard label="邮箱账户" :value="stats.email_count" :loading="statsLoading" />
      <StatCard label="邮件总数" :value="stats.total_mails" :loading="statsLoading" />
      <StatCard
        label="已检查覆盖率"
        :value="stats.success_rate"
        unit="%"
        :loading="statsLoading"
      />
      <StatCard
        label="服务状态"
        :value="stats.status === 'online' ? '在线' : stats.status || '未知'"
        :tone="stats.status === 'online' ? 'success' : 'warning'"
        :loading="statsLoading"
      >
        <template #footer>
          <StatusPill :tone="wsPill.tone" size="sm">{{ wsPill.label }}</StatusPill>
        </template>
      </StatCard>
    </section>

    <div class="fm-home-grid">
      <TokenPostureCard
        :health="emails.tokenHealth || {}"
        :keeper="emails.tokenKeeper || {}"
      />

      <section class="fm-card fm-quick-card">
        <div class="fm-card-head">
          <div>
            <h2 class="fm-card-title">快捷操作</h2>
            <p class="fm-card-sub">常用高频工作流入口</p>
          </div>
        </div>

        <div class="fm-quick-list">
          <button
            v-for="act in quickActions"
            :key="act.key"
            type="button"
            class="fm-quick-btn"
            :disabled="act.key === 'check-all' && checkingAll"
            @click="act.handler"
          >
            <span class="fm-quick-btn__icon">
              <el-icon :size="16"><component :is="act.icon" /></el-icon>
            </span>
            <span class="fm-quick-btn__body">
              <span class="fm-quick-btn__title">{{ act.title }}</span>
              <span class="fm-quick-btn__desc">{{ act.desc }}</span>
            </span>
            <el-icon class="fm-quick-btn__arrow" :size="14"><ArrowRight /></el-icon>
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Upload,
  Download,
  RefreshRight,
  User,
  Setting,
  ArrowRight
} from '@element-plus/icons-vue'
import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { useEmailsStore } from '@/stores/emails'
import { useWsStore } from '@/stores/ws'
import { usePolling } from '@/composables/usePolling'
import PageHeader from '@/components/common/PageHeader.vue'
import StatCard from '@/components/common/StatCard.vue'
import StatusPill from '@/components/common/StatusPill.vue'
import TokenPostureCard from '@/components/home/TokenPostureCard.vue'

const router = useRouter()
const auth = useAuthStore()
const emails = useEmailsStore()
const ws = useWsStore()

const statsLoading = ref(true)
const checkingAll = ref(false)
const stats = reactive({
  email_count: 0,
  total_mails: 0,
  success_rate: 0,
  status: 'online'
})

const greetingSubtitle = computed(() => {
  const hour = new Date().getHours()
  let greet = '晚上好'
  if (hour < 6) greet = '夜深了'
  else if (hour < 12) greet = '早上好'
  else if (hour < 14) greet = '中午好'
  else if (hour < 18) greet = '下午好'
  return `${greet}，${auth.currentUser?.username || '用户'}`
})

const wsPill = computed(() => {
  if (ws.status === 'connected') return { tone: 'success', label: 'WS 实时已连接' }
  if (ws.status === 'connecting') return { tone: 'info', label: 'WS 连接中…' }
  return { tone: 'danger', label: 'WS 未连接' }
})

async function handleCheckAll() {
  try {
    await ElMessageBox.confirm('确定要对当前全部邮箱执行一次收信任务吗？', '收取全部邮件', {
      type: 'info',
      confirmButtonText: '开始收取'
    })
    checkingAll.value = true
    await emails.ensureEmailsLoaded()
    const ids = emails.emails.map((e) => e.id)
    if (ids.length === 0) {
      ElMessage.warning('当前没有可检查的邮箱')
      return
    }
    await emails.checkEmails(ids)
    ElMessage.success(`已提交 ${ids.length} 个邮箱进入后台收信队列`)
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error(err?.response?.data?.error || '提交收信任务失败')
    }
  } finally {
    checkingAll.value = false
  }
}

const quickActions = computed(() => {
  const list = [
    {
      key: 'add',
      title: '添加邮箱',
      desc: '支持 Device Code、单条录入与批量导入',
      icon: Plus,
      handler: () => router.push('/emails?action=add')
    },
    {
      key: 'check-all',
      title: '收取全部邮件',
      desc: '对当前账户下所有邮箱触发一次全量同步',
      icon: RefreshRight,
      handler: handleCheckAll
    },
    {
      key: 'export',
      title: '导出数据',
      desc: '按标准四段格式导出邮箱凭据 TXT 文件',
      icon: Download,
      handler: () => router.push('/emails?action=export')
    },
    {
      key: 'account',
      title: '账户设置',
      desc: '修改登录密码、主题偏好与邮件纸张模式',
      icon: User,
      handler: () => router.push('/account')
    }
  ]

  if (auth.isAdmin) {
    list.push(
      {
        key: 'admin-users',
        title: '用户管理',
        desc: '创建用户、重置密码与维护管理员权限',
        icon: User,
        handler: () => router.push('/admin/users')
      },
      {
        key: 'admin-system',
        title: '系统设置',
        desc: '注册开关、实时收信调度与服务健康检查',
        icon: Setting,
        handler: () => router.push('/admin/system')
      }
    )
  }
  return list
})

async function loadDashboard({ silent = false } = {}) {
  if (!silent) statsLoading.value = true
  try {
    const [statsRes] = await Promise.all([api.getStats(), emails.fetchTokenStatus()])
    const d = statsRes?.data || {}
    stats.email_count = Number(d.email_count) || 0
    stats.total_mails = Number(d.total_mails) || 0
    stats.success_rate = Number(d.success_rate) || 0
    stats.status = d.status || 'online'
  } catch (err) {
    if (!silent) console.warn('加载仪表盘统计失败:', err?.message)
  } finally {
    statsLoading.value = false
  }
}

usePolling(() => loadDashboard({ silent: true }), 60000)

onMounted(() => {
  loadDashboard()
})
</script>

<style scoped>
.fm-home-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--fm-space-4);
  margin-bottom: var(--fm-space-5);
}

.fm-home-grid {
  display: grid;
  grid-template-columns: minmax(0, 7fr) minmax(0, 5fr);
  gap: var(--fm-space-5);
  align-items: start;
}

.fm-quick-card {
  padding: var(--fm-space-5);
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-4);
}

.fm-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--fm-space-3);
}

.fm-card-title {
  margin: 0;
  font-size: var(--fm-fs-md);
  font-weight: 600;
  color: var(--fm-text);
}

.fm-card-sub {
  margin: 2px 0 0;
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
}

.fm-quick-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.fm-quick-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--fm-border);
  border-radius: var(--fm-radius-md);
  background: var(--fm-surface-2);
  color: var(--fm-text);
  cursor: pointer;
  text-align: left;
  transition: background var(--fm-dur-fast) var(--fm-ease), border-color var(--fm-dur-fast) var(--fm-ease);
}

.fm-quick-btn:hover:not(:disabled) {
  background: var(--fm-surface-hover);
  border-color: var(--fm-border-strong);
}

.fm-quick-btn__icon {
  width: 32px;
  height: 32px;
  border-radius: var(--fm-radius-sm);
  background: var(--fm-primary-soft);
  color: var(--fm-text);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.fm-quick-btn__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.fm-quick-btn__title {
  font-size: var(--fm-fs-sm);
  font-weight: 500;
  color: var(--fm-text);
}

.fm-quick-btn__desc {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
}

.fm-quick-btn__arrow {
  color: var(--fm-text-3);
  flex-shrink: 0;
}

@media (max-width: 1199.98px) {
  .fm-home-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .fm-home-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767.98px) {
  .fm-home-stats {
    grid-template-columns: 1fr;
  }
}
</style>

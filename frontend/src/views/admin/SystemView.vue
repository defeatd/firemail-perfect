<template>
  <div class="fm-system-view">
    <PageHeader
      title="系统设置"
      subtitle="控制全局注册策略、实时收信调度并查看 Token 保活与服务健康"
    />

    <div class="fm-system-grid">
      <section class="fm-card fm-sys-card">
        <div class="fm-sys-card__head">
          <h2 class="fm-sys-card__title">用户注册</h2>
          <StatusPill :tone="auth.allowRegister ? 'success' : 'muted'">
            {{ auth.allowRegister ? '已开启' : '已关闭' }}
          </StatusPill>
        </div>
        <p class="fm-sys-card__desc">
          控制是否允许访客通过注册页面自行创建普通账户。关闭后仅管理员可在用户管理页新增账号。
        </p>
        <div class="fm-sys-card__row">
          <span class="fm-sys-card__label">允许新用户注册</span>
          <el-switch
            :model-value="auth.allowRegister"
            :loading="togglingReg"
            active-text="开启"
            inactive-text="关闭"
            @change="handleToggleRegistration"
          />
        </div>
      </section>

      <section class="fm-card fm-sys-card">
        <div class="fm-sys-card__head">
          <h2 class="fm-sys-card__title">实时收信调度</h2>
        </div>
        <p class="fm-sys-card__desc">
          控制后端全局定时轮询任务。开启了「实时收信」开关的邮箱将按指定间隔自动拉取新邮件。
        </p>

        <div class="fm-sys-card__realtime-form">
          <label class="fm-sys-card__label" for="fm-rt-interval">轮询间隔（秒，≥30）</label>
          <el-input-number
            id="fm-rt-interval"
            v-model="realtimeInterval"
            :min="30"
            :max="3600"
            :step="10"
            controls-position="right"
          />
        </div>

        <div class="fm-sys-card__actions">
          <el-button type="primary" :loading="startingRt" @click="handleStartRealtime">
            启动
          </el-button>
          <el-button :loading="stoppingRt" @click="handleStopRealtime">
            停止
          </el-button>
        </div>

        <p v-if="realtimeMessage" class="fm-sys-card__result">
          上次操作结果：{{ realtimeMessage }}
        </p>
      </section>

      <section class="fm-card fm-sys-card">
        <div class="fm-sys-card__head">
          <h2 class="fm-sys-card__title">Token 保活调度</h2>
          <div class="fm-sys-card__head-right">
            <StatusPill :tone="keeper?.running ? 'info' : 'muted'">
              {{ keeper?.running ? '运行中' : '未运行' }}
            </StatusPill>
            <el-button size="small" :loading="loadingKeeper" @click="loadKeeperStatus">
              刷新
            </el-button>
          </div>
        </div>
        <p class="fm-sys-card__desc">
          只读展示 Outlook 90 天 Refresh Token 后台保活调度器参数与账户池健康统计。
        </p>

        <div class="fm-sys-card__split">
          <div>
            <h3 class="fm-sys-card__sub">调度器状态</h3>
            <KeyValueList :items="keeperItems" dense />
          </div>
          <div>
            <h3 class="fm-sys-card__sub">令牌健康汇总</h3>
            <KeyValueList :items="healthItems" dense />
          </div>
        </div>
      </section>

      <section class="fm-card fm-sys-card">
        <div class="fm-sys-card__head">
          <h2 class="fm-sys-card__title">服务健康</h2>
        </div>
        <p class="fm-sys-card__desc">
          主动探测后端 REST API <code class="fm-mono">/api/health</code> 端点连通性与响应状态。
        </p>
        <div>
          <el-button :loading="testingHealth" @click="handleHealthTest">
            检测 API 连接
          </el-button>
        </div>
        <p v-if="healthResult" class="fm-sys-card__health" :class="healthOk ? 'is-ok' : 'is-err'">
          {{ healthResult }}
        </p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/services/api'
import { formatAbs } from '@/utils/time'
import { useAuthStore } from '@/stores/auth'
import { useEmailsStore } from '@/stores/emails'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusPill from '@/components/common/StatusPill.vue'
import KeyValueList from '@/components/common/KeyValueList.vue'

const auth = useAuthStore()
const emails = useEmailsStore()

const togglingReg = ref(false)
const realtimeInterval = ref(60)
const startingRt = ref(false)
const stoppingRt = ref(false)
const realtimeMessage = ref('')
const loadingKeeper = ref(false)
const testingHealth = ref(false)
const healthResult = ref('')
const healthOk = ref(false)

const keeper = computed(() => emails.tokenKeeper || {})
const health = computed(() => emails.tokenHealth || {})

const keeperItems = computed(() => {
  const k = keeper.value
  const stats = k.last_run_stats
  const tickVal = k.tick ?? k.tick_seconds
  const statsText = stats
    ? `检查 ${stats.checked ?? 0} · 成功 ${stats.rotated ?? 0} · 失败 ${stats.failed ?? 0}`
    : '—'
  return [
    { label: '运行状态', value: k.running ? '运行中' : '未运行' },
    { label: '巡检周期', value: tickVal ? `${tickVal}s` : '—', mono: true },
    { label: '并发数', value: k.concurrency ?? '—', mono: true },
    { label: '轮换阈值', value: k.rotate_after_days ? `${k.rotate_after_days} 天` : '—', mono: true },
    {
      label: '上次运行',
      value: k.last_run_at ? formatAbs(k.last_run_at) : '尚未运行',
      mono: true
    },
    { label: '上次统计', value: statsText, mono: true }
  ]
})

const healthItems = computed(() => {
  const h = health.value
  const earliest = h.earliest_rt_expires_at || h.earliest_expiry
  return [
    { label: 'Outlook 总数', value: String(h.total ?? h.total_outlook ?? 0), mono: true },
    { label: '正常', value: String(h.ok ?? 0), mono: true },
    { label: '15 天内到期', value: String(h.expiring_15d ?? 0), mono: true },
    { label: '7 天内到期', value: String(h.expiring_7d ?? 0), mono: true },
    { label: '需重授', value: String(h.need_reauth ?? 0), mono: true },
    { label: '已封禁 / 异常', value: `${h.banned ?? 0} / ${h.failing ?? h.error ?? 0}`, mono: true },
    {
      label: '最早到期',
      value: earliest ? formatAbs(earliest, 'YYYY-MM-DD') : '—',
      mono: true
    }
  ]
})

async function handleToggleRegistration(next) {
  const prev = auth.allowRegister
  togglingReg.value = true
  try {
    await auth.toggleRegistration(next)
    ElMessage.success(next ? '已开启注册功能' : '已关闭注册功能')
  } catch (err) {
    auth.allowRegister = prev
    const actionText = next ? '开启' : '关闭'
    ElMessage.error(
      `${actionText}注册功能失败: ${err?.response?.data?.error || err?.message || '未知错误'}`
    )
  } finally {
    togglingReg.value = false
  }
}

async function handleStartRealtime() {
  startingRt.value = true
  try {
    const interval = Math.max(30, Number(realtimeInterval.value) || 60)
    realtimeInterval.value = interval
    const res = await api.admin.startRealtime(interval)
    const msg = res?.data?.message || '实时邮件检查已启动'
    realtimeMessage.value = msg
    ElMessage[res?.data?.success === false ? 'warning' : 'success'](msg)
  } catch (err) {
    const msg = err?.response?.data?.message || err?.response?.data?.error || '启动失败'
    realtimeMessage.value = msg
    ElMessage.error(msg)
  } finally {
    startingRt.value = false
  }
}

async function handleStopRealtime() {
  stoppingRt.value = true
  try {
    const res = await api.admin.stopRealtime()
    const msg = res?.data?.message || '实时邮件检查已停止'
    realtimeMessage.value = msg
    ElMessage[res?.data?.success === false ? 'warning' : 'success'](msg)
  } catch (err) {
    const msg = err?.response?.data?.message || err?.response?.data?.error || '停止失败'
    realtimeMessage.value = msg
    ElMessage.error(msg)
  } finally {
    stoppingRt.value = false
  }
}

async function loadKeeperStatus() {
  loadingKeeper.value = true
  try {
    await emails.fetchTokenStatus()
  } finally {
    loadingKeeper.value = false
  }
}

async function handleHealthTest() {
  testingHealth.value = true
  healthResult.value = ''
  try {
    const res = await api.health()
    healthOk.value = true
    healthResult.value = `连接成功: ${res?.data?.message || res?.data?.status || 'ok'}`
  } catch (err) {
    healthOk.value = false
    const code = err?.response?.status
    healthResult.value = code ? `连接失败: HTTP ${code}` : `连接失败: ${err?.message || '网络异常'}`
  } finally {
    testingHealth.value = false
  }
}

onMounted(() => {
  auth.getConfig()
  loadKeeperStatus()
})
</script>

<style scoped>
.fm-system-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--fm-space-5);
  align-items: start;
}

.fm-sys-card {
  padding: var(--fm-space-5);
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-4);
}

.fm-sys-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--fm-space-2);
}

.fm-sys-card__head-right {
  display: inline-flex;
  align-items: center;
  gap: var(--fm-space-2);
}

.fm-sys-card__title {
  margin: 0;
  font-size: var(--fm-fs-md);
  font-weight: 600;
  color: var(--fm-text);
}

.fm-sys-card__sub {
  margin: 0 0 8px;
  font-size: var(--fm-fs-xs);
  font-weight: 600;
  color: var(--fm-text-2);
}

.fm-sys-card__desc {
  margin: 0;
  font-size: var(--fm-fs-sm);
  color: var(--fm-text-2);
  line-height: var(--fm-lh-base);
}

.fm-sys-card__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--fm-space-3);
}

.fm-sys-card__label {
  font-size: var(--fm-fs-sm);
  color: var(--fm-text);
}

.fm-sys-card__realtime-form {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--fm-space-3);
  flex-wrap: wrap;
}

.fm-sys-card__actions {
  display: flex;
  align-items: center;
  gap: var(--fm-space-2);
}

.fm-sys-card__result {
  margin: 0;
  padding: 8px 10px;
  border-radius: var(--fm-radius-sm);
  background: var(--fm-bg-subtle);
  border: 1px solid var(--fm-border);
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-2);
}

.fm-sys-card__split {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--fm-space-4);
}

.fm-sys-card__health {
  margin: 0;
  padding: 8px 10px;
  border-radius: var(--fm-radius-sm);
  font-size: var(--fm-fs-xs);
}

.fm-sys-card__health.is-ok {
  background: var(--fm-success-soft);
  color: var(--fm-success);
}

.fm-sys-card__health.is-err {
  background: var(--fm-danger-soft);
  color: var(--fm-danger);
}

@media (max-width: 1199.98px) {
  .fm-system-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767.98px) {
  .fm-sys-card__split {
    grid-template-columns: 1fr;
  }
}
</style>

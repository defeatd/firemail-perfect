<template>
  <section class="fm-card fm-posture-card">
    <div class="fm-card-head">
      <div>
        <h2 class="fm-card-title">Outlook 保活态势</h2>
        <p class="fm-card-sub">90 天 Refresh Token 生命周期健康分布</p>
      </div>
      <StatusPill :tone="keeperRunning ? 'info' : 'muted'">
        {{ keeperRunning ? '调度运行中' : '调度未运行' }}
      </StatusPill>
    </div>

    <div class="fm-posture-bar" role="img" aria-label="Outlook 令牌状态分布条">
      <template v-if="activeSegments.length > 0">
        <div
          v-for="seg in activeSegments"
          :key="seg.key"
          class="fm-posture-bar__seg"
          :class="`is-${seg.key}`"
          :style="{ width: `${seg.percent}%` }"
          :title="`${seg.label}：${seg.count}`"
        />
      </template>
      <div v-else class="fm-posture-bar__empty" />
    </div>

    <div class="fm-posture-legend">
      <div v-for="seg in segments" :key="seg.key" class="fm-posture-legend__item">
        <span class="fm-posture-legend__dot" :class="`is-${seg.key}`" />
        <span class="fm-posture-legend__label">{{ seg.label }}</span>
        <strong class="fm-mono fm-posture-legend__val">{{ seg.count }}</strong>
      </div>
    </div>

    <div class="fm-posture-meta">
      <div class="fm-posture-meta__row">
        <span class="fm-posture-meta__k">最早到期</span>
        <span class="fm-mono fm-posture-meta__v">{{ earliestSummary }}</span>
      </div>
      <div class="fm-posture-meta__row">
        <span class="fm-posture-meta__k">上次保活巡检</span>
        <span class="fm-mono fm-posture-meta__v">{{ lastRunSummary }}</span>
      </div>
    </div>

    <div class="fm-posture-foot">
      <router-link to="/emails?filter=attention" class="fm-posture-link">
        <span>前往保活中心</span>
        <el-icon><ArrowRight /></el-icon>
      </router-link>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'
import { formatAbs, daysUntil } from '@/utils/time'
import StatusPill from '@/components/common/StatusPill.vue'

const props = defineProps({
  health: { type: Object, default: () => ({}) },
  keeper: { type: Object, default: () => ({}) }
})

const keeperRunning = computed(() => Boolean(props.keeper?.running))
const totalOutlook = computed(() => Number(props.health?.total ?? props.health?.total_outlook ?? 0))

const segments = computed(() => {
  const h = props.health || {}
  const total = totalOutlook.value || 1
  const expiring7 = Number(h.expiring_7d) || 0
  const expiring15Only = Math.max((Number(h.expiring_15d) || 0) - expiring7, 0)
  const pending = Number(h.pending ?? h.pending_cnt ?? 0)
  const unverified = Number(h.never_verified ?? h.unverified ?? 0)
  const okHealthy = Math.max((Number(h.ok) || 0) - expiring7 - expiring15Only - unverified, 0)
  const needReauth = Number(h.need_reauth) || 0
  const banned = Number(h.banned) || 0

  const list = [
    { key: 'healthy', label: '正常', count: okHealthy },
    { key: 'warn15', label: '15 天预警', count: expiring15Only },
    { key: 'warn7', label: '7 天告警', count: expiring7 },
    { key: 'reauth', label: '需重授', count: needReauth },
    { key: 'banned', label: '已封禁', count: banned },
    { key: 'unverified', label: '未验证', count: unverified }
  ]
  if (pending > 0) {
    list.splice(1, 0, { key: 'pending', label: '首验中', count: pending })
  }
  return list.map((item) => ({
    ...item,
    percent: totalOutlook.value > 0 ? (item.count / total) * 100 : 0
  }))
})

const activeSegments = computed(() => segments.value.filter((seg) => seg.count > 0))

const earliestSummary = computed(() => {
  const raw = props.health?.earliest_rt_expires_at || props.health?.earliest_expiry
  if (!raw) return '暂无到期记录'
  const dateStr = formatAbs(raw, 'YYYY-MM-DD')
  const d = daysUntil(raw)
  if (d === null) return dateStr
  return d < 0 ? `${dateStr}（已超期 ${Math.abs(d)} 天）` : `${dateStr}（${d} 天后）`
})

const lastRunSummary = computed(() => {
  const k = props.keeper
  if (!k?.last_run_at) return '尚未执行'
  const timeStr = formatAbs(k.last_run_at, 'YYYY-MM-DD HH:mm')
  const st = k.last_run_stats
  if (!st) return timeStr
  return `${timeStr} · 成功 ${st.rotated || 0} / 失败 ${st.failed || 0}`
})
</script>

<style scoped>
.fm-posture-card {
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

.fm-posture-bar {
  display: flex;
  height: 10px;
  border-radius: var(--fm-radius-pill);
  background: var(--fm-bg-subtle);
  overflow: hidden;
  gap: 2px;
}

.fm-posture-bar__seg {
  height: 100%;
  min-width: 4px;
  transition: width var(--fm-dur) var(--fm-ease);
}

.fm-posture-bar__seg.is-healthy,
.fm-posture-legend__dot.is-healthy {
  background: var(--fm-success);
}

.fm-posture-bar__seg.is-warn15,
.fm-posture-legend__dot.is-warn15 {
  background: var(--fm-warning);
}

.fm-posture-bar__seg.is-warn7,
.fm-posture-legend__dot.is-warn7 {
  background: var(--fm-accent);
}

.fm-posture-bar__seg.is-reauth,
.fm-posture-legend__dot.is-reauth {
  background: var(--fm-danger);
}

.fm-posture-bar__seg.is-banned,
.fm-posture-legend__dot.is-banned {
  background: var(--fm-text-3);
}

.fm-posture-bar__seg.is-pending,
.fm-posture-legend__dot.is-pending {
  background: var(--fm-info);
}

.fm-posture-bar__seg.is-unverified,
.fm-posture-legend__dot.is-unverified {
  background: var(--fm-border-strong);
}

.fm-posture-bar__empty {
  width: 100%;
  background: var(--fm-bg-subtle);
}

.fm-posture-legend {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--fm-space-3);
}

.fm-posture-legend__item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--fm-fs-xs);
}

.fm-posture-legend__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.fm-posture-legend__label {
  color: var(--fm-text-2);
}

.fm-posture-legend__val {
  margin-left: auto;
  color: var(--fm-text);
}

.fm-posture-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: var(--fm-space-3);
  border-top: 1px solid var(--fm-border);
}

.fm-posture-meta__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--fm-space-2);
  font-size: var(--fm-fs-xs);
}

.fm-posture-meta__k {
  color: var(--fm-text-3);
}

.fm-posture-meta__v {
  color: var(--fm-text);
}

.fm-posture-foot {
  padding-top: var(--fm-space-2);
}

.fm-posture-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fm-fs-sm);
  font-weight: 500;
  color: var(--fm-accent);
  text-decoration: none;
}

.fm-posture-link:hover {
  text-decoration: underline;
}

@media (max-width: 767.98px) {
  .fm-posture-legend {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

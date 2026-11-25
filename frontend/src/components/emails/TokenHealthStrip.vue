<template>
  <section v-if="health" class="fm-health-strip" aria-label="Outlook 保活健康状态">
    <div class="fm-health-strip__metrics">
      <button
        type="button"
        class="fm-health-strip__item"
        :class="{ 'is-active': activeAuth === 'all' }"
        @click="$emit('select-filter', 'all')"
      >
        <StatusPill :tone="keeperRunning ? 'info' : 'muted'" size="sm">
          {{ keeperRunning ? '保活运行中' : '保活未运行' }}
        </StatusPill>
      </button>

      <span class="fm-health-strip__sep" aria-hidden="true" />

      <button
        type="button"
        class="fm-health-strip__item"
        :class="{ 'is-active': activeAuth === 'ok' }"
        @click="$emit('select-filter', 'ok')"
      >
        <span class="fm-health-strip__label">正常</span>
        <span class="fm-health-strip__val fm-mono is-success">
          {{ health.ok || 0 }}/{{ totalOutlook }}
        </span>
      </button>

      <span class="fm-health-strip__sep" aria-hidden="true" />

      <button
        type="button"
        class="fm-health-strip__item"
        :class="{ 'is-active': activeAuth === 'need_reauth' }"
        @click="$emit('select-filter', 'need_reauth')"
      >
        <span class="fm-health-strip__label">需重授</span>
        <span
          class="fm-health-strip__val fm-mono"
          :class="{ 'is-danger': (health.need_reauth || 0) > 0 }"
        >
          {{ health.need_reauth || 0 }}
        </span>
      </button>

      <template v-if="(health.banned || 0) > 0">
        <span class="fm-health-strip__sep" aria-hidden="true" />
        <button
          type="button"
          class="fm-health-strip__item"
          :class="{ 'is-active': activeAuth === 'banned' }"
          @click="$emit('select-filter', 'banned')"
        >
          <span class="fm-health-strip__label">已封禁</span>
          <span class="fm-health-strip__val fm-mono">{{ health.banned }}</span>
        </button>
      </template>

      <span class="fm-health-strip__sep" aria-hidden="true" />

      <button
        type="button"
        class="fm-health-strip__item"
        :class="{ 'is-active': activeAuth === 'expiring_7d' }"
        @click="$emit('select-filter', 'expiring_7d')"
      >
        <span class="fm-health-strip__label">7 天内到期</span>
        <span
          class="fm-health-strip__val fm-mono"
          :class="{ 'is-danger': (health.expiring_7d || 0) > 0 }"
        >
          {{ health.expiring_7d || 0 }}
        </span>
      </button>

      <span class="fm-health-strip__sep" aria-hidden="true" />

      <button
        type="button"
        class="fm-health-strip__item"
        :class="{ 'is-active': activeAuth === 'error' }"
        @click="$emit('select-filter', 'error')"
      >
        <span class="fm-health-strip__label">失败中</span>
        <span
          class="fm-health-strip__val fm-mono"
          :class="{ 'is-warning': failingCount > 0 }"
        >
          {{ failingCount }}
        </span>
      </button>
    </div>

    <button
      v-if="earliestDate"
      type="button"
      class="fm-health-strip__earliest"
      @click="$emit('select-filter', 'expiring_15d')"
    >
      <span class="fm-health-strip__label">最早到期</span>
      <span class="fm-mono fm-health-strip__date">{{ earliestDate }}</span>
    </button>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { formatAbs } from '@/utils/time'
import StatusPill from '@/components/common/StatusPill.vue'

const props = defineProps({
  health: { type: Object, default: null },
  keeper: { type: Object, default: null },
  activeAuth: { type: String, default: 'all' }
})

defineEmits(['select-filter'])

const keeperRunning = computed(() => Boolean(props.keeper?.running))
const totalOutlook = computed(() => Number(props.health?.total ?? props.health?.total_outlook ?? 0))
const failingCount = computed(() => Number(props.health?.failing ?? props.health?.error ?? 0))

const earliestDate = computed(() => {
  const raw = props.health?.earliest_rt_expires_at || props.health?.earliest_expiry
  if (!raw) return ''
  return formatAbs(raw, 'YYYY-MM-DD')
})
</script>

<style scoped>
.fm-health-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--fm-space-3);
  min-height: 48px;
  padding: 6px var(--fm-space-4);
  background: var(--fm-surface);
  border: 1px solid var(--fm-border);
  border-radius: var(--fm-radius-lg);
  box-shadow: var(--fm-shadow-xs);
  margin-bottom: var(--fm-space-4);
  flex-wrap: wrap;
}

.fm-health-strip__metrics {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.fm-health-strip__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: var(--fm-radius-sm);
  background: transparent;
  cursor: pointer;
  transition: background var(--fm-dur-fast) var(--fm-ease), border-color var(--fm-dur-fast) var(--fm-ease);
}

.fm-health-strip__item:hover {
  background: var(--fm-surface-hover);
}

.fm-health-strip__item.is-active {
  background: var(--fm-surface-active);
  border-color: var(--fm-border-strong);
}

.fm-health-strip__label {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
}

.fm-health-strip__val {
  font-size: 15px;
  font-weight: 600;
  color: var(--fm-text);
}

.fm-health-strip__val.is-success {
  color: var(--fm-success);
}

.fm-health-strip__val.is-danger {
  color: var(--fm-danger);
}

.fm-health-strip__val.is-warning {
  color: var(--fm-warning);
}

.fm-health-strip__sep {
  width: 1px;
  height: 18px;
  background: var(--fm-border);
}

.fm-health-strip__earliest {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 8px;
  border: none;
  border-radius: var(--fm-radius-sm);
  background: transparent;
  cursor: pointer;
}

.fm-health-strip__earliest:hover {
  background: var(--fm-surface-hover);
}

.fm-health-strip__date {
  font-size: var(--fm-fs-sm);
  font-weight: 500;
  color: var(--fm-text);
}
</style>

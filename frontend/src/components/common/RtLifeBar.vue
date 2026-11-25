<template>
  <div v-if="visible" class="fm-rt-bar">
    <div class="fm-rt-bar__track" role="progressbar" :aria-valuenow="percent" aria-valuemin="0" aria-valuemax="100">
      <div
        class="fm-rt-bar__fill"
        :class="`fm-rt-bar__fill--${tone}`"
        :style="{ width: `${percent}%` }"
      />
    </div>
    <span class="fm-rt-bar__text fm-mono" :class="`fm-rt-bar__text--${tone}`">
      {{ labelText }}
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { daysUntil } from '@/utils/time'

const props = defineProps({
  expiresAt: { type: [String, Date], default: null },
  status: { type: String, default: 'ok' },
  total: { type: Number, default: 90 }
})

const days = computed(() => daysUntil(props.expiresAt))

const visible = computed(() => {
  if (!props.expiresAt) return false
  if (props.status === 'need_reauth' || props.status === 'banned') return false
  return days.value !== null
})

const percent = computed(() => {
  if (days.value === null) return 0
  const ratio = Math.max(0, Math.min(1, days.value / (props.total || 90)))
  return Math.round(ratio * 100)
})

const tone = computed(() => {
  if (days.value === null) return 'muted'
  if (days.value < 7) return 'danger'
  if (days.value < 15) return 'warning'
  return 'success'
})

const labelText = computed(() => {
  if (days.value === null) return ''
  if (days.value < 0) return `已超期 ${Math.abs(days.value)} 天`
  return `剩 ${days.value} 天`
})
</script>

<style scoped>
.fm-rt-bar {
  display: flex;
  align-items: center;
  gap: var(--fm-space-2);
  margin-top: 5px;
}

.fm-rt-bar__track {
  flex: 1;
  min-width: 56px;
  height: 4px;
  border-radius: var(--fm-radius-pill);
  background: var(--fm-bg-subtle);
  overflow: hidden;
}

.fm-rt-bar__fill {
  height: 100%;
  border-radius: var(--fm-radius-pill);
  transition: width var(--fm-dur) var(--fm-ease);
}

.fm-rt-bar__fill--success {
  background: var(--fm-success);
}

.fm-rt-bar__fill--warning {
  background: var(--fm-warning);
}

.fm-rt-bar__fill--danger {
  background: var(--fm-danger);
}

.fm-rt-bar__text {
  font-size: var(--fm-fs-xs);
  white-space: nowrap;
  color: var(--fm-text-2);
}

.fm-rt-bar__text--warning {
  color: var(--fm-warning);
}

.fm-rt-bar__text--danger {
  color: var(--fm-danger);
}
</style>

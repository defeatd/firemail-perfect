<template>
  <section class="fm-stat-card" :class="`fm-stat-card--${tone}`">
    <div class="fm-stat-card__top">
      <span class="fm-stat-card__label">{{ label }}</span>
      <span v-if="trend" class="fm-stat-card__trend fm-mono">{{ trend }}</span>
    </div>

    <div class="fm-stat-card__body">
      <el-skeleton v-if="loading" animated :rows="0">
        <template #template>
          <el-skeleton-item variant="text" class="fm-stat-card__skeleton" />
        </template>
      </el-skeleton>
      <template v-else>
        <slot name="value">
          <div class="fm-stat-card__value-row">
            <span class="fm-stat-card__value fm-mono">{{ displayValue }}</span>
            <span v-if="unit" class="fm-stat-card__unit">{{ unit }}</span>
          </div>
        </slot>
      </template>
    </div>

    <div v-if="$slots.footer" class="fm-stat-card__footer">
      <slot name="footer" />
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [Number, String], default: '—' },
  unit: { type: String, default: '' },
  trend: { type: String, default: '' },
  tone: {
    type: String,
    default: 'default',
    validator: (v) => ['default', 'success', 'warning', 'danger', 'info'].includes(v)
  },
  loading: { type: Boolean, default: false }
})

const displayValue = computed(() => {
  if (props.value === null || props.value === undefined || props.value === '') return '—'
  return props.value
})
</script>

<style scoped>
.fm-stat-card {
  background: var(--fm-surface);
  border: 1px solid var(--fm-border);
  border-radius: var(--fm-radius-lg);
  padding: var(--fm-space-5);
  box-shadow: var(--fm-shadow-xs);
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-2);
  min-width: 0;
}

.fm-stat-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--fm-space-2);
}

.fm-stat-card__label {
  font-size: var(--fm-fs-xs);
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--fm-text-3);
}

.fm-stat-card__trend {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-2);
}

.fm-stat-card__body {
  min-height: 36px;
  display: flex;
  align-items: baseline;
}

.fm-stat-card__skeleton {
  width: 96px;
  height: 28px;
}

.fm-stat-card__value-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
  min-width: 0;
}

.fm-stat-card__value {
  font-size: 28px;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -0.02em;
  color: var(--fm-text);
}

.fm-stat-card--success .fm-stat-card__value {
  color: var(--fm-success);
}

.fm-stat-card--warning .fm-stat-card__value {
  color: var(--fm-warning);
}

.fm-stat-card--danger .fm-stat-card__value {
  color: var(--fm-danger);
}

.fm-stat-card--info .fm-stat-card__value {
  color: var(--fm-info);
}

.fm-stat-card__unit {
  font-size: var(--fm-fs-sm);
  color: var(--fm-text-3);
  font-weight: 500;
}

.fm-stat-card__footer {
  margin-top: var(--fm-space-1);
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
  display: flex;
  align-items: center;
  gap: var(--fm-space-2);
}
</style>

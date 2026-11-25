<template>
  <span class="fm-pill" :class="[`fm-pill--${tone}`, `fm-pill--${size}`]">
    <span v-if="dot" class="fm-pill__dot" aria-hidden="true" />
    <span class="fm-pill__label"><slot /></span>
  </span>
</template>

<script setup>
defineProps({
  tone: {
    type: String,
    default: 'default',
    validator: (v) =>
      ['default', 'muted', 'solid-muted', 'accent', 'success', 'warning', 'danger', 'info'].includes(v)
  },
  dot: { type: Boolean, default: true },
  size: {
    type: String,
    default: 'sm',
    validator: (v) => ['sm', 'md'].includes(v)
  }
})
</script>

<style scoped>
.fm-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: var(--fm-radius-pill);
  font-weight: 500;
  white-space: nowrap;
  line-height: 1;
  border: 1px solid transparent;
}

.fm-pill--sm {
  height: 22px;
  padding: 0 8px;
  font-size: var(--fm-fs-xs);
}

.fm-pill--md {
  height: 26px;
  padding: 0 10px;
  font-size: var(--fm-fs-sm);
}

.fm-pill__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}

.fm-pill--default,
.fm-pill--muted {
  background: var(--fm-muted-soft);
  color: var(--fm-text-2);
  border-color: var(--fm-border);
}

.fm-pill--solid-muted {
  background: var(--fm-text-2);
  color: var(--fm-text-inverse);
}

.fm-pill--accent {
  background: var(--fm-accent-soft);
  color: var(--fm-accent);
  border-color: var(--fm-accent-border);
}

.fm-pill--success {
  background: var(--fm-success-soft);
  color: var(--fm-success);
  border-color: var(--fm-success-border);
}

.fm-pill--warning {
  background: var(--fm-warning-soft);
  color: var(--fm-warning);
  border-color: var(--fm-warning-border);
}

.fm-pill--danger {
  background: var(--fm-danger-soft);
  color: var(--fm-danger);
  border-color: var(--fm-danger-border);
}

.fm-pill--info {
  background: var(--fm-info-soft);
  color: var(--fm-info);
  border-color: var(--fm-info-border);
}
</style>

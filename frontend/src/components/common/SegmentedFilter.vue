<template>
  <div class="fm-segmented" :class="`fm-segmented--${size}`" role="tablist">
    <button
      v-for="opt in options"
      :key="String(opt.value)"
      type="button"
      role="tab"
      class="fm-segmented__item"
      :class="{ 'is-active': modelValue === opt.value }"
      :aria-selected="modelValue === opt.value"
      @click="$emit('update:modelValue', opt.value)"
    >
      <span>{{ opt.label }}</span>
      <span
        v-if="opt.count !== undefined && opt.count !== null"
        class="fm-segmented__count fm-mono"
      >
        {{ opt.count }}
      </span>
    </button>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: [String, Number, Boolean], required: true },
  options: { type: Array, required: true },
  size: {
    type: String,
    default: 'md',
    validator: (v) => ['sm', 'md'].includes(v)
  }
})

defineEmits(['update:modelValue'])
</script>

<style scoped>
.fm-segmented {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 3px;
  border-radius: var(--fm-radius-md);
  background: var(--fm-bg-subtle);
  border: 1px solid var(--fm-border);
  max-width: 100%;
  overflow-x: auto;
}

.fm-segmented__item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: none;
  background: transparent;
  color: var(--fm-text-2);
  border-radius: var(--fm-radius-sm);
  font-size: var(--fm-fs-sm);
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--fm-dur-fast) var(--fm-ease), color var(--fm-dur-fast) var(--fm-ease), box-shadow var(--fm-dur-fast) var(--fm-ease);
}

.fm-segmented--md .fm-segmented__item {
  height: 28px;
  padding: 0 10px;
}

.fm-segmented--sm .fm-segmented__item {
  height: 24px;
  padding: 0 8px;
  font-size: var(--fm-fs-xs);
}

.fm-segmented__item:hover:not(.is-active) {
  color: var(--fm-text);
  background: var(--fm-surface-hover);
}

.fm-segmented__item.is-active {
  background: var(--fm-surface);
  color: var(--fm-text);
  box-shadow: var(--fm-shadow-xs);
}

.fm-segmented__count {
  font-size: 11px;
  color: var(--fm-text-3);
}

.fm-segmented__item.is-active .fm-segmented__count {
  color: var(--fm-text-2);
}
</style>

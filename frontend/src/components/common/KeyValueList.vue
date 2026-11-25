<template>
  <dl class="fm-kv" :class="{ 'fm-kv--dense': dense }">
    <div v-for="(item, idx) in items" :key="`${item.label}-${idx}`" class="fm-kv__row">
      <dt class="fm-kv__label">{{ item.label }}</dt>
      <dd class="fm-kv__value" :class="{ 'fm-mono': item.mono }">
        <CopyText
          v-if="item.copy && item.value"
          :text="String(item.value)"
          :label="item.labelForCopy || item.label"
          :mono="Boolean(item.mono)"
        />
        <span v-else>{{ item.value ?? '—' }}</span>
      </dd>
    </div>
  </dl>
</template>

<script setup>
import CopyText from './CopyText.vue'

defineProps({
  items: { type: Array, default: () => [] },
  dense: { type: Boolean, default: false }
})
</script>

<style scoped>
.fm-kv {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fm-kv--dense {
  gap: 4px;
}

.fm-kv__row {
  display: grid;
  grid-template-columns: minmax(84px, auto) 1fr;
  align-items: baseline;
  gap: var(--fm-space-3);
}

.fm-kv__label {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
  white-space: nowrap;
}

.fm-kv__value {
  margin: 0;
  font-size: var(--fm-fs-sm);
  color: var(--fm-text);
  word-break: break-word;
  text-align: right;
}

.fm-kv--dense .fm-kv__value {
  font-size: var(--fm-fs-xs);
}
</style>

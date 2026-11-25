<template>
  <span
    class="fm-brand-icon"
    :style="{ width: `${size}px`, height: `${size}px` }"
    :title="label"
    aria-hidden="true"
  >
    <!-- Brand official hex colors explicitly permitted per Contract §8.3 -->
    <svg v-if="type === 'outlook'" viewBox="0 0 24 24" fill="none">
      <rect x="2" y="4" width="20" height="16" rx="3" fill="#0078D4" />
      <path d="M3.5 6.5L12 12.8L20.5 6.5" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
      <circle cx="12" cy="14.5" r="3.2" fill="#0078D4" stroke="#FFFFFF" stroke-width="1.6" />
    </svg>

    <svg v-else-if="type === 'gmail'" viewBox="0 0 24 24" fill="none">
      <rect x="2" y="4" width="20" height="16" rx="3" fill="#FFFFFF" stroke="#E5E7EB" stroke-width="1" />
      <path d="M4.5 18V8.2L12 13.5L19.5 8.2V18" stroke="#EA4335" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" />
      <path d="M4.5 18V8.5" stroke="#4285F4" stroke-width="2.2" stroke-linecap="round" />
      <path d="M19.5 18V8.5" stroke="#34A853" stroke-width="2.2" stroke-linecap="round" />
      <path d="M19.5 8.2L12 13.5" stroke="#FBBC05" stroke-width="2.1" stroke-linecap="round" />
    </svg>

    <svg v-else-if="type === 'qq'" viewBox="0 0 24 24" fill="none">
      <rect x="2" y="2" width="20" height="20" rx="5" fill="#12B7F5" />
      <ellipse cx="12" cy="11.5" rx="5.2" ry="6" fill="#1F2329" />
      <ellipse cx="12" cy="13.5" rx="3.4" ry="3.8" fill="#FFFFFF" />
      <ellipse cx="12" cy="10.2" rx="2.4" ry="1.1" fill="#F59E0B" />
      <path d="M7.5 13.2C8.8 14.3 15.2 14.3 16.5 13.2" stroke="#EF4444" stroke-width="1.8" stroke-linecap="round" />
    </svg>

    <svg v-else viewBox="0 0 24 24" fill="none">
      <rect x="3" y="4" width="18" height="6.5" rx="2" fill="currentColor" fill-opacity="0.14" stroke="currentColor" stroke-width="1.6" />
      <rect x="3" y="13.5" width="18" height="6.5" rx="2" fill="currentColor" fill-opacity="0.14" stroke="currentColor" stroke-width="1.6" />
      <circle cx="7" cy="7.25" r="1" fill="currentColor" />
      <circle cx="7" cy="16.75" r="1" fill="currentColor" />
    </svg>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { getMailTypeLabel } from '@/utils/mailTypes'

const props = defineProps({
  type: {
    type: String,
    default: 'imap'
  },
  size: {
    type: Number,
    default: 18
  }
})

const label = computed(() => getMailTypeLabel(props.type))
</script>

<style scoped>
.fm-brand-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--fm-text-2);
  border-radius: var(--fm-radius-xs);
}

.fm-brand-icon svg {
  width: 100%;
  height: 100%;
  display: block;
}

:global(html.dark) .fm-brand-icon {
  box-shadow: 0 0 0 1px var(--fm-border-strong);
  padding: 1px;
}
</style>

<template>
  <button
    type="button"
    class="fm-copy-text"
    :class="{ 'fm-mono': mono, 'fm-copy-text--truncate': truncate }"
    :title="tooltipTitle"
    :aria-label="tooltipTitle"
    @click.stop="handleCopy"
  >
    <span class="fm-copy-text__value">{{ text }}</span>
    <span class="fm-copy-text__icon" :class="{ 'is-copied': justCopied }" aria-hidden="true">
      <el-icon :size="13">
        <Check v-if="justCopied" />
        <CopyDocument v-else />
      </el-icon>
    </span>
  </button>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { CopyDocument, Check } from '@element-plus/icons-vue'
import { useClipboard } from '@/composables/useClipboard'

const props = defineProps({
  text: { type: String, required: true },
  label: { type: String, default: '' },
  mono: { type: Boolean, default: true },
  truncate: { type: Boolean, default: false }
})

const emit = defineEmits(['copied'])

const { copy } = useClipboard()
const justCopied = ref(false)
let resetTimer = null

const tooltipTitle = computed(() => `点击复制：${props.text}`)

async function handleCopy() {
  const ok = await copy(props.text, props.label)
  if (!ok) return
  justCopied.value = true
  emit('copied', props.text)
  if (resetTimer) clearTimeout(resetTimer)
  resetTimer = setTimeout(() => {
    justCopied.value = false
  }, 1200)
}

onUnmounted(() => {
  if (resetTimer) clearTimeout(resetTimer)
})
</script>

<style scoped>
.fm-copy-text {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  padding: 2px 4px;
  margin: -2px -4px;
  border: none;
  border-radius: var(--fm-radius-xs);
  background: transparent;
  color: var(--fm-text);
  font-size: inherit;
  line-height: inherit;
  cursor: pointer;
  text-align: left;
  transition: background var(--fm-dur-fast) var(--fm-ease), color var(--fm-dur-fast) var(--fm-ease);
}

.fm-copy-text:hover {
  background: var(--fm-surface-hover);
}

.fm-copy-text__value {
  word-break: break-all;
}

.fm-copy-text--truncate .fm-copy-text__value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  word-break: normal;
}

.fm-copy-text__icon {
  display: inline-flex;
  align-items: center;
  color: var(--fm-text-3);
  opacity: 0;
  flex-shrink: 0;
  transition: opacity var(--fm-dur-fast) var(--fm-ease), color var(--fm-dur-fast) var(--fm-ease);
}

.fm-copy-text:hover .fm-copy-text__icon,
.fm-copy-text:focus-visible .fm-copy-text__icon,
.fm-copy-text__icon.is-copied {
  opacity: 1;
}

.fm-copy-text__icon.is-copied {
  color: var(--fm-success);
}
</style>

<template>
  <template v-if="codes.length > 0">
    <button
      v-if="mini"
      type="button"
      class="fm-vcode-mini fm-mono"
      :title="`点击复制验证码 ${codes[0].code}`"
      :aria-label="`复制验证码 ${codes[0].code}`"
      @click.stop="copyCode(codes[0].code)"
    >
      <el-icon :size="11"><Key /></el-icon>
      <span>{{ codes[0].code }}</span>
    </button>

    <div v-else class="fm-vcode-bar" aria-label="识别到的验证码">
      <el-tooltip
        v-for="(item, index) in codes"
        :key="item.code"
        :content="item.context || '点击复制验证码'"
        placement="top"
      >
        <button
          type="button"
          class="fm-vcode-chip"
          :class="{ 'is-primary': index === 0 }"
          :aria-label="`复制验证码 ${item.code}`"
          @click="copyCode(item.code)"
        >
          <el-icon :size="15" class="fm-vcode-chip__icon"><Key /></el-icon>
          <span class="fm-vcode-chip__code fm-mono">{{ item.code }}</span>
          <span v-if="index === 0" class="fm-vcode-chip__tag">复制</span>
        </button>
      </el-tooltip>
    </div>
  </template>
</template>

<script setup>
import { computed } from 'vue'
import { Key } from '@element-plus/icons-vue'
import { extractVerifyCodes } from '@/utils/verifyCode'
import { useClipboard } from '@/composables/useClipboard'

const props = defineProps({
  subject: { type: String, default: '' },
  html: { type: String, default: '' },
  text: { type: String, default: '' },
  mini: { type: Boolean, default: false }
})

const { copy } = useClipboard()

const codes = computed(() =>
  extractVerifyCodes({
    subject: props.subject,
    html: props.html,
    text: props.text
  })
)

function copyCode(code) {
  copy(code, `验证码 ${code}`)
}
</script>

<style scoped>
.fm-vcode-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--fm-space-2);
}

.fm-vcode-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 12px;
  border-radius: var(--fm-radius-md);
  border: 1px solid var(--fm-accent-border);
  background: var(--fm-accent-soft);
  color: var(--fm-accent);
  cursor: pointer;
  transition: transform var(--fm-dur-fast) var(--fm-ease), border-color var(--fm-dur-fast) var(--fm-ease);
}

.fm-vcode-chip:hover {
  border-color: var(--fm-accent);
  transform: translateY(-1px);
}

.fm-vcode-chip__icon {
  flex-shrink: 0;
}

.fm-vcode-chip__code {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.12em;
  line-height: 1;
}

.fm-vcode-chip__tag {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: var(--fm-radius-pill);
  background: var(--fm-accent);
  color: var(--fm-text-inverse);
}

.fm-vcode-mini {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 20px;
  padding: 0 6px;
  border-radius: var(--fm-radius-pill);
  border: 1px solid var(--fm-accent-border);
  background: var(--fm-accent-soft);
  color: var(--fm-accent);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  cursor: pointer;
  flex-shrink: 0;
}

.fm-vcode-mini:hover {
  border-color: var(--fm-accent);
}
</style>

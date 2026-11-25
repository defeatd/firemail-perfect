<template>
  <el-dialog
    :model-value="modelValue"
    title="查看凭据"
    :width="isMobile ? '94vw' : '480px'"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div v-loading="loading" class="fm-creds">
      <div v-if="email" class="fm-creds__email fm-mono">{{ email.email }}</div>

      <div class="fm-creds__list">
        <div v-for="field in fields" :key="field.key" class="fm-creds__row">
          <div class="fm-creds__label">{{ field.label }}</div>
          <div class="fm-creds__value-wrap">
            <span class="fm-creds__val fm-mono">
              <template v-if="!field.value">—</template>
              <template v-else-if="revealed[field.key]">{{ field.value }}</template>
              <template v-else>••••••••••••</template>
            </span>
            <div v-if="field.value" class="fm-creds__actions">
              <el-tooltip :content="revealed[field.key] ? '隐藏' : '显示'" placement="top">
                <button
                  type="button"
                  class="fm-creds__btn"
                  :aria-label="`${revealed[field.key] ? '隐藏' : '显示'}${field.label}`"
                  @click="revealed[field.key] = !revealed[field.key]"
                >
                  <el-icon :size="14">
                    <Hide v-if="revealed[field.key]" />
                    <View v-else />
                  </el-icon>
                </button>
              </el-tooltip>
              <el-tooltip content="复制" placement="top">
                <button
                  type="button"
                  class="fm-creds__btn"
                  :aria-label="`复制${field.label}`"
                  @click="copy(field.value, field.label)"
                >
                  <el-icon :size="14"><CopyDocument /></el-icon>
                </button>
              </el-tooltip>
            </div>
          </div>
        </div>
      </div>

      <p class="fm-creds__note">凭据仅在本次会话内存中保留，关闭窗口后自动清除。</p>
    </div>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { View, Hide, CopyDocument } from '@element-plus/icons-vue'
import { useCredentials } from '@/composables/useCredentials'
import { useClipboard } from '@/composables/useClipboard'
import { useBreakpoint } from '@/composables/useBreakpoint'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  email: { type: Object, default: null }
})

defineEmits(['update:modelValue'])

const { ensureCredentials, clear } = useCredentials()
const { copy } = useClipboard()
const { isMobile } = useBreakpoint()

const loading = ref(false)
const data = reactive({
  password: '',
  client_id: '',
  refresh_token: ''
})
const revealed = reactive({
  password: false,
  client_id: false,
  refresh_token: false
})

const fields = computed(() => {
  const list = [{ key: 'password', label: '密码', value: data.password }]
  if (props.email?.mail_type === 'outlook') {
    list.push(
      { key: 'client_id', label: 'Client ID', value: data.client_id },
      { key: 'refresh_token', label: 'Refresh Token', value: data.refresh_token }
    )
  }
  return list
})

function resetLocal() {
  data.password = ''
  data.client_id = ''
  data.refresh_token = ''
  revealed.password = false
  revealed.client_id = false
  revealed.refresh_token = false
  clear()
}

watch(
  () => [props.modelValue, props.email?.id],
  async ([open]) => {
    resetLocal()
    if (!open || !props.email) return
    loading.value = true
    try {
      const creds = await ensureCredentials(props.email, { force: true })
      data.password = creds?.password && creds.password !== '******' ? creds.password : ''
      data.client_id = creds?.client_id || ''
      data.refresh_token =
        creds?.refresh_token && creds.refresh_token !== '******' ? creds.refresh_token : ''
    } catch (_err) {
      ElMessage.error('获取邮箱凭据失败')
    } finally {
      loading.value = false
    }
  }
)
</script>

<style scoped>
.fm-creds {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-4);
}

.fm-creds__email {
  font-size: var(--fm-fs-sm);
  font-weight: 500;
  color: var(--fm-text);
  padding: 8px 12px;
  border-radius: var(--fm-radius-md);
  background: var(--fm-bg-subtle);
  border: 1px solid var(--fm-border);
  word-break: break-all;
}

.fm-creds__list {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-3);
}

.fm-creds__row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.fm-creds__label {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
}

.fm-creds__value-wrap {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--fm-space-2);
  padding: 8px 10px;
  border-radius: var(--fm-radius-md);
  background: var(--fm-surface-2);
  border: 1px solid var(--fm-border);
}

.fm-creds__val {
  flex: 1;
  min-width: 0;
  font-size: var(--fm-fs-xs);
  color: var(--fm-text);
  word-break: break-all;
  line-height: 1.5;
}

.fm-creds__actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.fm-creds__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: var(--fm-radius-xs);
  background: transparent;
  color: var(--fm-text-2);
  cursor: pointer;
}

.fm-creds__btn:hover {
  background: var(--fm-surface-hover);
  color: var(--fm-text);
}

.fm-creds__note {
  margin: 0;
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
}
</style>

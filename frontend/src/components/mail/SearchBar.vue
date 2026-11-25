<template>
  <form class="fm-search-bar" @submit.prevent="handleSubmit">
    <div class="fm-search-bar__row">
      <el-input
        ref="inputRef"
        v-model="queryText"
        size="large"
        clearable
        placeholder="输入关键词搜索邮件…（按 / 聚焦）"
        class="fm-search-bar__input"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <el-button
        type="primary"
        size="large"
        native-type="submit"
        :loading="loading"
        class="fm-search-bar__submit"
      >
        搜索
      </el-button>
    </div>

    <div class="fm-search-bar__scopes">
      <span class="fm-search-bar__scope-label">搜索范围</span>
      <el-checkbox-group v-model="selectedScopes">
        <el-checkbox value="subject">标题</el-checkbox>
        <el-checkbox value="sender">发件人</el-checkbox>
        <el-checkbox value="recipient">收件人</el-checkbox>
        <el-checkbox value="content">正文</el-checkbox>
      </el-checkbox-group>
    </div>
  </form>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'

const DEFAULT_SCOPES = ['subject', 'sender', 'content']

const props = defineProps({
  initialQuery: { type: String, default: '' },
  initialIn: { type: Array, default: () => ['subject', 'sender', 'content'] },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['search'])

const inputRef = ref(null)
const queryText = ref(props.initialQuery || '')
const selectedScopes = ref(
  Array.isArray(props.initialIn) && props.initialIn.length > 0
    ? [...props.initialIn]
    : [...DEFAULT_SCOPES]
)

watch(
  () => props.initialQuery,
  (val) => {
    queryText.value = val || ''
  }
)

watch(
  () => props.initialIn,
  (val) => {
    if (Array.isArray(val) && val.length > 0) {
      selectedScopes.value = [...val]
    }
  }
)

function handleSubmit() {
  const q = queryText.value.trim()
  if (!q) {
    ElMessage.warning('请输入搜索关键词')
    return
  }
  if (selectedScopes.value.length === 0) {
    ElMessage.warning('请至少选择一个搜索范围')
    return
  }
  emit('search', { q, in: [...selectedScopes.value] })
}

function handleKeydown(event) {
  if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return
  const tag = event.target?.tagName?.toLowerCase()
  if (tag === 'input' || tag === 'textarea' || event.target?.isContentEditable) return
  event.preventDefault()
  inputRef.value?.focus()
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.fm-search-bar {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-3);
  padding: var(--fm-space-4);
  background: var(--fm-surface);
  border: 1px solid var(--fm-border);
  border-radius: var(--fm-radius-lg);
  box-shadow: var(--fm-shadow-xs);
  margin-bottom: var(--fm-space-4);
}

.fm-search-bar__row {
  display: flex;
  align-items: center;
  gap: var(--fm-space-2);
}

.fm-search-bar__input {
  flex: 1;
}

.fm-search-bar__input :deep(.el-input__wrapper) {
  min-height: 44px;
}

.fm-search-bar__submit {
  height: 44px;
  padding: 0 22px;
}

.fm-search-bar__scopes {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--fm-space-3);
}

.fm-search-bar__scope-label {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
}
</style>

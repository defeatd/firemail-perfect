<template>
  <div class="fm-email-filters">
    <div class="fm-email-filters__search">
      <el-input
        ref="inputRef"
        :model-value="query"
        placeholder="搜索邮箱地址…（按 / 聚焦）"
        clearable
        @update:model-value="$emit('update:query', $event)"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
    </div>

    <SegmentedFilter
      :model-value="type"
      :options="typeOptions"
      @update:model-value="$emit('update:type', $event)"
    />

    <el-select
      :model-value="auth"
      placeholder="授权状态"
      class="fm-email-filters__auth"
      @update:model-value="$emit('update:auth', $event)"
    >
      <el-option
        v-for="opt in AUTH_OPTIONS"
        :key="opt.value"
        :value="opt.value"
        :label="opt.label"
      />
    </el-select>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import SegmentedFilter from '@/components/common/SegmentedFilter.vue'

const AUTH_OPTIONS = [
  { value: 'all', label: '全部状态' },
  { value: 'attention', label: '需要关注' },
  { value: 'ok', label: '正常' },
  { value: 'pending', label: '首验中' },
  { value: 'expiring_15d', label: '15 天内到期' },
  { value: 'expiring_7d', label: '7 天内到期' },
  { value: 'need_reauth', label: '需重授' },
  { value: 'banned', label: '已封禁' },
  { value: 'error', label: '异常' },
  { value: 'unverified', label: '未验证' }
]

const props = defineProps({
  query: { type: String, default: '' },
  type: { type: String, default: 'all' },
  auth: { type: String, default: 'all' },
  typeCounts: {
    type: Object,
    default: () => ({ all: 0, outlook: 0, imap: 0, gmail: 0, qq: 0 })
  }
})

defineEmits(['update:query', 'update:type', 'update:auth'])

const inputRef = ref(null)

const typeOptions = computed(() => [
  { value: 'all', label: '全部', count: props.typeCounts.all ?? 0 },
  { value: 'outlook', label: 'Outlook', count: props.typeCounts.outlook ?? 0 },
  { value: 'imap', label: 'IMAP', count: props.typeCounts.imap ?? 0 },
  { value: 'gmail', label: 'Gmail', count: props.typeCounts.gmail ?? 0 },
  { value: 'qq', label: 'QQ', count: props.typeCounts.qq ?? 0 }
])

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
.fm-email-filters {
  display: flex;
  align-items: center;
  gap: var(--fm-space-3);
  flex-wrap: wrap;
  margin-bottom: var(--fm-space-4);
}

.fm-email-filters__search {
  flex: 1;
  min-width: 220px;
  max-width: 320px;
}

.fm-email-filters__auth {
  width: 156px;
}

@media (max-width: 767.98px) {
  .fm-email-filters__search {
    max-width: none;
    width: 100%;
    flex-basis: 100%;
  }

  .fm-email-filters__auth {
    width: 100%;
  }
}
</style>

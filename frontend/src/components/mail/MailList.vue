<template>
  <div class="fm-mail-list">
    <div v-if="!hideSearch" class="fm-mail-list__header">
      <el-input
        v-model="filterText"
        placeholder="搜索主题、发件人或内容"
        size="small"
        clearable
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <span class="fm-mail-list__count fm-mono">{{ filteredRecords.length }} 封</span>
    </div>

    <div v-else class="fm-mail-list__summary">
      <span>找到 <strong class="fm-mono">{{ filteredRecords.length }}</strong> 条结果</span>
    </div>

    <div
      v-loading="loading"
      class="fm-mail-list__scroll"
      role="listbox"
      tabindex="0"
      aria-label="邮件列表"
      @keydown="handleKeydown"
    >
      <template v-if="filteredRecords.length > 0">
        <MailListItem
          v-for="item in filteredRecords"
          :key="item.id"
          :mail="item"
          :selected="Number(selectedId) === Number(item.id)"
          :highlight-query="highlightQuery || filterText"
          :show-email-badge="showEmailBadge"
          @select="$emit('select', $event)"
          @click-sender="$emit('click-sender', $event)"
          @click-email="$emit('click-email', $event)"
        />
      </template>

      <EmptyState
        v-else-if="!loading"
        :icon="Message"
        :title="emptyTitle"
        :description="emptyDescription"
      >
        <template v-if="showEmptyAction && !filterText" #actions>
          <el-button type="primary" size="small" @click="$emit('check-mail')">
            收取邮件
          </el-button>
        </template>
      </EmptyState>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Search, Message } from '@element-plus/icons-vue'
import EmptyState from '@/components/common/EmptyState.vue'
import MailListItem from './MailListItem.vue'

const props = defineProps({
  records: { type: Array, default: () => [] },
  selectedId: { type: [Number, String], default: null },
  loading: { type: Boolean, default: false },
  hideSearch: { type: Boolean, default: false },
  highlightQuery: { type: String, default: '' },
  showEmailBadge: { type: Boolean, default: false },
  emptyTitle: { type: String, default: '暂无邮件记录' },
  emptyDescription: { type: String, default: '可点击上方「收取邮件」拉取最新邮件。' },
  showEmptyAction: { type: Boolean, default: true }
})

const emit = defineEmits(['select', 'check-mail', 'click-sender', 'click-email'])

const filterText = ref('')

const filteredRecords = computed(() => {
  const q = filterText.value.trim().toLowerCase()
  if (!q) return props.records
  return props.records.filter((item) => {
    const subject = String(item.subject || '').toLowerCase()
    const sender = String(item.sender || '').toLowerCase()
    const content =
      typeof item.content === 'string'
        ? item.content.toLowerCase()
        : JSON.stringify(item.content || '').toLowerCase()
    return subject.includes(q) || sender.includes(q) || content.includes(q)
  })
})

function handleKeydown(event) {
  const list = filteredRecords.value
  if (list.length === 0) return
  const currentIdx = list.findIndex((m) => Number(m.id) === Number(props.selectedId))

  if (event.key === 'ArrowDown') {
    event.preventDefault()
    const nextIdx = currentIdx < list.length - 1 ? currentIdx + 1 : 0
    emit('select', list[nextIdx])
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    const nextIdx = currentIdx > 0 ? currentIdx - 1 : list.length - 1
    emit('select', list[nextIdx])
  } else if (event.key === 'Enter' && currentIdx >= 0) {
    event.preventDefault()
    emit('select', list[currentIdx])
  }
}
</script>

<style scoped>
.fm-mail-list {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--fm-surface);
}

.fm-mail-list__header {
  display: flex;
  align-items: center;
  gap: var(--fm-space-2);
  padding: var(--fm-space-3);
  border-bottom: 1px solid var(--fm-border);
  flex-shrink: 0;
}

.fm-mail-list__count {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
  white-space: nowrap;
}

.fm-mail-list__summary {
  padding: 10px 14px;
  border-bottom: 1px solid var(--fm-border);
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-2);
  flex-shrink: 0;
}

.fm-mail-list__scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  outline: none;
}

.fm-mail-list__scroll:focus-visible {
  box-shadow: inset 0 0 0 2px var(--fm-accent-border);
}
</style>

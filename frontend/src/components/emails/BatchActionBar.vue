<template>
  <div v-if="selectedCount > 0" class="fm-batch-bar">
    <div class="fm-batch-bar__left">
      <span class="fm-batch-bar__count">
        已选 <strong class="fm-mono">{{ selectedCount }}</strong> 项
      </span>
    </div>

    <div class="fm-batch-bar__actions">
      <el-button size="small" :loading="checking" @click="$emit('batch-check')">
        批量收信
      </el-button>

      <el-tooltip
        content="仅支持 Outlook"
        :disabled="outlookSelectedCount > 0"
        placement="top"
      >
        <span>
          <el-button
            size="small"
            :loading="refreshing"
            :disabled="outlookSelectedCount === 0"
            @click="$emit('batch-refresh')"
          >
            批量保活
          </el-button>
        </span>
      </el-tooltip>

      <el-button size="small" :loading="exporting" @click="$emit('export')">
        导出 TXT
      </el-button>

      <el-button
        size="small"
        type="danger"
        plain
        :loading="deleting"
        @click="$emit('batch-delete')"
      >
        批量删除
      </el-button>

      <el-button size="small" text @click="$emit('clear')">取消选择</el-button>
    </div>
  </div>

  <div v-else class="fm-batch-idle">
    <span class="fm-batch-idle__hint">
      当前展示 <strong class="fm-mono">{{ filteredCount }}</strong> 个邮箱
    </span>
    <el-button
      size="small"
      :disabled="filteredCount === 0"
      :loading="exporting"
      @click="$emit('export')"
    >
      <el-icon><Download /></el-icon>
      <span>导出 TXT</span>
    </el-button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Download } from '@element-plus/icons-vue'

const props = defineProps({
  selectedRows: { type: Array, default: () => [] },
  filteredCount: { type: Number, default: 0 },
  checking: { type: Boolean, default: false },
  refreshing: { type: Boolean, default: false },
  deleting: { type: Boolean, default: false },
  exporting: { type: Boolean, default: false }
})

defineEmits(['batch-check', 'batch-refresh', 'export', 'batch-delete', 'clear'])

const selectedCount = computed(() => props.selectedRows.length)
const outlookSelectedCount = computed(
  () => props.selectedRows.filter((row) => row.mail_type === 'outlook').length
)
</script>

<style scoped>
.fm-batch-bar {
  position: sticky;
  top: 8px;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--fm-space-3);
  padding: 10px var(--fm-space-4);
  margin-bottom: var(--fm-space-3);
  background: var(--fm-surface-active);
  border: 1px solid var(--fm-border-strong);
  border-radius: var(--fm-radius-md);
  box-shadow: var(--fm-shadow-sm);
}

.fm-batch-bar__count {
  font-size: var(--fm-fs-sm);
  color: var(--fm-text);
}

.fm-batch-bar__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--fm-space-2);
}

.fm-batch-idle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--fm-space-2);
  margin-bottom: var(--fm-space-3);
}

.fm-batch-idle__hint {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
}
</style>

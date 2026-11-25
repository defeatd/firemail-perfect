<template>
  <div class="fm-row-actions" :class="{ 'fm-row-actions--compact': compact }">
    <el-tooltip :content="isProcessing ? '检查中…' : '检查邮件'" placement="top">
      <button
        type="button"
        class="fm-icon-btn"
        :disabled="isProcessing"
        :aria-label="isProcessing ? '检查中' : '检查邮件'"
        @click="$emit('check', row)"
      >
        <el-icon :size="15" :class="{ 'is-loading': isProcessing }">
          <Loading v-if="isProcessing" />
          <Download v-else />
        </el-icon>
      </button>
    </el-tooltip>

    <el-tooltip content="查看邮件" placement="top">
      <button
        type="button"
        class="fm-icon-btn"
        aria-label="查看邮件"
        @click="$emit('view', row)"
      >
        <el-icon :size="15"><Message /></el-icon>
      </button>
    </el-tooltip>

    <el-tooltip v-if="row.mail_type === 'outlook'" content="立即保活" placement="top">
      <button
        type="button"
        class="fm-icon-btn"
        :disabled="refreshing"
        aria-label="立即保活"
        @click="$emit('keepalive', row)"
      >
        <el-icon :size="15" :class="{ 'is-loading': refreshing }">
          <Loading v-if="refreshing" />
          <RefreshRight v-else />
        </el-icon>
      </button>
    </el-tooltip>

    <el-dropdown trigger="click" placement="bottom-end" @command="handleCommand">
      <button
        type="button"
        class="fm-icon-btn"
        aria-label="更多操作"
        title="更多操作"
      >
        <el-icon :size="15"><MoreFilled /></el-icon>
      </button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="edit">
            <el-icon><Edit /></el-icon>
            <span>编辑</span>
          </el-dropdown-item>
          <el-dropdown-item v-if="row.mail_type === 'outlook'" command="reauth">
            <el-icon><Key /></el-icon>
            <span>重新授权</span>
          </el-dropdown-item>
          <el-dropdown-item command="credentials">
            <el-icon><View /></el-icon>
            <span>查看凭据</span>
          </el-dropdown-item>
          <el-dropdown-item divided command="delete" class="fm-dropdown-danger">
            <el-icon><Delete /></el-icon>
            <span>删除</span>
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  Download,
  Message,
  RefreshRight,
  MoreFilled,
  Edit,
  Key,
  View,
  Delete,
  Loading
} from '@element-plus/icons-vue'

const props = defineProps({
  row: { type: Object, required: true },
  processing: { type: Object, default: null },
  refreshing: { type: Boolean, default: false },
  compact: { type: Boolean, default: false }
})

const emit = defineEmits(['check', 'view', 'keepalive', 'edit', 'reauth', 'credentials', 'delete'])

const isProcessing = computed(() => Boolean(props.processing))

function handleCommand(cmd) {
  emit(cmd, props.row)
}
</script>

<style scoped>
.fm-row-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.fm-row-actions--compact {
  width: 100%;
  justify-content: flex-end;
}

.fm-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid transparent;
  border-radius: var(--fm-radius-sm);
  background: transparent;
  color: var(--fm-text-2);
  cursor: pointer;
  transition: background var(--fm-dur-fast) var(--fm-ease), color var(--fm-dur-fast) var(--fm-ease);
}

.fm-icon-btn:hover:not(:disabled) {
  background: var(--fm-surface-hover);
  color: var(--fm-text);
}

.fm-icon-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

:global(.fm-dropdown-danger) {
  color: var(--fm-danger);
}
</style>

<template>
  <el-tooltip :content="tooltipText" :placement="collapsed ? 'right' : 'top'">
    <button
      type="button"
      class="fm-ws-dot"
      :class="[`fm-ws-dot--${ws.status}`, { 'fm-ws-dot--icon-only': compact || collapsed }]"
      :aria-label="tooltipText"
      @click="handleReconnect"
    >
      <span class="fm-ws-dot__indicator" aria-hidden="true" />
      <span v-if="!compact && !collapsed" class="fm-ws-dot__label">{{ statusLabel }}</span>
    </button>
  </el-tooltip>
</template>

<script setup>
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useWsStore } from '@/stores/ws'

defineProps({
  compact: { type: Boolean, default: false },
  collapsed: { type: Boolean, default: false }
})

const ws = useWsStore()

const statusLabel = computed(() => {
  if (ws.status === 'connected') return '实时已连接'
  if (ws.status === 'connecting') return '连接中…'
  return '未连接'
})

const tooltipText = computed(() => `${statusLabel.value}（点击重新连接 WebSocket）`)

function handleReconnect() {
  ws.reconnect()
  ElMessage.info('正在重新连接实时通道…')
}
</script>

<style scoped>
.fm-ws-dot {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 30px;
  padding: 0 10px;
  border: 1px solid transparent;
  border-radius: var(--fm-radius-sm);
  background: transparent;
  color: var(--fm-text-2);
  font-size: var(--fm-fs-xs);
  cursor: pointer;
  width: 100%;
  transition: background var(--fm-dur-fast) var(--fm-ease), color var(--fm-dur-fast) var(--fm-ease);
}

.fm-ws-dot:hover {
  background: var(--fm-surface-hover);
  color: var(--fm-text);
}

.fm-ws-dot--icon-only {
  width: 32px;
  height: 32px;
  padding: 0;
  justify-content: center;
}

.fm-ws-dot__indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--fm-danger);
}

.fm-ws-dot--connected .fm-ws-dot__indicator {
  background: var(--fm-success);
  animation: fm-ws-breathe 2s ease-in-out infinite;
}

.fm-ws-dot--connecting .fm-ws-dot__indicator {
  background: var(--fm-info);
}

.fm-ws-dot--disconnected .fm-ws-dot__indicator {
  background: var(--fm-danger);
}

.fm-ws-dot__label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@keyframes fm-ws-breathe {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.45;
    transform: scale(0.88);
  }
}
</style>

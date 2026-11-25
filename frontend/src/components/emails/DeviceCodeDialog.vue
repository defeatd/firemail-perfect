<template>
  <el-dialog
    :model-value="modelValue"
    :title="dialogTitle"
    :width="isMobile ? '94vw' : '520px'"
    :close-on-click-modal="false"
    destroy-on-close
    @update:model-value="handleVisibleChange"
  >
    <div class="fm-dc">
      <div v-if="request?.email" class="fm-dc__target">
        <span class="fm-dc__target-label">目标邮箱</span>
        <span class="fm-mono fm-dc__target-email">{{ request.email }}</span>
      </div>

      <ol v-if="state.userCode" class="fm-dc__steps">
        <li class="fm-dc__step">
          <span class="fm-dc__step-num fm-mono">1</span>
          <div class="fm-dc__step-body">
            <div class="fm-dc__step-title">打开微软验证页面</div>
            <a
              :href="state.verificationUriComplete || state.verificationUri"
              target="_blank"
              rel="noopener noreferrer"
              class="fm-dc__link"
            >
              <el-icon><Link /></el-icon>
              <span>{{ state.verificationUri || 'https://microsoft.com/devicelogin' }}</span>
              <span>↗</span>
            </a>
          </div>
        </li>

        <li class="fm-dc__step">
          <span class="fm-dc__step-num fm-mono">2</span>
          <div class="fm-dc__step-body">
            <div class="fm-dc__step-title">输入一次性设备代码</div>
            <div class="fm-dc__code-row">
              <button
                type="button"
                class="fm-dc__code fm-mono"
                title="点击复制设备代码"
                @click="copyCode"
              >
                {{ state.userCode }}
              </button>
              <el-button size="small" @click="copyCode">复制</el-button>
            </div>
          </div>
        </li>

        <li class="fm-dc__step">
          <span class="fm-dc__step-num fm-mono">3</span>
          <div class="fm-dc__step-body">
            <div class="fm-dc__step-title">使用目标 Outlook 账号完成登录并同意授权</div>
          </div>
        </li>
      </ol>

      <div class="fm-dc__status" :class="`is-${state.status}`">
        <template v-if="state.status === 'pending'">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>等待登录中… 剩余 <strong class="fm-mono">{{ formattedCountdown }}</strong></span>
        </template>
        <template v-else-if="state.status === 'success'">
          <span>✅ 授权成功，Token 已保存</span>
        </template>
        <template v-else-if="state.status === 'expired'">
          <span>⏰ 代码已过期，请关闭后重新发起</span>
        </template>
        <template v-else-if="state.status === 'denied'">
          <span>❌ 用户拒绝了授权</span>
        </template>
        <template v-else-if="state.status === 'error'">
          <span>❌ {{ state.error || '授权失败' }}</span>
        </template>
        <template v-else>
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>准备中…</span>
        </template>
      </div>

      <p v-if="state.message" class="fm-dc__message">{{ state.message }}</p>
    </div>

    <template #footer>
      <div class="fm-dc__footer">
        <el-button
          v-if="canRestart"
          :loading="state.loading"
          @click="restart"
        >
          重新发起
        </el-button>
        <el-button
          :type="state.status === 'success' ? 'primary' : 'default'"
          @click="handleClose"
        >
          {{ state.status === 'success' ? '完成' : '关闭' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, watch, onUnmounted } from 'vue'
import { ElNotification } from 'element-plus'
import { Link, Loading } from '@element-plus/icons-vue'
import { useDeviceCodeFlow } from '@/composables/useDeviceCodeFlow'
import { useClipboard } from '@/composables/useClipboard'
import { useBreakpoint } from '@/composables/useBreakpoint'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  request: { type: Object, default: null }
})

const emit = defineEmits(['update:modelValue', 'success'])

const { state, start, restart, stop } = useDeviceCodeFlow()
const { copy } = useClipboard()
const { isMobile } = useBreakpoint()

let successEmitTimer = null
let hasEmittedSuccess = false

const dialogTitle = computed(() =>
  props.request?.mode === 'add' ? 'Device Code 添加 Outlook' : 'Device Code 重新授权'
)

const canRestart = computed(() => ['expired', 'denied', 'error'].includes(state.status))

const formattedCountdown = computed(() => {
  const sec = Math.max(0, Number(state.expiresIn) || 0)
  const mm = String(Math.floor(sec / 60)).padStart(2, '0')
  const ss = String(sec % 60).padStart(2, '0')
  return `${mm}:${ss}`
})

function clearSuccessTimer() {
  if (successEmitTimer) {
    clearTimeout(successEmitTimer)
    successEmitTimer = null
  }
}

watch(
  () => [props.modelValue, props.request],
  ([open, req]) => {
    clearSuccessTimer()
    hasEmittedSuccess = false
    if (open && req) {
      start(req)
    } else if (!open) {
      stop()
    }
  },
  { immediate: true }
)

watch(
  () => state.status,
  (next) => {
    if (next === 'success') {
      ElNotification({
        title: '重新授权成功',
        message: `${props.request?.email || 'Outlook 邮箱'} 授权已完成，Token 已写入`,
        type: 'success',
        duration: 5000
      })
      clearSuccessTimer()
      successEmitTimer = setTimeout(() => {
        if (!hasEmittedSuccess) {
          hasEmittedSuccess = true
          emit('success')
        }
      }, 5000)
    }
  }
)

onUnmounted(() => {
  clearSuccessTimer()
  stop()
})

function copyCode() {
  if (state.userCode) {
    copy(state.userCode, '设备代码')
  }
}

function handleVisibleChange(val) {
  if (!val) {
    handleClose()
  } else {
    emit('update:modelValue', true)
  }
}

function handleClose() {
  if (state.status === 'success' && !hasEmittedSuccess) {
    clearSuccessTimer()
    hasEmittedSuccess = true
    emit('success')
  }
  stop()
  emit('update:modelValue', false)
}
</script>

<style scoped>
.fm-dc {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-4);
}

.fm-dc__target {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--fm-space-2);
  padding: 10px 12px;
  border-radius: var(--fm-radius-md);
  background: var(--fm-bg-subtle);
  border: 1px solid var(--fm-border);
}

.fm-dc__target-label {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
}

.fm-dc__target-email {
  font-size: var(--fm-fs-sm);
  font-weight: 500;
  color: var(--fm-text);
  word-break: break-all;
}

.fm-dc__steps {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-4);
}

.fm-dc__step {
  display: flex;
  align-items: flex-start;
  gap: var(--fm-space-3);
}

.fm-dc__step-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--fm-primary-soft);
  color: var(--fm-text);
  font-size: var(--fm-fs-xs);
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.fm-dc__step-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fm-dc__step-title {
  font-size: var(--fm-fs-sm);
  font-weight: 500;
  color: var(--fm-text);
}

.fm-dc__link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border-radius: var(--fm-radius-md);
  background: var(--fm-surface-2);
  border: 1px solid var(--fm-border-strong);
  color: var(--fm-accent);
  font-size: var(--fm-fs-sm);
  text-decoration: none;
  word-break: break-all;
  width: fit-content;
  max-width: 100%;
}

.fm-dc__link:hover {
  border-color: var(--fm-accent);
}

.fm-dc__code-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--fm-space-3);
}

.fm-dc__code {
  padding: 8px 16px;
  border-radius: var(--fm-radius-md);
  background: var(--fm-accent-soft);
  border: 1px solid var(--fm-accent-border);
  color: var(--fm-accent);
  font-size: 28px;
  font-weight: 600;
  letter-spacing: 0.2em;
  cursor: pointer;
  max-width: 100%;
  overflow-x: auto;
}

.fm-dc__status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: var(--fm-radius-md);
  font-size: var(--fm-fs-sm);
  background: var(--fm-bg-subtle);
  color: var(--fm-text-2);
}

.fm-dc__status.is-pending {
  background: var(--fm-info-soft);
  color: var(--fm-info);
}

.fm-dc__status.is-success {
  background: var(--fm-success-soft);
  color: var(--fm-success);
}

.fm-dc__status.is-expired {
  background: var(--fm-warning-soft);
  color: var(--fm-warning);
}

.fm-dc__status.is-denied,
.fm-dc__status.is-error {
  background: var(--fm-danger-soft);
  color: var(--fm-danger);
}

.fm-dc__message {
  margin: 0;
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
  line-height: var(--fm-lh-base);
}

.fm-dc__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--fm-space-2);
}
</style>

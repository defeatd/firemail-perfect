<template>
  <el-drawer
    v-model="visible"
    title="调试工具"
    direction="rtl"
    :size="drawerSize"
    destroy-on-close
  >
    <div class="fm-debug">
      <section class="fm-debug__section">
        <h4 class="fm-debug__title">连接状态</h4>
        <div class="fm-debug__pills">
          <StatusPill :tone="ws.connected ? 'success' : 'danger'">
            WS {{ ws.connected ? '已连接' : '未连接' }}
          </StatusPill>
          <StatusPill :tone="ws.authenticated ? 'success' : 'warning'">
            {{ ws.authenticated ? '已认证' : '未认证' }}
          </StatusPill>
        </div>
        <KeyValueList :items="endpointItems" dense />
        <el-button
          size="small"
          :loading="reconnecting"
          @click="handleReconnect"
        >
          {{ reconnecting ? '重连中...' : '重新连接' }}
        </el-button>
      </section>

      <section class="fm-debug__section">
        <h4 class="fm-debug__title">Cookie 状态</h4>
        <div class="fm-debug__meta">
          <span>当前 Cookie 数量：</span>
          <strong class="fm-mono">{{ cookieList.length }}</strong>
        </div>
        <div class="fm-debug__actions">
          <el-button size="small" @click="fixCookies">修复 Cookie</el-button>
          <el-button size="small" type="danger" plain @click="clearAllCookies">
            清除所有 Cookie
          </el-button>
          <el-button size="small" text @click="showCookieDetails = !showCookieDetails">
            {{ showCookieDetails ? '收起详情' : '查看详情' }}
          </el-button>
        </div>
        <ul v-if="showCookieDetails" class="fm-debug__cookie-list fm-mono">
          <li v-if="cookieList.length === 0">暂无 Cookie</li>
          <li v-for="c in cookieList" :key="c.name">
            {{ c.name }} = {{ c.masked }}
          </li>
        </ul>
      </section>

      <section class="fm-debug__section">
        <h4 class="fm-debug__title">调试选项</h4>
        <el-checkbox v-model="debugMode" @change="toggleDebugMode">
          启用调试模式（debug_mode）
        </el-checkbox>
      </section>

      <section class="fm-debug__section">
        <h4 class="fm-debug__title">网络测试</h4>
        <el-button size="small" :loading="testingApi" @click="testApiConnection">
          测试 API 连接
        </el-button>
        <p v-if="apiTestResult" class="fm-debug__result" :class="apiTestOk ? 'is-ok' : 'is-err'">
          {{ apiTestResult }}
        </p>
      </section>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/services/api'
import websocket from '@/services/websocket'
import { useUiStore } from '@/stores/ui'
import { useWsStore } from '@/stores/ws'
import { useBreakpoint } from '@/composables/useBreakpoint'
import StatusPill from '@/components/common/StatusPill.vue'
import KeyValueList from '@/components/common/KeyValueList.vue'

const ui = useUiStore()
const ws = useWsStore()
const { isMobile } = useBreakpoint()

const reconnecting = ref(false)
const testingApi = ref(false)
const apiTestResult = ref('')
const apiTestOk = ref(false)
const showCookieDetails = ref(false)
const cookieList = ref([])
const debugMode = ref(
  typeof localStorage !== 'undefined' && localStorage.getItem('debug_mode') === 'true'
)

let unsubscribers = []

const visible = computed({
  get: () => ui.debugDrawerOpen,
  set: (val) => ui.setDebugDrawerOpen(val)
})

const drawerSize = computed(() => (isMobile.value ? '94vw' : '400px'))

const endpointItems = computed(() => {
  const apiUrl =
    (typeof window !== 'undefined' && window.API_URL) || `${window.location.origin}/api`
  const wsUrl = websocket.getWebSocketUrl()
  return [
    { label: 'API URL', value: apiUrl, mono: true },
    { label: 'WS URL', value: wsUrl, mono: true }
  ]
})

function refreshCookies() {
  if (typeof document === 'undefined' || !document.cookie) {
    cookieList.value = []
    return
  }
  cookieList.value = document.cookie
    .split(';')
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const idx = entry.indexOf('=')
      const name = idx >= 0 ? entry.slice(0, idx) : entry
      const rawVal = idx >= 0 ? entry.slice(idx + 1) : ''
      const isSensitive = /token|auth|session|pass|key/i.test(name)
      const masked = isSensitive ? '••••••' : rawVal.slice(0, 32)
      return { name, masked }
    })
}

function cleanupListeners() {
  unsubscribers.forEach((fn) => {
    try {
      fn()
    } catch (_e) {
      // ignore
    }
  })
  unsubscribers = []
}

function bindListeners() {
  cleanupListeners()
  unsubscribers.push(
    websocket.onConnect(() => {
      reconnecting.value = false
    }),
    websocket.onDisconnect(() => {
      reconnecting.value = false
    })
  )
}

watch(visible, (open) => {
  if (open) {
    refreshCookies()
    bindListeners()
  } else {
    cleanupListeners()
  }
})

onUnmounted(() => {
  cleanupListeners()
})

function handleReconnect() {
  reconnecting.value = true
  ws.reconnect()
  setTimeout(() => {
    reconnecting.value = false
  }, 5000)
}

function fixCookies() {
  refreshCookies()
  const invalid = cookieList.value.filter((c) => !c.name || c.name.includes(' '))
  invalid.forEach((c) => {
    document.cookie = `${c.name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
  })
  refreshCookies()
  ElMessage.success('Cookie 检查与修复完成')
}

function clearAllCookies() {
  if (typeof document === 'undefined') return
  const cookies = document.cookie.split(';')
  cookies.forEach((cookie) => {
    const eqPos = cookie.indexOf('=')
    const name = (eqPos > -1 ? cookie.slice(0, eqPos) : cookie).trim()
    if (name) {
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
    }
  })
  refreshCookies()
  ElMessage.success('已清除所有 Cookie')
}

function toggleDebugMode(val) {
  try {
    localStorage.setItem('debug_mode', String(Boolean(val)))
  } catch (_e) {
    // ignore
  }
  ElMessage.info(val ? '已启用调试模式' : '已关闭调试模式')
}

async function testApiConnection() {
  testingApi.value = true
  apiTestResult.value = ''
  try {
    const res = await api.health()
    const msg = res?.data?.message || res?.data?.status || 'ok'
    apiTestOk.value = true
    apiTestResult.value = `连接成功: ${msg}`
  } catch (err) {
    apiTestOk.value = false
    const status = err?.response?.status
    apiTestResult.value = status ? `连接失败: HTTP ${status}` : `连接失败: ${err?.message || '网络异常'}`
  } finally {
    testingApi.value = false
  }
}
</script>

<style scoped>
.fm-debug {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-5);
}

.fm-debug__section {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-3);
  padding-bottom: var(--fm-space-4);
  border-bottom: 1px solid var(--fm-border);
}

.fm-debug__section:last-child {
  border-bottom: none;
}

.fm-debug__title {
  margin: 0;
  font-size: var(--fm-fs-sm);
  font-weight: 600;
  color: var(--fm-text);
}

.fm-debug__pills {
  display: flex;
  align-items: center;
  gap: var(--fm-space-2);
  flex-wrap: wrap;
}

.fm-debug__meta {
  font-size: var(--fm-fs-sm);
  color: var(--fm-text-2);
}

.fm-debug__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--fm-space-2);
}

.fm-debug__cookie-list {
  margin: 0;
  padding: var(--fm-space-2) var(--fm-space-3);
  list-style: none;
  border-radius: var(--fm-radius-sm);
  background: var(--fm-bg-subtle);
  border: 1px solid var(--fm-border);
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-2);
  max-height: 160px;
  overflow-y: auto;
}

.fm-debug__cookie-list li + li {
  margin-top: 4px;
}

.fm-debug__result {
  margin: 0;
  font-size: var(--fm-fs-xs);
  padding: 6px 10px;
  border-radius: var(--fm-radius-sm);
}

.fm-debug__result.is-ok {
  background: var(--fm-success-soft);
  color: var(--fm-success);
}

.fm-debug__result.is-err {
  background: var(--fm-danger-soft);
  color: var(--fm-danger);
}
</style>

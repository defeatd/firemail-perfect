<template>
  <div class="debug-tools">
    <el-collapse v-model="activeNames">
      <el-collapse-item title="调试工具" name="1">
        <div class="debug-section">
          <h3>连接状态</h3>
          <div class="status-item">
            <span class="label">WebSocket:</span>
            <el-tag :type="wsConnected ? 'success' : 'danger'" effect="dark">
              {{ wsConnected ? '已连接' : '未连接' }}
            </el-tag>
            <el-button size="small" @click="reconnectWebSocket" :disabled="reconnecting">
              {{ reconnecting ? '重连中...' : '重新连接' }}
            </el-button>
          </div>

          <div class="status-item">
            <span class="label">认证状态:</span>
            <el-tag :type="wsAuthenticated ? 'success' : 'warning'" effect="dark">
              {{ wsAuthenticated ? '已认证' : '未认证' }}
            </el-tag>
          </div>

          <div class="status-item">
            <span class="label">API URL:</span>
            <span>{{ apiUrl }}</span>
          </div>

          <div class="status-item">
            <span class="label">WebSocket URL:</span>
            <span>{{ wsUrl }}</span>
          </div>
        </div>

        <div class="debug-section">
          <h3>Cookie 设置</h3>
          <div class="cookie-controls">
            <el-button size="small" type="primary" @click="fixCookies">
              修复 Cookie 问题
            </el-button>
            <el-button size="small" @click="clearCookies">
              清除所有 Cookie
            </el-button>
          </div>

          <div class="cookie-info">
            <p>当前Cookie数量: {{ cookiesCount }}</p>
            <el-checkbox v-model="showCookies">显示Cookie详情</el-checkbox>
            <div v-if="showCookies" class="cookies-list">
              <div v-for="(cookie, index) in cookies" :key="index" class="cookie-item">
                <strong>{{ cookie.name }}</strong>: {{ cookie.value }}
                <div class="cookie-attrs">
                  <span v-if="cookie.sameSite">SameSite: {{ cookie.sameSite }}</span>
                  <span v-if="cookie.secure">Secure</span>
                  <span v-if="cookie.httpOnly">HttpOnly</span>
                  <span v-if="cookie.partitioned">Partitioned</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="debug-section">
          <h3>调试选项</h3>
          <div class="debug-options">
            <el-checkbox v-model="debugMode" @change="toggleDebugMode">
              启用调试模式 (显示详细日志)
            </el-checkbox>
          </div>
        </div>

        <div class="debug-section">
          <h3>网络测试</h3>
          <div class="network-test">
            <el-button size="small" @click="testApiConnection" :loading="testingApi">
              测试API连接
            </el-button>
            <span v-if="apiTestResult" :class="['test-result', apiTestResult.success ? 'success' : 'error']">
              {{ apiTestResult.message }}
            </span>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import websocket from '@/services/websocket'

// 状态变量
const activeNames = ref(['1'])
const wsConnected = ref(false)
const wsAuthenticated = ref(false)
const reconnecting = ref(false)
const showCookies = ref(false)
const debugMode = ref(false)
const cookies = ref([])
const testingApi = ref(false)
const apiTestResult = ref(null)

// 计算属性
const apiUrl = computed(() => window.API_URL || '未设置')
const wsUrl = computed(() => window.WS_URL || '未设置')
const cookiesCount = computed(() => cookies.value.length)

// 初始化
onMounted(() => {
  // 获取WebSocket状态
  wsConnected.value = websocket.isConnected
  wsAuthenticated.value = websocket.isAuthenticated

  // 监听WebSocket状态变化
  websocket.onConnect(() => {
    wsConnected.value = true
  })

  websocket.onDisconnect(() => {
    wsConnected.value = false
    wsAuthenticated.value = false
  })

  websocket.onAuthSuccess(() => {
    wsAuthenticated.value = true
  })

  // 获取调试模式状态
  debugMode.value = localStorage.getItem('debug_mode') === 'true'

  // 解析Cookie
  parseCookies()
})

// 解析Cookie
const parseCookies = () => {
  const cookieList = []
  const cookieStr = document.cookie

  if (cookieStr) {
    const pairs = cookieStr.split(';')
    pairs.forEach(pair => {
      const parts = pair.split('=')
      const name = parts[0].trim()
      const value = parts.length > 1 ? parts[1].trim() : ''

      // 尝试获取Cookie属性（这只是一个近似值，因为JS无法直接获取Cookie属性）
      const sameSite = pair.includes('SameSite=None') ? 'None' :
                       pair.includes('SameSite=Lax') ? 'Lax' :
                       pair.includes('SameSite=Strict') ? 'Strict' : null

      const secure = pair.includes('Secure')
      const httpOnly = pair.includes('HttpOnly')
      const partitioned = pair.includes('Partitioned')

      cookieList.push({ name, value, sameSite, secure, httpOnly, partitioned })
    })
  }

  cookies.value = cookieList
}

// 重新连接WebSocket
const reconnectWebSocket = () => {
  reconnecting.value = true

  // 断开现有连接
  websocket.disconnect()

  // 延迟1秒后重新连接
  setTimeout(() => {
    websocket.connect()
    reconnecting.value = false
  }, 1000)
}

// 修复Cookie问题
const fixCookies = () => {
  // 设置SameSite=None和Partitioned属性
  document.cookie = "CookieConsent=true; SameSite=None; Secure; Partitioned; Path=/;"

  // 刷新Cookie列表
  setTimeout(() => {
    parseCookies()
    ElMessage.success('已尝试修复Cookie问题，请刷新页面测试效果')
  }, 100)
}

// 清除所有Cookie
const clearCookies = () => {
  const cookieNames = cookies.value.map(c => c.name)

  cookieNames.forEach(name => {
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/;`
  })

  // 刷新Cookie列表
  setTimeout(() => {
    parseCookies()
    ElMessage.success('已清除所有Cookie')
  }, 100)
}

// 切换调试模式
const toggleDebugMode = (value) => {
  localStorage.setItem('debug_mode', value)
  ElMessage.success(`已${value ? '启用' : '禁用'}调试模式`)
}

// 测试API连接
const testApiConnection = async () => {
  testingApi.value = true
  apiTestResult.value = null

  try {
    // 构建正确的API URL
    let apiUrl = window.API_URL || '/api';
    // 确保URL不会重复包含/api
    if (!apiUrl.endsWith('/api')) {
      apiUrl = apiUrl + '/api';
    }

    const response = await fetch(`${apiUrl}/health`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json'
      }
    })

    if (response.ok) {
      const data = await response.json()
      apiTestResult.value = {
        success: true,
        message: `连接成功: ${data.message || 'API服务正常'}`
      }
    } else {
      apiTestResult.value = {
        success: false,
        message: `连接失败: HTTP ${response.status}`
      }
    }
  } catch (error) {
    apiTestResult.value = {
      success: false,
      message: `连接错误: ${error.message}`
    }
  } finally {
    testingApi.value = false
  }
}
</script>

<style scoped>
.debug-tools {
  margin: 20px 0;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.debug-section {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px dashed #ebeef5;
}

.debug-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.status-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.label {
  width: 120px;
  font-weight: bold;
}

.cookie-controls {
  margin-bottom: 12px;
  display: flex;
  gap: 8px;
}

.cookies-list {
  margin-top: 12px;
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px;
}

.cookie-item {
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f0f0;
}

.cookie-item:last-child {
  border-bottom: none;
}

.cookie-attrs {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
  display: flex;
  gap: 8px;
}

.test-result {
  margin-left: 12px;
}

.test-result.success {
  color: #67c23a;
}

.test-result.error {
  color: #f56c6c;
}
</style>

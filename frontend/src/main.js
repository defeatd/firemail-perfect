import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import store from './store'
import './assets/main.css'
import WebSocketService from './services/websocket'

const app = createApp(App)

// 全局错误处理
app.config.errorHandler = (err, vm, info) => {
  console.error('Vue全局错误:', err, info)
  // 可以在这里添加错误上报逻辑
}

// 使用WebSocket服务
app.config.globalProperties.$webSocket = WebSocketService

// 设置WebSocket连接状态和消息处理
WebSocketService.onConnect(() => {
  // 通知状态变更
  store.commit('SET_WEBSOCKET_CONNECTED', true);
  
  // 注意：此时只是连接成功，但可能尚未完成认证
  console.log('WebSocket连接成功，等待认证...');
  
  // 不要立即获取数据，而是在认证成功后再获取
  // 认证成功的逻辑应该在WebSocketService内部处理
});

WebSocketService.onDisconnect(() => {
  // 通知状态变更
  store.commit('SET_WEBSOCKET_CONNECTED', false)
})

// 注册WebSocket消息处理器
WebSocketService.onMessage('emails_list', (message) => {
  store.commit('emails/SET_EMAILS', message.data)
})

WebSocketService.onMessage('check_progress', (message) => {
  store.commit('emails/UPDATE_EMAIL_PROGRESS', {
    id: message.email_id,
    progress: message.progress,
    message: message.message
  })
  
  // 添加检查中状态
  if (message.progress < 100) {
    store.dispatch('addCheckingEmail', message.email_id)
  } else {
    store.dispatch('removeCheckingEmail', message.email_id)
  }
})

WebSocketService.onMessage('mail_records', (message) => {
  store.commit('emails/SET_MAIL_RECORDS', {
    emailId: message.email_id,
    records: message.data
  })
})

WebSocketService.onMessage('emails_imported', (message) => {
  // 刷新邮箱列表
  store.dispatch('emails/fetchAllEmails')
  const success = message?.success
  const failed = message?.failed
  if (typeof failed === 'number' && failed > 0) {
    store.dispatch('notifications/addNotification', {
      type: 'warning',
      title: '部分导入成功',
      message: `成功 ${success || 0} 个，失败 ${failed} 个（失败账号未写入）`
    })
  } else {
    store.dispatch('notifications/addNotification', {
      type: 'success',
      title: '导入成功',
      message: success ? `已成功导入 ${success} 个邮箱` : '邮箱数据已成功导入'
    })
  }
})

WebSocketService.onMessage('import_result', (message) => {
  // 结构化导入结果：若有失败，额外通知
  if (message?.failed > 0) {
    const first = (message.failed_details || [])[0]
    const tip = first
      ? `${first.email || '某账号'}: ${first.reason}`
      : `有 ${message.failed} 个失败`
    store.dispatch('notifications/addNotification', {
      type: message.success > 0 ? 'warning' : 'error',
      title: message.success > 0 ? '部分导入失败' : '导入全部失败',
      message: tip
    })
  }
})

WebSocketService.onMessage('emails_deleted', (message) => {
  // 处理邮箱删除消息
  store.commit('emails/REMOVE_EMAILS', message.email_ids)
  // 显示成功通知
  store.dispatch('notifications/addNotification', {
    type: 'success',
    title: '删除成功',
    message: `已成功删除 ${message.email_ids.length} 个邮箱`
  })
})

WebSocketService.onMessage('email_added', (message) => {
  // 刷新邮箱列表
  store.dispatch('emails/fetchAllEmails')
  // 显示成功通知
  store.dispatch('notifications/addNotification', {
    type: 'success',
    title: '添加成功',
    message: '新邮箱已成功添加'
  })
})

WebSocketService.onMessage('error', (message) => {
  store.dispatch('notifications/addNotification', {
    type: 'error',
    title: '错误',
    message: message.message
  })
})

// 添加对info类型消息的处理
WebSocketService.onMessage('info', (message) => {
  store.dispatch('notifications/addNotification', {
    type: 'info',
    title: '系统消息',
    message: message.message
  })
})

// 添加对success类型消息的处理
WebSocketService.onMessage('success', (message) => {
  store.dispatch('notifications/addNotification', {
    type: 'success',
    title: '成功',
    message: message.message
  })
})

// 添加对warning类型消息的处理
WebSocketService.onMessage('warning', (message) => {
  store.dispatch('notifications/addNotification', {
    type: 'warning',
    title: '警告',
    message: message.message
  })
})

// 添加WebSocket认证成功处理器
WebSocketService.onAuthSuccess(() => {
  console.log('WebSocket认证成功，正在请求更新邮箱列表...');
  
  // 只有在用户已登录的情况下才获取邮箱列表
  if (store.getters['auth/isAuthenticated']) {
    store.dispatch('emails/fetchAllEmails');
  }
});

// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 挂载应用前获取系统配置
store.dispatch('auth/getConfig').then(() => {
  // 挂载应用
  app.mount('#app')
  
  // 根据认证状态决定是否初始化WebSocket连接
  if (store.getters['auth/isAuthenticated']) {
    WebSocketService.connect()
  } else {
    console.log('用户未登录，暂不连接WebSocket')
  }
  
  // 监听认证状态变化
  store.watch(
    (state, getters) => getters['auth/isAuthenticated'], 
    (newValue) => {
      if (newValue) {
        // 用户登录后，连接WebSocket
        WebSocketService.connect()
      } else {
        // 用户登出后，断开WebSocket
        WebSocketService.disconnect()
      }
    }
  )
})

app.use(createPinia())
app.use(router)
app.use(store)
app.use(ElementPlus) 
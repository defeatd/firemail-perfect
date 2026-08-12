<template>
  <div class="dashboard-container">
    <!-- 欢迎区域 -->
    <div class="welcome-section">
      <div class="welcome-card">
        <div class="welcome-content">
          <div class="welcome-text">
            <h1 class="welcome-title">欢迎回来！</h1>
            <p class="welcome-subtitle">管理您的邮箱，掌控您的邮件</p>
          </div>
          <div class="welcome-actions">
            <el-button
              type="primary"
              size="large"
              @click="navigateToEmails"
              class="action-btn primary-action"
              :icon="Message"
            >
              邮箱管理
            </el-button>
            <el-button
              size="large"
              @click="navigateToSearch"
              class="action-btn secondary-action"
              :icon="Search"
            >
              搜索邮件
            </el-button>
          </div>
        </div>
        <div class="welcome-decoration">
          <div class="decoration-circle circle-1"></div>
          <div class="decoration-circle circle-2"></div>
          <div class="decoration-circle circle-3"></div>
        </div>
      </div>
    </div>

    <!-- 快速统计 -->
    <div class="stats-section">
      <div class="stats-grid">
        <div class="stat-card" v-for="(stat, index) in stats" :key="index">
          <div class="stat-icon" :class="stat.iconClass">
            <el-icon :size="24"><component :is="stat.icon" /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-number">{{ stat.value }}</div>
            <div class="stat-label">{{ stat.label }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 功能卡片 -->
    <div class="features-section">
      <h2 class="section-title">功能中心</h2>
      <div class="features-grid">
        <div
          class="feature-card"
          v-for="(feature, index) in features"
          :key="index"
          @click="handleFeatureClick(feature)"
        >
          <div class="feature-icon" :class="feature.colorClass">
            <el-icon :size="28"><component :is="feature.icon" /></el-icon>
          </div>
          <div class="feature-content">
            <h3 class="feature-title">{{ feature.title }}</h3>
            <p class="feature-description">{{ feature.description }}</p>
          </div>
          <div class="feature-arrow">
            <el-icon><ArrowRight /></el-icon>
          </div>
        </div>
      </div>
    </div>

    <!-- 快速操作 -->
    <div class="quick-actions-section">
      <h2 class="section-title">快速操作</h2>
      <div class="quick-actions-grid">
        <div
          class="quick-action-card"
          v-for="(action, index) in quickActions"
          :key="index"
          @click="handleQuickAction(action)"
        >
          <div class="quick-action-icon" :class="action.colorClass">
            <el-icon :size="20"><component :is="action.icon" /></el-icon>
          </div>
          <span class="quick-action-text">{{ action.text }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Message, Search, Plus, Setting, Document,
  User, DataAnalysis, Connection, ArrowRight,
  Refresh, Download
} from '@element-plus/icons-vue'
import api from '@/services/api'

const router = useRouter()

// 统计数据
const stats = ref([
  {
    icon: 'Message',
    value: '-',
    label: '邮箱账户',
    iconClass: 'stat-icon-primary'
  },
  {
    icon: 'Document',
    value: '-',
    label: '邮件总数',
    iconClass: 'stat-icon-success'
  },
  {
    icon: 'DataAnalysis',
    value: '-',
    label: '收信成功率',
    iconClass: 'stat-icon-warning'
  },
  {
    icon: 'Connection',
    value: '-',
    label: '服务状态',
    iconClass: 'stat-icon-info'
  }
])

// 获取统计数据
const fetchStats = async () => {
  try {
    const response = await api.getStats()
    if (response.data) {
      const data = response.data
      stats.value[0].value = data.email_count.toLocaleString()
      stats.value[1].value = data.total_mails.toLocaleString()
      stats.value[2].value = data.success_rate + '%'
      stats.value[3].value = data.status === 'online' ? '在线' : '离线'
    }
  } catch (error) {
    console.error('获取统计数据失败:', error)
    // 保持默认的 '-' 值
  }
}

onMounted(() => {
  fetchStats()
})

// 功能卡片
const features = ref([
  {
    icon: 'Message',
    title: '邮箱管理',
    description: '添加、管理和监控您的邮箱账户',
    colorClass: 'feature-icon-primary',
    route: '/emails'
  },
  {
    icon: 'Search',
    title: '邮件搜索',
    description: '快速搜索和过滤邮件内容',
    colorClass: 'feature-icon-success',
    route: '/search'
  },
  {
    icon: 'User',
    title: '用户管理',
    description: '管理系统用户和权限设置',
    colorClass: 'feature-icon-warning',
    route: '/admin/users'
  },
  {
    icon: 'Setting',
    title: '系统设置',
    description: '配置系统参数和个人偏好',
    colorClass: 'feature-icon-info',
    route: '/account'
  }
])

// 快速操作
const quickActions = ref([
  {
    icon: 'Plus',
    text: '添加邮箱',
    colorClass: 'quick-action-primary',
    action: 'addEmail'
  },
  {
    icon: 'Refresh',
    text: '刷新邮件',
    colorClass: 'quick-action-success',
    action: 'refreshEmails'
  },
  {
    icon: 'Download',
    text: '导出数据',
    colorClass: 'quick-action-warning',
    action: 'exportData'
  },
  {
    icon: 'Setting',
    text: '系统设置',
    colorClass: 'quick-action-info',
    action: 'settings'
  }
])

// 导航方法
const navigateToEmails = () => {
  router.push('/emails')
}

const navigateToSearch = () => {
  router.push('/search')
}

const handleFeatureClick = (feature) => {
  router.push(feature.route)
}

const handleQuickAction = (action) => {
  switch (action.action) {
    case 'addEmail':
      router.push('/emails')
      break
    case 'refreshEmails':
      router.push('/emails')
      break
    case 'exportData':
      router.push('/emails')
      break
    case 'settings':
      router.push('/account')
      break
  }
}
</script>

<style scoped>
.dashboard-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

/* 欢迎区域 — 扁平卡其，无动画 */
.welcome-section {
  margin-bottom: 0.5rem;
}

.welcome-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 1.5rem 1.75rem;
  color: var(--text-color);
  position: relative;
  overflow: hidden;
  box-shadow: none;
}

.welcome-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: relative;
  z-index: 2;
  gap: 1rem;
}

.welcome-text {
  flex: 1;
}

.welcome-title {
  font-size: 1.5rem;
  font-weight: 500;
  margin: 0 0 0.35rem 0;
  color: var(--neutral-900);
  letter-spacing: -0.02em;
}

.welcome-subtitle {
  font-size: 0.9rem;
  margin: 0;
  color: var(--neutral-500);
}

.welcome-actions {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
}

.action-btn {
  border-radius: 8px;
  font-weight: 500;
  border: 1px solid var(--border-color);
}

.primary-action {
  background: var(--primary-color) !important;
  color: #fff !important;
  border-color: var(--primary-color) !important;
}

.primary-action:hover {
  background: var(--primary-light) !important;
  border-color: var(--primary-light) !important;
}

.secondary-action {
  background: var(--card-bg) !important;
  color: var(--neutral-700) !important;
  border: 1px solid var(--border-color) !important;
}

.secondary-action:hover {
  background: var(--neutral-50) !important;
}

.welcome-decoration,
.decoration-circle {
  display: none;
}

/* 统计区域 — 统一浅卡其图标 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.75rem;
}

.stat-card {
  background: var(--card-bg);
  border-radius: 10px;
  padding: 1rem 1.15rem;
  display: flex;
  align-items: center;
  gap: 0.85rem;
  box-shadow: none;
  border: 1px solid var(--border-color);
  transition: border-color 0.15s ease;
}

.stat-card:hover {
  border-color: var(--primary-muted);
}

.stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-dark);
  background: var(--primary-soft);
  flex-shrink: 0;
}

.stat-icon-primary,
.stat-icon-success,
.stat-icon-warning,
.stat-icon-info {
  background: var(--primary-soft);
  color: var(--primary-dark);
}

.stat-content {
  flex: 1;
  min-width: 0;
}

.stat-number {
  font-size: 1.35rem;
  font-weight: 500;
  color: var(--neutral-900);
  margin-bottom: 0.1rem;
  letter-spacing: -0.02em;
}

.stat-label {
  font-size: 0.8rem;
  color: var(--neutral-500);
  font-weight: 500;
}

.section-title {
  font-size: 1.05rem;
  font-weight: 500;
  color: var(--neutral-800);
  margin: 0 0 0.85rem 0;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0.75rem;
}

.feature-card {
  background: var(--card-bg);
  border-radius: 10px;
  padding: 1rem 1.15rem;
  display: flex;
  align-items: center;
  gap: 0.85rem;
  box-shadow: none;
  border: 1px solid var(--border-color);
  transition: border-color 0.15s ease, background-color 0.15s ease;
  cursor: pointer;
}

.feature-card:hover {
  border-color: var(--primary-muted);
  background: var(--neutral-50);
}

.feature-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-dark);
  background: var(--primary-soft);
  flex-shrink: 0;
}

.feature-icon-primary,
.feature-icon-success,
.feature-icon-warning,
.feature-icon-info {
  background: var(--primary-soft);
  color: var(--primary-dark);
}

.feature-content {
  flex: 1;
  min-width: 0;
}

.feature-title {
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--neutral-900);
  margin: 0 0 0.2rem 0;
}

.feature-description {
  font-size: 0.8rem;
  color: var(--neutral-500);
  margin: 0;
  line-height: 1.45;
}

.feature-arrow {
  color: var(--neutral-400);
}

.feature-card:hover .feature-arrow {
  color: var(--primary-dark);
}

.quick-actions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.65rem;
}

.quick-action-card {
  background: var(--card-bg);
  border-radius: 10px;
  padding: 0.9rem 1rem;
  display: flex;
  align-items: center;
  gap: 0.65rem;
  box-shadow: none;
  border: 1px solid var(--border-color);
  transition: border-color 0.15s ease, background-color 0.15s ease;
  cursor: pointer;
}

.quick-action-card:hover {
  border-color: var(--primary-muted);
  background: var(--neutral-50);
}

.quick-action-icon {
  width: 32px;
  height: 32px;
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-dark);
  background: var(--primary-soft);
  flex-shrink: 0;
}

.quick-action-primary,
.quick-action-success,
.quick-action-warning,
.quick-action-info {
  background: var(--primary-soft);
  color: var(--primary-dark);
}

.quick-action-text {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--neutral-700);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .dashboard-container {
    padding: 1rem;
    gap: 1.5rem;
  }

  .welcome-card {
    padding: 1.5rem;
  }

  .welcome-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 1.5rem;
  }

  .welcome-title {
    font-size: 2rem;
  }

  .welcome-subtitle {
    font-size: 1rem;
  }

  .welcome-actions {
    width: 100%;
    flex-direction: column;
  }

  .action-btn {
    width: 100%;
    justify-content: center;
  }

  .stats-grid {
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
  }

  .stat-card {
    padding: 1rem;
  }

  .features-grid {
    grid-template-columns: 1fr;
    gap: 1rem;
  }

  .feature-card {
    padding: 1rem;
  }

  .quick-actions-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 0.75rem;
  }

  .quick-action-card {
    padding: 1rem;
    flex-direction: column;
    text-align: center;
    gap: 0.5rem;
  }
}

@media (max-width: 480px) {
  .welcome-title {
    font-size: 1.75rem;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .quick-actions-grid {
    grid-template-columns: 1fr;
  }
}
</style>
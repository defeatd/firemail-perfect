<template>
  <div class="about-container">
    <div class="about-header">
      <h1 class="page-title">关于花火邮箱助手</h1>
      <div class="version-badge">v1.0.0</div>
    </div>
    
    <el-row :gutter="20">
      <el-col :xs="24" :md="8">
        <el-card class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <h2><el-icon><InfoFilled /></el-icon> 项目介绍</h2>
            </div>
          </template>
          <div class="card-content">
            <p>花火邮箱助手是一款专为Microsoft邮箱设计的批量收件工具，旨在提供简单高效的邮件管理解决方案。</p>
            <p>通过实时的WebSocket通信，多线程并行处理，用户可以轻松管理多个邮箱账户，批量收取邮件。</p>
          </div>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :md="8">
        <el-card class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <h2><el-icon><TrendCharts /></el-icon> 版本信息</h2>
            </div>
          </template>
          <div class="card-content">
            <ul class="info-list">
              <li>
                <span class="label">当前版本:</span>
                <span class="value">v1.0.0</span>
              </li>
              <li>
                <span class="label">更新日期:</span>
                <span class="value">{{ new Date().toLocaleDateString() }}</span>
              </li>
              <li>
                <span class="label">协议:</span>
                <span class="value">MIT</span>
              </li>
            </ul>
          </div>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :md="8">
        <el-card class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <h2><el-icon><Monitor /></el-icon> 技术栈</h2>
            </div>
          </template>
          <div class="card-content">
            <div class="tech-tags">
              <el-tag class="tech-tag">Python 3.13</el-tag>
              <el-tag class="tech-tag" type="success">Flask</el-tag>
              <el-tag class="tech-tag" type="warning">SQLite</el-tag>
              <el-tag class="tech-tag" type="danger">WebSocket</el-tag>
              <el-tag class="tech-tag">Vue 3</el-tag>
              <el-tag class="tech-tag" type="success">Vite</el-tag>
              <el-tag class="tech-tag" type="warning">Element Plus</el-tag>
              <el-tag class="tech-tag" type="info">OAuth 2.0</el-tag>
              <el-tag class="tech-tag" type="danger">IMAP</el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-card class="features-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <h2><el-icon><Star /></el-icon> 功能特点</h2>
        </div>
      </template>
      <div class="features-grid">
        <div class="feature-item" v-for="(feature, index) in features" :key="index">
          <div class="feature-icon">
            <el-icon><component :is="feature.icon" /></el-icon>
          </div>
          <div class="feature-content">
            <h3>{{ feature.title }}</h3>
            <p>{{ feature.description }}</p>
          </div>
        </div>
      </div>
    </el-card>
    
    <el-card class="notice-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <h2><el-icon><Warning /></el-icon> 注意事项</h2>
        </div>
      </template>
      <div class="notice-content">
        <el-alert
          v-for="(notice, index) in notices"
          :key="index"
          :title="notice"
          :type="noticeTypes[index % noticeTypes.length]"
          :closable="false"
          show-icon
          class="notice-alert"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { InfoFilled, Star, Warning, Monitor, TrendCharts, Connection, DocumentCopy, Upload, Finished, Management } from '@element-plus/icons-vue'

const features = [
  {
    icon: 'Management',
    title: '邮箱管理',
    description: '提供邮箱添加、查看、删除等功能，支持单个和批量导入邮箱'
  },
  {
    icon: 'DocumentCopy',
    title: '批量管理',
    description: '支持多选、全选邮箱，进行批量删除、收信，允许单个邮箱手动收信'
  },
  {
    icon: 'Connection',
    title: 'WebSocket支持',
    description: '实时通信，及时反馈处理进度和结果'
  },
  {
    icon: 'Finished',
    title: '多线程处理',
    description: '提高邮件收取效率，支持并行处理多个邮箱'
  },
  {
    icon: 'Monitor',
    title: '简洁界面',
    description: '简约现代的用户界面，操作简单直观'
  },
  {
    icon: 'Upload',
    title: '跨平台支持',
    description: '支持Windows和Linux平台，可打包为Docker容器部署'
  }
]

const notices = [
  '本工具仅用于方便用户管理自己的邮箱账户，请勿用于非法用途',
  '邮箱账号和密码等敏感信息仅存储在本地SQLite数据库中，请确保服务器安全',
  '由于Microsoft API限制，可能会有请求频率限制，请合理使用'
]

const noticeTypes = ['warning', 'info', 'error']
</script>

<style scoped>
.about-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 20px;
}

.about-header {
  display: flex;
  align-items: center;
  margin-bottom: 30px;
  position: relative;
}

.page-title {
  font-size: 2rem;
  color: var(--primary-color);
  margin: 0;
  position: relative;
  display: inline-block;
}

.page-title::after {
  content: '';
  position: absolute;
  bottom: -8px;
  left: 0;
  width: 60px;
  height: 4px;
  background-color: var(--primary-color);
  border-radius: var(--border-radius-full);
}

.version-badge {
  background-color: var(--primary-color);
  color: white;
  border-radius: 20px;
  padding: 4px 12px;
  font-size: 0.9rem;
  margin-left: 15px;
  font-weight: 500;
}

.card-header {
  display: flex;
  align-items: center;
}

.card-header h2 {
  font-size: 1.4rem;
  margin: 0;
  color: var(--primary-text-color);
  display: flex;
  align-items: center;
  gap: 10px;
}

.info-card {
  height: 100%;
  transition: transform var(--transition-normal), box-shadow var(--transition-normal);
  margin-bottom: 20px;
}

.info-card:hover {
  transform: translateY(-5px);
}

.card-content {
  color: var(--regular-text-color);
  line-height: 1.6;
}

.info-list {
  list-style-type: none;
  padding: 0;
  margin: 0;
}

.info-list li {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--border-color-lighter);
}

.info-list li:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.label {
  font-weight: 500;
  color: var(--primary-text-color);
}

.value {
  color: var(--secondary-text-color);
}

.tech-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.tech-tag {
  margin-right: 0;
}

.features-card {
  margin-bottom: 20px;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.feature-item {
  display: flex;
  gap: 15px;
  padding: 15px;
  border-radius: var(--border-radius);
  transition: background-color var(--transition-normal), transform var(--transition-normal);
}

.feature-item:hover {
  background-color: var(--border-color-lighter);
  transform: translateX(5px);
}

.feature-icon {
  font-size: 24px;
  color: var(--primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background-color: rgba(59, 130, 246, 0.1);
  flex-shrink: 0;
}

.feature-content h3 {
  margin: 0 0 5px 0;
  color: var(--primary-text-color);
  font-size: 1.1rem;
}

.feature-content p {
  margin: 0;
  color: var(--regular-text-color);
}

.notice-card {
  margin-bottom: 20px;
}

.notice-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.notice-alert {
  margin: 0;
}

@media (max-width: 768px) {
  .about-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
  
  .version-badge {
    margin-left: 0;
  }
  
  .features-grid {
    grid-template-columns: 1fr;
  }
}
</style>
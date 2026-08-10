<template>
  <div class="search-view">
    <h1 class="page-title">搜索邮件</h1>

    <!-- 搜索组件 -->
    <div class="search-bar">
      <SearchComponent />
    </div>

    <!-- 搜索结果 -->
    <el-card class="search-results-card" v-loading="loading">
      <template #header>
        <div class="card-header">
          <h2>搜索结果</h2>
          <div class="result-info" v-if="!loading">
            找到 {{ searchResults.length }} 条结果
          </div>
        </div>
      </template>

      <div v-if="searchResults.length > 0">
        <el-table
          :data="searchResults"
          style="width: 100%"
          stripe
          border
        >
          <el-table-column prop="subject" label="标题" min-width="250" show-overflow-tooltip>
            <template #default="scope">
              <a href="#" @click.prevent="viewMailContent(scope.row)" class="mail-link">
                {{ scope.row.subject }}
              </a>
            </template>
          </el-table-column>
          <el-table-column prop="sender" label="发件人" min-width="200" show-overflow-tooltip>
            <template #default="scope">
              <a href="#" @click.prevent="searchBySender(scope.row.sender)" class="mail-link">
                {{ scope.row.sender }}
              </a>
            </template>
          </el-table-column>
          <el-table-column prop="email_address" label="收件人" min-width="180" show-overflow-tooltip>
            <template #default="scope">
              <a href="#" @click.prevent="viewAllMailsByEmail(scope.row.email_id)" class="mail-link">
                {{ scope.row.email_address }}
              </a>
            </template>
          </el-table-column>
          <el-table-column prop="received_time" label="接收时间" width="180">
            <template #default="scope">
              {{ formatDate(scope.row.received_time) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="scope">
              <el-button
                type="primary"
                size="small"
                @click="viewMailContent(scope.row)"
                :icon="Document"
              >
                查看
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div v-else-if="hasSearched && !loading" class="no-results">
        <el-empty description="未找到符合条件的邮件" />
      </div>
      <div v-else-if="!hasSearched && !loading" class="search-tip">
        请在上方输入关键词开始搜索
      </div>
    </el-card>

    <!-- 邮件内容查看对话框 -->
    <el-dialog
      v-model="mailContentDialogVisible"
      :title="selectedMail ? selectedMail.subject : '邮件内容'"
      width="70%"
      top="5vh"
      class="mail-content-dialog"
    >
      <div v-if="selectedMail" class="mail-detail">
        <!-- 使用EmailContentViewer组件 -->
        <EmailContentViewer
          :mail="selectedMail"
          :attachments="selectedMail.attachments || []"
          :loading-attachments="false"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { ElMessage } from 'element-plus';
import { Document } from '@element-plus/icons-vue';
import SearchComponent from '@/components/SearchComponent.vue';
import api from '@/services/api';
import DOMPurify from 'dompurify';
import EmailContentViewer from '@/components/EmailContentViewer.vue';

// 路由器和当前路由
const router = useRouter();
const route = useRoute();

// 状态
const loading = ref(false);
const searchResults = ref([]);
const hasSearched = ref(false);
const mailContentDialogVisible = ref(false);
const selectedMail = ref(null);

// 格式化日期
const formatDate = (dateString) => {
  if (!dateString) return '未知';
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return dateString;

  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

// 执行搜索
const performSearch = async (query, searchInFields) => {
  if (!query || !searchInFields || searchInFields.length === 0) {
    return;
  }

  loading.value = true;
  hasSearched.value = true;

  try {
    const response = await api.search(query, searchInFields);
    searchResults.value = response.data.results || [];
    if (searchResults.value.length === 0) {
      ElMessage.info('未找到符合条件的邮件');
    }
  } catch (error) {
    console.error('搜索失败:', error);
    ElMessage.error(error.response?.data?.error || '搜索失败，请稍后重试');
    searchResults.value = [];
  } finally {
    loading.value = false;
  }
};

// 查看邮件内容
const viewMailContent = (mail) => {
  selectedMail.value = mail;
  mailContentDialogVisible.value = true;
};

// 检查邮件内容是否为HTML格式
const isHtmlContent = (mail) => {
  if (!mail || !mail.content) return false;

  // 兼容新旧格式
  if (typeof mail.content === 'object') {
    return mail.content.has_html === true || mail.content.content_type === 'text/html';
  }

  // 旧格式，检查内容是否包含HTML标签
  const content = String(mail.content);
  return content.includes('<html') || content.includes('<body') ||
         content.includes('<div') || content.includes('<p>') ||
         content.includes('<table') || content.includes('<img');
}

// 获取邮件内容
const getMailContent = (mail) => {
  if (!mail) return '';

  // 兼容新旧格式
  if (typeof mail.content === 'object' && mail.content !== null) {
    return mail.content.content || '';
  }

  return mail.content || '';
}

// 净化HTML内容，防止XSS攻击
const sanitizeHtml = (html) => {
  if (!html) return '';
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'a', 'b', 'br', 'div', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'i', 'img', 'li', 'ol', 'p', 'span', 'strong', 'table', 'tbody',
      'td', 'th', 'thead', 'tr', 'u', 'ul', 'font', 'blockquote', 'hr',
      'pre', 'code', 'col', 'colgroup', 'section', 'header', 'footer',
      'nav', 'article', 'aside', 'figure', 'figcaption', 'address', 'main',
      'caption', 'center', 'cite', 'dd', 'dl', 'dt', 'mark', 's', 'small',
      'strike', 'sub', 'sup'
    ],
    ALLOWED_ATTR: [
      'href', 'target', 'src', 'alt', 'style', 'class', 'id', 'width', 'height',
      'align', 'valign', 'bgcolor', 'border', 'cellpadding', 'cellspacing',
      'color', 'colspan', 'dir', 'face', 'frame', 'frameborder', 'headers',
      'hspace', 'lang', 'marginheight', 'marginwidth', 'nowrap', 'rel',
      'rev', 'rowspan', 'scrolling', 'shape', 'span', 'summary', 'title',
      'usemap', 'vspace', 'start', 'type', 'value', 'size', 'data-*'
    ]
  });
};

// 按发件人搜索
const searchBySender = (sender) => {
  router.push({
    name: 'search',
    query: {
      q: sender,
      in: 'sender'
    }
  });
};

// 查看指定邮箱的所有邮件
const viewAllMailsByEmail = (emailId) => {
  router.push({
    name: 'emailDetail',
    params: { id: emailId }
  });
};

// 监听URL参数变化
watch(() => route.query, (newQuery) => {
  if (newQuery.q) {
    const query = newQuery.q;
    const searchInFields = newQuery.in ? newQuery.in.split(',') : ['subject', 'sender', 'content'];
    performSearch(query, searchInFields);
  }
}, { immediate: true, deep: true });

// 初始化
onMounted(() => {
  // 从URL获取查询参数
  if (route.query.q) {
    const query = route.query.q;
    const searchInFields = route.query.in ? route.query.in.split(',') : ['subject', 'sender', 'content'];
    performSearch(query, searchInFields);
  }
});
</script>

<style scoped>
.search-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  min-height: calc(100vh - 180px); /* 确保内容区域足够高以推动页脚到底部 */
}

.page-title {
  font-size: 26px;
  margin-bottom: 20px;
  color: #303133;
  text-align: center;
  font-weight: 600;
}

.search-bar {
  margin-bottom: 30px;
}

.search-results-card {
  background-color: #fff;
  border-radius: 12px;
  min-height: 300px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  margin-bottom: 30px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
}

.card-header h2 {
  font-size: 18px;
  margin: 0;
  color: #303133;
  font-weight: 600;
}

.result-info {
  color: #909399;
  font-size: 14px;
  background-color: #f2f6fc;
  padding: 4px 10px;
  border-radius: 4px;
}

.no-results, .search-tip {
  text-align: center;
  padding: 60px 0;
  color: #909399;
  font-size: 16px;
}

.mail-link {
  color: var(--primary-color);
  text-decoration: none;
  transition: color 0.2s;
}

.mail-link:hover {
  text-decoration: underline;
  color: #66b1ff;
}

.mail-detail {
  padding: 0 20px;
}

.mail-info {
  margin-bottom: 20px;
  background-color: #f8f9fa;
  padding: 15px;
  border-radius: 8px;
}

.info-item {
  margin-bottom: 8px;
  display: flex;
}

.label {
  width: 80px;
  color: #606266;
  font-weight: bold;
}

.value {
  flex: 1;
  word-break: break-all;
}

.mail-content {
  padding: 20px;
  background-color: #f5f7fa;
  border-radius: 8px;
  min-height: 200px;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}

pre {
  font-family: 'PingFang SC', 'Helvetica Neue', Helvetica, 'Hiragino Sans GB', 'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
  white-space: pre-wrap;
  margin: 0;
}

.html-content {
  max-width: 100%;
  overflow-x: auto;
  padding: 10px;
  background-color: #f5f7fa;
  border-radius: 8px;
  line-height: 1.6;
}

.html-content img {
  max-width: 100%;
  height: auto;
}

.html-content a {
  color: var(--primary-color);
  text-decoration: underline;
}

.html-content table {
  border-collapse: collapse;
  margin: 10px 0;
}

.html-content th,
.html-content td {
  border: 1px solid #ddd;
  padding: 8px;
}

/* 表格样式优化 */
:deep(.el-table) {
  border-radius: 8px;
  overflow: hidden;
}

:deep(.el-table th) {
  background-color: #f5f7fa;
  font-weight: 600;
}

:deep(.el-table .cell) {
  padding: 12px 8px;
}

:deep(.el-button) {
  padding: 8px 15px;
}

@media (max-width: 768px) {
  .search-view {
    padding: 10px;
  }

  .mail-detail {
    padding: 0 10px;
  }

  .page-title {
    font-size: 22px;
  }
}
</style>
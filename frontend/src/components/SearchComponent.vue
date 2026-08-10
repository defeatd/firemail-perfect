<template>
  <div class="search-component">
    <div class="search-container">
      <el-input
        v-model="searchQuery"
        placeholder="搜索邮件..."
        clearable
        :prefix-icon="Search"
        @keyup.enter="handleSearch"
      >
        <template #append>
          <el-button :icon="Search" @click="handleSearch">搜索</el-button>
        </template>
      </el-input>
      
      <div class="search-options">
        <span class="search-in-label">搜索范围:</span>
        <el-checkbox-group v-model="searchIn">
          <el-checkbox label="subject">标题</el-checkbox>
          <el-checkbox label="sender">发件人</el-checkbox>
          <el-checkbox label="recipient">收件人</el-checkbox>
          <el-checkbox label="content">正文</el-checkbox>
        </el-checkbox-group>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { Search } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';

const router = useRouter();

// 搜索状态
const searchQuery = ref('');
const searchIn = ref(['subject', 'sender', 'content']); // 默认勾选主题、发件人和正文

// 搜索处理
const handleSearch = () => {
  if (!searchQuery.value || searchQuery.value.trim() === '') {
    ElMessage.warning('请输入搜索关键词');
    return;
  }

  // 至少选择一个搜索范围
  if (searchIn.value.length === 0) {
    ElMessage.warning('请至少选择一个搜索范围');
    return;
  }

  // 导航到搜索结果页面
  router.push({
    name: 'search',
    query: {
      q: searchQuery.value,
      in: searchIn.value.join(',')
    }
  });
};

onMounted(() => {
  // 如果从URL中获取查询参数
  const query = router.currentRoute.value.query;
  if (query.q) {
    searchQuery.value = query.q;
  }
  if (query.in) {
    searchIn.value = query.in.split(',');
  }
});
</script>

<style scoped>
.search-component {
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
}

.search-container {
  background-color: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  transition: all 0.3s ease;
}

.search-container:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}

:deep(.el-input__wrapper) {
  padding: 0 10px;
  height: 46px;
}

:deep(.el-input__inner) {
  font-size: 16px;
}

:deep(.el-button) {
  height: 46px;
  font-size: 16px;
  padding: 0 20px;
}

.search-options {
  margin-top: 16px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  padding: 5px 0;
}

.search-in-label {
  margin-right: 16px;
  color: #606266;
  font-size: 14px;
  font-weight: 600;
}

:deep(.el-checkbox__label) {
  font-size: 14px;
  padding-left: 6px;
}

:deep(.el-checkbox) {
  margin-right: 16px;
  margin-top: 5px;
  margin-bottom: 5px;
}

@media (max-width: 768px) {
  .search-options {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .search-in-label {
    margin-bottom: 10px;
  }
  
  .search-container {
    padding: 16px;
  }
}
</style> 
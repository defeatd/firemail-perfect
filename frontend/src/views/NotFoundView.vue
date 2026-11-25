<template>
  <div class="fm-status-page">
    <EmptyState
      large
      code="404"
      :icon="QuestionFilled"
      title="页面不存在"
      description="您访问的地址可能已被移动或拼写有误，请返回首页继续操作。"
    >
      <template #actions>
        <el-button type="primary" @click="router.push('/')">返回首页</el-button>
      </template>
    </EmptyState>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { QuestionFilled } from '@element-plus/icons-vue'
import EmptyState from '@/components/common/EmptyState.vue'

const router = useRouter()
</script>

<style scoped>
.fm-status-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}
</style>

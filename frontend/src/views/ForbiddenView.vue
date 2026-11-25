<template>
  <div class="fm-status-page">
    <EmptyState
      large
      code="403"
      :icon="Lock"
      title="无权限访问此页面"
      description="该页面仅对系统管理员开放，如需权限请联系管理员。"
    >
      <template #actions>
        <el-button type="primary" @click="router.push('/')">返回首页</el-button>
      </template>
    </EmptyState>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { Lock } from '@element-plus/icons-vue'
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

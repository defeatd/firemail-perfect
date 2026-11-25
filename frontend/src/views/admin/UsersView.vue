<template>
  <div class="fm-users-view">
    <PageHeader title="用户管理" :count="users.length">
      <template #meta>
        <router-link to="/admin/system" class="fm-users-view__reg-link">
          注册：{{ auth.allowRegister ? '已开启' : '已关闭' }} →
        </router-link>
      </template>

      <template #actions>
        <el-button :loading="loading" @click="loadUsers">
          <el-icon><Refresh /></el-icon>
          <span>刷新列表</span>
        </el-button>
        <el-button type="primary" @click="createDialogOpen = true">
          <el-icon><Plus /></el-icon>
          <span>添加用户</span>
        </el-button>
      </template>
    </PageHeader>

    <div class="fm-card fm-users-table-wrap">
      <el-table v-loading="loading" :data="users" row-key="id">
        <el-table-column prop="id" label="ID" width="84">
          <template #default="{ row }">
            <span class="fm-mono">{{ row.id }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="username" label="用户名" min-width="180">
          <template #default="{ row }">
            <span class="fm-users-view__name">{{ row.username }}</span>
            <span v-if="isCurrentUser(row)" class="fm-users-view__self">当前</span>
          </template>
        </el-table-column>

        <el-table-column label="类型" width="130">
          <template #default="{ row }">
            <StatusPill :tone="row.is_admin ? 'accent' : 'muted'">
              {{ row.is_admin ? '管理员' : '普通用户' }}
            </StatusPill>
          </template>
        </el-table-column>

        <el-table-column label="创建时间" min-width="180">
          <template #default="{ row }">
            <span class="fm-mono fm-users-view__time">
              {{ row.created_at ? formatAbs(row.created_at) : '未知' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="180" align="right">
          <template #default="{ row }">
            <el-tooltip
              content="不能操作当前登录账户"
              :disabled="!isCurrentUser(row)"
              placement="top"
            >
              <div class="fm-users-view__ops">
                <el-button
                  size="small"
                  :disabled="isCurrentUser(row)"
                  @click="openResetDialog(row)"
                >
                  重置密码
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  plain
                  :disabled="isCurrentUser(row)"
                  @click="handleDelete(row)"
                >
                  删除
                </el-button>
              </div>
            </el-tooltip>
          </template>
        </el-table-column>

        <template #empty>
          <EmptyState title="暂无用户" description="点击右上角「添加用户」创建新账户。" />
        </template>
      </el-table>
    </div>

    <UserFormDialog v-model="createDialogOpen" @created="loadUsers" />
    <ResetPasswordDialog v-model="resetDialogOpen" :user="activeUser" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { formatAbs } from '@/utils/time'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusPill from '@/components/common/StatusPill.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import UserFormDialog from '@/components/admin/UserFormDialog.vue'
import ResetPasswordDialog from '@/components/admin/ResetPasswordDialog.vue'

const auth = useAuthStore()

const users = ref([])
const loading = ref(false)
const createDialogOpen = ref(false)
const resetDialogOpen = ref(false)
const activeUser = ref(null)

function isCurrentUser(row) {
  return Number(row.id) === Number(auth.currentUser?.id)
}

async function loadUsers() {
  loading.value = true
  try {
    const data = await auth.getAllUsers()
    users.value = Array.isArray(data) ? data : data?.users || []
  } catch (err) {
    ElMessage.error(err?.response?.data?.error || '获取用户列表失败')
  } finally {
    loading.value = false
  }
}

function openResetDialog(row) {
  activeUser.value = row
  resetDialogOpen.value = true
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `您确定要删除用户 ${row.username} 吗？此操作不可逆，用户所有数据将被永久删除。`,
      '确认删除用户',
      {
        type: 'warning',
        confirmButtonText: '删除',
        confirmButtonClass: 'el-button--danger'
      }
    )
    await auth.deleteUser(row.id)
    ElMessage.success('用户删除成功')
    await loadUsers()
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error(err?.response?.data?.error || '删除用户失败')
    }
  }
}

onMounted(() => {
  auth.getConfig()
  loadUsers()
})
</script>

<style scoped>
.fm-users-view__reg-link {
  color: var(--fm-accent);
  text-decoration: none;
  font-weight: 500;
}

.fm-users-view__reg-link:hover {
  text-decoration: underline;
}

.fm-users-table-wrap {
  overflow: hidden;
}

.fm-users-view__name {
  font-weight: 500;
  color: var(--fm-text);
}

.fm-users-view__self {
  margin-left: 8px;
  padding: 1px 6px;
  border-radius: var(--fm-radius-pill);
  background: var(--fm-primary-soft);
  color: var(--fm-text-2);
  font-size: 11px;
}

.fm-users-view__time {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-2);
}

.fm-users-view__ops {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
</style>

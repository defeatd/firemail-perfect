<template>
  <div class="fm-account-view">
    <PageHeader title="账户设置" subtitle="管理个人账户安全与工作台外观偏好" />

    <div class="fm-account-grid">
      <section class="fm-card fm-account-card">
        <h2 class="fm-account-card__title">个人信息</h2>
        <div class="fm-profile-row">
          <span class="fm-profile-row__label">用户名</span>
          <span class="fm-profile-row__val fm-mono">{{ username }}</span>
        </div>
        <div class="fm-profile-row">
          <span class="fm-profile-row__label">账户类型</span>
          <StatusPill :tone="auth.isAdmin ? 'accent' : 'muted'">
            {{ auth.isAdmin ? '管理员' : '普通用户' }}
          </StatusPill>
        </div>
      </section>

      <section class="fm-card fm-account-card">
        <h2 class="fm-account-card__title">外观与阅读偏好</h2>

        <div class="fm-pref-row">
          <div>
            <div class="fm-pref-row__label">界面主题</div>
            <div class="fm-pref-row__desc">选择亮色、暗色或跟随系统主题</div>
          </div>
          <SegmentedFilter
            :model-value="ui.theme"
            :options="THEME_OPTIONS"
            size="sm"
            @update:model-value="ui.setTheme($event)"
          />
        </div>

        <div class="fm-pref-row">
          <div>
            <div class="fm-pref-row__label">邮件纸张模式</div>
            <div class="fm-pref-row__desc">暗色主题下以白纸黑字阅读 HTML 邮件，避免反色失真</div>
          </div>
          <el-switch
            :model-value="ui.mailPaperMode"
            @change="ui.setMailPaperMode($event)"
          />
        </div>

        <div v-if="isMobile" class="fm-pref-row">
          <div>
            <div class="fm-pref-row__label">调试工具</div>
            <div class="fm-pref-row__desc">打开连接诊断、Cookie 清理与 API 测试抽屉</div>
          </div>
          <el-button size="small" @click="openDebugDrawer">打开</el-button>
        </div>
      </section>

      <section class="fm-card fm-account-card fm-account-card--full">
        <h2 class="fm-account-card__title">修改密码</h2>

        <el-alert
          v-if="pwdError"
          type="error"
          :closable="false"
          show-icon
          :title="pwdError"
        />

        <el-form
          ref="pwdFormRef"
          :model="pwdForm"
          :rules="pwdRules"
          label-position="top"
          class="fm-pwd-form"
          @submit.prevent="handleChangePassword"
        >
          <el-form-item label="当前密码" prop="oldPassword">
            <el-input
              v-model="pwdForm.oldPassword"
              type="password"
              show-password
              autocomplete="current-password"
            />
          </el-form-item>

          <el-form-item label="新密码" prop="newPassword">
            <el-input
              v-model="pwdForm.newPassword"
              type="password"
              show-password
              placeholder="至少 8 个字符"
              autocomplete="new-password"
            />
          </el-form-item>

          <el-form-item label="确认新密码" prop="confirmPassword">
            <el-input
              v-model="pwdForm.confirmPassword"
              type="password"
              show-password
              autocomplete="new-password"
            />
          </el-form-item>

          <div>
            <el-button type="primary" native-type="submit" :loading="savingPwd">
              保存新密码
            </el-button>
          </div>
        </el-form>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { useBreakpoint } from '@/composables/useBreakpoint'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusPill from '@/components/common/StatusPill.vue'
import SegmentedFilter from '@/components/common/SegmentedFilter.vue'

const THEME_OPTIONS = [
  { value: 'light', label: '亮色' },
  { value: 'dark', label: '暗色' },
  { value: 'system', label: '跟随系统' }
]

const auth = useAuthStore()
const ui = useUiStore()
const { isMobile } = useBreakpoint()

const pwdFormRef = ref(null)
const savingPwd = ref(false)
const pwdError = ref('')

const pwdForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const username = computed(() => auth.currentUser?.username || '—')

const pwdRules = {
  oldPassword: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '新密码长度不能少于 8 个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, val, cb) => {
        if (val !== pwdForm.newPassword) cb(new Error('两次输入的新密码不一致'))
        else cb()
      },
      trigger: 'blur'
    }
  ]
}

watch(
  () => pwdForm.newPassword,
  () => {
    if (pwdForm.confirmPassword) {
      pwdFormRef.value?.validateField('confirmPassword').catch(() => {})
    }
  }
)

function openDebugDrawer() {
  ui.setShowDebugTools(true)
  ui.setDebugDrawerOpen(true)
}

async function handleChangePassword() {
  pwdError.value = ''
  const ok = await pwdFormRef.value?.validate().catch(() => false)
  if (!ok) return

  savingPwd.value = true
  try {
    await auth.changePassword({
      oldPassword: pwdForm.oldPassword,
      newPassword: pwdForm.newPassword
    })
    ElMessage.success('密码已成功更新')
    pwdForm.oldPassword = ''
    pwdForm.newPassword = ''
    pwdForm.confirmPassword = ''
    pwdFormRef.value?.clearValidate()
  } catch (err) {
    pwdError.value = err?.response?.data?.error || err?.message || '修改密码失败'
  } finally {
    savingPwd.value = false
  }
}
</script>

<style scoped>
.fm-account-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--fm-space-5);
}

.fm-account-card {
  padding: var(--fm-space-5);
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-4);
}

.fm-account-card--full {
  grid-column: 1 / -1;
}

.fm-account-card__title {
  margin: 0;
  font-size: var(--fm-fs-md);
  font-weight: 600;
  color: var(--fm-text);
}

.fm-profile-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--fm-border);
}

.fm-profile-row:last-child {
  border-bottom: none;
}

.fm-profile-row__label {
  font-size: var(--fm-fs-sm);
  color: var(--fm-text-2);
}

.fm-profile-row__val {
  font-size: var(--fm-fs-sm);
  font-weight: 500;
  color: var(--fm-text);
}

.fm-pref-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--fm-space-4);
  flex-wrap: wrap;
}

.fm-pref-row__label {
  font-size: var(--fm-fs-sm);
  font-weight: 500;
  color: var(--fm-text);
}

.fm-pref-row__desc {
  font-size: var(--fm-fs-xs);
  color: var(--fm-text-3);
  margin-top: 2px;
}

.fm-pwd-form {
  max-width: 440px;
}

@media (max-width: 1023.98px) {
  .fm-account-grid {
    grid-template-columns: 1fr;
  }
}
</style>

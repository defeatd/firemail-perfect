<template>
  <div class="fm-auth-form">
    <div class="fm-auth-form__head">
      <h2 class="fm-auth-form__title">创建账户</h2>
      <p class="fm-auth-form__sub">注册 FireMail 工作台账户</p>
    </div>

    <el-alert
      v-if="!auth.allowRegister"
      type="error"
      :closable="false"
      show-icon
      title="系统当前不允许注册新用户，请联系管理员"
    />

    <el-alert
      v-else-if="errorMessage"
      type="error"
      :closable="false"
      show-icon
      :title="errorMessage"
    />

    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      @submit.prevent="handleSubmit"
    >
      <el-form-item label="用户名" prop="username">
        <el-input
          v-model="form.username"
          placeholder="3-20 个字符"
          autocomplete="username"
          size="large"
        />
      </el-form-item>

      <el-form-item label="密码" prop="password">
        <el-input
          v-model="form.password"
          type="password"
          show-password
          placeholder="至少 8 位字符"
          autocomplete="new-password"
          size="large"
        />
      </el-form-item>

      <el-form-item label="确认密码" prop="confirmPassword">
        <el-input
          v-model="form.confirmPassword"
          type="password"
          show-password
          placeholder="再次输入密码"
          autocomplete="new-password"
          size="large"
          @keyup.enter="handleSubmit"
        />
      </el-form-item>

      <el-button
        type="primary"
        size="large"
        native-type="submit"
        :disabled="!auth.allowRegister"
        :loading="submitting"
        class="fm-auth-form__submit"
      >
        {{ submitting ? '注册中…' : '立即注册' }}
      </el-button>
    </el-form>

    <div class="fm-auth-form__footer">
      <span>已有账号？</span>
      <router-link to="/login" class="fm-auth-form__link">返回登录</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const formRef = ref(null)
const submitting = ref(false)
const errorMessage = ref('')

const form = reactive({
  username: '',
  password: '',
  confirmPassword: ''
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度须在 3 到 20 个字符之间', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码长度不能少于 8 个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, val, cb) => {
        if (val !== form.password) cb(new Error('两次输入的密码不一致'))
        else cb()
      },
      trigger: 'blur'
    }
  ]
}

watch(
  () => form.password,
  () => {
    if (form.confirmPassword) {
      formRef.value?.validateField('confirmPassword').catch(() => {})
    }
  }
)

onMounted(() => {
  auth.clearError()
  auth.getConfig()
})

async function handleSubmit() {
  if (!auth.allowRegister) return
  errorMessage.value = ''
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return

  submitting.value = true
  try {
    const res = await auth.registerAndLogin({
      username: form.username.trim(),
      password: form.password
    })
    if (res.success) {
      router.replace('/')
    } else {
      router.replace({
        name: 'login',
        query: {
          registered: '1',
          autologin: 'failed',
          username: form.username.trim()
        }
      })
    }
  } catch (err) {
    errorMessage.value =
      err?.response?.data?.error ||
      err?.response?.data?.message ||
      auth.error ||
      err?.message ||
      '注册失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.fm-auth-form {
  display: flex;
  flex-direction: column;
  gap: var(--fm-space-4);
}

.fm-auth-form__title {
  margin: 0;
  font-size: var(--fm-fs-xl);
  font-weight: 600;
  color: var(--fm-text);
  letter-spacing: -0.02em;
}

.fm-auth-form__sub {
  margin: 4px 0 0;
  font-size: var(--fm-fs-sm);
  color: var(--fm-text-2);
}

.fm-auth-form__submit {
  width: 100%;
  margin-top: var(--fm-space-2);
}

.fm-auth-form__footer {
  text-align: center;
  font-size: var(--fm-fs-sm);
  color: var(--fm-text-2);
}

.fm-auth-form__link {
  color: var(--fm-accent);
  font-weight: 500;
  text-decoration: none;
  margin-left: 4px;
}

.fm-auth-form__link:hover {
  text-decoration: underline;
}
</style>

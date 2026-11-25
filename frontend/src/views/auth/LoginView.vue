<template>
  <div class="fm-auth-form">
    <div class="fm-auth-form__head">
      <h2 class="fm-auth-form__title">欢迎回来</h2>
      <p class="fm-auth-form__sub">登录到 FireMail</p>
    </div>

    <el-alert
      v-if="registeredSuccess"
      type="success"
      :closable="false"
      show-icon
      title="注册成功！请登录您的新账户。"
    />

    <el-alert
      v-if="autoLoginFailed"
      type="warning"
      :closable="false"
      show-icon
      title="自动登录失败，请手动登录"
    />

    <el-alert
      v-if="errorMessage"
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
          placeholder="请输入用户名"
          autocomplete="username"
          size="large"
        />
      </el-form-item>

      <el-form-item label="密码" prop="password">
        <el-input
          v-model="form.password"
          type="password"
          show-password
          placeholder="请输入密码"
          autocomplete="current-password"
          size="large"
          @keyup.enter="handleSubmit"
        />
      </el-form-item>

      <el-button
        type="primary"
        size="large"
        native-type="submit"
        :loading="auth.loading"
        class="fm-auth-form__submit"
      >
        {{ auth.loading ? '登录中…' : '登录' }}
      </el-button>
    </el-form>

    <div v-if="auth.allowRegister" class="fm-auth-form__footer">
      <span>还没有账号？</span>
      <router-link to="/register" class="fm-auth-form__link">立即注册</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const formRef = ref(null)
const errorMessage = ref('')

const form = reactive({
  username: String(route.query.username || ''),
  password: ''
})

const registeredSuccess = computed(
  () => route.query.registered === '1' && route.query.autologin !== 'failed'
)
const autoLoginFailed = computed(() => route.query.autologin === 'failed')

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

onMounted(() => {
  auth.clearError()
  auth.getConfig()
})

async function handleSubmit() {
  errorMessage.value = ''
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return

  try {
    await auth.login({
      username: form.username.trim(),
      password: form.password
    })
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect.startsWith('/') ? redirect : '/')
  } catch (err) {
    errorMessage.value =
      err?.response?.data?.error ||
      err?.response?.data?.message ||
      auth.error ||
      err?.message ||
      '登录失败，请检查用户名和密码'
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

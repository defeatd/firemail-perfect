<template>
  <div class="login-page">
    <!-- Animated background -->
    <div class="bg-gradient"></div>
    <div class="bg-shapes">
      <div class="shape shape-1"></div>
      <div class="shape shape-2"></div>
      <div class="shape shape-3"></div>
    </div>

    <!-- Login card -->
    <div class="login-card">
      <div class="login-header">
        <div class="logo-icon">
          <el-icon :size="32"><Message /></el-icon>
        </div>
        <h1 class="login-title">欢迎回来</h1>
        <p class="login-subtitle">登录到 FireMail 邮箱管理系统</p>
      </div>

      <el-alert
        v-if="error"
        :title="error"
        type="error"
        show-icon
        :closable="false"
        class="login-alert"
      />

      <el-alert
        v-if="successMessage"
        :title="successMessage"
        type="success"
        show-icon
        :closable="false"
        class="login-alert"
      />

      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        class="login-form"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            size="large"
            placeholder="请输入用户名"
            :prefix-icon="User"
            clearable
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            size="large"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            class="login-btn"
            :loading="loading"
            @click="handleLogin"
          >
            {{ loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-footer">
        <span class="footer-text">还没有账号?</span>
        <router-link :to="{ name: 'register' }" class="register-link">
          立即注册
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { useStore } from 'vuex';
import { useRouter, useRoute } from 'vue-router';
import { User, Lock, Message } from '@element-plus/icons-vue';

const store = useStore();
const router = useRouter();
const route = useRoute();

const loginFormRef = ref(null);
const loading = ref(false);
const error = ref('');
const successMessage = ref('');

const loginForm = reactive({
  username: '',
  password: ''
});

const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
};

onMounted(() => {
  if (route.params.registrationSuccess) {
    successMessage.value = '注册成功！请登录您的新账户。';
    if (route.params.loginAttemptFailed) {
      error.value = '自动登录失败，请手动登录';
    }
    if (route.params.username) {
      loginForm.username = route.params.username;
    }
  }
});

const handleLogin = async () => {
  if (!loginFormRef.value) return;

  await loginFormRef.value.validate(async (valid) => {
    if (!valid) return;

    loading.value = true;
    error.value = '';
    successMessage.value = '';

    try {
      await store.dispatch('auth/login', {
        username: loginForm.username,
        password: loginForm.password
      });
      const redirectPath = route.query.redirect || '/';
      router.push(redirectPath);
    } catch (err) {
      if (err.response?.data?.error) {
        error.value = err.response.data.error;
      } else if (err.message) {
        error.value = err.message;
      } else {
        error.value = '登录失败，请检查用户名和密码';
      }
    } finally {
      loading.value = false;
    }
  });
};
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  position: relative;
  overflow: hidden;
}

.bg-gradient {
  position: fixed;
  inset: 0;
  background: linear-gradient(145deg, #E8E2D4 0%, #D4C4A8 40%, #C4A974 70%, #A68B5B 100%);

  z-index: -2;
}

.bg-shapes {
  position: fixed;
  inset: 0;
  z-index: -1;
  overflow: hidden;
}

.shape {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  animation: float 20s infinite ease-in-out;
}

.shape-1 {
  width: 400px;
  height: 400px;
  top: -100px;
  left: -100px;
  animation-delay: 0s;
}

.shape-2 {
  width: 300px;
  height: 300px;
  bottom: -50px;
  right: -50px;
  animation-delay: -5s;
}

.shape-3 {
  width: 200px;
  height: 200px;
  top: 50%;
  left: 50%;
  animation-delay: -10s;
}

@keyframes float {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  33% { transform: translateY(-30px) rotate(5deg); }
  66% { transform: translateY(20px) rotate(-5deg); }
}

.login-card {
  width: 100%;
  max-width: 420px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-radius: 1.5rem;
  padding: 2.5rem;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  animation: slideUp 0.5s ease-out;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.login-header {
  text-align: center;
  margin-bottom: 2rem;
}

.logo-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 1rem;
  background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-light) 100%);
  border-radius: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.3);
}

.login-title {
  font-size: 1.75rem;
  font-weight: 700;
  color: #1E293B;
  margin: 0 0 0.5rem 0;
}

.login-subtitle {
  font-size: 0.95rem;
  color: #64748B;
  margin: 0;
}

.login-alert {
  margin-bottom: 1.5rem;
  border-radius: 0.75rem;
}

.login-form {
  margin-bottom: 1.5rem;
}

.login-form :deep(.el-input__wrapper) {
  border-radius: 0.75rem;
  padding: 0.25rem 0.75rem;
  box-shadow: 0 0 0 1px #E2E8F0;
  transition: all 0.25s ease;
}

.login-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--primary-color);
}

.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2), 0 0 0 1px var(--primary-color);
}

.login-form :deep(.el-form-item) {
  margin-bottom: 1.25rem;
}

.login-btn {
  width: 100%;
  height: 48px;
  font-size: 1rem;
  font-weight: 600;
  border-radius: 0.75rem;
  background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-light) 100%);
  border: none;
  transition: all 0.25s ease;
}

.login-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(99, 102, 241, 0.4);
}

.login-btn:active {
  transform: translateY(0);
}

.login-footer {
  text-align: center;
  padding-top: 1rem;
  border-top: 1px solid #E2E8F0;
}

.footer-text {
  color: #64748B;
  font-size: 0.95rem;
}

.register-link {
  color: var(--primary-color);
  font-weight: 600;
  text-decoration: none;
  margin-left: 0.5rem;
  transition: color 0.25s ease;
}

.register-link:hover {
  color: var(--primary-dark);
  text-decoration: underline;
}

@media (max-width: 480px) {
  .login-card {
    padding: 1.5rem;
    border-radius: 1.25rem;
  }

  .login-title {
    font-size: 1.5rem;
  }
}
</style>

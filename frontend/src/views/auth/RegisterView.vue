<template>
  <div class="register-page">
    <!-- Animated background -->
    <div class="bg-gradient"></div>
    <div class="bg-shapes">
      <div class="shape shape-1"></div>
      <div class="shape shape-2"></div>
      <div class="shape shape-3"></div>
    </div>

    <!-- Register card -->
    <div class="register-card">
      <div class="register-header">
        <div class="logo-icon">
          <el-icon :size="32"><UserFilled /></el-icon>
        </div>
        <h1 class="register-title">创建账户</h1>
        <p class="register-subtitle">注册 FireMail 邮箱管理系统</p>
      </div>

      <el-alert
        v-if="error"
        :title="error"
        type="error"
        show-icon
        :closable="false"
        class="register-alert"
      />

      <el-form
        ref="registerFormRef"
        :model="registerForm"
        :rules="registerRules"
        class="register-form"
        @submit.prevent="handleRegister"
      >
        <el-form-item prop="username">
          <el-input
            v-model="registerForm.username"
            size="large"
            placeholder="请输入用户名 (3-20个字符)"
            :prefix-icon="User"
            clearable
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="registerForm.password"
            type="password"
            size="large"
            placeholder="请输入密码 (至少8个字符)"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <el-form-item prop="confirmPassword">
          <el-input
            v-model="registerForm.confirmPassword"
            type="password"
            size="large"
            placeholder="请确认密码"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="handleRegister"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            class="register-btn"
            :loading="loading"
            :disabled="!registrationEnabled"
            @click="handleRegister"
          >
            {{ loading ? '注册中...' : '注 册' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="register-footer">
        <span class="footer-text">已有账号?</span>
        <router-link :to="{ name: 'login' }" class="login-link">
          立即登录
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { useStore } from 'vuex';
import { useRouter } from 'vue-router';
import { User, Lock, UserFilled } from '@element-plus/icons-vue';
import api from '@/services/api';

const store = useStore();
const router = useRouter();

const registerFormRef = ref(null);
const loading = ref(false);
const error = ref('');
const registrationEnabled = ref(true);

const registerForm = reactive({
  username: '',
  password: '',
  confirmPassword: ''
});

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== registerForm.password) {
    callback(new Error('两次输入的密码不一致'));
  } else {
    callback();
  }
};

const registerRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度应为3-20个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码长度至少为8个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
};

const checkRegistrationStatus = async () => {
  try {
    const response = await api.getConfig();
    if (response.data && response.data.allow_register === false) {
      registrationEnabled.value = false;
      error.value = '系统当前不允许注册新用户，请联系管理员';
    } else {
      registrationEnabled.value = true;
      error.value = '';
    }
  } catch (err) {
    registrationEnabled.value = true;
    error.value = '';
  }
};

const handleRegister = async () => {
  if (!registerFormRef.value) return;

  await registerFormRef.value.validate(async (valid) => {
    if (!valid) return;

    if (!registrationEnabled.value) {
      error.value = '系统当前不允许注册新用户，请联系管理员';
      return;
    }

    loading.value = true;
    error.value = '';

    try {
      const result = await store.dispatch('auth/registerAndLogin', {
        username: registerForm.username,
        password: registerForm.password
      });

      if (result.success) {
        router.push('/');
      } else {
        router.push({
          name: 'login',
          params: {
            registrationSuccess: true,
            loginAttemptFailed: true
          }
        });
      }
    } catch (err) {
      error.value = err.response?.data?.error || err.message || '注册失败，请稍后再试';
    } finally {
      loading.value = false;
    }
  });
};

onMounted(() => {
  checkRegistrationStatus();
});
</script>

<style scoped>
.register-page {
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
  right: -100px;
  animation-delay: 0s;
}

.shape-2 {
  width: 300px;
  height: 300px;
  bottom: -50px;
  left: -50px;
  animation-delay: -5s;
}

.shape-3 {
  width: 200px;
  height: 200px;
  top: 40%;
  right: 30%;
  animation-delay: -10s;
}

@keyframes float {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  33% { transform: translateY(-30px) rotate(5deg); }
  66% { transform: translateY(20px) rotate(-5deg); }
}

.register-card {
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

.register-header {
  text-align: center;
  margin-bottom: 2rem;
}

.logo-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 1rem;
  background: linear-gradient(135deg, #10B981 0%, #34D399 100%);
  border-radius: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 8px 20px rgba(16, 185, 129, 0.3);
}

.register-title {
  font-size: 1.75rem;
  font-weight: 700;
  color: #1E293B;
  margin: 0 0 0.5rem 0;
}

.register-subtitle {
  font-size: 0.95rem;
  color: #64748B;
  margin: 0;
}

.register-alert {
  margin-bottom: 1.5rem;
  border-radius: 0.75rem;
}

.register-form {
  margin-bottom: 1.5rem;
}

.register-form :deep(.el-input__wrapper) {
  border-radius: 0.75rem;
  padding: 0.25rem 0.75rem;
  box-shadow: 0 0 0 1px #E2E8F0;
  transition: all 0.25s ease;
}

.register-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #10B981;
}

.register-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2), 0 0 0 1px #10B981;
}

.register-form :deep(.el-form-item) {
  margin-bottom: 1.25rem;
}

.register-btn {
  width: 100%;
  height: 48px;
  font-size: 1rem;
  font-weight: 600;
  border-radius: 0.75rem;
  background: linear-gradient(135deg, #10B981 0%, #34D399 100%);
  border: none;
  transition: all 0.25s ease;
}

.register-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(16, 185, 129, 0.4);
}

.register-btn:active {
  transform: translateY(0);
}

.register-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.register-footer {
  text-align: center;
  padding-top: 1rem;
  border-top: 1px solid #E2E8F0;
}

.footer-text {
  color: #64748B;
  font-size: 0.95rem;
}

.login-link {
  color: #10B981;
  font-weight: 600;
  text-decoration: none;
  margin-left: 0.5rem;
  transition: color 0.25s ease;
}

.login-link:hover {
  color: #059669;
  text-decoration: underline;
}

@media (max-width: 480px) {
  .register-page {
    padding: 1rem;
  }

  .register-card {
    padding: 1.5rem;
    border-radius: 1.25rem;
  }

  .register-title {
    font-size: 1.5rem;
  }

  .logo-icon {
    width: 56px;
    height: 56px;
  }
}
</style>

<template>
  <div class="account-container">
    <div class="account-header">
      <h1>账户管理</h1>
    </div>
    
    <div class="account-section">
      <div class="account-info">
        <h2>个人信息</h2>
        <div class="info-row">
          <span class="info-label">用户名</span>
          <span class="info-value">{{ currentUser.username }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">账户类型</span>
          <span class="info-value">{{ currentUser.isAdmin ? '管理员' : '普通用户' }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">注册时间</span>
          <span class="info-value">{{ formatDate(currentUser.created_at) }}</span>
        </div>
      </div>
    </div>
    
    <div class="account-section">
      <h2>修改密码</h2>
      <div v-if="passwordMessage" :class="['alert', passwordMessage.type === 'success' ? 'alert-success' : 'alert-danger']">
        {{ passwordMessage.text }}
      </div>
      
      <form @submit.prevent="changePassword" class="password-form">
        <div class="form-group">
          <label for="currentPassword">当前密码</label>
          <input 
            type="password" 
            id="currentPassword" 
            v-model="passwordData.currentPassword" 
            class="form-control" 
            placeholder="请输入当前密码" 
            required
          />
        </div>
        
        <div class="form-group">
          <label for="newPassword">新密码</label>
          <input 
            type="password" 
            id="newPassword" 
            v-model="passwordData.newPassword" 
            class="form-control" 
            placeholder="请输入新密码" 
            required
          />
          <small class="form-text text-muted">密码长度应至少为6个字符</small>
        </div>
        
        <div class="form-group">
          <label for="confirmPassword">确认新密码</label>
          <input 
            type="password" 
            id="confirmPassword" 
            v-model="passwordData.confirmPassword" 
            class="form-control" 
            placeholder="请再次输入新密码" 
            required
          />
        </div>
        
        <div class="form-actions">
          <button type="submit" class="btn btn-primary" :disabled="passwordLoading || !passwordFormValid">
            <span v-if="passwordLoading">提交中...</span>
            <span v-else>更新密码</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script>
import { mapGetters, mapActions } from 'vuex';

export default {
  name: 'AccountView',
  data() {
    return {
      passwordData: {
        currentPassword: '',
        newPassword: '',
        confirmPassword: ''
      },
      passwordLoading: false,
      passwordMessage: null
    };
  },
  computed: {
    ...mapGetters('auth', ['currentUser']),
    passwordFormValid() {
      return this.passwordData.currentPassword.length > 0 && 
             this.passwordData.newPassword.length >= 6 && 
             this.passwordData.newPassword === this.passwordData.confirmPassword;
    }
  },
  methods: {
    ...mapActions('auth', ['changeUserPassword']),
    formatDate(dateString) {
      if (!dateString) return '未知';
      
      const date = new Date(dateString);
      return new Intl.DateTimeFormat('zh-CN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      }).format(date);
    },
    async changePassword() {
      // 表单验证
      if (!this.passwordFormValid) {
        if (this.passwordData.newPassword.length < 6) {
          this.passwordMessage = {
            type: 'error',
            text: '新密码长度应至少为6个字符'
          };
        } else if (this.passwordData.newPassword !== this.passwordData.confirmPassword) {
          this.passwordMessage = {
            type: 'error',
            text: '两次输入的新密码不一致'
          };
        }
        return;
      }
      
      this.passwordLoading = true;
      this.passwordMessage = null;
      
      try {
        await this.changeUserPassword({
          currentPassword: this.passwordData.currentPassword,
          newPassword: this.passwordData.newPassword
        });
        
        // 成功提示
        this.passwordMessage = {
          type: 'success',
          text: '密码已成功更新'
        };
        
        // 重置表单
        this.passwordData = {
          currentPassword: '',
          newPassword: '',
          confirmPassword: ''
        };
      } catch (error) {
        this.passwordMessage = {
          type: 'error',
          text: error.response?.data?.message || '密码更新失败，请检查当前密码是否正确'
        };
      } finally {
        this.passwordLoading = false;
      }
    }
  }
};
</script>

<style scoped>
.account-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.account-header {
  margin-bottom: 30px;
  border-bottom: 1px solid #eee;
  padding-bottom: 10px;
}

.account-header h1 {
  font-size: 28px;
  font-weight: 600;
  color: #333;
}

.account-section {
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  padding: 25px;
  margin-bottom: 30px;
}

.account-section h2 {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 20px;
  color: #333;
}

.account-info {
  margin-bottom: 20px;
}

.info-row {
  padding: 12px 0;
  display: flex;
  border-bottom: 1px solid #eee;
}

.info-row:last-child {
  border-bottom: none;
}

.info-label {
  flex: 0 0 120px;
  font-weight: 500;
  color: #666;
}

.info-value {
  flex: 1;
  color: #333;
}

.password-form {
  margin-top: 20px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
}

.form-control {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 16px;
  transition: border-color 0.3s;
}

.form-control:focus {
  border-color: #42b983;
  outline: none;
}

.form-text {
  display: block;
  margin-top: 5px;
  font-size: 12px;
}

.text-muted {
  color: #6c757d;
}

.btn {
  display: inline-block;
  padding: 10px 20px;
  font-size: 16px;
  font-weight: 500;
  text-align: center;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s, opacity 0.3s;
  border: none;
}

.btn-primary {
  background-color: #42b983;
  color: white;
}

.btn-primary:hover {
  background-color: #3aa876;
}

.btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.form-actions {
  margin-top: 30px;
}

.alert {
  padding: 12px;
  border-radius: 4px;
  margin-bottom: 20px;
}

.alert-success {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.alert-danger {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}
</style> 
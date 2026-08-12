<template>
  <div class="users-container">
    <div class="users-header">
      <h1>用户管理</h1>
      <div class="header-actions">
        <div class="registration-toggle">
          <span>注册功能：</span>
          <el-switch
            v-model="registrationEnabled"
            active-text="开启"
            inactive-text="关闭"
            @change="toggleRegistration"
          />
        </div>
        <button class="btn btn-primary" @click="showAddUserModal = true">添加用户</button>
      </div>
    </div>

    <div class="alert-container">
      <div v-if="message" :class="['alert', message.type === 'success' ? 'alert-success' : 'alert-danger']">
        {{ message.text }}
      </div>
    </div>

    <div class="users-list-container">
      <div v-if="loading" class="loading-spinner">
        <div class="spinner"></div>
        <p>加载中...</p>
      </div>

      <table v-else class="users-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>用户名</th>
            <th>类型</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="users.length === 0">
            <td colspan="5" class="text-center">暂无用户数据</td>
          </tr>
          <tr v-for="user in users" :key="user.id">
            <td>{{ user.id }}</td>
            <td>{{ user.username }}</td>
            <td>{{ user.is_admin ? '管理员' : '普通用户' }}</td>
            <td>{{ formatDate(user.created_at) }}</td>
            <td class="actions">
              <button
                class="btn btn-sm btn-warning"
                @click="openResetPasswordModal(user)"
                :disabled="user.id === currentUser.id"
              >
                重置密码
              </button>
              <button
                class="btn btn-sm btn-danger"
                @click="openDeleteUserModal(user)"
                :disabled="user.id === currentUser.id"
              >
                删除
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 添加用户模态框 -->
    <div v-if="showAddUserModal" class="modal-overlay">
      <div class="modal-container">
        <div class="modal-header">
          <h2>添加新用户</h2>
          <button class="modal-close" @click="showAddUserModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="addUserError" class="alert alert-danger">
            {{ addUserError }}
          </div>

          <form @submit.prevent="handleAddUser">
            <div class="form-group">
              <label for="newUsername">用户名</label>
              <input
                type="text"
                id="newUsername"
                v-model="newUser.username"
                class="form-control"
                placeholder="请输入用户名"
                required
              />
              <small class="form-text text-muted">用户名长度应为3-20个字符</small>
            </div>

            <div class="form-group">
              <label for="newPassword">密码</label>
              <input
                type="password"
                id="newPassword"
                v-model="newUser.password"
                class="form-control"
                placeholder="请输入密码"
                required
              />
              <small class="form-text text-muted">密码长度应至少为6个字符</small>
            </div>

            <div class="form-group">
              <label>
                <input type="checkbox" v-model="newUser.is_admin" /> 管理员权限
              </label>
            </div>

            <div class="form-actions">
              <button type="button" class="btn btn-secondary" @click="showAddUserModal = false">取消</button>
              <button type="submit" class="btn btn-primary" :disabled="addUserLoading || !newUserFormValid">
                <span v-if="addUserLoading">添加中...</span>
                <span v-else>添加用户</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- 重置密码模态框 -->
    <div v-if="showResetPasswordModal" class="modal-overlay">
      <div class="modal-container">
        <div class="modal-header">
          <h2>重置用户密码</h2>
          <button class="modal-close" @click="showResetPasswordModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="resetPasswordError" class="alert alert-danger">
            {{ resetPasswordError }}
          </div>

          <form @submit.prevent="handleResetPassword">
            <div class="form-group">
              <label for="newPasswordInput">新密码</label>
              <input
                type="password"
                id="newPasswordInput"
                v-model="resetPasswordData.newPassword"
                class="form-control"
                placeholder="请输入新密码"
                required
              />
              <small class="form-text text-muted">密码长度应至少为6个字符</small>
            </div>

            <div class="form-group">
              <label for="confirmPasswordInput">确认密码</label>
              <input
                type="password"
                id="confirmPasswordInput"
                v-model="resetPasswordData.confirmPassword"
                class="form-control"
                placeholder="请再次输入新密码"
                required
              />
            </div>

            <div class="form-actions">
              <button type="button" class="btn btn-secondary" @click="showResetPasswordModal = false">取消</button>
              <button type="submit" class="btn btn-primary" :disabled="resetPasswordLoading || !resetPasswordFormValid">
                <span v-if="resetPasswordLoading">重置中...</span>
                <span v-else>重置密码</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- 删除用户模态框 -->
    <div v-if="showDeleteUserModal" class="modal-overlay">
      <div class="modal-container">
        <div class="modal-header">
          <h2>删除用户</h2>
          <button class="modal-close" @click="showDeleteUserModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="deleteUserError" class="alert alert-danger">
            {{ deleteUserError }}
          </div>

          <p>您确定要删除用户 <strong>{{ selectedUser?.username }}</strong> 吗？</p>
          <p class="text-danger">此操作不可逆，用户所有数据将被永久删除。</p>

          <div class="form-actions">
            <button type="button" class="btn btn-secondary" @click="showDeleteUserModal = false">取消</button>
            <button
              type="button"
              class="btn btn-danger"
              @click="handleDeleteUser"
              :disabled="deleteUserLoading"
            >
              <span v-if="deleteUserLoading">删除中...</span>
              <span v-else>确认删除</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'UsersView',
  data() {
    return {
      users: [],
      loading: false,
      message: null,
      messageTimeout: null,
      registrationEnabled: false,

      // 当前用户
      currentUser: {
        id: null,
        username: '',
        is_admin: false
      },

      // 添加用户
      showAddUserModal: false,
      newUser: {
        username: '',
        password: '',
        is_admin: false
      },
      addUserLoading: false,
      addUserError: null,

      // 重置密码
      showResetPasswordModal: false,
      selectedUser: null,
      resetPasswordData: {
        newPassword: '',
        confirmPassword: ''
      },
      resetPasswordLoading: false,
      resetPasswordError: null,

      // 删除用户
      showDeleteUserModal: false,
      deleteUserLoading: false,
      deleteUserError: null
    };
  },
  computed: {
    newUserFormValid() {
      return this.newUser.username.length >= 3 &&
             this.newUser.username.length <= 20 &&
             this.newUser.password.length >= 6;
    },
    resetPasswordFormValid() {
      return this.resetPasswordData.newPassword.length >= 6 &&
             this.resetPasswordData.newPassword === this.resetPasswordData.confirmPassword;
    }
  },
  methods: {
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

    showMessage(type, text, duration = 3000) {
      this.message = { type, text };

      if (this.messageTimeout) {
        clearTimeout(this.messageTimeout);
      }

      this.messageTimeout = setTimeout(() => {
        this.message = null;
      }, duration);
    },

    async fetchUsers() {
      this.loading = true;

      try {
        // 使用api对象调用，确保使用正确的基础URL
        const response = await this.$store.dispatch('auth/getAllUsers');
        this.users = response;
      } catch (error) {
        this.showMessage('error', '获取用户列表失败: ' + (error.message || '未知错误'));
      } finally {
        this.loading = false;
      }
    },

    async fetchSystemConfig() {
      try {
        // 使用api对象调用，确保使用正确的基础URL
        const response = await this.$store.dispatch('auth/getConfig');
        if (response) {
          this.registrationEnabled = response.allow_register;
        }
      } catch (error) {
        console.error('获取系统配置失败', error);
      }
    },

    async toggleRegistration(value) {
      try {
        // 使用api对象调用，确保使用正确的基础URL
        await this.$store.dispatch('auth/toggleRegistration', value);
        this.showMessage('success', `已${value ? '开启' : '关闭'}注册功能`);
      } catch (error) {
        this.registrationEnabled = !value; // 恢复原状态
        this.showMessage('error', `${value ? '开启' : '关闭'}注册功能失败: ${error.message || '未知错误'}`);
      }
    },

    // 添加用户
    async handleAddUser() {
      if (!this.newUserFormValid) {
        if (this.newUser.username.length < 3 || this.newUser.username.length > 20) {
          this.addUserError = '用户名长度应为3-20个字符';
        } else if (this.newUser.password.length < 6) {
          this.addUserError = '密码长度应至少为6个字符';
        }
        return;
      }

      this.addUserLoading = true;
      this.addUserError = null;

      try {
        // 使用api对象调用，确保使用正确的基础URL
        await this.$store.dispatch('auth/createUser', {
          username: this.newUser.username,
          password: this.newUser.password,
          is_admin: this.newUser.is_admin
        });

        // 刷新用户列表
        await this.fetchUsers();

        // 关闭模态框并重置表单
        this.showAddUserModal = false;
        this.newUser = {
          username: '',
          password: '',
          is_admin: false
        };

        this.showMessage('success', '用户创建成功');
      } catch (error) {
        this.addUserError = error.message || '创建用户失败';
      } finally {
        this.addUserLoading = false;
      }
    },

    // 重置密码
    openResetPasswordModal(user) {
      this.selectedUser = user;
      this.resetPasswordData = {
        newPassword: '',
        confirmPassword: ''
      };
      this.resetPasswordError = null;
      this.showResetPasswordModal = true;
    },

    async handleResetPassword() {
      if (!this.resetPasswordFormValid) {
        if (this.resetPasswordData.newPassword.length < 6) {
          this.resetPasswordError = '密码长度应至少为6个字符';
        } else if (this.resetPasswordData.newPassword !== this.resetPasswordData.confirmPassword) {
          this.resetPasswordError = '两次输入的密码不一致';
        }
        return;
      }

      this.resetPasswordLoading = true;
      this.resetPasswordError = null;

      try {
        // 使用api对象调用，确保使用正确的基础URL
        await this.$store.dispatch('auth/resetUserPassword', {
          userId: this.selectedUser.id,
          newPassword: this.resetPasswordData.newPassword
        });

        // 关闭模态框
        this.showResetPasswordModal = false;
        this.selectedUser = null;

        this.showMessage('success', '用户密码重置成功');
      } catch (error) {
        this.resetPasswordError = error.message || '重置密码失败';
      } finally {
        this.resetPasswordLoading = false;
      }
    },

    // 删除用户
    openDeleteUserModal(user) {
      this.selectedUser = user;
      this.deleteUserError = null;
      this.showDeleteUserModal = true;
    },

    async handleDeleteUser() {
      this.deleteUserLoading = true;
      this.deleteUserError = null;

      try {
        // 使用api对象调用，确保使用正确的基础URL
        await this.$store.dispatch('auth/deleteUser', this.selectedUser.id);

        // 刷新用户列表
        await this.fetchUsers();

        // 关闭模态框
        this.showDeleteUserModal = false;
        this.selectedUser = null;

        this.showMessage('success', '用户删除成功');
      } catch (error) {
        this.deleteUserError = error.message || '删除用户失败';
      } finally {
        this.deleteUserLoading = false;
      }
    },

    // 获取当前用户信息
    async fetchCurrentUser() {
      try {
        // 使用api对象调用，确保使用正确的基础URL
        const response = await this.$store.dispatch('auth/getCurrentUser');
        if (response) {
          this.currentUser = {
            id: response.id,
            username: response.username,
            is_admin: response.isAdmin
          };
        }
      } catch (error) {
        console.error('获取当前用户信息失败:', error);
      }
    }
  },
  mounted() {
    this.fetchCurrentUser();
    this.fetchUsers();
    this.fetchSystemConfig();
  },
  beforeUnmount() {
    // 清除消息定时器
    if (this.messageTimeout) {
      clearTimeout(this.messageTimeout);
    }
  }
};
</script>

<style scoped>
/* 与全站 Claude 卡其主题一致 */
.users-container {
  min-height: calc(100vh - 160px);
  display: flex;
  flex-direction: column;
  padding: 1.25rem 1.5rem;
  max-width: 1200px;
  margin: 0 auto;
}

.users-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
  gap: 1rem;
  flex-wrap: wrap;
}

.users-header h1 {
  font-size: 1.35rem;
  font-weight: 500;
  color: var(--neutral-800, #2C2A24);
  margin: 0;
  letter-spacing: -0.02em;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.registration-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--neutral-600, #6B6558);
  font-size: 0.9rem;
}

.alert-container { margin-bottom: 1rem; }

.users-list-container {
  background: var(--card-bg, #FFFEFB);
  border-radius: 12px;
  border: 1px solid var(--border-color, #E5E0D2);
  box-shadow: none;
  padding: 0;
  overflow-x: auto;
}

.users-table {
  width: 100%;
  border-collapse: collapse;
}

.users-table th,
.users-table td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid var(--border-color-light, #EFEBE0);
  color: var(--neutral-800, #2C2A24);
  font-size: 0.9rem;
}

.users-table th {
  font-weight: 500;
  color: var(--neutral-500, #8A8374);
  background: var(--neutral-50, #FAF9F5);
  font-size: 0.8rem;
}

.users-table tbody tr:last-child td { border-bottom: none; }
.users-table tbody tr:hover { background: var(--neutral-50, #FAF9F5); }

.text-center {
  text-align: center;
  color: var(--neutral-500, #8A8374);
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  font-size: 0.875rem;
  font-weight: 500;
  text-align: center;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
  border: 1px solid transparent;
  line-height: 1.3;
}

.btn-sm {
  padding: 5px 12px;
  font-size: 0.8rem;
}

.btn-primary {
  background: var(--primary-color, #9A8458);
  border-color: var(--primary-color, #9A8458);
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-light, #B59A6A);
  border-color: var(--primary-light, #B59A6A);
}

.btn-secondary {
  background: var(--neutral-100, #F4F1E8);
  border-color: var(--border-color, #E5E0D2);
  color: var(--neutral-700, #4A463C);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--neutral-150, #EFEBE0);
}

.btn-warning {
  background: var(--primary-soft, #EDE6D6);
  border-color: var(--primary-muted, #C9B896);
  color: var(--primary-dark, #7A6844);
}

.btn-warning:hover:not(:disabled) {
  background: var(--primary-muted, #C9B896);
  color: var(--primary-dark, #7A6844);
}

.btn-danger {
  background: #F5E8E4;
  border-color: #E5C9C2;
  color: #B56B5C;
}

.btn-danger:hover:not(:disabled) {
  background: #EDD8D2;
  border-color: #B56B5C;
  color: #B56B5C;
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.alert {
  padding: 12px 14px;
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 0.9rem;
}

.alert-success {
  background: #E8F0E9;
  color: #5A7A5E;
  border: 1px solid #C9D9CB;
}

.alert-danger {
  background: #F8EBE7;
  color: #A65A4A;
  border: 1px solid #E8C9C0;
}

.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 0;
  color: var(--neutral-500, #8A8374);
}

.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid var(--neutral-200, #E5E0D2);
  border-top: 3px solid var(--primary-color, #9A8458);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 10px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(44, 42, 36, 0.4);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  padding: 1rem;
}

.modal-container {
  background: var(--card-bg, #FFFEFB);
  border-radius: 12px;
  width: 100%;
  max-width: 480px;
  max-height: 90vh;
  overflow-y: auto;
  border: 1px solid var(--border-color, #E5E0D2);
  box-shadow: 0 8px 28px rgba(44, 42, 36, 0.12);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-color-light, #EFEBE0);
}

.modal-header h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 500;
  color: var(--neutral-800, #2C2A24);
}

.modal-close {
  background: none;
  border: none;
  font-size: 22px;
  cursor: pointer;
  color: var(--neutral-500, #8A8374);
  line-height: 1;
  padding: 4px 8px;
  border-radius: 6px;
}

.modal-close:hover {
  background: var(--neutral-100, #F4F1E8);
  color: var(--neutral-800, #2C2A24);
}

.modal-body { padding: 18px; }

.form-group { margin-bottom: 16px; }

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-weight: 500;
  color: var(--neutral-700, #4A463C);
  font-size: 0.9rem;
}

.form-control {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-color, #E5E0D2);
  border-radius: 8px;
  font-size: 0.95rem;
  background: var(--card-bg, #FFFEFB);
  color: var(--neutral-800, #2C2A24);
  transition: border-color 0.15s ease;
  box-sizing: border-box;
}

.form-control:focus {
  border-color: var(--primary-color, #9A8458);
  outline: none;
  box-shadow: 0 0 0 3px rgba(154, 132, 88, 0.12);
}

.form-text {
  display: block;
  margin-top: 5px;
  font-size: 12px;
}

.text-muted { color: var(--neutral-500, #8A8374); }
.text-danger { color: #B56B5C; }

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 24px;
}

@media (max-width: 640px) {
  .users-header {
    flex-direction: column;
    align-items: flex-start;
  }
  .header-actions { width: 100%; }
}
</style>

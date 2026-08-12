<template>
  <div class="users-container">
    <h1>用户管理</h1>
    
    <div v-if="loading" class="loading">
      <p>加载中...</p>
    </div>
    
    <div v-else>
      <div class="toolbar">
        <button class="btn btn-primary" @click="fetchUsers">刷新列表</button>
        <button class="btn btn-success" @click="showAddUserModal = true">添加用户</button>
      </div>
      
      <table class="users-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>用户名</th>
            <th>类型</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="users.length === 0">
            <td colspan="4">暂无用户数据</td>
          </tr>
          <tr v-for="user in users" :key="user.id">
            <td>{{ user.id }}</td>
            <td>{{ user.username }}</td>
            <td>{{ user.is_admin ? '管理员' : '普通用户' }}</td>
            <td>
              <button class="btn btn-sm btn-warning" @click="openResetPasswordModal(user)">重置密码</button>
              <button class="btn btn-sm btn-danger" @click="confirmDeleteUser(user)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    
    <!-- 添加用户对话框 -->
    <div v-if="showAddUserModal" class="modal">
      <div class="modal-content">
        <h2>添加新用户</h2>
        <form @submit.prevent="addUser">
          <div class="form-group">
            <label>用户名:</label>
            <input type="text" v-model="newUser.username" required />
          </div>
          <div class="form-group">
            <label>密码:</label>
            <input type="password" v-model="newUser.password" required />
          </div>
          <div class="form-group">
            <label>
              <input type="checkbox" v-model="newUser.is_admin" /> 管理员
            </label>
          </div>
          <div class="buttons">
            <button type="button" class="btn btn-secondary" @click="cancelAdd">取消</button>
            <button type="submit" class="btn btn-primary">添加</button>
          </div>
        </form>
      </div>
    </div>
    
    <!-- 重置密码对话框 -->
    <div v-if="showResetModal" class="modal">
      <div class="modal-content">
        <h2>重置密码</h2>
        <form @submit.prevent="resetPassword">
          <div class="form-group">
            <label>新密码:</label>
            <input type="password" v-model="resetPasswordForm.password" required />
          </div>
          <div class="form-group">
            <label>确认密码:</label>
            <input type="password" v-model="resetPasswordForm.confirmPassword" required />
          </div>
          <div class="buttons">
            <button type="button" class="btn btn-secondary" @click="cancelReset">取消</button>
            <button type="submit" class="btn btn-primary">重置</button>
          </div>
        </form>
      </div>
    </div>
    
    <!-- 删除用户确认对话框 -->
    <div v-if="showDeleteModal" class="modal">
      <div class="modal-content">
        <h2>删除用户</h2>
        <p>您确定要删除用户 <strong>{{ selectedUser?.username }}</strong> 吗？</p>
        <p class="warning">此操作不可撤销！</p>
        <div class="buttons">
          <button class="btn btn-secondary" @click="cancelDelete">取消</button>
          <button class="btn btn-danger" @click="deleteUser">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'SimplifiedUsersView',
  data() {
    return {
      users: [],
      loading: false,
      error: null,
      
      // 添加用户
      showAddUserModal: false,
      newUser: {
        username: '',
        password: '',
        is_admin: false
      },
      
      // 重置密码
      showResetModal: false,
      resetPasswordForm: {
        password: '',
        confirmPassword: ''
      },
      
      // 删除用户
      showDeleteModal: false,
      selectedUser: null
    }
  },
  mounted() {
    this.fetchUsers()
  },
  methods: {
    async fetchUsers() {
      this.loading = true
      this.error = null
      
      try {
        const response = await fetch('/api/users', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        })
        
        if (!response.ok) {
          throw new Error(`获取用户列表失败: ${response.status}`)
        }
        
        this.users = await response.json()
      } catch (error) {
        this.error = error.message
        alert('获取用户列表失败: ' + error.message)
      } finally {
        this.loading = false
      }
    },
    
    // 添加用户
    cancelAdd() {
      this.showAddUserModal = false
      this.newUser = { username: '', password: '', is_admin: false }
    },
    
    async addUser() {
      if (!this.newUser.username || !this.newUser.password) {
        alert('请填写所有必填字段')
        return
      }
      
      try {
        const response = await fetch('/api/users', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          },
          body: JSON.stringify(this.newUser)
        })
        
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.error || '添加用户失败')
        }
        
        alert('添加用户成功')
        this.cancelAdd()
        this.fetchUsers()
      } catch (error) {
        alert('添加用户失败: ' + error.message)
      }
    },
    
    // 重置密码
    openResetPasswordModal(user) {
      this.selectedUser = user
      this.resetPasswordForm = { password: '', confirmPassword: '' }
      this.showResetModal = true
    },
    
    cancelReset() {
      this.showResetModal = false
      this.selectedUser = null
      this.resetPasswordForm = { password: '', confirmPassword: '' }
    },
    
    async resetPassword() {
      if (!this.resetPasswordForm.password) {
        alert('请输入新密码')
        return
      }
      
      if (this.resetPasswordForm.password !== this.resetPasswordForm.confirmPassword) {
        alert('两次输入的密码不一致')
        return
      }
      
      try {
        const response = await fetch(`/api/users/${this.selectedUser.id}/reset-password`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          },
          body: JSON.stringify({ new_password: this.resetPasswordForm.password })
        })
        
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.error || '重置密码失败')
        }
        
        alert('重置密码成功')
        this.cancelReset()
      } catch (error) {
        alert('重置密码失败: ' + error.message)
      }
    },
    
    // 删除用户
    confirmDeleteUser(user) {
      this.selectedUser = user
      this.showDeleteModal = true
    },
    
    cancelDelete() {
      this.showDeleteModal = false
      this.selectedUser = null
    },
    
    async deleteUser() {
      try {
        const response = await fetch(`/api/users/${this.selectedUser.id}`, {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        })
        
        if (!response.ok) {
          const data = await response.json()
          throw new Error(data.error || '删除用户失败')
        }
        
        alert('删除用户成功')
        this.cancelDelete()
        this.fetchUsers()
      } catch (error) {
        alert('删除用户失败: ' + error.message)
      }
    }
  }
}
</script>

<style scoped>
.users-container {
  padding: 1.25rem 1.5rem;
  max-width: 1000px;
  margin: 0 auto;
}

h1 {
  color: var(--neutral-800, #2C2A24);
  margin-bottom: 1rem;
  font-size: 1.35rem;
  font-weight: 500;
}

.toolbar {
  margin-bottom: 1rem;
  display: flex;
  gap: 10px;
}

.users-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1rem;
  background: var(--card-bg, #FFFEFB);
  border: 1px solid var(--border-color, #E5E0D2);
  border-radius: 12px;
  overflow: hidden;
}

.users-table th,
.users-table td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border-color-light, #EFEBE0);
  text-align: left;
  color: var(--neutral-800, #2C2A24);
}

.users-table th {
  background: var(--neutral-50, #FAF9F5);
  font-weight: 500;
  color: var(--neutral-500, #8A8374);
  font-size: 0.8rem;
}

.users-table tr:last-child td { border-bottom: none; }
.users-table tr:hover { background: var(--neutral-50, #FAF9F5); }

.btn {
  padding: 8px 14px;
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 500;
}

.btn-sm { padding: 5px 10px; font-size: 0.8rem; }

.btn-primary {
  background: var(--primary-color, #9A8458);
  border-color: var(--primary-color, #9A8458);
  color: #fff;
}

.btn-secondary {
  background: var(--neutral-100, #F4F1E8);
  border-color: var(--border-color, #E5E0D2);
  color: var(--neutral-700, #4A463C);
}

.btn-success {
  background: var(--primary-color, #9A8458);
  border-color: var(--primary-color, #9A8458);
  color: #fff;
}

.btn-warning {
  background: var(--primary-soft, #EDE6D6);
  border-color: var(--primary-muted, #C9B896);
  color: var(--primary-dark, #7A6844);
}

.btn-danger {
  background: #F5E8E4;
  border-color: #E5C9C2;
  color: #B56B5C;
}

.modal {
  position: fixed;
  inset: 0;
  background: rgba(44, 42, 36, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.modal-content {
  background: var(--card-bg, #FFFEFB);
  padding: 1.25rem;
  border-radius: 12px;
  min-width: 300px;
  max-width: 480px;
  width: 100%;
  border: 1px solid var(--border-color, #E5E0D2);
}

.form-group { margin-bottom: 14px; }
.form-group label {
  display: block;
  margin-bottom: 6px;
  font-weight: 500;
  color: var(--neutral-700, #4A463C);
}
.form-group input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-color, #E5E0D2);
  border-radius: 8px;
  box-sizing: border-box;
  background: var(--card-bg, #FFFEFB);
}
.form-group input:focus {
  outline: none;
  border-color: var(--primary-color, #9A8458);
}

.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}

.warning {
  color: #B56B5C;
  font-weight: 500;
}

.loading {
  text-align: center;
  padding: 20px;
  color: var(--neutral-500, #8A8374);
}
</style>

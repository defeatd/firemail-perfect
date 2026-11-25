import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { jwtDecode } from 'jwt-decode'
import api from '@/services/api'
import { safeGetStorage, safeSetStorage, safeRemoveStorage } from '@/utils/storage'

function restoreInitialAuth() {
  const saved = safeGetStorage('token', null)
  if (!saved) return { token: null, user: null }
  try {
    const decoded = jwtDecode(saved)
    if (decoded.exp && decoded.exp * 1000 > Date.now()) {
      api.setAuthHeader(saved)
      return {
        token: saved,
        user: {
          id: decoded.user_id,
          username: decoded.username,
          isAdmin: Boolean(decoded.is_admin)
        }
      }
    }
    safeRemoveStorage('token')
  } catch (_e) {
    safeRemoveStorage('token')
  }
  api.removeAuthHeader()
  return { token: null, user: null }
}

export const useAuthStore = defineStore('auth', () => {
  const initial = restoreInitialAuth()
  const token = ref(initial.token)
  const user = ref(initial.user)
  const loading = ref(false)
  const initialized = ref(!initial.token)
  const error = ref(null)
  const allowRegister = ref(true)

  const isAuthenticated = computed(() => Boolean(token.value))
  const isAdmin = computed(() => Boolean(user.value?.isAdmin))
  const currentUser = computed(() => user.value)

  function extractErrorMessage(err, fallback = '操作失败') {
    if (err?.fetchError?.isConnectionError) {
      return '无法连接到服务器，请检查网络或服务器状态'
    }
    if (err?.htmlResponse) {
      return '后端服务连接错误，请确保服务已启动'
    }
    return err?.response?.data?.error || err?.response?.data?.message || err?.message || fallback
  }

  function clearError() {
    error.value = null
  }

  async function login({ username, password }) {
    loading.value = true
    error.value = null
    try {
      const response = await api.login(username, password)
      const data = response.data
      if (
        !data?.token ||
        !data?.user ||
        data.user.id === undefined ||
        data.user.username === undefined ||
        data.user.is_admin === undefined
      ) {
        throw new Error('登录失败：服务器返回数据不完整')
      }

      const nextUser = {
        id: data.user.id,
        username: data.user.username,
        isAdmin: Boolean(data.user.is_admin)
      }
      safeSetStorage('token', data.token)
      api.setAuthHeader(data.token)
      token.value = data.token
      user.value = nextUser
      initialized.value = true
      return nextUser
    } catch (err) {
      safeRemoveStorage('token')
      api.removeAuthHeader()
      token.value = null
      user.value = null
      error.value = extractErrorMessage(err, '登录失败')
      throw err
    } finally {
      loading.value = false
    }
  }

  async function register({ username, password }) {
    loading.value = true
    error.value = null
    try {
      const response = await api.register(username, password)
      return response.data
    } catch (err) {
      error.value = extractErrorMessage(err, '注册失败')
      throw err
    } finally {
      loading.value = false
    }
  }

  async function registerAndLogin({ username, password }) {
    await register({ username, password })
    await new Promise((resolve) => setTimeout(resolve, 1000))
    try {
      const loggedIn = await login({ username, password })
      return { success: true, user: loggedIn }
    } catch (loginError) {
      return {
        success: false,
        error: loginError,
        message: '注册成功，但自动登录失败，请手动登录'
      }
    }
  }

  async function logout() {
    try {
      await api.logout()
    } catch (err) {
      console.error('登出请求失败:', err?.message)
    } finally {
      safeRemoveStorage('token')
      api.removeAuthHeader()
      token.value = null
      user.value = null
      error.value = null
    }
  }

  async function fetchCurrentUser() {
    if (!token.value) {
      initialized.value = true
      return null
    }
    loading.value = true
    try {
      const response = await api.getCurrentUser()
      const data = response.data
      user.value = {
        id: data.id,
        username: data.username,
        isAdmin: Boolean(data.is_admin)
      }
      return user.value
    } catch (err) {
      if (err?.response?.status === 401) {
        safeRemoveStorage('token')
        api.removeAuthHeader()
        token.value = null
        user.value = null
      }
      error.value = extractErrorMessage(err, '获取用户信息失败')
      return null
    } finally {
      loading.value = false
      initialized.value = true
    }
  }

  async function changePassword({ oldPassword, newPassword }) {
    loading.value = true
    error.value = null
    try {
      const response = await api.changePassword(oldPassword, newPassword)
      return response.data
    } catch (err) {
      error.value = extractErrorMessage(err, '修改密码失败')
      throw err
    } finally {
      loading.value = false
    }
  }

  async function getConfig() {
    try {
      const response = await api.getConfig()
      allowRegister.value = response.data?.allow_register !== false
      return response.data
    } catch (_err) {
      allowRegister.value = true
      return { allow_register: true }
    }
  }

  async function toggleRegistration(allow) {
    const response = await api.toggleRegistration(allow)
    allowRegister.value = Boolean(allow)
    return response.data
  }

  async function getAllUsers() {
    const response = await api.getAllUsers()
    return response.data
  }

  async function createUser(userData) {
    const response = await api.createUser(userData)
    return response.data
  }

  async function deleteUser(userId) {
    const response = await api.deleteUser(userId)
    return response.data
  }

  async function resetUserPassword({ userId, newPassword }) {
    const response = await api.resetUserPassword(userId, newPassword)
    return response.data
  }

  return {
    token,
    user,
    loading,
    initialized,
    error,
    allowRegister,
    isAuthenticated,
    isAdmin,
    currentUser,
    clearError,
    login,
    register,
    registerAndLogin,
    logout,
    fetchCurrentUser,
    changePassword,
    getConfig,
    toggleRegistration,
    getAllUsers,
    createUser,
    deleteUser,
    resetUserPassword
  }
})

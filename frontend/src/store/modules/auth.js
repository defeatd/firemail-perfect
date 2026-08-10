import api from '@/services/api'
import { jwtDecode } from 'jwt-decode'
import router from '@/router'

// 从localStorage获取保存的token
const token = localStorage.getItem('token')
let initialUser = null

// 如果有token，尝试解析用户信息
if (token) {
  try {
    const decoded = jwtDecode(token)
    if (decoded.exp * 1000 > Date.now()) {
      initialUser = {
        id: decoded.user_id,
        username: decoded.username,
        isAdmin: decoded.is_admin
      }
    } else {
      // token已过期，清除
      localStorage.removeItem('token')
    }
  } catch (e) {
    console.error('无效的token:', e)
    localStorage.removeItem('token')
  }
}

const state = {
  token: token || null,
  user: initialUser,
  loading: false,
  error: null,
  config: {
    allowRegister: false
  }
}

const mutations = {
  AUTH_REQUEST(state) {
    state.loading = true
    state.error = null
  },
  AUTH_SUCCESS(state, { token, user }) {
    state.loading = false
    state.token = token
    state.user = user
  },
  AUTH_ERROR(state, error) {
    state.loading = false
    state.error = error
  },
  LOGOUT(state) {
    state.token = null
    state.user = null
  },
  CLEAR_ERROR(state) {
    state.error = null
  },
  SET_CONFIG(state, config) {
    state.config = config
  }
}

// 异常处理方法，提供统一错误处理
const handleApiError = (commit, error) => {
  console.error('API错误:', error)

  // 检查是否为连接错误
  if (error.fetchError && error.fetchError.isConnectionError) {
    console.error('连接错误:', error.fetchError.message)
    commit('AUTH_ERROR', '无法连接到服务器，请检查网络或服务器状态')
  } else if (error.response) {
    commit('AUTH_ERROR', error.response.data.error || '操作失败')
  } else {
    commit('AUTH_ERROR', error.message || '未知错误')
  }

  throw error
}

const actions = {
  // 用户登录
  async login({ commit }, { username, password }) {
    commit('AUTH_REQUEST')
    try {
      console.log('登录请求开始，用户名:', username);
      const response = await api.login(username, password)

      // 额外检查：处理HTML响应
      if (typeof response.data === 'string' && response.data.includes('<!DOCTYPE html>')) {
        console.error('登录API返回了HTML而不是JSON，可能是后端服务未正确配置');
        throw new Error('登录失败：后端服务返回了HTML而不是JSON');
      }

      // 验证响应数据格式
      if (!response.data) {
        throw new Error('服务器响应数据格式错误')
      }

      const token = response.data.token
      if (!token) {
        throw new Error('登录失败：缺少令牌')
      }

      // 检查user对象是否存在
      if (!response.data.user) {
        console.error('登录响应中缺少user对象:', response.data)
        throw new Error('登录失败：服务器返回数据不完整')
      }

      // 检查user对象是否包含所需属性
      if (response.data.user.id === undefined ||
          response.data.user.username === undefined ||
          response.data.user.is_admin === undefined) {
        console.error('登录响应中user对象缺少必要属性:', response.data.user)
        throw new Error('登录失败：用户数据不完整')
      }

      const user = {
        id: response.data.user.id,
        username: response.data.user.username,
        isAdmin: response.data.user.is_admin
      }

      console.log('登录成功，用户信息:', user, '管理员状态:', user.isAdmin, '原始数据:', response.data.user)

      // 保存token到localStorage
      localStorage.setItem('token', token)

      // 更新API请求头
      api.setAuthHeader(token)

      commit('AUTH_SUCCESS', { token, user })
      console.log('登录成功:', user.username);

      return user
    } catch (error) {
      console.error('登录失败:', error);
      localStorage.removeItem('token')

      // 特殊处理HTML响应错误
      if (error.htmlResponse || (error.message && error.message.includes('HTML'))) {
        commit('AUTH_ERROR', '后端服务连接错误，请确保服务已启动');
        throw new Error('登录失败：后端服务连接错误');
      }

      handleApiError(commit, error)
    }
  },

  // 用户注册
  async register({ commit }, { username, password }) {
    commit('AUTH_REQUEST');
    try {
      console.log('发送注册请求:', username);
      const response = await api.register(username, password);
      commit('CLEAR_ERROR');

      console.log('注册成功，返回数据:', response.data);
      return response.data;
    } catch (error) {
      console.error('注册失败:', error);
      commit('AUTH_ERROR', error.response?.data?.error || '注册失败');
      throw error;
    }
  },

  // 注册后自动登录
  async registerAndLogin({ dispatch, commit }, { username, password }) {
    try {
      // 先进行注册
      await dispatch('register', { username, password });

      // 注册成功后等待一秒再尝试登录，给后端处理时间
      console.log('注册成功，准备自动登录...');
      await new Promise(resolve => setTimeout(resolve, 1000));

      // 尝试登录
      try {
        const user = await dispatch('login', { username, password });
        console.log('自动登录成功:', user.username);
        return { success: true, user };
      } catch (loginError) {
        console.error('自动登录失败:', loginError);
        // 自动登录失败，但注册成功了
        return {
          success: false,
          error: loginError,
          message: '注册成功，但自动登录失败，请手动登录'
        };
      }
    } catch (error) {
      console.error('注册过程失败:', error);
      throw error; // 注册失败，向上传递错误
    }
  },

  // 用户登出
  async logout({ commit }) {
    try {
      await api.logout()
    } catch (e) {
      console.error('登出API调用失败:', e)
    }

    localStorage.removeItem('token')
    api.removeAuthHeader()
    commit('LOGOUT')

    // 重定向到登录页
    if (router.currentRoute.value.meta.requiresAuth) {
      router.push('/login')
    }
  },

  // 获取当前用户信息
  async getCurrentUser({ commit, state }) {
    if (!state.token) return null

    commit('AUTH_REQUEST')
    try {
      const response = await api.getCurrentUser()
      const user = {
        id: response.data.id,
        username: response.data.username,
        isAdmin: response.data.is_admin
      }
      console.log('获取当前用户信息成功:', user.username, '管理员状态:', user.isAdmin, '原始数据:', response.data)
      commit('AUTH_SUCCESS', { token: state.token, user })
      return user
    } catch (error) {
      // 如果令牌无效，登出用户
      if (error.response?.status === 401) {
        localStorage.removeItem('token')
        commit('LOGOUT')
        router.push('/login')
      }
      handleApiError(commit, error)
    }
  },

  // 修改密码
  async changePassword({ commit }, { oldPassword, newPassword }) {
    commit('AUTH_REQUEST')
    try {
      const response = await api.changePassword(oldPassword, newPassword)
      commit('CLEAR_ERROR')
      return response.data
    } catch (error) {
      commit('AUTH_ERROR', error.response?.data?.error || '修改密码失败')
      throw error
    }
  },

  // 用户管理（管理员功能）
  async getAllUsers({ commit, state }) {
    try {
      const response = await api.getAllUsers();
      return response.data;
    } catch (error) {
      console.error('获取用户列表失败:', error);
      throw error;
    }
  },

  async createUser({ commit, state }, userData) {
    try {
      const response = await api.createUser(userData);
      return response.data;
    } catch (error) {
      console.error('创建用户失败:', error);
      throw error;
    }
  },

  async deleteUser({ commit, state }, userId) {
    try {
      const response = await api.deleteUser(userId);
      return response.data;
    } catch (error) {
      console.error('删除用户失败:', error);
      throw error;
    }
  },

  async resetUserPassword({ commit, state }, { userId, newPassword }) {
    try {
      const response = await api.resetUserPassword(userId, newPassword);
      return response.data;
    } catch (error) {
      console.error('重置用户密码失败:', error);
      throw error;
    }
  },

  // 切换注册功能
  async toggleRegistration({ commit }, allow) {
    try {
      const response = await api.toggleRegistration(allow);
      return response.data;
    } catch (error) {
      console.error('切换注册功能失败:', error);
      throw error;
    }
  },

  // 清除认证错误
  clearError({ commit }) {
    commit('CLEAR_ERROR')
  },

  // 获取系统配置
  async getConfig({ commit }) {
    try {
      const response = await api.getConfig();
      console.log('获取系统配置成功:', response.data);

      // 只有明确设置为false时才禁用注册
      const allowRegister = response.data && response.data.allow_register !== false;

      commit('SET_CONFIG', {
        allowRegister: allowRegister
      });
      return response.data;
    } catch (error) {
      console.error('获取系统配置失败:', error);

      // 检查是否为连接错误
      if (error.fetchError && error.fetchError.isConnectionError) {
        console.warn('无法连接到服务器，默认允许注册');
      }

      // 默认设置为允许注册，防止配置获取失败时无法注册
      commit('SET_CONFIG', { allowRegister: true });
      return { allow_register: true };
    }
  }
}

const getters = {
  isAuthenticated: state => !!state.token,
  currentUser: state => state.user,
  isAdmin: state => state.user?.isAdmin || false,
  authError: state => state.error,
  authLoading: state => state.loading,
  registrationEnabled: state => state.config.allowRegister
}

export default {
  namespaced: true,
  state,
  mutations,
  actions,
  getters
}
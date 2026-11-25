import axios from 'axios'
import { safeGetStorage, safeRemoveStorage } from '@/utils/storage'

const getBaseUrl = () => {
  if (typeof window !== 'undefined' && window.API_URL) {
    const raw = String(window.API_URL).trim()
    if (raw) {
      return raw.endsWith('/api') ? raw : `${raw}/api`
    }
  }
  return '/api'
}

const api = axios.create({
  baseURL: getBaseUrl(),
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const isEmailTokenReauth = error.response.data?.need_reauth === true
      if (error.response.status === 401 && !isEmailTokenReauth) {
        safeRemoveStorage('token')
        delete api.defaults.headers.common.Authorization
        if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      }
    } else if (error.request) {
      const errorMessage = '无法连接到服务器，请检查后端服务是否启动'
      error.response = { data: { message: errorMessage, error: 'Failed to fetch' } }
      const fetchError = new Error(errorMessage)
      fetchError.name = 'fetchError'
      fetchError.isConnectionError = true
      error.fetchError = fetchError
    } else {
      error.response = { data: { message: error.message || '请求出错' } }
    }
    return Promise.reject(error)
  }
)

export const setAuthHeader = (token) => {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`
  }
}

export const removeAuthHeader = () => {
  delete api.defaults.headers.common.Authorization
}

const parseFilenameFromDisposition = (header) => {
  if (!header) return 'attachment'
  const utf8Match = header.match(/filename\*\s*=\s*UTF-8''([^;\n]+)/i)
  if (utf8Match && utf8Match[1]) {
    try {
      return decodeURIComponent(utf8Match[1].trim())
    } catch (_e) {
      return utf8Match[1].trim()
    }
  }
  const plainMatch = header.match(/filename\s*=\s*"?([^";\n]+)"?/i)
  return plainMatch && plainMatch[1] ? plainMatch[1].trim() : 'attachment'
}

const apiMethods = {
  getStats: () => api.get('/stats'),

  health: () => api.get('/health'),

  getConfig(retryCount = 0, maxRetries = 2) {
    return api.get('/config').catch((error) => {
      const isNetworkError = !error.response && Boolean(error.request)
      if (isNetworkError && retryCount < maxRetries) {
        const retryDelay = Math.min(1000 * Math.pow(2, retryCount), 4000)
        return new Promise((resolve) => {
          setTimeout(() => resolve(this.getConfig(retryCount + 1, maxRetries)), retryDelay)
        })
      }
      return Promise.resolve({
        data: { allow_register: true }
      })
    })
  },

  toggleRegistration: (allow) => api.post('/admin/config/registration', { allow }),

  login: (username, password) =>
    api.post('/auth/login', { username, password }).then((response) => {
      if (typeof response.data === 'string' && response.data.includes('<!DOCTYPE html>')) {
        const err = new Error('登录失败：收到HTML响应，请检查后端服务配置')
        err.htmlResponse = true
        return Promise.reject(err)
      }
      if (!response.data?.token) {
        return Promise.reject(new Error('登录失败：响应缺少token'))
      }
      if (!response.data?.user) {
        return Promise.reject(new Error('登录失败：响应缺少用户信息'))
      }
      return response
    }),

  logout: () => api.post('/auth/logout'),

  register: (username, password) => api.post('/auth/register', { username, password }),

  getCurrentUser: () => api.get('/auth/user'),

  changePassword: (oldPassword, newPassword) =>
    api.post('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword
    }),

  getAllUsers: () => api.get('/users'),
  createUser: (userData) => api.post('/users', userData),
  deleteUser: (userId) => api.delete(`/users/${userId}`),
  resetUserPassword: (userId, newPassword) =>
    api.post(`/users/${userId}/reset-password`, { new_password: newPassword }),

  importEmails: (payloadOrData, mailType = 'outlook') => {
    const body =
      payloadOrData && typeof payloadOrData === 'object'
        ? {
            data: payloadOrData.data,
            mail_type: payloadOrData.mail_type ?? payloadOrData.mailType ?? 'outlook',
            separator: payloadOrData.separator ?? 'auto',
            on_duplicate: payloadOrData.on_duplicate ?? payloadOrData.onDuplicate ?? 'skip',
            verify: payloadOrData.verify ?? true
          }
        : {
            data: payloadOrData,
            mail_type: mailType,
            separator: 'auto',
            on_duplicate: 'skip',
            verify: true
          }
    return api.post('/emails/import', body, { timeout: 60000 })
  },

  getImportJob: (id) => api.get(`/import_jobs/${id}`),

  cancelImportJob: (id) => api.post(`/import_jobs/${id}/cancel`),

  refreshEmailToken: (id) =>
    api.post(`/emails/${id}/refresh_token`, {}, { timeout: 60000 }),

  batchRefreshTokens: (ids) =>
    api.post('/emails/batch_refresh_token', { email_ids: ids }),

  getTokenKeeperStatus: () => api.get('/token_keeper/status'),

  startEmailDeviceCode: (emailId, payload = {}) =>
    api.post(`/emails/${emailId}/oauth/device/start`, payload),

  startDeviceCodeAdd: (payload) => api.post('/oauth/device/start', payload),

  pollDeviceCode: (sessionId) => api.post(`/oauth/device/${sessionId}/poll`),

  search: (query, searchIn = []) =>
    api.post('/search', { query, search_in: searchIn }),

  emails: {
    getAll: () => api.get('/emails').then((res) => res.data),
    getPassword: (emailId) => api.get(`/emails/${emailId}/password`).then((res) => res.data),
    getRecords: (emailId) => api.get(`/emails/${emailId}/mail_records`).then((res) => res.data),
    add: (emailData) => api.post('/emails', emailData),
    update: (emailId, emailData) => api.put(`/emails/${emailId}`, emailData),
    toggleRealtime: (emailId, enable) =>
      api.post(`/emails/${emailId}/realtime`, { enable: Boolean(enable) }),
    check: (emailIds) => {
      if (Array.isArray(emailIds) && emailIds.length === 1) {
        return api.post(`/emails/${emailIds[0]}/check`, {}, { timeout: 300000 })
      }
      return api.post('/emails/batch_check', { email_ids: emailIds })
    },
    delete: (emailIds) => {
      if (Array.isArray(emailIds) && emailIds.length === 1) {
        return api.delete(`/emails/${emailIds[0]}`)
      }
      return api.post('/emails/batch_delete', { email_ids: emailIds })
    },
    uploadMailFile: (emailId, file) => {
      const formData = new FormData()
      formData.append('file', file)
      return api.post(`/emails/${emailId}/upload_email_file`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000
      })
    }
  },

  admin: {
    startRealtime: (interval = 60) =>
      api.post('/email/start_real_time_check', { check_interval: interval }),
    stopRealtime: () => api.post('/email/stop_real_time_check')
  },

  mail: {
    attachments: (mailId) =>
      api.get(`/mail_records/${mailId}/attachments`).then((res) => res.data),
    downloadAttachment: (attachmentId) =>
      api
        .get(`/attachments/${attachmentId}/download`, {
          responseType: 'blob',
          timeout: 120000
        })
        .then((res) => ({
          blob: res.data,
          filename: parseFilenameFromDisposition(res.headers?.['content-disposition'])
        }))
  },

  setAuthHeader,
  removeAuthHeader
}

const initialToken = safeGetStorage('token', null)
if (initialToken) {
  setAuthHeader(initialToken)
}

export default apiMethods

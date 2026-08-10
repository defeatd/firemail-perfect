import api from '@/services/api'
import WebSocketService from '@/services/websocket'

export const useEmailsStore = {
  state: () => ({
    emails: [],
    loading: false,
    currentEmail: null,
    mailRecords: {},
    emailProgress: {}
  }),

  mutations: {
    SET_EMAILS(state, emails) {
      state.emails = emails;
    },
    SET_LOADING(state, status) {
      state.loading = status;
    },
    SET_CURRENT_EMAIL(state, email) {
      state.currentEmail = email;
    },
    ADD_EMAIL(state, email) {
      state.emails.push(email);
    },
    UPDATE_EMAIL(state, updatedEmail) {
      const index = state.emails.findIndex(email => email.id === updatedEmail.id);
      if (index !== -1) {
        state.emails.splice(index, 1, updatedEmail);
      }
    },
    REMOVE_EMAIL(state, id) {
      state.emails = state.emails.filter(email => email.id !== id);
    },
    REMOVE_EMAILS(state, ids) {
      state.emails = state.emails.filter(email => !ids.includes(email.id));
    },
    SET_MAIL_RECORDS(state, { emailId, records }) {
      state.mailRecords = {
        ...state.mailRecords,
        [emailId]: records
      };
    },
    UPDATE_EMAIL_PROGRESS(state, { id, progress, message }) {
      state.emailProgress = {
        ...state.emailProgress,
        [id]: { progress, message }
      };
    }
  },

  actions: {
    // 获取所有邮箱
    async fetchAllEmails({ commit }) {
      commit('SET_LOADING', true);
      try {
        // 首先尝试使用WebSocket获取
        if (WebSocketService.isConnected) {
          WebSocketService.getEmails();
        } else {
          // 如果WebSocket未连接，则使用API
          const response = await api.getAllEmails();
          if (response && response.data) {
            commit('SET_EMAILS', response.data);
          } else {
            console.warn('API未返回有效的邮箱数据');
            commit('SET_EMAILS', []);
          }
        }
      } catch (error) {
        console.error('获取邮箱列表失败:', error);
        // 设置空数组防止进一步错误
        commit('SET_EMAILS', []);
        throw error;
      } finally {
        commit('SET_LOADING', false);
      }
    },

    // 添加新邮箱
    async addEmail({ commit }, { email, password, clientId, refreshToken }) {
      try {
        if (WebSocketService.isConnected) {
          return WebSocketService.addEmail(email, password, clientId, refreshToken);
        } else {
          const response = await api.post('/emails', {
            email,
            password,
            client_id: clientId,
            refresh_token: refreshToken
          });
          commit('ADD_EMAIL', response.data);
          return response.data;
        }
      } catch (error) {
        console.error('添加邮箱失败:', error);
        throw error;
      }
    },

    // 删除邮箱
    async deleteEmail({ commit }, id) {
      try {
        if (WebSocketService.isConnected) {
          return WebSocketService.deleteEmails([id]);
        } else {
          await api.delete(`/emails/${id}`);
          commit('REMOVE_EMAIL', id);
        }
      } catch (error) {
        console.error('删除邮箱失败:', error);
        throw error;
      }
    },

    // 批量删除邮箱
    async batchDeleteEmails({ commit }, ids) {
      try {
        if (WebSocketService.isConnected) {
          return WebSocketService.deleteEmails(ids);
        } else {
          await api.post('/emails/batch-delete', { email_ids: ids });
          commit('REMOVE_EMAILS', ids);
        }
      } catch (error) {
        console.error('批量删除邮箱失败:', error);
        throw error;
      }
    },

    // 检查邮箱
    async checkEmail({ commit }, id) {
      try {
        if (WebSocketService.isConnected) {
          return WebSocketService.checkEmails([id]);
        } else {
          await api.post(`/emails/${id}/check`);
        }
      } catch (error) {
        console.error('检查邮箱失败:', error);
        throw error;
      }
    },

    // 批量检查邮箱
    async batchCheckEmails({ commit }, ids) {
      try {
        if (WebSocketService.isConnected) {
          return WebSocketService.checkEmails(ids);
        } else {
          await api.post('/emails/batch-check', { email_ids: ids });
        }
      } catch (error) {
        console.error('批量检查邮箱失败:', error);
        throw error;
      }
    },

    // 导入邮箱（HTTP + 结构化失败详情）
    async importEmails({ commit }, payload) {
      try {
        const data = typeof payload === 'string' ? payload : payload?.data || ''
        const mailType =
          (typeof payload === 'object' && (payload.mail_type || payload.mailType)) ||
          'outlook'
        const response = await api.post('/emails/import', {
          data,
          mail_type: mailType,
          validate: true
        })
        return response.data
      } catch (error) {
        console.error('导入邮箱失败:', error)
        throw error
      }
    },

    // 获取邮件记录
    async getMailRecords({ commit }, emailId) {
      try {
        if (WebSocketService.isConnected) {
          WebSocketService.getMailRecords(emailId);
        } else {
          const response = await api.get(`/emails/${emailId}/records`);
          commit('SET_MAIL_RECORDS', {
            emailId,
            records: response.data
          });
        }
      } catch (error) {
        console.error('获取邮件记录失败:', error);
        throw error;
      }
    }
  },

  getters: {
    emails: state => state.emails,
    loading: state => state.loading,
    currentEmail: state => state.currentEmail,
    mailRecords: (state) => (id) => state.mailRecords[id] || [],
    emailProgress: (state) => (id) => state.emailProgress[id] || { progress: 0, message: '' }
  },

  namespaced: true
}

export default useEmailsStore 
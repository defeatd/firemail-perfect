// 生成唯一ID
const generateId = () => {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
};

const state = {
  notifications: []
};

const mutations = {
  ADD_NOTIFICATION(state, notification) {
    state.notifications.push(notification);
  },
  REMOVE_NOTIFICATION(state, id) {
    state.notifications = state.notifications.filter(notification => notification.id !== id);
  },
  CLEAR_NOTIFICATIONS(state) {
    state.notifications = [];
  }
};

const actions = {
  // 添加通知
  addNotification({ commit, dispatch }, { message, type = 'info', timeout = 5000 }) {
    const id = generateId();
    const notification = {
      id,
      message,
      type,
      timestamp: Date.now()
    };
    
    commit('ADD_NOTIFICATION', notification);
    
    // 自动移除通知
    if (timeout > 0) {
      setTimeout(() => {
        dispatch('removeNotification', id);
      }, timeout);
    }
    
    return id;
  },
  
  // 移除指定通知
  removeNotification({ commit }, id) {
    commit('REMOVE_NOTIFICATION', id);
  },
  
  // 清除所有通知
  clearNotifications({ commit }) {
    commit('CLEAR_NOTIFICATIONS');
  },
  
  // 添加不同类型的通知的快捷方法
  addSuccessNotification({ dispatch }, message) {
    return dispatch('addNotification', { message, type: 'success' });
  },
  
  addErrorNotification({ dispatch }, message) {
    return dispatch('addNotification', { message, type: 'error' });
  },
  
  addInfoNotification({ dispatch }, message) {
    return dispatch('addNotification', { message, type: 'info' });
  },
  
  addWarningNotification({ dispatch }, message) {
    return dispatch('addNotification', { message, type: 'warning' });
  }
};

const getters = {
  notifications: state => state.notifications
};

export default {
  namespaced: true,
  state,
  mutations,
  actions,
  getters
}; 
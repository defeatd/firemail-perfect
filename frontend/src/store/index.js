import { createStore } from 'vuex'
import auth from './modules/auth'
import notifications from './modules/notifications'
import emails from './modules/emails'

export default createStore({
  state: {
    websocketConnected: false,
    checkingEmails: []
  },
  getters: {
    websocketConnected: state => state.websocketConnected,
    isCheckingEmail: state => id => state.checkingEmails.includes(id)
  },
  mutations: {
    SET_WEBSOCKET_CONNECTED(state, status) {
      state.websocketConnected = status;
    },
    ADD_CHECKING_EMAIL(state, id) {
      if (!state.checkingEmails.includes(id)) {
        state.checkingEmails.push(id);
      }
    },
    REMOVE_CHECKING_EMAIL(state, id) {
      state.checkingEmails = state.checkingEmails.filter(emailId => emailId !== id);
    }
  },
  actions: {
    setWebsocketConnected({ commit }, status) {
      commit('SET_WEBSOCKET_CONNECTED', status);
    },
    
    addCheckingEmail({ commit }, id) {
      commit('ADD_CHECKING_EMAIL', id);
    },
    
    removeCheckingEmail({ commit }, id) {
      commit('REMOVE_CHECKING_EMAIL', id);
    }
  },
  modules: {
    auth,
    notifications,
    emails
  }
}) 
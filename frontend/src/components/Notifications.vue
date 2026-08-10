<template>
  <div class="notifications-container">
    <transition-group name="notification">
      <div 
        v-for="notification in notifications" 
        :key="notification.id" 
        :class="['notification', `notification-${notification.type}`]"
      >
        <span class="notification-message">{{ notification.message }}</span>
        <el-icon class="notification-close" @click="removeNotification(notification.id)">
          <Close />
        </el-icon>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useStore } from 'vuex';
import { Close } from '@element-plus/icons-vue';

const store = useStore();
const notifications = computed(() => store.state.notifications.notifications);

const removeNotification = (id) => {
  store.dispatch('notifications/removeNotification', id);
};
</script>

<style scoped>
.notifications-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
  width: 300px;
}

.notification {
  margin-bottom: 10px;
  padding: 15px;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  display: flex;
  justify-content: space-between;
  align-items: center;
  animation: slide-in 0.3s ease-out forwards;
}

.notification-success {
  background-color: #d4edda;
  color: #155724;
  border-left: 4px solid #28a745;
}

.notification-error {
  background-color: #f8d7da;
  color: #721c24;
  border-left: 4px solid #dc3545;
}

.notification-info {
  background-color: #d1ecf1;
  color: #0c5460;
  border-left: 4px solid #17a2b8;
}

.notification-warning {
  background-color: #fff3cd;
  color: #856404;
  border-left: 4px solid #ffc107;
}

.notification-message {
  flex: 1;
}

.notification-close {
  cursor: pointer;
  color: inherit;
  opacity: 0.7;
  margin-left: 8px;
  font-size: 18px;
}

.notification-close:hover {
  opacity: 1;
}

/* 通知动画 */
.notification-enter-active {
  transition: all 0.3s ease-out;
}

.notification-leave-active {
  transition: all 0.3s ease-in;
}

.notification-enter-from, 
.notification-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

@keyframes slide-in {
  0% {
    transform: translateX(100%);
    opacity: 0;
  }
  100% {
    transform: translateX(0);
    opacity: 1;
  }
}
</style> 
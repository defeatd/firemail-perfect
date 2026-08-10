// 添加WebSocket消息类型的常量
const MessageTypes = {
  // 认证相关
  AUTHENTICATE: 'authenticate',
  AUTH_RESULT: 'auth_result',
  CONNECTION_ESTABLISHED: 'connection_established',

  // 邮箱操作
  GET_ALL_EMAILS: 'get_all_emails',    // 获取所有邮箱
  CHECK_EMAILS: 'check_emails',         // 批量检查邮箱
  DELETE_EMAILS: 'delete_emails',       // 批量删除邮箱
  ADD_EMAIL: 'add_email',               // 添加单个邮箱
  GET_MAIL_RECORDS: 'get_mail_records', // 获取邮件记录

  // 批量导入
  IMPORT_EMAILS: 'import_emails',       // 批量导入邮箱

  // 响应消息
  EMAILS_LIST: 'emails_list',          // 邮箱列表
  CHECK_PROGRESS: 'check_progress',    // 检查进度
  EMAILS_IMPORTED: 'emails_imported',  // 邮箱已导入
  EMAILS_DELETED: 'emails_deleted',    // 邮箱已删除
  EMAIL_ADDED: 'email_added',          // 邮箱已添加
  MAIL_RECORDS: 'mail_records',        // 邮件记录

  // 通知消息
  INFO: 'info',                        // 信息通知
  SUCCESS: 'success',                  // 成功通知
  WARNING: 'warning',                  // 警告通知
  ERROR: 'error'                       // 错误通知
};

class WebSocketService {
  constructor() {
    this.socket = null;
    this.isConnected = false;
    this.isAuthenticated = false; // 添加认证状态追踪
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectTimeoutId = null;
    this.baseDelay = 1000; // 1秒
    this.messageHandlers = {};
    this.connectHandlers = [];
    this.disconnectHandlers = [];
    this.authSuccessHandlers = []; // 认证成功处理器

    // 心跳检测
    this.heartbeatInterval = null;
    this.heartbeatTimeout = null;
    this.lastHeartbeatReceived = 0;

    this.url = this.getWebSocketUrl();
    console.log(`WebSocket服务URL: ${this.url}`);
  }

  getWebSocketUrl() {
    // 优先使用环境配置中的WebSocket URL
    if (window.WS_URL && typeof window.WS_URL === 'string') {
      // 检查是否是完整URL（包含协议）
      if (window.WS_URL.startsWith('ws://') || window.WS_URL.startsWith('wss://')) {
        console.log('使用配置的WebSocket URL:', window.WS_URL);
        return window.WS_URL;
      }

      // 如果只是路径，添加协议和主机
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const hostname = window.location.hostname;
      const port = window.location.port;

      // 构建完整的主机地址（包含端口）
      const host = port ? `${hostname}:${port}` : hostname;
      const url = `${protocol}//${host}${window.WS_URL}`;
      console.log('使用配置的WebSocket路径:', url);
      return url;
    }

    // 回退到直接连接后端WebSocket服务器
    // 在生产环境中，这应该由nginx等代理处理
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const hostname = window.location.hostname;
    const wsPort = '8765'; // WebSocket服务器端口
    const url = `${protocol}//${hostname}:${wsPort}`;
    console.log('使用直接WebSocket URL:', url);
    return url;
  }

  connect() {
    // 如果已经连接或正在连接中，不要重复连接
    if (this.socket && (this.socket.readyState === WebSocket.CONNECTING || this.socket.readyState === WebSocket.OPEN)) {
      console.log('WebSocket已经连接或正在连接中');
      return;
    }

    // 先清除之前的心跳检测
    this.clearHeartbeat();

    // 重置认证状态
    this.isAuthenticated = false;
    this.authAttempted = false;

    // 从localStorage获取token
    const token = localStorage.getItem('token');
    if (!token) {
      console.error('WebSocket连接失败: 未找到认证令牌');
      // 这是预期行为，未登录用户不应该连接WebSocket
      return;
    }

    try {
      console.log(`尝试连接WebSocket: ${this.url}`);
      this.socket = new WebSocket(this.url);

      // 设置超时检测
      const connectionTimeout = setTimeout(() => {
        if (this.socket && this.socket.readyState !== WebSocket.OPEN) {
          console.error('WebSocket连接超时');
          this.socket.close();
          // 会触发onclose事件，进而启动重连
        }
      }, 10000); // 10秒连接超时

      this.socket.onopen = () => {
        console.log('WebSocket连接成功');
        clearTimeout(connectionTimeout);
        this.isConnected = true;
        this.reconnectAttempts = 0;

        // 连接成功后立即发送认证消息
        setTimeout(() => {
          this.sendAuthMessage(token);
        }, 500); // 延迟500ms，确保连接完全建立

        // 启动心跳检测
        this.startHeartbeat();
      };

      this.socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          // 处理心跳响应
          if (message.type === 'heartbeat_response') {
            this.handleHeartbeatResponse();
            return;
          }

          this.handleMessage(message);
        } catch (error) {
          console.error('WebSocket消息解析失败:', error);
        }
      };

      this.socket.onclose = (event) => {
        console.log(`WebSocket连接关闭: Code=${event.code}, Reason=${event.reason}`);
        clearTimeout(connectionTimeout);
        this.isConnected = false;
        this.clearHeartbeat();
        this.notifyDisconnect();

        // 自动重新连接，除非是正常关闭
        if (event.code !== 1000) {
          this.scheduleReconnect();
        }
      };

      this.socket.onerror = (error) => {
        console.error('WebSocket错误:', error);
        this.isConnected = false;
        this.clearHeartbeat();
      };
    } catch (error) {
      console.error('创建WebSocket连接失败:', error);
    }
  }

  sendAuthMessage(token) {
    if (!this.isConnected) return;

    try {
      // 发送认证消息
      const authMessage = JSON.stringify({
        type: MessageTypes.AUTHENTICATE,
        token
      });
      this.socket.send(authMessage);
      console.log('已发送WebSocket认证消息:', MessageTypes.AUTHENTICATE);

      // 记录认证尝试
      this.authAttempted = true;
    } catch (error) {
      console.error('发送WebSocket认证消息失败:', error);
      // 如果发送认证消息失败，尝试重新连接
      this.reconnect();
    }
  }

  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('达到最大重连次数，停止重连');
      // 通知应用WebSocket连接失败
      this.messageHandlers[MessageTypes.ERROR]?.forEach(handler => {
        try {
          handler({
            type: MessageTypes.ERROR,
            message: '无法连接到WebSocket服务器，请刷新页面重试或联系管理员'
          });
        } catch (e) {
          console.error('发送WebSocket错误通知失败:', e);
        }
      });
      return;
    }

    // 清除之前的重连计时器
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
    }

    // 指数退避重连，但最长不超过30秒
    const delay = Math.min(this.baseDelay * Math.pow(2, this.reconnectAttempts), 30000);
    console.log(`将在${delay}毫秒后尝试重新连接 (尝试 ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);

    this.reconnectTimeoutId = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  send(type, data = {}) {
    if (!this.isConnected) {
      console.error('WebSocket未连接，无法发送消息');
      // 尝试重新连接
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        console.log('尝试重新连接WebSocket...');
        this.connect();
      }
      return false;
    }

    // 如果不是认证消息且未通过认证，先记录错误
    if (type !== MessageTypes.AUTHENTICATE && !this.isAuthenticated) {
      console.warn(`WebSocket未认证，不能发送[${type}]消息，将尝试重新认证`);

      // 尝试重新认证
      const token = localStorage.getItem('token');
      if (token) {
        setTimeout(() => this.sendAuthMessage(token), 500);

        // 保存请求，认证后可能需要重发
        this.pendingRequests = this.pendingRequests || [];
        this.pendingRequests.push({type, data});

        // 设置超时重发
        setTimeout(() => {
          if (this.isAuthenticated && this.isConnected) {
            console.log('认证成功，重新发送之前的请求:', type);
            this.doSend(type, data);
          }
        }, 2000);
      }

      return false;
    }

    return this.doSend(type, data);
  }

  // 实际发送消息的方法
  doSend(type, data = {}) {
    try {
      const message = JSON.stringify({
        type,
        ...data
      });
      this.socket.send(message);
      console.log(`已发送WebSocket消息: ${type}`, data);
      return true;
    } catch (error) {
      console.error('发送WebSocket消息失败:', error);
      // 发送失败时尝试重新连接
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.isConnected = false;
        this.isAuthenticated = false;
        this.scheduleReconnect();
      }
      return false;
    }
  }

  handleMessage(message) {
    const type = message.type || 'unknown';
    console.log(`接收到WebSocket消息: ${type}`, message);

    // 处理认证结果消息
    if (type === MessageTypes.AUTH_RESULT) {
      if (message.success) {
        console.log('WebSocket认证成功');
        // 设置认证状态标志
        this.isAuthenticated = true;
        // 执行认证成功回调
        this.notifyAuthSuccess();
        // 通知连接已建立
        this.notifyConnect();

        // 处理之前因未认证而挂起的请求
        if (this.pendingRequests && this.pendingRequests.length > 0) {
          console.log(`处理${this.pendingRequests.length}个挂起的请求`);

          // 克隆一份，避免在处理过程中被修改
          const requests = [...this.pendingRequests];
          this.pendingRequests = [];

          // 延迟处理，确保认证状态已完全更新
          setTimeout(() => {
            requests.forEach(req => {
              console.log('发送挂起的请求:', req.type);
              this.doSend(req.type, req.data);
            });
          }, 500);
        }
      } else {
        console.error('WebSocket认证失败:', message.error);
        // 认证失败清除标志
        this.isAuthenticated = false;
        // 如果认证失败，尝试重新认证
        const token = localStorage.getItem('token');
        if (token) {
          console.log('尝试重新进行WebSocket认证...');
          setTimeout(() => this.sendAuthMessage(token), 1000);
        } else {
          this.disconnect();
        }
      }
      return;
    }

    // 处理错误消息，检查是否是认证错误
    if (type === MessageTypes.ERROR && message.message === '请先进行认证') {
      console.warn('收到未认证错误，检查认证状态');
      // 只有在之前未认证的情况下才重试认证
      if (!this.isAuthenticated) {
        const token = localStorage.getItem('token');
        if (token) {
          console.log('尝试重新进行WebSocket认证...');
          setTimeout(() => this.sendAuthMessage(token), 1000);
        }
      } else {
        console.warn('认证状态不一致！服务器认为未认证但客户端认为已认证');
        // 标记状态并重新连接
        this.isAuthenticated = false;
        this.reconnect();
      }
      return;
    }

    // 处理连接建立消息
    if (type === MessageTypes.CONNECTION_ESTABLISHED) {
      this.notifyConnect();
      return;
    }

    // 调用对应类型的处理函数
    const handlers = this.messageHandlers[type] || [];
    handlers.forEach(handler => {
      try {
        handler(message);
      } catch (error) {
        console.error(`处理"${type}"类型的消息时出错:`, error);
      }
    });
  }

  onMessage(type, handler) {
    if (!this.messageHandlers[type]) {
      this.messageHandlers[type] = [];
    }
    this.messageHandlers[type].push(handler);
  }

  offMessage(type, handler) {
    if (!this.messageHandlers[type]) return;

    if (handler) {
      // 移除特定处理函数
      this.messageHandlers[type] = this.messageHandlers[type].filter(h => h !== handler);
    } else {
      // 移除该类型的所有处理函数
      delete this.messageHandlers[type];
    }
  }

  onConnect(handler) {
    this.connectHandlers.push(handler);
    // 如果已经连接，立即调用
    if (this.isConnected) {
      handler();
    }
  }

  offConnect(handler) {
    this.connectHandlers = this.connectHandlers.filter(h => h !== handler);
  }

  onDisconnect(handler) {
    this.disconnectHandlers.push(handler);
  }

  offDisconnect(handler) {
    this.disconnectHandlers = this.disconnectHandlers.filter(h => h !== handler);
  }

  notifyConnect() {
    // 延迟执行回调，确保认证状态已设置
    setTimeout(() => {
      if (this.isAuthenticated) {
        console.log('WebSocket已连接且已认证，执行连接回调');
        this.connectHandlers.forEach(handler => {
          try {
            handler();
          } catch (error) {
            console.error('执行连接回调时出错:', error);
          }
        });
      } else {
        console.warn('WebSocket已连接但未认证，不执行连接回调');
      }
    }, 500);
  }

  notifyDisconnect() {
    this.disconnectHandlers.forEach(handler => {
      try {
        handler();
      } catch (error) {
        console.error('执行断开连接回调时出错:', error);
      }
    });
  }

  // 添加特定的邮箱相关消息发送方法
  getEmails() {
    return this.send(MessageTypes.GET_ALL_EMAILS);
  }

  checkEmails(emailIds) {
    return this.send(MessageTypes.CHECK_EMAILS, { email_ids: emailIds });
  }

  deleteEmails(emailIds) {
    return this.send(MessageTypes.DELETE_EMAILS, { email_ids: emailIds });
  }

  addEmail(emailData) {
    return this.send(MessageTypes.ADD_EMAIL, emailData);
  }

  getMailRecords(emailId) {
    return this.send(MessageTypes.GET_MAIL_RECORDS, { email_id: emailId });
  }

  importEmails(data) {
    // 检查数据类型，支持新旧两种格式
    if (typeof data === 'string') {
      return this.send(MessageTypes.IMPORT_EMAILS, { data });
    } else if (typeof data === 'object') {
      // 确保数据符合预期格式
      if (!data.data) {
        console.error('批量导入数据格式错误: 缺少data字段');
        return false;
      }

      // 确保有mailType字段，默认为outlook
      const payload = {
        data: data.data,
        mail_type: data.mailType || 'outlook'
      };

      return this.send(MessageTypes.IMPORT_EMAILS, payload);
    }

    console.error('批量导入数据格式错误:', data);
    return false;
  }

  // 心跳检测
  startHeartbeat() {
    this.lastHeartbeatReceived = Date.now();

    // 定期发送心跳
    this.heartbeatInterval = setInterval(() => {
      if (this.isConnected) {
        try {
          this.socket.send(JSON.stringify({ type: 'heartbeat' }));
          // 减少日志输出，只在调试模式下输出
          if (localStorage.getItem('debug_mode') === 'true') {
            console.log('已发送心跳消息');
          }

          // 设置心跳超时检测
          this.heartbeatTimeout = setTimeout(() => {
            const timeSinceLastHeartbeat = Date.now() - this.lastHeartbeatReceived;
            // 如果超过30秒未收到心跳响应，认为连接已断开
            if (timeSinceLastHeartbeat > 30000) {
              console.warn('心跳检测超时，重新连接WebSocket');
              this.disconnect();
              this.connect();
            }
          }, 10000); // 10秒超时
        } catch (error) {
          console.error('发送心跳消息失败:', error);
          this.clearHeartbeat();
          this.disconnect();
          this.connect();
        }
      }
    }, 20000); // 每20秒发送一次心跳
  }

  handleHeartbeatResponse() {
    // 减少日志输出，只在调试模式下输出
    if (localStorage.getItem('debug_mode') === 'true') {
      console.log('收到心跳响应');
    }
    this.lastHeartbeatReceived = Date.now();
    // 清除当前的心跳超时检测
    if (this.heartbeatTimeout) {
      clearTimeout(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }
  }

  clearHeartbeat() {
    // 清除心跳检测
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }

    if (this.heartbeatTimeout) {
      clearTimeout(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }
  }

  // 重置WebSocket状态
  resetState() {
    // 清除心跳检测
    this.clearHeartbeat();

    // 重置连接和认证状态
    this.isConnected = false;
    this.isAuthenticated = false;
    this.authAttempted = false;

    // 清除重连计时器
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }
  }

  // 重新连接WebSocket
  reconnect() {
    console.log('重新连接WebSocket...');
    // 先断开现有连接并重置状态
    this.disconnect();

    // 延迟一段时间后重新连接
    setTimeout(() => {
      // 连接前检查token
      const token = localStorage.getItem('token');
      if (token) {
        console.log('使用现有token进行重连');
        this.connect();
      } else {
        console.warn('没有有效token，无法重连');
      }
    }, 1000);
  }

  // 断开WebSocket连接
  disconnect() {
    // 先重置状态
    this.resetState();

    // 关闭WebSocket连接
    if (this.socket) {
      try {
        this.socket.close(1000, '正常关闭');
      } catch (error) {
        console.error('关闭WebSocket连接时出错:', error);
      }
      this.socket = null;
      console.log('WebSocket连接已手动关闭');
    }
  }

  // 添加认证成功回调
  onAuthSuccess(handler) {
    this.authSuccessHandlers.push(handler);
    // 如果已经认证成功，立即调用
    if (this.isAuthenticated) {
      handler();
    }
  }

  // 移除认证成功回调
  offAuthSuccess(handler) {
    this.authSuccessHandlers = this.authSuccessHandlers.filter(h => h !== handler);
  }

  // 通知认证成功
  notifyAuthSuccess() {
    this.authSuccessHandlers.forEach(handler => {
      try {
        handler();
      } catch (error) {
        console.error('执行认证成功回调时出错:', error);
      }
    });
  }
}

// 单例模式
export default new WebSocketService();
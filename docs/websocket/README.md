# WebSocket服务文档

## 概述

花火邮箱助手WebSocket服务用于实现前后端之间的实时通信，主要用于邮箱状态更新、操作进度反馈以及系统通知等功能。相比传统的HTTP轮询方式，WebSocket提供了更高效、低延迟的双向通信机制。

## 技术选型

- **服务端**: Python的`websockets`库
- **客户端**: 浏览器原生WebSocket API
- **消息格式**: JSON
- **通信协议**: WebSocket over TCP

## 服务架构

WebSocket服务作为独立线程运行在后端服务中，与Flask API服务并行运行。

```
+----------------+       +----------------+
|                |       |                |
|  前端应用      |<----->|  Flask API     |  (HTTP)
|  (Browser)     |       |  服务          |
|                |       |                |
+-------^--------+       +----------------+
        |                        |
        |                        | 共享数据和状态
        | WebSocket              |
        |                +-------v--------+
        |                |                |
        +--------------->|  WebSocket     |
                         |  服务          |
                         |                |
                         +----------------+
```

## 核心组件

### 1. WebSocketHandler类

WebSocketHandler是WebSocket服务的核心类，负责处理WebSocket连接和消息。

**主要职责**：
- 管理客户端连接
- 处理客户端消息
- 广播系统消息
- 发送进度更新

**初始化**：

```python
def __init__(self, host='0.0.0.0', port=8765):
    self.host = host
    self.port = port
    self.connections = set()
    self.email_processor = None
    self.db = None
    self.connected_clients = {}
```

### 2. 连接管理

**注册连接**：
```python
async def register(self, websocket):
    """注册新的WebSocket连接"""
    self.connections.add(websocket)
    logger.info(f"New client connected. Total connections: {len(self.connections)}")
```

**注销连接**：
```python
async def unregister(self, websocket):
    """注销WebSocket连接"""
    self.connections.remove(websocket)
    # 清除客户端信息
    if websocket in self.connected_clients:
        del self.connected_clients[websocket]
    logger.info(f"Client disconnected. Total connections: {len(self.connections)}")
```

### 3. 消息处理

**消息分发**：
```python
async def handle_message(self, websocket, message_str):
    """处理客户端消息"""
    try:
        message = json.loads(message_str)
        action = message.get('action')
        
        if action == 'get_all_emails':
            await self.handle_get_all_emails(websocket)
        elif action == 'add_email':
            # 处理添加邮箱
            ...
        elif action == 'delete_emails':
            # 处理删除邮箱
            ...
        # 其他动作处理
        ...
    except Exception as e:
        logger.error(f"处理消息时出错: {str(e)}")
        await self.send_to_client(websocket, {
            'type': 'error',
            'message': f'处理消息时出错: {str(e)}'
        })
```

### 4. 消息广播

**广播消息**：
```python
async def broadcast(self, message):
    """向所有连接的客户端广播消息"""
    if not self.connections:
        return
    
    message_str = json.dumps(message)
    await asyncio.gather(
        *[connection.send(message_str) for connection in self.connections],
        return_exceptions=True
    )
```

**发送给特定客户端**：
```python
async def send_to_client(self, websocket, message):
    """发送消息给特定客户端"""
    await websocket.send(json.dumps(message))
```

## 消息协议

### 1. 消息格式

所有WebSocket消息使用JSON格式，包含以下基本字段：

```json
{
  "type": "消息类型",
  "action": "操作类型（客户端发送的消息）",
  "data": "消息数据（可选）",
  "message": "消息文本（可选）",
  "timestamp": "时间戳（可选）"
}
```

### 2. 客户端到服务器消息

客户端发送的消息通常包含`action`字段，指定需要执行的操作。

**示例 - 获取邮箱列表**：
```json
{
  "action": "get_all_emails"
}
```

**示例 - 添加邮箱**：
```json
{
  "action": "add_email",
  "email": "example@outlook.com",
  "password": "password123",
  "client_id": "client_id_value",
  "refresh_token": "refresh_token_value",
  "mail_type": "outlook"
}
```

**示例 - 检查邮件**：
```json
{
  "action": "check_emails",
  "email_ids": [1, 2, 3]
}
```

### 3. 服务器到客户端消息

服务器发送的消息通常包含`type`字段，指定消息类型。

**示例 - 操作成功**：
```json
{
  "type": "success",
  "message": "邮箱添加成功"
}
```

**示例 - 进度更新**：
```json
{
  "type": "check_progress",
  "email_id": 1,
  "progress": 75,
  "message": "正在检查邮件 15/20"
}
```

**示例 - 错误通知**：
```json
{
  "type": "error",
  "message": "连接邮箱服务器失败",
  "details": "认证失败，请检查凭据"
}
```

**示例 - 邮箱状态更新**：
```json
{
  "type": "email_status_update",
  "email_id": 1,
  "status": "processing",
  "message": "正在处理"
}
```

### 4. 系统消息

系统级别的广播消息，发送给所有连接的客户端。

**示例 - 系统通知**：
```json
{
  "type": "system_notification",
  "message": "系统将在5分钟后进行维护",
  "level": "warning"
}
```

## 认证机制

WebSocket连接需要进行认证才能使用完整功能，认证方式如下：

### 1. 令牌认证

客户端连接后发送认证消息，包含JWT令牌：

```json
{
  "action": "authenticate",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

服务端验证令牌并响应：

```json
{
  "type": "authentication_result",
  "success": true,
  "message": "认证成功"
}
```

### 2. 令牌验证

```python
def validate_token(self, token):
    """验证JWT令牌"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get('user_id')
        username = payload.get('username')
        is_admin = payload.get('is_admin', False)
        
        return {
            'user_id': user_id,
            'username': username,
            'is_admin': is_admin
        }
    except jwt.ExpiredSignatureError:
        return None
    except Exception as e:
        logger.error(f"令牌验证失败: {str(e)}")
        return None
```

## 邮箱状态更新流程

### 1. 状态变更

当邮箱状态发生变化时，WebSocket服务会发送状态更新消息：

```python
def update_email_status(self, email_id, status, message=""):
    """更新邮箱状态并通过WebSocket广播"""
    # 更新数据库中的状态
    self.db.update_email_status(email_id, status)
    
    # 构造状态更新消息
    status_message = {
        "type": "email_status_update",
        "email_id": email_id,
        "status": status,
        "message": message,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    # 广播状态更新
    asyncio.run_coroutine_threadsafe(
        self.broadcast(status_message),
        asyncio.get_event_loop()
    )
```

### 2. 进度通知

邮件处理过程中会定期发送进度通知：

```python
def progress_callback(email_id, progress, message):
    """邮件处理进度回调函数"""
    progress_message = {
        "type": "check_progress",
        "email_id": email_id,
        "progress": progress,
        "message": message
    }
    
    # 发送进度消息
    asyncio.run_coroutine_threadsafe(
        self.broadcast(progress_message),
        asyncio.get_event_loop()
    )
```

## 前端集成

### 1. 连接建立

```javascript
// WebSocket服务
class WebSocketService {
  constructor() {
    this.socket = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.listeners = {
      connect: [],
      disconnect: [],
      message: []
    };
  }
  
  // 建立连接
  connect() {
    const wsUrl = `ws://${window.location.hostname}:8765`;
    this.socket = new WebSocket(wsUrl);
    
    this.socket.onopen = () => {
      console.log('WebSocket连接已建立');
      this.isConnected = true;
      this.reconnectAttempts = 0;
      this._notifyListeners('connect');
      
      // 发送认证消息
      this.authenticate();
    };
    
    this.socket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this._handleMessage(message);
    };
    
    this.socket.onclose = () => {
      console.log('WebSocket连接已关闭');
      this.isConnected = false;
      this._notifyListeners('disconnect');
      this._attemptReconnect();
    };
    
    this.socket.onerror = (error) => {
      console.error('WebSocket错误:', error);
    };
  }
  
  // 其他方法...
}
```

### 2. 消息处理

```javascript
_handleMessage(message) {
  // 通知所有消息监听器
  this._notifyListeners('message', message);
  
  // 处理特定类型的消息
  switch (message.type) {
    case 'check_progress':
      this._handleProgress(message);
      break;
    case 'email_status_update':
      this._handleStatusUpdate(message);
      break;
    case 'error':
      this._handleError(message);
      break;
    // 处理其他消息类型...
  }
}
```

## 性能与可靠性

### 1. 心跳机制

为了保持连接活跃并检测死连接，实现了心跳机制：

**服务端**：
```python
async def send_heartbeat(self):
    """定期发送心跳消息"""
    while True:
        await asyncio.sleep(30)  # 每30秒发送一次
        heartbeat = {
            "type": "heartbeat",
            "timestamp": datetime.datetime.now().isoformat()
        }
        await self.broadcast(heartbeat)
```

**客户端**：
```javascript
// 处理心跳
_handleHeartbeat(message) {
  // 收到心跳，重置无响应计时器
  if (this.heartbeatTimeout) {
    clearTimeout(this.heartbeatTimeout);
  }
  
  // 设置新的无响应超时
  this.heartbeatTimeout = setTimeout(() => {
    console.warn('服务器心跳超时，尝试重新连接');
    this.reconnect();
  }, 45000); // 45秒无心跳则重连
  
  // 回复心跳
  this.send({
    action: "heartbeat_response",
    timestamp: new Date().toISOString()
  });
}
```

### 2. 重连机制

当连接断开时自动尝试重新连接：

```javascript
_attemptReconnect() {
  if (this.reconnectAttempts >= this.maxReconnectAttempts) {
    console.error('WebSocket重连次数达到上限，不再尝试重连');
    return;
  }
  
  const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 30000);
  console.log(`将在 ${delay}ms 后尝试重新连接...`);
  
  setTimeout(() => {
    console.log(`尝试重新连接 (${++this.reconnectAttempts}/${this.maxReconnectAttempts})`);
    this.connect();
  }, delay);
}
```

### 3. 消息队列

当连接断开时，缓存待发送的消息：

```javascript
send(message) {
  const messageStr = JSON.stringify(message);
  
  if (this.isConnected && this.socket.readyState === WebSocket.OPEN) {
    this.socket.send(messageStr);
    return true;
  } else {
    // 连接未就绪，添加到队列
    this.messageQueue.push(messageStr);
    
    // 如果未连接，尝试连接
    if (!this.isConnected) {
      this.connect();
    }
    return false;
  }
}

// 连接恢复后发送队列中的消息
_sendQueuedMessages() {
  while (this.messageQueue.length > 0) {
    const message = this.messageQueue.shift();
    this.socket.send(message);
  }
}
```

## 扩展与优化

### 1. 连接限流

防止单个客户端建立过多连接：

```python
def can_accept_connection(self, ip_address):
    """检查是否可以接受来自该IP的新连接"""
    if ip_address not in self.ip_connections:
        self.ip_connections[ip_address] = 1
        return True
    
    if self.ip_connections[ip_address] >= self.max_connections_per_ip:
        logger.warning(f"IP {ip_address} 连接数超过限制")
        return False
    
    self.ip_connections[ip_address] += 1
    return True
```

### 2. 消息压缩

对大型消息进行压缩以减少传输数据量：

```python
async def send_compressed(self, websocket, message):
    """发送压缩后的消息"""
    message_str = json.dumps(message)
    
    # 仅对大消息进行压缩
    if len(message_str) > 1024:
        compressed = zlib.compress(message_str.encode('utf-8'))
        await websocket.send(compressed, binary=True)
    else:
        await websocket.send(message_str)
```

### 3. 分组广播

按用户或功能分组广播消息，减少不必要的消息传输：

```python
async def broadcast_to_group(self, group, message):
    """向指定分组的客户端广播消息"""
    if group not in self.connection_groups:
        return
    
    message_str = json.dumps(message)
    await asyncio.gather(
        *[conn.send(message_str) for conn in self.connection_groups[group]],
        return_exceptions=True
    )
```

## 常见问题与解决方案

### 1. 连接断开处理

问题：网络不稳定导致连接频繁断开

解决方案：
- 实现指数退避的重连策略
- 在前端缓存待发送的消息
- 使用唯一消息ID防止消息重复处理

### 2. 消息顺序保证

问题：消息可能乱序到达

解决方案：
- 添加序列号字段追踪消息顺序
- 在客户端按序列号重排消息
- 实现确认机制确保关键消息送达

### 3. 资源占用控制

问题：大量连接占用服务器资源

解决方案：
- 限制单IP连接数量
- 实现连接空闲超时机制
- 对不活跃连接定期清理 
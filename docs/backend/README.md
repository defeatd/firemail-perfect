# 后端开发文档

## 技术栈概述

花火邮箱助手后端基于以下技术栈开发：

- **核心框架**：Python 3.13, Flask
- **数据库**：SQLite
- **通信协议**：HTTP RESTful API, WebSocket
- **认证机制**：JWT (JSON Web Token)
- **邮件处理**：IMAP, OAuth 2.0

## 目录结构

```
backend/
├── app.py                  # 应用入口，Flask应用配置
├── database/               # 数据库相关模块
│   └── db.py               # 数据库操作类
├── websocket/              # WebSocket服务模块
│   └── handler.py          # WebSocket消息处理器
├── utils/                  # 工具类
│   ├── email/              # 邮件处理工具
│   │   └── processor.py    # 邮件处理器
│   │   └── outlook.py      # Outlook邮箱处理
│   │   └── oauth.py        # OAuth认证处理
│   ├── security.py         # 安全相关工具
│   └── logger.py           # 日志工具
├── apis/                   # API模块
│   └── email_api.py        # 邮箱相关API
├── ws_server/              # WebSocket服务器
│   └── handler.py          # WebSocket消息处理
└── data/                   # 数据存储目录
    └── huohuo_email.db     # SQLite数据库文件
```

## 核心模块

### 1. Flask应用 (app.py)

Flask应用是整个后端的入口，负责初始化应用、配置路由和启动服务。

**主要功能**：
- 应用初始化和配置
- API路由注册
- 中间件配置
- 认证管理
- 错误处理

**关键组件**：
- `token_required` 装饰器：JWT认证中间件
- `admin_required` 装饰器：管理员权限验证
- API路由处理函数

### 2. 数据库模块 (database/db.py)

SQLite数据库操作模块，使用单例模式实现。

**主要功能**：
- 数据库连接管理
- 表结构初始化
- 用户管理
- 邮箱管理
- 邮件记录管理
- 系统配置管理

**核心类**：
- `Database`: 数据库操作类，实现各种数据操作方法

### 3. WebSocket服务 (websocket/handler.py)

WebSocket服务器，用于实时通信和状态更新。

**主要功能**：
- WebSocket连接管理
- 消息处理
- 实时状态更新
- 进度通知

**核心类**：
- `WebSocketHandler`: WebSocket消息处理器

### 4. 邮件处理模块 (utils/email/)

邮件处理相关工具，负责与邮件服务器交互。

**主要功能**：
- 邮箱连接
- 邮件检索
- 邮件解析
- OAuth认证

**核心类**：
- `EmailBatchProcessor`: 邮件批量处理器
- `OutlookMailHandler`: Outlook邮箱处理器
- `OAuthHandler`: OAuth认证处理器

### 5. API模块 (apis/)

API接口定义模块，实现RESTful API。

**主要功能**：
- 用户认证API
- 邮箱管理API
- 邮件检索API
- 系统配置API

## 关键流程

### 1. 用户认证流程

1. 客户端发送登录请求
2. 服务器验证用户凭据
3. 验证成功，生成JWT令牌
4. 返回令牌给客户端
5. 客户端保存令牌并在后续请求中使用

```python
@app.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = db.authenticate_user(username, password)
    if not user:
        return jsonify({'error': '用户名或密码错误'}), 401
    
    # 生成JWT令牌
    token = jwt.encode({
        'user_id': user['id'],
        'username': user['username'],
        'is_admin': user['is_admin'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }, JWT_SECRET, algorithm="HS256")
    
    # 创建响应
    response = make_response(jsonify({
        'token': token,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'is_admin': user['is_admin']
        }
    }))
    
    # 设置Cookie
    response.set_cookie(
        'token', 
        token, 
        httponly=True, 
        max_age=7*24*60*60,
        secure=False,
        samesite='Lax'
    )
    
    return response
```

### 2. 邮箱检查流程

1. 客户端请求检查邮箱
2. 服务器开启后台线程处理邮箱
3. 创建邮箱处理器并开始检查
4. 通过WebSocket发送进度通知
5. 处理完成后更新数据库并发送结果

```python
def check_emails(self, email_ids, progress_callback=None):
    """批量检查多个邮箱的邮件"""
    if not email_ids:
        return
    
    # 获取邮箱对象
    emails = self.db.get_emails_by_ids(email_ids)
    
    # 启动后台线程处理
    thread = threading.Thread(
        target=self._process_emails,
        args=(emails, progress_callback)
    )
    thread.daemon = True
    thread.start()
```

### 3. WebSocket通信流程

1. 客户端建立WebSocket连接
2. 服务器验证客户端身份
3. 注册客户端连接
4. 处理客户端消息
5. 向客户端发送实时通知
6. 连接关闭时注销客户端

```python
async def handle_client(self, websocket, path):
    """处理WebSocket客户端连接"""
    await self.register(websocket)
    try:
        async for message in websocket:
            try:
                await self.handle_message(websocket, message)
            except Exception as e:
                logger.error(f"处理消息时出错: {str(e)}")
                await websocket.send(json.dumps({
                    'type': 'error',
                    'message': f'处理消息时出错: {str(e)}'
                }))
    except ConnectionClosed:
        logger.info("客户端断开连接")
    finally:
        await self.unregister(websocket)
```

## 数据库设计

数据库使用SQLite，核心表结构包括：

1. **users** - 用户表
   - id (INTEGER): 主键
   - username (TEXT): 用户名，唯一
   - password (TEXT): 加密密码
   - salt (TEXT): 密码盐值
   - is_admin (INTEGER): 是否管理员
   - created_at (TIMESTAMP): 创建时间
   - updated_at (TIMESTAMP): 更新时间

2. **emails** - 邮箱表
   - id (INTEGER): 主键
   - user_id (INTEGER): 用户ID，外键
   - email (TEXT): 邮箱地址
   - password (TEXT): 邮箱密码
   - mail_type (TEXT): 邮箱类型
   - client_id (TEXT): 客户端ID
   - refresh_token (TEXT): 刷新令牌
   - access_token (TEXT): 访问令牌
   - last_check_time (TIMESTAMP): 上次检查时间
   - enable_realtime_check (INTEGER): 是否启用实时检查
   - created_at (TIMESTAMP): 创建时间
   - updated_at (TIMESTAMP): 更新时间

3. **mail_records** - 邮件记录表
   - id (INTEGER): 主键
   - email_id (INTEGER): 邮箱ID，外键
   - subject (TEXT): 邮件主题
   - sender (TEXT): 发件人
   - received_time (TIMESTAMP): 接收时间
   - content (TEXT): 邮件内容
   - folder (TEXT): 邮件文件夹
   - created_at (TIMESTAMP): 创建时间

4. **system_config** - 系统配置表
   - id (INTEGER): 主键
   - key (TEXT): 配置键
   - value (TEXT): 配置值
   - description (TEXT): 描述
   - created_at (TIMESTAMP): 创建时间
   - updated_at (TIMESTAMP): 更新时间

## 安全设计

1. **密码加密**：
   - 使用PBKDF2和SHA-256算法
   - 为每个用户生成唯一盐值
   - 多次哈希迭代增强安全性

```python
def _hash_password(self, password, salt):
    """密码哈希"""
    return hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode('utf-8'), 
        salt.encode('utf-8'), 
        100000
    ).hex()
```

2. **JWT认证**：
   - 使用HS256算法签名
   - 设置令牌过期时间
   - 在请求头或Cookie中传输

3. **权限控制**：
   - 基于装饰器的权限控制
   - 管理员和普通用户权限分离
   - 资源访问控制

4. **敏感数据保护**：
   - 邮箱凭据加密存储
   - 避免明文记录敏感信息
   - 敏感信息只存储在本地数据库

## 错误处理

后端实现了统一的错误处理机制：

1. **HTTP状态码**：使用标准HTTP状态码表示错误类型
2. **结构化错误响应**：统一的错误响应格式
3. **日志记录**：详细记录错误信息和堆栈跟踪
4. **异常捕获**：全面的异常捕获和处理

错误响应格式示例：
```json
{
  "error": "错误描述信息",
  "details": "详细错误信息",
  "code": "错误代码"
}
```

## API设计原则

1. **RESTful设计**：遵循REST设计原则
2. **版本控制**：API路径包含版本信息
3. **统一响应格式**：标准化的响应结构
4. **幂等性**：确保关键操作的幂等性
5. **参数验证**：严格的请求参数验证

## 性能优化

1. **异步处理**：使用线程池处理耗时操作
2. **连接池**：数据库连接池管理
3. **缓存机制**：关键数据缓存
4. **批量操作**：支持批量处理提高效率
5. **惰性加载**：按需加载数据减少资源消耗 
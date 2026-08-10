# API接口文档

## 基本信息

- **基础路径**: `/api`
- **数据格式**: JSON
- **认证方式**: JWT Token (Bearer Authentication)
- **状态码**:
  - `200` - 成功
  - `201` - 创建成功
  - `400` - 请求错误
  - `401` - 未认证
  - `403` - 权限不足
  - `404` - 资源不存在
  - `500` - 服务器错误

## 认证接口

### 登录

- **URL**: `/api/auth/login`
- **方法**: `POST`
- **描述**: 用户登录并获取JWT令牌
- **请求体**:
  ```json
  {
    "username": "用户名",
    "password": "密码"
  }
  ```
- **成功响应** (200):
  ```json
  {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "id": 1,
      "username": "用户名",
      "is_admin": false
    }
  }
  ```
- **错误响应** (401):
  ```json
  {
    "error": "用户名或密码错误"
  }
  ```

### 登出

- **URL**: `/api/auth/logout`
- **方法**: `POST`
- **描述**: 用户登出，删除Cookie中的令牌
- **成功响应** (200):
  ```json
  {
    "message": "已成功登出"
  }
  ```

### 注册

- **URL**: `/api/auth/register`
- **方法**: `POST`
- **描述**: 新用户注册
- **请求体**:
  ```json
  {
    "username": "用户名",
    "password": "密码"
  }
  ```
- **成功响应** (201):
  ```json
  {
    "message": "注册成功",
    "username": "用户名",
    "is_admin": false
  }
  ```
- **错误响应** (400):
  ```json
  {
    "error": "用户名已存在"
  }
  ```

### 获取当前用户

- **URL**: `/api/auth/user`
- **方法**: `GET`
- **描述**: 获取当前登录用户信息
- **权限**: 需要认证
- **成功响应** (200):
  ```json
  {
    "id": 1,
    "username": "用户名",
    "is_admin": false
  }
  ```
- **错误响应** (401):
  ```json
  {
    "error": "未认证，请先登录"
  }
  ```

### 修改密码

- **URL**: `/api/auth/change-password`
- **方法**: `POST`
- **描述**: 修改当前用户密码
- **权限**: 需要认证
- **请求体**:
  ```json
  {
    "old_password": "旧密码",
    "new_password": "新密码"
  }
  ```
- **成功响应** (200):
  ```json
  {
    "message": "密码已成功更新"
  }
  ```
- **错误响应** (400):
  ```json
  {
    "error": "旧密码不正确"
  }
  ```

## 用户管理接口

### 获取所有用户

- **URL**: `/api/users`
- **方法**: `GET`
- **描述**: 获取所有用户信息
- **权限**: 需要管理员权限
- **成功响应** (200):
  ```json
  [
    {
      "id": 1,
      "username": "admin",
      "is_admin": true,
      "created_at": "2025-01-01T12:00:00"
    },
    {
      "id": 2,
      "username": "user1",
      "is_admin": false,
      "created_at": "2025-01-02T12:00:00"
    }
  ]
  ```
- **错误响应** (403):
  ```json
  {
    "error": "需要管理员权限"
  }
  ```

### 创建用户

- **URL**: `/api/users`
- **方法**: `POST`
- **描述**: 创建新用户（管理员功能）
- **权限**: 需要管理员权限
- **请求体**:
  ```json
  {
    "username": "新用户名",
    "password": "密码",
    "is_admin": false
  }
  ```
- **成功响应** (201):
  ```json
  {
    "message": "用户创建成功",
    "username": "新用户名",
    "is_admin": false
  }
  ```
- **错误响应** (400):
  ```json
  {
    "error": "用户名已存在"
  }
  ```

### 删除用户

- **URL**: `/api/users/<user_id>`
- **方法**: `DELETE`
- **描述**: 删除指定用户
- **权限**: 需要管理员权限
- **成功响应** (200):
  ```json
  {
    "message": "用户ID 3 已删除"
  }
  ```
- **错误响应** (403):
  ```json
  {
    "error": "需要管理员权限"
  }
  ```

### 重置用户密码

- **URL**: `/api/users/<user_id>/reset-password`
- **方法**: `POST`
- **描述**: 重置指定用户的密码
- **权限**: 需要管理员权限
- **请求体**:
  ```json
  {
    "new_password": "新密码"
  }
  ```
- **成功响应** (200):
  ```json
  {
    "message": "用户ID 3 的密码已重置"
  }
  ```
- **错误响应** (404):
  ```json
  {
    "error": "用户不存在"
  }
  ```

## 邮箱管理接口

### 获取所有邮箱

- **URL**: `/api/emails`
- **方法**: `GET`
- **描述**: 获取当前用户的所有邮箱（管理员可查看所有用户邮箱）
- **权限**: 需要认证
- **成功响应** (200):
  ```json
  [
    {
      "id": 1,
      "user_id": 1,
      "email": "example1@outlook.com",
      "mail_type": "outlook",
      "last_check_time": "2025-04-01T10:30:00",
      "enable_realtime_check": false,
      "created_at": "2025-03-15T08:20:00"
    },
    {
      "id": 2,
      "user_id": 1,
      "email": "example2@outlook.com",
      "mail_type": "outlook",
      "last_check_time": "2025-04-01T11:45:00",
      "enable_realtime_check": true,
      "created_at": "2025-03-20T09:15:00"
    }
  ]
  ```

### 添加邮箱

- **URL**: `/api/emails`
- **方法**: `POST`
- **描述**: 添加新邮箱
- **权限**: 需要认证
- **请求体**:
  ```json
  {
    "email": "example@outlook.com",
    "password": "邮箱密码",
    "client_id": "客户端ID",
    "refresh_token": "刷新令牌",
    "mail_type": "outlook"
  }
  ```
- **成功响应** (201):
  ```json
  {
    "message": "邮箱 example@outlook.com 添加成功",
    "id": 3
  }
  ```
- **错误响应** (400):
  ```json
  {
    "error": "邮箱已存在"
  }
  ```

### 删除邮箱

- **URL**: `/api/emails/<email_id>`
- **方法**: `DELETE`
- **描述**: 删除指定邮箱
- **权限**: 需要认证
- **成功响应** (200):
  ```json
  {
    "message": "邮箱 ID 3 已删除"
  }
  ```
- **错误响应** (404):
  ```json
  {
    "error": "邮箱不存在"
  }
  ```

### 批量删除邮箱

- **URL**: `/api/emails/batch_delete`
- **方法**: `POST`
- **描述**: 批量删除多个邮箱
- **权限**: 需要认证
- **请求体**:
  ```json
  {
    "email_ids": [1, 2, 3]
  }
  ```
- **成功响应** (200):
  ```json
  {
    "message": "已删除 3 个邮箱"
  }
  ```
- **错误响应** (400):
  ```json
  {
    "error": "邮箱ID列表不能为空"
  }
  ```

### 检查邮箱

- **URL**: `/api/emails/<email_id>/check`
- **方法**: `POST`
- **描述**: 检查单个邮箱的邮件
- **权限**: 需要认证
- **成功响应** (200):
  ```json
  {
    "message": "开始检查邮箱 ID 1",
    "email": "example@outlook.com"
  }
  ```
- **错误响应** (400):
  ```json
  {
    "message": "邮箱 ID 1 正在处理中",
    "status": "processing"
  }
  ```

### 批量检查邮箱

- **URL**: `/api/emails/batch_check`
- **方法**: `POST`
- **描述**: 批量检查多个邮箱的邮件
- **权限**: 需要认证
- **请求体**:
  ```json
  {
    "email_ids": [1, 2, 3]
  }
  ```
- **成功响应** (200):
  ```json
  {
    "message": "开始检查 3 个邮箱",
    "skipped": 0,
    "total": 3
  }
  ```
- **错误响应** (400):
  ```json
  {
    "error": "未找到有效的邮箱"
  }
  ```

### 获取邮件记录

- **URL**: `/api/emails/<email_id>/mail_records`
- **方法**: `GET`
- **描述**: 获取指定邮箱的邮件记录
- **权限**: 需要认证
- **成功响应** (200):
  ```json
  [
    {
      "id": 1,
      "email_id": 1,
      "subject": "测试邮件",
      "sender": "sender@example.com",
      "received_time": "2025-04-01T12:00:00",
      "content": "邮件内容...",
      "folder": "收件箱",
      "created_at": "2025-04-01T12:05:00"
    },
    {
      "id": 2,
      "email_id": 1,
      "subject": "重要通知",
      "sender": "important@example.com",
      "received_time": "2025-04-01T13:30:00",
      "content": "重要邮件内容...",
      "folder": "收件箱",
      "created_at": "2025-04-01T13:35:00"
    }
  ]
  ```
- **错误响应** (404):
  ```json
  {
    "error": "邮箱不存在"
  }
  ```

### 导入邮箱

- **URL**: `/api/emails/import`
- **方法**: `POST`
- **描述**: 批量导入邮箱
- **权限**: 需要认证
- **请求体**:
  ```json
  {
    "data": "example1@outlook.com----password1----client_id1----token1\nexample2@outlook.com----password2----client_id2----token2",
    "mail_type": "outlook"
  }
  ```
- **成功响应** (200):
  ```json
  {
    "total": 2,
    "success": 2,
    "failed": 0,
    "failed_details": []
  }
  ```
- **错误响应** (400):
  ```json
  {
    "error": "导入数据格式不正确"
  }
  ```

### 更新邮箱

- **URL**: `/api/emails/<email_id>`
- **方法**: `PUT`
- **描述**: 更新邮箱信息
- **权限**: 需要认证
- **请求体**:
  ```json
  {
    "password": "新密码",
    "client_id": "新客户端ID",
    "refresh_token": "新刷新令牌"
  }
  ```
- **成功响应** (200):
  ```json
  {
    "message": "邮箱信息已更新",
    "email_id": 1
  }
  ```
- **错误响应** (404):
  ```json
  {
    "error": "邮箱不存在"
  }
  ```

### 切换实时检查

- **URL**: `/api/emails/<email_id>/realtime`
- **方法**: `POST`
- **描述**: 开启或关闭邮箱的实时检查功能
- **权限**: 需要认证
- **请求体**:
  ```json
  {
    "enable": true
  }
  ```
- **成功响应** (200):
  ```json
  {
    "message": "已开启实时检查",
    "email_id": 1,
    "enable_realtime_check": true
  }
  ```
- **错误响应** (404):
  ```json
  {
    "error": "邮箱不存在"
  }
  ```

## 系统配置接口

### 获取系统配置

- **URL**: `/api/config`
- **方法**: `GET`
- **描述**: 获取系统配置信息
- **成功响应** (200):
  ```json
  {
    "allow_register": true,
    "server_time": "2025-04-05T12:34:56"
  }
  ```

### 切换注册功能

- **URL**: `/api/admin/config/registration`
- **方法**: `POST`
- **描述**: 开启或关闭用户注册功能
- **权限**: 需要管理员权限
- **请求体**:
  ```json
  {
    "allow": true
  }
  ```
- **成功响应** (200):
  ```json
  {
    "message": "已成功开启注册功能",
    "allow_register": true
  }
  ```
- **错误响应** (403):
  ```json
  {
    "error": "需要管理员权限"
  }
  ```

### 健康检查

- **URL**: `/api/health`
- **方法**: `GET`
- **描述**: 检查服务是否正常运行
- **成功响应** (200):
  ```json
  {
    "status": "ok",
    "message": "花火邮箱助手服务正在运行"
  }
  ```

## 搜索接口

### 搜索邮件

- **URL**: `/api/search`
- **方法**: `POST`
- **描述**: 搜索邮件内容
- **权限**: 需要认证
- **请求体**:
  ```json
  {
    "query": "搜索关键词",
    "email_ids": [1, 2],
    "search_in_subject": true,
    "search_in_sender": true,
    "search_in_content": true
  }
  ```
- **成功响应** (200):
  ```json
  {
    "results": [
      {
        "id": 5,
        "email_id": 1,
        "subject": "包含搜索关键词的邮件",
        "sender": "sender@example.com",
        "received_time": "2025-04-01T14:30:00",
        "content_preview": "这是一封包含搜索关键词的邮件...",
        "email": "example@outlook.com"
      }
    ],
    "total": 1
  }
  ```
- **错误响应** (400):
  ```json
  {
    "error": "搜索关键词不能为空"
  }
  ```

## 实时检查接口

### 开始实时检查

- **URL**: `/api/email/start_real_time_check`
- **方法**: `POST`
- **描述**: 开始实时检查邮件
- **权限**: 需要认证
- **成功响应** (200):
  ```json
  {
    "message": "实时检查已启动",
    "status": "running"
  }
  ```
- **错误响应** (400):
  ```json
  {
    "error": "实时检查已在运行中"
  }
  ```

### 停止实时检查

- **URL**: `/api/email/stop_real_time_check`
- **方法**: `POST`
- **描述**: 停止实时检查邮件
- **权限**: 需要认证
- **成功响应** (200):
  ```json
  {
    "message": "实时检查已停止",
    "status": "stopped"
  }
  ```
- **错误响应** (400):
  ```json
  {
    "error": "实时检查未运行"
  }
  ```

### 添加到实时队列

- **URL**: `/api/email/add_to_real_time_queue`
- **方法**: `POST`
- **描述**: 将邮箱添加到实时检查队列
- **权限**: 需要认证
- **请求体**:
  ```json
  {
    "email_ids": [1, 2, 3]
  }
  ```
- **成功响应** (200):
  ```json
  {
    "message": "已添加3个邮箱到实时检查队列",
    "added": 3,
    "skipped": 0
  }
  ```
- **错误响应** (400):
  ```json
  {
    "error": "邮箱ID列表不能为空"
  }
  ```

## 错误处理

所有API都使用统一的错误响应格式：

```json
{
  "error": "错误描述信息"
}
```

对于更复杂的错误情况，可能包含更多字段：

```json
{
  "error": "错误描述信息",
  "details": "详细错误信息",
  "code": "错误代码"
}
```

## 认证说明

### JWT令牌

API使用JSON Web Token (JWT)进行认证。客户端需要在以下位置之一提供令牌：

1. **请求头**:
   ```
   Authorization: Bearer <token>
   ```

2. **Cookie**:
   ```
   token=<token>
   ```

### 认证失败响应

当认证失败时，API将返回以下响应之一：

- **令牌缺失** (401):
  ```json
  {
    "error": "未认证，请先登录"
  }
  ```

- **令牌无效** (401):
  ```json
  {
    "error": "无效的令牌"
  }
  ```

- **令牌过期** (401):
  ```json
  {
    "error": "令牌已过期，请重新登录"
  }
  ```

### 权限检查

某些API需要管理员权限。如果没有足够的权限，将返回以下响应：

- **权限不足** (403):
  ```json
  {
    "error": "需要管理员权限"
  }
  ```

## 分页说明

支持分页的API使用以下查询参数：

- `page`: 页码，默认为1
- `per_page`: 每页条数，默认为20

分页响应包含以下字段：

```json
{
  "items": [...],  // 当前页的数据项
  "total": 42,     // 总条数
  "page": 2,       // 当前页码
  "per_page": 10,  // 每页条数
  "pages": 5       // 总页数
}
``` 
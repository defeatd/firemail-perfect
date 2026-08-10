# 前端开发文档

## 开发环境配置

### 启动开发服务器

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 使用默认端口(3000)启动开发服务器
npm run dev

# 使用自定义端口启动
# Linux/Mac
VITE_PORT=3001 npm run dev

# Windows
set VITE_PORT=3001
npm run dev

# 使用带端口提示的脚本(会显示当前使用的端口)
npm run dev:port
```

### 环境变量配置

前端开发服务器支持以下环境变量：

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| VITE_PORT | 开发服务器端口 | 3000 |

## 技术栈概述

花火邮箱助手前端基于以下技术栈开发：

- **核心框架**：Vue.js 3 (使用Composition API)
- **构建工具**：Vite
- **UI组件库**：Element Plus
- **状态管理**：Vuex 4
- **路由管理**：Vue Router 4
- **HTTP客户端**：Axios
- **WebSocket**：原生WebSocket API

## 目录结构

```
frontend/
├── public/             # 静态资源
├── src/                # 源代码目录
│   ├── assets/         # 静态资源(图片、字体等)
│   ├── components/     # 可复用组件
│   ├── router/         # 路由配置
│   ├── services/       # API服务和WebSocket
│   ├── store/          # Vuex状态管理
│   ├── views/          # 视图组件
│   ├── App.vue         # 根组件
│   └── main.js         # 入口文件
├── index.html          # HTML模板
├── package.json        # 项目依赖管理
└── vite.config.js      # Vite配置
```

## 核心模块

### 1. 用户认证模块

用户认证模块处理用户登录、注册和权限管理，主要包含以下功能：

- 用户登录
- 用户注册
- JWT令牌管理
- 权限验证

相关文件：
- `src/store/modules/auth.js` - 认证状态管理
- `src/services/auth.js` - 认证API服务
- `src/views/LoginView.vue` - 登录界面
- `src/views/RegisterView.vue` - 注册界面

### 2. 邮箱管理模块

邮箱管理模块处理邮箱的添加、删除和批量操作，主要包含以下功能：

- 邮箱列表展示
- 添加邮箱
- 删除邮箱
- 批量操作邮箱
- 邮箱状态显示

相关文件：
- `src/views/EmailsView.vue` - 邮箱管理界面
- `src/components/EmailList.vue` - 邮箱列表组件
- `src/components/AddEmailForm.vue` - 添加邮箱表单
- `src/services/emails.js` - 邮箱相关API服务

### 3. 邮件查看模块

邮件查看模块负责展示和搜索邮件内容，主要包含以下功能：

- 邮件列表显示
- 邮件内容查看
- 邮件搜索
- 邮件排序和筛选

相关文件：
- `src/views/MailRecords.vue` - 邮件记录界面
- `src/components/MailList.vue` - 邮件列表组件
- `src/components/MailDetail.vue` - 邮件详情组件
- `src/services/mails.js` - 邮件相关API服务

### 4. 实时通知模块

实时通知模块基于WebSocket实现，负责接收和显示实时状态更新，主要包含以下功能：

- WebSocket连接管理
- 进度通知处理
- 消息通知展示

相关文件：
- `src/services/websocket.js` - WebSocket服务
- `src/components/Notifications.vue` - 通知组件
- `src/store/modules/notifications.js` - 通知状态管理

### 5. 管理员模块

管理员模块提供系统管理功能，仅对管理员用户可见，主要包含以下功能：

- 用户管理
- 系统配置
- 注册控制

相关文件：
- `src/views/AdminView.vue` - 管理员界面
- `src/components/UserManagement.vue` - 用户管理组件
- `src/services/admin.js` - 管理员API服务

## 组件通信

组件间通信主要通过以下几种方式：

1. **Props & Events**：父子组件间传递数据和事件
2. **Vuex**：全局状态管理，用于跨组件共享数据
3. **Provide/Inject**：用于深层嵌套组件的状态共享
4. **WebSocket**：使用实时消息更新UI状态

## 状态管理

Vuex存储分为以下几个模块：

- **auth**: 用户认证状态
- **emails**: 邮箱相关状态
- **mails**: 邮件相关状态
- **notifications**: 通知相关状态
- **admin**: 管理员相关状态

## API服务

前端通过`services`目录中的服务与后端API通信，使用Axios进行HTTP请求。主要服务包括：

- `auth.js`: 处理认证相关API
- `emails.js`: 处理邮箱相关API
- `mails.js`: 处理邮件相关API
- `admin.js`: 处理管理员相关API
- `websocket.js`: 处理WebSocket连接和消息

## 路由设计

应用路由结构如下：

- `/` - 首页
- `/login` - 登录页
- `/register` - 注册页
- `/emails` - 邮箱管理页
- `/emails/:id/mails` - 邮件列表页
- `/search` - 邮件搜索页
- `/account` - 账户设置页
- `/admin/users` - 用户管理页 (管理员)
- `/about` - 关于页面

## 权限控制

通过路由守卫实现权限控制：

1. 未登录用户只能访问登录、注册和关于页面
2. 普通用户可以访问自己的邮箱和邮件
3. 管理员用户可以访问所有页面，包括用户管理

## UI组件设计

应用使用Element Plus组件库，主要使用以下组件：

- `ElTable`: 数据表格展示
- `ElForm`: 表单输入和验证
- `ElButton`: 按钮操作
- `ElMessage`: 消息提示
- `ElNotification`: 通知消息
- `ElDialog`: 弹出对话框
- `ElTabs`: 标签页切换
- `ElMenu`: 导航菜单

## 响应式设计

应用实现了完整的响应式设计，适配不同屏幕尺寸：

- 桌面端: > 1200px
- 平板端: 768px - 1199px
- 移动端: < 768px

响应式设计主要通过Element Plus的栅格系统和CSS媒体查询实现。
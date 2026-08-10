# 花火邮箱助手 (FireMail) 项目文档

项目仓库：`https://github.com/defeatd/firemail-perfect.git`

## 项目概述

“花火邮箱助手”是一款专为 Microsoft 邮箱设计的批量收件工具，提供简单高效的邮件管理解决方案。该项目旨在帮助用户批量管理多个邮箱账户，自动收取邮件，并提供用户友好的界面进行操作。

### 主要功能

- **批量导入邮箱**：支持“邮箱----密码----客户端ID----RefreshToken”的批量导入格式
- **邮箱管理**：批量操作多个邮箱账户
- **自动收信**：对导入的邮箱进行自动收信操作
- **多用户系统**：支持用户注册、登录，权限分级管理
- **安全管理**：数据存储在本地 SQLite 数据库，确保安全性

### 技术栈

- **后端**：Python 3.10+, Flask, SQLite, WebSocket
- **前端**：Vue 3, Vite, Element Plus
- **其他**：OAuth 2.0, IMAP, Docker

## 文档目录

1. [系统架构](./系统架构.md)
2. [前端文档](./frontend/README.md)
3. [后端文档](./backend/README.md)
4. [WebSocket 服务](./websocket/README.md)
5. [数据库设计](./database/README.md)
6. [API 接口文档](./API接口文档.md)
7. [部署指南](./部署指南.md)
8. [用户指南](./用户指南.md)

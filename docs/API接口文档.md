# API 接口文档

## 认证相关

| 接口 | 方法 | 路径 | 参数 | 返回 |
|------|------|------|------|------|
| 登录 | POST | `/api/auth/login` | `{username, password}` | `{token, user}` |
| 注册 | POST | `/api/auth/register` | `{username, password}` | `{message}` |
| 修改密码 | POST | `/api/auth/change-password` | `{old_password, new_password}` | `{message}` |

## 邮箱相关

| 接口 | 方法 | 路径 | 参数 | 返回 |
|------|------|------|------|------|
| 添加邮箱 | POST | `/api/emails` | `{email, password, mail_type, client_id, refresh_token}` | `{message}` |
| 获取邮箱列表 | GET | `/api/emails` | - | `[email, ...]` |
| 删除邮箱 | DELETE | `/api/emails/{id}` | - | `{message}` |
| 批量删除 | POST | `/api/emails/batch_delete` | `{email_ids: []}` | `{message}` |
| 检查邮箱 | POST | `/api/emails/{id}/check` | - | `{success, message}` |
| 获取邮件记录 | GET | `/api/emails/{id}/mail_records` | - | `[record, ...]` |
| 导出 TXT | GET | `/api/emails/export` | - | `text/plain` |

## Outlook 特殊接口

| 接口 | 方法 | 路径 | 参数 | 返回 |
|------|------|------|------|------|
| Device Code 重新授权 | POST | `/api/emails/{id}/oauth/device/start` | - | `{user_code, verification_uri}` |
| 轮询授权结果 | POST | `/api/oauth/device/{session_id}/poll` | - | `{status}` |

## 健康检查

| 接口 | 方法 | 路径 | 返回 |
|------|------|------|------|
| 健康检查 | GET | `/api/health` | `{status: "ok", message}` |

## 安全说明

- JWT 必须在生产环境自定义
- 邮箱列表 API 对 `password` 脱敏
- 接口无限速（私有部署默认）
- 附件下载 Content-Disposition 安全

---

**完整文档见** `docs/API接口文档.md`。

---

欢迎在 GitHub Issues 中提交问题。
# 花火邮箱助手 (FireMail)

多账号邮箱聚合管理系统：支持 Outlook（OAuth Device Code / Refresh Token）、IMAP、Gmail、QQ 邮箱，提供 Web 管理界面、批量导入、实时收信与邮件搜索。

**仓库：** https://github.com/defeatd/firemail-perfect

---

## 功能概览

| 能力 | 说明 |
|------|------|
| 多协议邮箱 | Outlook OAuth2、通用 IMAP、Gmail、QQ |
| 账号管理 | 添加 / 编辑 / 批量导入 / 批量删除 / 导出 TXT |
| 收信 | 单账号检查、批量收信、后台实时检查 |
| Outlook 授权 | Device Code 重新授权、Token 自动续期 |
| 邮件 | 列表、详情、HTML 渲染（DOMPurify）、附件下载、搜索 |
| 用户与权限 | 注册（可关闭）、管理员用户管理、JWT 认证 |
| 部署 | Docker 一键构建，Caddy 反代前端 + API + WebSocket |

详细文档见 [`docs/`](docs/README.md)。

---

## 快速开始（推荐）

```bash
# 1. 克隆
git clone https://github.com/defeatd/firemail-perfect.git
cd firemail-perfect

# 2. 一键配置并启动（生成 JWT、写 .env、可选改端口）
chmod +x setup-firemail.sh
./setup-firemail.sh

# 3. 浏览器访问（默认端口 11180）
#    http://你的服务器IP:11180/
```

首次打开页面 → **注册**（第一个用户自动成为管理员）→ 登录使用。

### 部署出问题？

```bash
chmod +x troubleshoot.sh
./troubleshoot.sh
```

更完整的从零部署步骤：[docs/DEPLOYMENT-GUIDE.md](docs/DEPLOYMENT-GUIDE.md)

---

## 手动配置

### 1. 环境变量

```bash
cp .env.example .env
# 编辑 .env，至少设置：
openssl rand -hex 32   # 生成后填入 JWT_SECRET_KEY
```

| 变量 | 必需 | 说明 |
|------|------|------|
| `JWT_SECRET_KEY` | ✅ | JWT 签名密钥，生产环境必须自定义 |
| `ALLOWED_ORIGINS` | 推荐 | CORS 允许来源，逗号分隔，需含实际访问 URL |
| `TZ` | 否 | 时区，默认 `Asia/Shanghai` |
| `OUTLOOK_TOKEN_REFRESH_INTERVAL` | 否 | Outlook Token 巡检间隔（秒），默认 1500 |
| `OUTLOOK_TOKEN_RENEW_BEFORE` | 否 | 过期前多少秒续期，默认 600 |

完整说明：[docs/ENVIRONMENT-SETUP.md](docs/ENVIRONMENT-SETUP.md)

### 2. 端口（`docker-compose.yml`）

默认：

```yaml
ports:
  - "11180:80"   # 主机:容器 → 访问 http://IP:11180/
```

改成其他端口示例：

```yaml
ports:
  - "11180:80"   # 主机:容器 → 访问 http://IP:11180/
  - "80:80"      # http://IP/
  - "8080:80"    # http://IP:8080/
```

同时把 `.env` 里的 `ALLOWED_ORIGINS` 改成对应地址。

> 若只绑定某网卡（如 Tailscale），可写成 `"100.x.x.x:11180:80"`，仅该 IP 可访问。

### 3. 启动

```bash
docker compose up --build -d
```

健康检查：`http://服务器IP:端口/api/health`

---

## 架构简述

```
浏览器
  → Caddy(:80)
       → 静态前端 (Vue3 + Element Plus)
       → /api/*  → Flask(:5000)
       → /ws     → WebSocket(:8765)
  → SQLite 数据卷 ./data
  → 日志 ./logs
```

- 前端：`frontend/`（Vite + Vue3）
- 后端：`backend/app.py` + `backend/utils/email/`
- 反向代理：`Caddyfile`
- 镜像构建：`Dockerfile`（多阶段：Node 构建前端 + Python 运行时）

---

## 常用命令

```bash
docker compose logs -f      # 看日志
docker compose restart      # 重启
docker compose down         # 停止并移除容器
git pull && docker compose up --build -d   # 更新代码后重建
```

---

## 安全说明

- 用户登录密码：PBKDF2-SHA256 哈希存储
- 生产环境强制 `JWT_SECRET_KEY`，禁止默认密钥
- 可配置 CORS
- 邮箱列表 API 对 `password` / `access_token` 脱敏（密码需单独接口获取）
- **不要**把 `.env`、`data/*.db`、`logs/` 提交到 Git（已在 `.gitignore`）

历史安全审核文档：[docs/安全审核报告.md](docs/安全审核报告.md)（部分项已在后续版本修复，以当前代码为准）。

---

## 多架构 / ARM

支持 `amd64` / `arm64` / `armv7`。一般直接：

```bash
docker compose up --build -d
```

专用说明：[docs/ARM-DEPLOYMENT.md](docs/ARM-DEPLOYMENT.md)，或使用 `./build-multiarch.sh`。

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/DEPLOYMENT-GUIDE.md](docs/DEPLOYMENT-GUIDE.md) | 完整部署 |
| [docs/ENVIRONMENT-SETUP.md](docs/ENVIRONMENT-SETUP.md) | 环境变量 |
| [docs/用户指南.md](docs/用户指南.md) | 使用说明 |
| [docs/系统架构.md](docs/系统架构.md) | 架构 |
| [docs/API接口文档.md](docs/API接口文档.md) | API |
| [docs/README.md](docs/README.md) | 文档总目录 |

---

## 故障排除（简要）

1. **启动失败**：检查 `.env` 是否含 `JWT_SECRET_KEY`；执行 `docker compose logs -f`
2. **无法访问**：防火墙放行端口；`ALLOWED_ORIGINS` 是否包含当前访问 URL
3. **端口冲突**：修改 `docker-compose.yml` 的 `ports` 左侧端口，或运行 `./troubleshoot.sh`

---

欢迎提交 Issue / PR。

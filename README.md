# 花火邮箱助手 (FireMail) 部署指南

项目仓库：`https://github.com/defeatd/firemail-perfect.git`

本文档提供 **花火邮箱助手（FireMail）** 的快速部署方法。如需详细的完整部署指南，请查看 **[📚 完整部署指南](docs/DEPLOYMENT-GUIDE.md)**。

---

## 🚀 快速开始

### 一键自动部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/defeatd/firemail-perfect.git
cd firemail-perfect

# 2. 运行自动配置脚本
chmod +x setup-firemail.sh
./setup-firemail.sh

# 3. 完成！访问 http://你的IP:端口/
```

### 🔧 遇到问题？一键修复

如果部署过程中遇到任何问题，运行故障排除脚本：

```bash
# 自动诊断和修复常见问题
chmod +x troubleshoot.sh
./troubleshoot.sh
```

故障排除脚本会自动：
- ✅ 检查 Docker 环境
- ✅ 生成缺失的环境变量
- ✅ 解决容器名冲突
- ✅ 处理端口占用问题
- ✅ 清理磁盘空间
- ✅ 自动启动服务

> 💡 **需要详细指导？** 查看 [📚 完整部署指南](docs/DEPLOYMENT-GUIDE.md) 获取从零开始的详细部署步骤。

---

## 📦 克隆项目

```bash
git clone https://github.com/defeatd/firemail-perfect.git
cd firemail-perfect
```

---

## 🔐 安全配置（必须）

**重要：** 在启动服务前，必须配置以下安全参数：

### 🚀 快速配置（推荐）

使用自动配置脚本，一键完成所有设置：

```bash
# 运行自动配置脚本
chmod +x setup-firemail.sh
./setup-firemail.sh
```

脚本会自动：
- 检测本机 IP 地址
- 生成安全的 JWT 密钥
- 配置 CORS 域名
- 创建 .env 配置文件
- 可选择立即启动服务

### 🔧 手动配置

如果需要手动配置，请按以下步骤：

#### 1. 生成 JWT 密钥

```bash
# 生成随机 JWT 密钥
openssl rand -hex 32
```

#### 2. 设置环境变量

创建 `.env` 文件或直接设置环境变量：

```bash
# 方式一：创建 .env 文件
cat > .env << EOF
JWT_SECRET_KEY=你生成的32位随机密钥
ALLOWED_ORIGINS=http://你的IP,http://你的IP:端口
TZ=Asia/Shanghai
EOF

# 方式二：直接导出环境变量
export JWT_SECRET_KEY="你生成的32位随机密钥"
export ALLOWED_ORIGINS="http://你的域名,https://你的域名"
```

#### 3. 环境变量说明

| 变量名 | 必需 | 说明 | 示例 |
|--------|------|------|------|
| `JWT_SECRET_KEY` | ✅ | JWT 签名密钥，必须是32位随机字符串 | `a1b2c3d4e5f6...` |
| `ALLOWED_ORIGINS` | 推荐 | 允许的 CORS 域名，多个用逗号分隔 | `http://192.168.1.100:8080` |

> 📚 **详细配置指南**：查看 [docs/ENVIRONMENT-SETUP.md](docs/ENVIRONMENT-SETUP.md) 了解完整的环境变量配置方法。

---

## ⚙️ 修改配置（可选）

默认情况下，项目会以 Docker Compose **本地构建镜像**并启动，核心配置在 `docker-compose.yml` 中。

你可以按需修改：

### 🌐 端口配置

**默认端口**：80
```yaml
ports:
  - "80:80"  # 访问地址：http://IP/
```

**自定义端口**：
```yaml
ports:
  - "8080:80"  # 访问地址：http://IP:8080/
  - "3000:80"  # 访问地址：http://IP:3000/
  - "任意端口:80"  # 访问地址：http://IP:任意端口/
```

### 📁 其他配置

- **数据与日志持久化目录**：默认挂载 `./data`、`./logs`
- **时区**：默认 `Asia/Shanghai`

---

## ▶️ 构建并启动服务

在项目根目录执行：

```bash
# 确保已设置 JWT_SECRET_KEY 环境变量
docker compose up --build -d
```

### 🏗️ 多架构支持

FireMail 支持以下架构的部署：

- **AMD64** (x86_64) - Intel/AMD 处理器
- **ARM64** (aarch64) - Apple M1/M2, 树莓派 4B+, AWS Graviton
- **ARMv7** (armhf) - 树莓派 3B/3B+

#### ARM 设备部署

对于 ARM 设备（如树莓派），可以直接使用标准命令：

```bash
# 自动检测架构并构建对应镜像
docker compose up --build -d
```

#### 手动多架构构建

如果需要手动构建多架构镜像：

```bash
# 使用提供的构建脚本
chmod +x build-multiarch.sh
./build-multiarch.sh
```

或者使用 Docker Buildx：

```bash
# 创建多架构构建器
docker buildx create --name firemail-builder --use

# 构建多架构镜像
docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7 -t firemail:latest --load .
```

这会：

- 构建前端（Vue3 + Element Plus）产物
- 安装后端依赖并启动 Flask API + WebSocket 服务
- 根据目标架构自动下载对应的 Caddy 二进制文件
- 启动内置的 Caddy 作为反向代理与静态文件服务器
- 应用所有安全配置（密码哈希、JWT 安全、CORS 限制等）

---

## ✅ 启动完成

部署成功后，你可以通过以下方式访问：

### 🌐 Web 界面访问

**默认端口 80：**
- `http://服务器IP/`
- `http://192.168.1.100/`（局域网）
- `http://你的公网IP/`（公网）

**自定义端口（如修改为 8080）：**
- `http://服务器IP:8080/`
- `http://192.168.1.100:8080/`

### 🔍 健康检查

- **默认端口**：`http://服务器IP/api/health`
- **自定义端口**：`http://服务器IP:端口/api/health`

### 📱 移动端访问

FireMail 支持响应式设计，可以在手机浏览器中正常使用：
- 在手机浏览器中输入相同的地址
- 界面会自动适配移动端显示

### 🔐 首次使用

1. 访问 Web 界面
2. 点击"注册"创建管理员账户
3. 登录后即可开始使用邮箱管理功能

---

## 🔧 常用命令

停止服务：

```bash
docker compose down
```

查看日志：

```bash
docker compose logs -f
```

重启服务：

```bash
docker compose restart
```

更新服务（拉取最新代码后）：

```bash
git pull
docker compose up --build -d
```

---

## 🛡️ 安全特性

本版本包含以下安全改进：

- ✅ **密码安全**：使用 PBKDF2-SHA256 哈希存储密码
- ✅ **JWT 安全**：强制要求自定义 JWT 密钥
- ✅ **CORS 保护**：可配置允许的域名
- ✅ **Cookie 安全**：生产环境启用 Secure 标志
- ✅ **密码策略**：最少 8 位字符要求
- ✅ **请求限制**：登录和注册接口限流保护
- ✅ **安全响应头**：防止 XSS、点击劫持等攻击

---

## 📱 界面特性

- 🎨 **现代化设计**：圆润界面，渐变背景，玻璃态效果
- 📱 **移动端适配**：响应式布局，抽屉式菜单
- 🌙 **Element Plus**：完整的 Vue3 组件库支持
- ⚡ **性能优化**：Vite 构建，快速加载

---

## 🚨 故障排除

### 启动失败

1. **检查环境变量**：确保 `JWT_SECRET_KEY` 已设置
2. **检查端口占用**：确保 80 端口未被占用
3. **查看日志**：`docker compose logs -f` 查看详细错误

### 无法访问

1. **防火墙设置**：确保 80 端口已开放
2. **CORS 配置**：检查 `ALLOWED_ORIGINS` 是否包含你的域名

### ARM 架构问题

1. **架构不匹配**：
   ```bash
   # 检查当前架构
   uname -m
   # 或
   dpkg --print-architecture
   ```

2. **构建失败**：
   ```bash
   # 清理构建缓存
   docker system prune -a

   # 重新构建
   docker compose up --build -d
   ```

3. **树莓派内存不足**：
   ```bash
   # 增加交换空间
   sudo dphys-swapfile swapoff
   sudo sed -i 's/CONF_SWAPSIZE=100/CONF_SWAPSIZE=1024/' /etc/dphys-swapfile
   sudo dphys-swapfile setup
   sudo dphys-swapfile swapon
   ```

4. **Docker Buildx 问题**：
   ```bash
   # 安装/更新 Docker Buildx
   docker buildx install

   # 检查支持的平台
   docker buildx ls
   ```

---

## 📚 项目文档

更多文档请见：`docs/README.md`

---

欢迎提交 Issue / PR！

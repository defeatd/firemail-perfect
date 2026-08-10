# FireMail 环境变量配置详细指南

本指南详细说明 FireMail 部署时需要的所有环境变量配置。

## 🔐 必需的环境变量

### JWT_SECRET_KEY（必须设置）

**作用**：用于 JWT 令牌的签名和验证，确保用户会话安全。

**生成方法**：
```bash
# 方法1：使用 openssl（推荐）
openssl rand -hex 32

# 方法2：使用 Python
python3 -c "import secrets; print(secrets.token_hex(32))"

# 方法3：在线生成
# 访问 https://generate-secret.vercel.app/32
```

**示例输出**：
```
a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456
```

## 🌐 可选的环境变量

### ALLOWED_ORIGINS（推荐设置）

**作用**：控制哪些域名可以访问 API，防止跨域攻击。

**默认值**：`http://localhost`

**配置示例**：
```bash
# 单个域名
ALLOWED_ORIGINS="http://192.168.1.100"

# 多个域名（用逗号分隔）
ALLOWED_ORIGINS="http://192.168.1.100,http://192.168.1.100:8080,https://yourdomain.com"

# 包含不同端口
ALLOWED_ORIGINS="http://localhost,http://127.0.0.1,http://192.168.1.100:8080"
```

## 📝 环境变量设置方法

### 方法1：创建 .env 文件（推荐）

在项目根目录创建 `.env` 文件：

```bash
# 进入项目目录
cd firemail-perfect

# 创建 .env 文件
cat > .env << 'EOF'
# JWT 密钥（必须）- 请替换为你生成的密钥
JWT_SECRET_KEY=a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456

# 允许的访问域名（可选）- 请替换为你的实际 IP/域名
ALLOWED_ORIGINS=http://192.168.1.100,http://192.168.1.100:8080

# 时区（可选）
TZ=Asia/Shanghai
EOF
```

### 方法2：直接导出环境变量

```bash
# 设置 JWT 密钥
export JWT_SECRET_KEY="你生成的32位密钥"

# 设置允许的域名
export ALLOWED_ORIGINS="http://你的IP,http://你的IP:端口"

# 设置时区
export TZ="Asia/Shanghai"
```

### 方法3：在 docker-compose.yml 中直接设置

编辑 `docker-compose.yml` 文件：

```yaml
environment:
  - TZ=Asia/Shanghai
  - HOST=0.0.0.0
  - FLASK_PORT=5000
  - WS_PORT=8765
  - FLASK_ENV=production
  # 直接设置 JWT 密钥（不推荐，安全性较低）
  - JWT_SECRET_KEY=你的32位密钥
  # 直接设置允许的域名
  - ALLOWED_ORIGINS=http://192.168.1.100,http://192.168.1.100:8080
```

## 🚀 完整部署示例

### 示例1：局域网部署（IP: 192.168.1.100）

```bash
# 1. 克隆项目
git clone https://github.com/defeatd/firemail-perfect.git
cd firemail-perfect

# 2. 生成 JWT 密钥
JWT_KEY=$(openssl rand -hex 32)
echo "生成的 JWT 密钥: $JWT_KEY"

# 3. 创建 .env 文件
cat > .env << EOF
JWT_SECRET_KEY=$JWT_KEY
ALLOWED_ORIGINS=http://192.168.1.100,http://192.168.1.100:8080
TZ=Asia/Shanghai
EOF

# 4. 启动服务
docker compose up --build -d

# 5. 访问服务
echo "请访问: http://192.168.1.100/"
```

### 示例2：自定义端口部署（端口: 8080）

```bash
# 1. 克隆项目
git clone https://github.com/defeatd/firemail-perfect.git
cd firemail-perfect

# 2. 生成 JWT 密钥
JWT_KEY=$(openssl rand -hex 32)

# 3. 修改端口
sed -i 's/"80:80"/"8080:80"/' docker-compose.yml

# 4. 创建 .env 文件
cat > .env << EOF
JWT_SECRET_KEY=$JWT_KEY
ALLOWED_ORIGINS=http://192.168.1.100:8080,http://localhost:8080
TZ=Asia/Shanghai
EOF

# 5. 启动服务
docker compose up --build -d

# 6. 访问服务
echo "请访问: http://192.168.1.100:8080/"
```

### 示例3：公网部署（域名: yourdomain.com）

```bash
# 1. 克隆项目
git clone https://github.com/defeatd/firemail-perfect.git
cd firemail-perfect

# 2. 生成 JWT 密钥
JWT_KEY=$(openssl rand -hex 32)

# 3. 创建 .env 文件
cat > .env << EOF
JWT_SECRET_KEY=$JWT_KEY
ALLOWED_ORIGINS=https://yourdomain.com,http://yourdomain.com
TZ=Asia/Shanghai
EOF

# 4. 启动服务
docker compose up --build -d

# 5. 配置反向代理（Nginx/Caddy）
# 将 yourdomain.com 指向服务器的 80 端口
```

## 🔍 验证配置

### 检查环境变量是否生效

```bash
# 查看容器环境变量
docker exec firemail env | grep -E "(JWT_SECRET_KEY|ALLOWED_ORIGINS)"

# 检查服务状态
docker compose ps

# 查看日志
docker compose logs -f
```

### 测试访问

```bash
# 测试健康检查
curl http://你的IP/api/health

# 测试 CORS（应该返回正常响应）
curl -H "Origin: http://你的IP" http://你的IP/api/health
```

## ⚠️ 安全注意事项

### JWT_SECRET_KEY 安全

1. **必须是随机生成**：不要使用简单的字符串
2. **长度至少32位**：确保足够的安全强度
3. **不要泄露**：不要在日志或代码中暴露
4. **定期更换**：建议定期更换密钥

### ALLOWED_ORIGINS 配置

1. **不要使用通配符**：避免使用 `*`
2. **明确指定域名**：只允许需要的域名
3. **包含协议**：必须包含 `http://` 或 `https://`
4. **考虑端口**：如果使用非标准端口，必须明确指定

## 🚨 常见错误和解决方案

### 错误1：JWT_SECRET_KEY 未设置

**错误信息**：
```
请设置 JWT_SECRET_KEY 环境变量
```

**解决方案**：
```bash
# 生成并设置 JWT 密钥
export JWT_SECRET_KEY=$(openssl rand -hex 32)
```

### 错误2：CORS 错误

**错误信息**：
```
Access to fetch at 'http://IP/api/...' from origin 'http://IP' has been blocked by CORS policy
```

**解决方案**：
```bash
# 设置正确的 ALLOWED_ORIGINS
export ALLOWED_ORIGINS="http://你的实际IP,http://你的实际IP:端口"
```

### 错误3：无法访问服务

**可能原因**：
1. 端口被占用
2. 防火墙阻止
3. Docker 服务未启动

**解决方案**：
```bash
# 检查端口占用
netstat -tlnp | grep :80

# 检查防火墙
sudo ufw status

# 检查 Docker 服务
docker compose ps
docker compose logs
```

## 📋 环境变量完整列表

| 变量名 | 必需 | 默认值 | 说明 | 示例 |
|--------|------|--------|------|------|
| `JWT_SECRET_KEY` | ✅ | 无 | JWT 签名密钥 | `a1b2c3d4e5f6...` |
| `ALLOWED_ORIGINS` | 推荐 | `http://localhost` | 允许的 CORS 域名 | `http://192.168.1.100` |
| `TZ` | 可选 | `Asia/Shanghai` | 时区设置 | `Asia/Shanghai` |
| `HOST` | 自动 | `0.0.0.0` | 服务绑定地址 | `0.0.0.0` |
| `FLASK_PORT` | 自动 | `5000` | Flask 端口 | `5000` |
| `WS_PORT` | 自动 | `8765` | WebSocket 端口 | `8765` |
| `FLASK_ENV` | 自动 | `production` | Flask 环境 | `production` |

## 🎯 快速配置脚本

创建一个自动配置脚本：

```bash
#!/bin/bash
# 文件名: setup-firemail.sh

echo "🚀 FireMail 自动配置脚本"

# 获取本机 IP
LOCAL_IP=$(hostname -I | awk '{print $1}')
echo "检测到本机 IP: $LOCAL_IP"

# 询问端口
read -p "请输入要使用的端口 (默认 80): " PORT
PORT=${PORT:-80}

# 生成 JWT 密钥
JWT_KEY=$(openssl rand -hex 32)

# 创建 .env 文件
cat > .env << EOF
JWT_SECRET_KEY=$JWT_KEY
ALLOWED_ORIGINS=http://$LOCAL_IP:$PORT,http://localhost:$PORT,http://127.0.0.1:$PORT
TZ=Asia/Shanghai
EOF

# 修改端口配置
if [ "$PORT" != "80" ]; then
    sed -i "s/\"11180:80\"/\"$PORT:80\"/" docker-compose.yml
fi

echo "✅ 配置完成！"
echo "📋 配置信息："
echo "   JWT 密钥: $JWT_KEY"
echo "   访问地址: http://$LOCAL_IP:$PORT/"
echo "   允许域名: http://$LOCAL_IP:$PORT/"

echo ""
echo "🚀 启动服务："
echo "   docker compose up --build -d"
```

使用方法：
```bash
chmod +x setup-firemail.sh
./setup-firemail.sh
```

这样就可以自动完成所有环境变量的配置了！
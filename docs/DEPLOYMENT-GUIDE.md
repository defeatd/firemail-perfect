# FireMail 完整部署指南

本指南将从零开始，详细介绍如何在任何 Linux 服务器上部署 FireMail 邮箱管理系统。

## 📋 目录

- [系统要求](#系统要求)
- [环境准备](#环境准备)
- [获取项目](#获取项目)
- [自动部署（推荐）](#自动部署推荐)
- [手动部署](#手动部署)
- [常见问题解决](#常见问题解决)
- [部署后配置](#部署后配置)
- [维护和管理](#维护和管理)

---

## 📦 系统要求

### 最低配置
- **CPU**: 1 核心
- **内存**: 1GB RAM
- **存储**: 5GB 可用空间
- **网络**: 稳定的互联网连接

### 推荐配置
- **CPU**: 2 核心或以上
- **内存**: 2GB RAM 或以上
- **存储**: 10GB 可用空间
- **网络**: 带宽 10Mbps 或以上

### 支持的系统
- Ubuntu 18.04+ / Debian 9+
- CentOS 7+ / RHEL 7+
- 树莓派 OS (ARM)
- 其他支持 Docker 的 Linux 发行版

---

## 🛠 环境准备

### 1. 更新系统

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt upgrade -y
```

**CentOS/RHEL:**
```bash
sudo yum update -y
# 或者 (CentOS 8+)
sudo dnf update -y
```

### 2. 安装必要工具

**Ubuntu/Debian:**
```bash
sudo apt install -y curl wget git openssl
```

**CentOS/RHEL:**
```bash
sudo yum install -y curl wget git openssl
# 或者 (CentOS 8+)
sudo dnf install -y curl wget git openssl
```

### 3. 安装 Docker

**方法1: 官方一键安装脚本（推荐）**
```bash
# 下载并运行 Docker 安装脚本
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 将当前用户添加到 docker 组
sudo usermod -aG docker $USER

# 启动 Docker 服务
sudo systemctl start docker
sudo systemctl enable docker

# 重新登录或重启以使组权限生效
sudo reboot
```

**方法2: 手动安装（Ubuntu/Debian）**
```bash
# 添加 Docker 官方 GPG 密钥
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# 添加 Docker 仓库
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动服务
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
```

### 4. 验证 Docker 安装

```bash
# 检查 Docker 版本
docker --version

# 检查 Docker Compose 版本
docker compose version

# 测试 Docker 运行
docker run hello-world
```

如果看到 "Hello from Docker!" 消息，说明 Docker 安装成功。

---

## 📥 获取项目

### 1. 克隆项目

```bash
# 克隆到当前用户目录
cd ~
git clone https://github.com/defeatd/firemail-perfect.git

# 进入项目目录
cd firemail-perfect
```

### 2. 检查项目文件

```bash
# 查看项目结构
ls -la

# 应该看到以下文件：
# - docker-compose.yml
# - Dockerfile
# - setup-firemail.sh
# - README.md
# - frontend/ (前端代码)
# - backend/ (后端代码)
```

---

## 🚀 自动部署（推荐）

### 1. 运行自动配置脚本

```bash
# 给脚本执行权限
chmod +x setup-firemail.sh

# 运行自动配置脚本
./setup-firemail.sh
```

### 2. 脚本交互流程

脚本会依次询问以下问题：

#### 步骤1: 端口配置
```
请输入要使用的端口 (默认 80):
```
- **默认端口 11180**: 直接按回车，访问地址为 `http://IP:11180/`
- **自定义端口**: 输入端口号（如 `8080`），访问地址为 `http://IP:8080/`
- **推荐**: 如果 80 端口被占用，使用 `8080` 或 `9610`

#### 步骤2: CORS 域名配置
```
🌐 CORS 域名配置
默认允许的域名: http://你的IP:端口
是否添加其他域名? (y/N):
```
- **选择 N**: 只允许检测到的 IP 访问（推荐）
- **选择 Y**: 可以添加其他域名，如 `https://yourdomain.com`

#### 步骤3: 立即启动
```
是否立即启动 FireMail 服务? (Y/n):
```
- **选择 Y**: 立即启动服务（推荐）
- **选择 n**: 稍后手动启动

### 3. 自动部署完成

如果一切顺利，你会看到：

```
🎉 FireMail 启动成功！
================================
🌐 访问地址: http://你的IP:端口/
🔍 健康检查: http://你的IP:端口/api/health
```

**跳转到 [验证部署](#验证部署) 部分**

---

## 🔧 手动部署

如果自动脚本失败或你想手动控制每个步骤，请按以下步骤操作：

### 1. 生成 JWT 密钥

```bash
# 生成 32 位随机密钥
JWT_KEY=$(openssl rand -hex 32)
echo "生成的 JWT 密钥: $JWT_KEY"
```

### 2. 获取服务器 IP

```bash
# 获取本机 IP
SERVER_IP=$(hostname -I | awk '{print $1}')
echo "服务器 IP: $SERVER_IP"
```

### 3. 创建环境变量文件

```bash
# 创建 .env 文件
cat > .env << EOF
# FireMail 环境变量配置
JWT_SECRET_KEY=$JWT_KEY
ALLOWED_ORIGINS=http://$SERVER_IP,http://$SERVER_IP:8080,http://localhost
TZ=Asia/Shanghai
EOF

echo "环境变量文件已创建"
```

### 4. 配置端口（可选）

如果要使用非 80 端口，修改 docker-compose.yml：

```bash
# 使用 8080 端口示例
sed -i "s/\"80:80\"/\"$PORT:80\"/" docker-compose.yml

# 验证修改
grep "ports:" -A 1 docker-compose.yml
```

### 5. 解决容器名冲突（如果存在）

```bash
# 检查是否有同名容器
docker ps -a | grep firemail

# 如果存在，停止并删除
docker compose down 2>/dev/null || true

# 或者修改容器名
sed -i 's/container_name: firemail/container_name: firemail-'$(date +%s)'/' docker-compose.yml
```

### 6. 启动服务

```bash
# 构建并启动服务
docker compose up --build -d

# 查看启动状态
docker compose ps
```

---

## 🔍 验证部署

### 1. 检查容器状态

```bash
# 查看容器运行状态
docker compose ps

# 应该看到类似输出：
# NAME       COMMAND                  SERVICE   STATUS    PORTS
# firemail   "/bin/bash /app/dock…"   firemail  running   0.0.0.0:80->80/tcp
```

### 2. 检查服务健康

```bash
# 获取访问地址
SERVER_IP=$(hostname -I | awk '{print $1}')
PORT=$(docker compose ps --format "table {{.Ports}}" | grep -o '[0-9]*:80' | cut -d: -f1 | head -1)
PORT=${PORT:-80}

echo "访问地址: http://$SERVER_IP:$PORT/"

# 测试健康检查接口
curl -f http://$SERVER_IP:$PORT/api/health

# 如果返回 {"status": "ok"} 说明服务正常
```

### 3. 查看日志

```bash
# 查看实时日志
docker compose logs -f

# 查看最近日志
docker compose logs --tail=50

# 如果看到类似输出说明启动成功：
# firemail  | [INFO] Flask app started on 0.0.0.0:5000
# firemail  | [INFO] WebSocket server started on 0.0.0.0:8765
# firemail  | [INFO] Caddy server started on :80
```

### 4. 浏览器访问

打开浏览器，访问：`http://你的服务器IP:端口/`

如果看到 FireMail 登录页面，说明部署成功！

---

## 🚨 常见问题解决

### 问题1: 容器名冲突

**错误信息:**
```
Error response from daemon: Conflict. The container name "/firemail" is already in use
```

**解决方案:**
```bash
# 方法1: 停止现有容器
docker compose down

# 方法2: 修改容器名
sed -i 's/container_name: firemail/container_name: firemail-new/' docker-compose.yml

# 重新启动
docker compose up --build -d
```

### 问题2: JWT_SECRET_KEY 未设置

**错误信息:**
```
required variable JWT_SECRET_KEY is missing a value
```

**解决方案:**
```bash
# 快速设置环境变量
export JWT_SECRET_KEY=$(openssl rand -hex 32)
export ALLOWED_ORIGINS="http://$(hostname -I | awk '{print $1}')"

# 或创建 .env 文件
cat > .env << EOF
JWT_SECRET_KEY=$(openssl rand -hex 32)
ALLOWED_ORIGINS=http://$(hostname -I | awk '{print $1}')
TZ=Asia/Shanghai
EOF
```

### 问题3: 端口被占用

**错误信息:**
```
Error starting userland proxy: listen tcp4 0.0.0.0:80: bind: address already in use
```

**解决方案:**
```bash
# 检查端口占用
sudo netstat -tlnp | grep :80

# 修改为其他端口
sed -i "s/\"80:80\"/\"$PORT:80\"/" docker-compose.yml

# 重新启动
docker compose up --build -d
```

### 问题4: Docker 权限问题

**错误信息:**
```
permission denied while trying to connect to the Docker daemon socket
```

**解决方案:**
```bash
# 将用户添加到 docker 组
sudo usermod -aG docker $USER

# 重新登录或重启
sudo reboot

# 或临时使用 sudo
sudo docker compose up --build -d
```

### 问题5: 内存不足

**错误信息:**
```
Cannot allocate memory
```

**解决方案:**
```bash
# 检查内存使用
free -h

# 增加交换空间（临时）
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 清理 Docker 缓存
docker system prune -a -f
```

### 问题6: 网络连接问题

**错误信息:**
```
Could not resolve host: github.com
```

**解决方案:**
```bash
# 检查网络连接
ping -c 3 8.8.8.8

# 检查 DNS 设置
cat /etc/resolv.conf

# 临时设置 DNS
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf

# 重试部署
docker compose up --build -d
```

### 问题7: 构建超时

**错误信息:**
```
context deadline exceeded
```

**解决方案:**
```bash
# 增加构建超时时间
export DOCKER_CLIENT_TIMEOUT=300
export COMPOSE_HTTP_TIMEOUT=300

# 使用国内镜像源（中国用户）
mkdir -p ~/.docker
cat > ~/.docker/daemon.json << EOF
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com"
  ]
}
EOF

sudo systemctl restart docker
```

---

## 🔐 部署后配置

### 1. 创建管理员账户

1. 打开浏览器访问 FireMail
2. 点击"注册"按钮
3. 填写用户名和密码（首个注册用户自动成为管理员）
4. 点击"注册"完成账户创建

### 2. 配置防火墙

**Ubuntu/Debian (UFW):**
```bash
# 允许访问端口
sudo ufw allow 80/tcp
# 或自定义端口
sudo ufw allow 8080/tcp

# 启用防火墙
sudo ufw enable
```

**CentOS/RHEL (firewalld):**
```bash
# 允许访问端口
sudo firewall-cmd --permanent --add-port=80/tcp
# 或自定义端口
sudo firewall-cmd --permanent --add-port=8080/tcp

# 重载配置
sudo firewall-cmd --reload
```

### 3. 配置域名（可选）

如果你有域名，可以配置反向代理：

**Nginx 配置示例:**
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### 4. 配置 SSL（推荐）

使用 Let's Encrypt 免费 SSL 证书：

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d yourdomain.com

# 自动续期
sudo crontab -e
# 添加以下行：
# 0 12 * * * /usr/bin/certbot renew --quiet
```

---

## 🔧 维护和管理

### 日常管理命令

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 更新服务
git pull
docker compose up --build -d
```

### 数据备份

```bash
# 备份数据目录
sudo tar -czf firemail-backup-$(date +%Y%m%d).tar.gz ./data

# 恢复数据
sudo tar -xzf firemail-backup-20231225.tar.gz
```

### 监控和日志

```bash
# 查看资源使用
docker stats firemail

# 查看磁盘使用
du -sh ./data ./logs

# 清理日志（保留最近7天）
find ./logs -name "*.log" -mtime +7 -delete
```

### 性能优化

```bash
# 清理 Docker 缓存
docker system prune -a

# 限制日志大小
# 编辑 docker-compose.yml 添加：
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

---

## 📞 技术支持

如果遇到问题，请按以下步骤获取帮助：

### 1. 收集诊断信息

```bash
# 创建诊断脚本
cat > diagnose.sh << 'EOF'
#!/bin/bash
echo "=== FireMail 诊断信息 ==="
echo "时间: $(date)"
echo "系统: $(uname -a)"
echo "Docker版本: $(docker --version)"
echo "Docker Compose版本: $(docker compose version)"
echo ""
echo "=== 容器状态 ==="
docker compose ps
echo ""
echo "=== 最近日志 ==="
docker compose logs --tail=50
echo ""
echo "=== 环境变量 ==="
cat .env 2>/dev/null || echo "未找到 .env 文件"
echo ""
echo "=== 端口占用 ==="
netstat -tlnp | grep -E ":(80|8080|9610) "
echo ""
echo "=== 磁盘空间 ==="
df -h
echo ""
echo "=== 内存使用 ==="
free -h
EOF

chmod +x diagnose.sh
./diagnose.sh > firemail-diagnose.txt
```

### 2. 提交问题

将 `firemail-diagnose.txt` 文件内容复制，然后：

1. 访问 [GitHub Issues](https://github.com/defeatd/firemail-perfect/issues)
2. 点击 "New Issue"
3. 详细描述问题和操作步骤
4. 粘贴诊断信息

### 3. 社区支持

- GitHub Discussions: 讨论功能和使用问题
- GitHub Issues: 报告 Bug 和功能请求

---

## 🎉 部署完成

恭喜！你已经成功部署了 FireMail 邮箱管理系统。

**下一步:**
1. 创建管理员账户
2. 添加邮箱账户
3. 开始管理你的邮件

**访问地址:** `http://你的服务器IP:端口/`

享受使用 FireMail 吧！ 🚀
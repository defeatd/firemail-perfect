# ARM 设备部署指南

本指南专门针对 ARM 架构设备（如树莓派、Apple M1/M2 Mac、AWS Graviton 等）的 FireMail 部署。

## 🔧 支持的 ARM 架构

- **ARM64** (aarch64) - 树莓派 4B+, Apple M1/M2, AWS Graviton
- **ARMv7** (armhf) - 树莓派 3B/3B+

## 📋 系统要求

### 树莓派
- **最低配置**：树莓派 3B+ (1GB RAM)
- **推荐配置**：树莓派 4B (4GB+ RAM)
- **操作系统**：Raspberry Pi OS (64位推荐)
- **存储空间**：至少 8GB 可用空间

### Apple Silicon Mac
- **处理器**：M1/M2/M3 芯片
- **内存**：至少 4GB 可用
- **操作系统**：macOS 11.0+

## 🚀 快速部署

### 1. 安装 Docker

#### 树莓派
```bash
# 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 添加用户到 docker 组
sudo usermod -aG docker $USER

# 重新登录或重启
sudo reboot
```

#### Apple Silicon Mac
```bash
# 下载并安装 Docker Desktop for Mac (Apple Silicon)
# https://docs.docker.com/desktop/install/mac-install/
```

### 2. 克隆项目
```bash
git clone https://github.com/defeatd/firemail-perfect.git
cd firemail-perfect
```

### 3. 配置环境变量
```bash
# 生成 JWT 密钥
openssl rand -hex 32

# 设置环境变量
export JWT_SECRET_KEY="你生成的密钥"
export ALLOWED_ORIGINS="http://你的设备IP"
```

### 4. 启动服务
```bash
# 自动检测架构并构建
docker compose up --build -d
```

## ⚡ 性能优化

### 树莓派优化

#### 增加交换空间
```bash
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=100/CONF_SWAPSIZE=1024/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

#### GPU 内存分配
```bash
# 编辑配置文件
sudo nano /boot/config.txt

# 添加以下行（为 CPU 分配更多内存）
gpu_mem=16
```

#### 启用 cgroup
```bash
# 编辑 cmdline.txt
sudo nano /boot/cmdline.txt

# 在行末添加
cgroup_enable=cpuset cgroup_enable=memory cgroup_memory=1
```

### 构建优化

#### 使用本地缓存
```bash
# 设置 Docker 构建缓存
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
```

#### 限制并行构建
```bash
# 对于内存较小的设备，限制并行构建
export MAKEFLAGS="-j1"
```

## 🔍 监控和维护

### 查看资源使用
```bash
# 查看容器资源使用
docker stats firemail

# 查看系统资源
htop
```

### 日志管理
```bash
# 查看日志
docker compose logs -f

# 限制日志大小
docker compose down
# 编辑 docker-compose.yml 添加日志配置
```

### 定期维护
```bash
# 清理未使用的镜像和容器
docker system prune -a

# 更新系统（树莓派）
sudo apt update && sudo apt upgrade -y
```

## 🚨 常见问题

### 构建时间过长
- **原因**：ARM 设备性能相对较低
- **解决**：耐心等待，首次构建可能需要 30-60 分钟

### 内存不足错误
- **原因**：编译过程需要大量内存
- **解决**：增加交换空间，关闭其他应用

### 网络超时
- **原因**：下载依赖时网络不稳定
- **解决**：使用国内镜像源，重试构建

### 架构不匹配
- **原因**：使用了错误的镜像架构
- **解决**：确保使用本项目的多架构 Dockerfile

## 📊 性能基准

### 树莓派 4B (4GB)
- **构建时间**：约 45 分钟
- **内存使用**：约 800MB
- **并发用户**：10-20 用户

### Apple M1 Mac
- **构建时间**：约 5 分钟
- **内存使用**：约 500MB
- **并发用户**：100+ 用户

## 🎯 最佳实践

1. **使用 SSD 存储**：提高 I/O 性能
2. **定期备份数据**：备份 `./data` 目录
3. **监控温度**：避免过热降频
4. **使用有线网络**：提高网络稳定性
5. **定期更新**：保持系统和 Docker 最新

## 📞 技术支持

如果在 ARM 设备上遇到部署问题，请提供以下信息：

```bash
# 系统信息
uname -a
cat /etc/os-release

# 架构信息
dpkg --print-architecture

# Docker 信息
docker version
docker info

# 错误日志
docker compose logs
```

然后在项目 GitHub 页面提交 Issue。
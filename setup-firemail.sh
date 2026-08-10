#!/bin/bash

# FireMail 自动配置脚本
# 自动检测 IP、生成密钥、配置环境变量

set -e

echo "🚀 FireMail 自动配置脚本"
echo "================================"

# 检查依赖
if ! command -v openssl &> /dev/null; then
    echo "❌ 错误: 未找到 openssl 命令"
    echo "请安装 openssl: sudo apt install openssl"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "❌ 错误: 未找到 docker 命令"
    echo "请先安装 Docker"
    exit 1
fi

# 获取本机 IP
echo "🔍 检测网络配置..."
LOCAL_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "127.0.0.1")
echo "检测到本机 IP: $LOCAL_IP"

# 询问端口
echo ""
read -p "请输入要使用的端口 (默认 80): " PORT
PORT=${PORT:-80}

# 验证端口
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
    echo "❌ 错误: 端口号必须是 1-65535 之间的数字"
    exit 1
fi

# 检查端口是否被占用
if netstat -tlnp 2>/dev/null | grep -q ":$PORT "; then
    echo "⚠️  警告: 端口 $PORT 可能已被占用"
    read -p "是否继续? (y/N): " CONTINUE
    if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
        echo "配置已取消"
        exit 1
    fi
fi

# 询问是否添加其他域名
echo ""
echo "🌐 CORS 域名配置"
echo "默认允许的域名: http://$LOCAL_IP:$PORT"
read -p "是否添加其他域名? (y/N): " ADD_DOMAINS
ADDITIONAL_DOMAINS=""
if [[ "$ADD_DOMAINS" =~ ^[Yy]$ ]]; then
    read -p "请输入其他域名 (多个用逗号分隔): " ADDITIONAL_DOMAINS
fi

# 生成 JWT 密钥
echo ""
echo "🔐 生成安全密钥..."
JWT_KEY=$(openssl rand -hex 32)
echo "JWT 密钥已生成: ${JWT_KEY:0:16}..."

# 构建 ALLOWED_ORIGINS
ALLOWED_ORIGINS="http://$LOCAL_IP:$PORT,http://localhost:$PORT,http://127.0.0.1:$PORT"
if [ -n "$ADDITIONAL_DOMAINS" ]; then
    ALLOWED_ORIGINS="$ALLOWED_ORIGINS,$ADDITIONAL_DOMAINS"
fi

# 创建 .env 文件
echo ""
echo "📝 创建配置文件..."
cat > .env << EOF
# FireMail 环境变量配置
# 生成时间: $(date)

# JWT 签名密钥（必须）
JWT_SECRET_KEY=$JWT_KEY

# 允许的 CORS 域名（推荐）
ALLOWED_ORIGINS=$ALLOWED_ORIGINS

# 时区设置
TZ=Asia/Shanghai

# 其他配置（自动设置）
HOST=0.0.0.0
FLASK_PORT=5000
WS_PORT=8765
FLASK_ENV=production
EOF

# 修改端口配置
if [ "$PORT" != "80" ]; then
    echo "🔧 修改端口配置..."
    if [ -f "docker-compose.yml" ]; then
        sed -i.bak "s/\"80:80\"/\"$PORT:80\"/" docker-compose.yml
        echo "端口已修改为: $PORT"
    else
        echo "⚠️  警告: 未找到 docker-compose.yml 文件"
    fi
fi

# 处理容器名冲突
echo "🔍 检查容器名冲突..."
if docker ps -a --format "table {{.Names}}" | grep -q "^firemail$"; then
    echo "⚠️  发现同名容器，正在处理..."

    # 尝试停止现有容器
    docker compose down 2>/dev/null || true

    # 如果还存在，修改容器名
    if docker ps -a --format "table {{.Names}}" | grep -q "^firemail$"; then
        echo "🔄 修改容器名以避免冲突..."
        TIMESTAMP=$(date +%s)
        sed -i.bak2 "s/container_name: firemail/container_name: firemail-$TIMESTAMP/" docker-compose.yml
        echo "容器名已修改为: firemail-$TIMESTAMP"
    fi
fi

# 显示配置摘要
echo ""
echo "✅ 配置完成！"
echo "================================"
echo "📋 配置摘要:"
echo "   访问端口: $PORT"
echo "   访问地址: http://$LOCAL_IP:$PORT/"
echo "   JWT 密钥: ${JWT_KEY:0:16}...(已保存到 .env 文件)"
echo "   允许域名: $ALLOWED_ORIGINS"
echo ""

# 询问是否立即启动
read -p "是否立即启动 FireMail 服务? (Y/n): " START_NOW
if [[ ! "$START_NOW" =~ ^[Nn]$ ]]; then
    echo ""
    echo "🚀 启动服务..."

    if docker compose up --build -d; then
        echo ""
        echo "🎉 FireMail 启动成功！"
        echo "================================"
        echo "🌐 访问地址: http://$LOCAL_IP:$PORT/"
        echo "🔍 健康检查: http://$LOCAL_IP:$PORT/api/health"
        echo ""
        echo "📱 移动端访问:"
        echo "   在手机浏览器中输入相同地址即可"
        echo ""
        echo "🔧 管理命令:"
        echo "   查看日志: docker compose logs -f"
        echo "   停止服务: docker compose down"
        echo "   重启服务: docker compose restart"
        echo ""
        echo "📚 更多帮助请查看 README.md"
    else
        echo "❌ 启动失败，请检查错误信息"
        echo "查看日志: docker compose logs"
        exit 1
    fi
else
    echo ""
    echo "📋 手动启动命令:"
    echo "   docker compose up --build -d"
    echo ""
    echo "🌐 启动后访问: http://$LOCAL_IP:$PORT/"
fi

echo ""
echo "🎯 配置文件已保存:"
echo "   .env - 环境变量配置"
if [ "$PORT" != "80" ]; then
    echo "   docker-compose.yml.bak - 原始配置备份"
fi
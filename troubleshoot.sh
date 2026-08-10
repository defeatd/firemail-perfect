#!/bin/bash

# FireMail 故障排除脚本
# 自动诊断和修复常见问题

set -e

echo "🔧 FireMail 故障排除脚本"
echo "=========================="

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装"
    echo "请先安装 Docker: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

# 检查 Docker Compose 是否可用
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose 不可用"
    echo "请升级 Docker 到最新版本"
    exit 1
fi

echo "✅ Docker 环境检查通过"

# 检查项目文件
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ 未找到 docker-compose.yml 文件"
    echo "请确保在 firemail-perfect 项目目录中运行此脚本"
    exit 1
fi

echo "✅ 项目文件检查通过"

# 检查环境变量
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件，正在创建..."

    # 生成 JWT 密钥
    JWT_KEY=$(openssl rand -hex 32)
    LOCAL_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "127.0.0.1")

    cat > .env << EOF
JWT_SECRET_KEY=$JWT_KEY
ALLOWED_ORIGINS=http://$LOCAL_IP,http://localhost
TZ=Asia/Shanghai
EOF
    echo "✅ .env 文件已创建"
else
    echo "✅ .env 文件存在"
fi

# 检查 JWT_SECRET_KEY
if ! grep -q "JWT_SECRET_KEY=" .env || grep -q "JWT_SECRET_KEY=$" .env; then
    echo "⚠️  JWT_SECRET_KEY 未设置，正在修复..."
    JWT_KEY=$(openssl rand -hex 32)

    if grep -q "JWT_SECRET_KEY=" .env; then
        sed -i "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$JWT_KEY/" .env
    else
        echo "JWT_SECRET_KEY=$JWT_KEY" >> .env
    fi
    echo "✅ JWT_SECRET_KEY 已设置"
fi

# 处理容器名冲突
echo "🔍 检查容器冲突..."
if docker ps -a --format "table {{.Names}}" | grep -q "^firemail$"; then
    echo "⚠️  发现容器名冲突，正在处理..."

    # 停止现有容器
    docker compose down 2>/dev/null || true

    # 如果还存在，修改容器名
    if docker ps -a --format "table {{.Names}}" | grep -q "^firemail$"; then
        TIMESTAMP=$(date +%s)
        sed -i.bak "s/container_name: firemail/container_name: firemail-$TIMESTAMP/" docker-compose.yml
        echo "✅ 容器名已修改为: firemail-$TIMESTAMP"
    fi
else
    echo "✅ 无容器名冲突"
fi

# 检查端口占用
PORT=$(grep -o '"[0-9]*:80"' docker-compose.yml | cut -d'"' -f2 | cut -d':' -f1)
PORT=${PORT:-80}

if netstat -tlnp 2>/dev/null | grep -q ":$PORT "; then
    echo "⚠️  端口 $PORT 被占用"

    # 建议替代端口
    for alt_port in 8080 9610 3000 8000; do
        if ! netstat -tlnp 2>/dev/null | grep -q ":$alt_port "; then
            echo "💡 建议使用端口 $alt_port"
            read -p "是否修改为端口 $alt_port? (Y/n): " change_port
            if [[ ! "$change_port" =~ ^[Nn]$ ]]; then
                sed -i.bak "s/\"$PORT:80\"/\"$alt_port:80\"/" docker-compose.yml

                # 更新 ALLOWED_ORIGINS
                LOCAL_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "127.0.0.1")
                sed -i "s|ALLOWED_ORIGINS=.*|ALLOWED_ORIGINS=http://$LOCAL_IP:$alt_port,http://localhost:$alt_port|" .env

                echo "✅ 端口已修改为: $alt_port"
                PORT=$alt_port
            fi
            break
        fi
    done
else
    echo "✅ 端口 $PORT 可用"
fi

# 清理 Docker 缓存（如果空间不足）
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 85 ]; then
    echo "⚠️  磁盘空间不足 ($DISK_USAGE% 已使用)"
    echo "正在清理 Docker 缓存..."
    docker system prune -f
    echo "✅ Docker 缓存已清理"
fi

# 检查内存
MEMORY_AVAILABLE=$(free -m | awk 'NR==2{printf "%.0f", $7}')
if [ "$MEMORY_AVAILABLE" -lt 500 ]; then
    echo "⚠️  可用内存不足 (${MEMORY_AVAILABLE}MB)"
    echo "建议关闭其他应用或增加交换空间"
fi

echo ""
echo "🚀 开始启动 FireMail..."

# 启动服务
if docker compose up --build -d; then
    echo ""
    echo "🎉 FireMail 启动成功！"
    echo "=========================="

    # 获取访问信息
    LOCAL_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "127.0.0.1")
    echo "🌐 访问地址: http://$LOCAL_IP:$PORT/"
    echo "🔍 健康检查: http://$LOCAL_IP:$PORT/api/health"

    # 等待服务启动
    echo ""
    echo "⏳ 等待服务启动..."
    sleep 10

    # 测试健康检查
    if curl -f -s "http://localhost:$PORT/api/health" > /dev/null 2>&1; then
        echo "✅ 服务健康检查通过"
    else
        echo "⚠️  服务可能还在启动中，请稍等片刻"
        echo "📋 查看日志: docker compose logs -f"
    fi

    echo ""
    echo "📱 移动端访问:"
    echo "   在手机浏览器中输入相同地址即可"
    echo ""
    echo "🔧 管理命令:"
    echo "   查看日志: docker compose logs -f"
    echo "   停止服务: docker compose down"
    echo "   重启服务: docker compose restart"

else
    echo ""
    echo "❌ 启动失败"
    echo "============"
    echo "📋 查看详细日志:"
    echo "   docker compose logs"
    echo ""
    echo "🔧 常见解决方案:"
    echo "   1. 检查端口是否被占用: netstat -tlnp | grep :$PORT"
    echo "   2. 检查磁盘空间: df -h"
    echo "   3. 检查内存: free -h"
    echo "   4. 清理 Docker: docker system prune -a"
    echo ""
    echo "💡 如需帮助，请查看完整部署指南:"
    echo "   docs/DEPLOYMENT-GUIDE.md"
fi
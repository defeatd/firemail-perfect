#!/bin/bash

# FireMail 多架构构建脚本
# 支持 AMD64, ARM64, ARMv7 架构

set -e

echo "🚀 开始构建 FireMail 多架构镜像..."

# 检查 Docker Buildx 是否可用
if ! docker buildx version > /dev/null 2>&1; then
    echo "❌ Docker Buildx 不可用，请升级 Docker 到最新版本"
    exit 1
fi

# 创建并使用多架构构建器
echo "📦 设置多架构构建器..."
docker buildx create --name firemail-builder --use --bootstrap 2>/dev/null || docker buildx use firemail-builder

# 构建多架构镜像
echo "🔨 构建多架构镜像 (AMD64, ARM64, ARMv7)..."
docker buildx build \
    --platform linux/amd64,linux/arm64,linux/arm/v7 \
    --tag firemail:latest \
    --load \
    .

echo "✅ 多架构镜像构建完成！"

# 显示镜像信息
echo "📋 镜像信息："
docker images firemail:latest

echo ""
echo "🎉 现在可以在以下架构上部署 FireMail："
echo "   - AMD64 (x86_64) - Intel/AMD 处理器"
echo "   - ARM64 (aarch64) - Apple M1/M2, 树莓派 4B+"
echo "   - ARMv7 (armhf) - 树莓派 3B/3B+"
echo ""
echo "💡 使用方法："
echo "   docker compose up -d"
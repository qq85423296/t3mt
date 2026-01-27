#!/bin/bash
# Docker 多架构镜像构建脚本
# 支持 AMD64 和 ARM64 架构

set -e

# 配置变量
IMAGE_NAME="85423296/t3mt"
VERSION=$(cat VERSION.md 2>/dev/null | grep -oP '(?<=版本号：v)\d+\.\d+\.\d+' | head -1)

if [ -z "$VERSION" ]; then
    echo "警告: 无法从 VERSION.md 读取版本号，使用默认版本 latest"
    VERSION="latest"
fi

echo "=================================================="
echo "Docker 多架构镜像构建脚本"
echo "镜像名称: ${IMAGE_NAME}"
echo "版本标签: ${VERSION}"
echo "支持架构: linux/amd64, linux/arm64"
echo "=================================================="

# 检查必要文件
echo "检查必要文件..."
if [ ! -f "backend/config.ini" ]; then
    echo "错误: backend/config.ini 不存在"
    exit 1
fi

if [ ! -f "backend/config/encrypted_config.dat" ]; then
    echo "错误: backend/config/encrypted_config.dat 不存在"
    exit 1
fi

# 检查 Docker Buildx 是否可用
if ! docker buildx version &> /dev/null; then
    echo "错误: Docker Buildx 不可用"
    echo "请升级 Docker 到最新版本或安装 Buildx 插件"
    exit 1
fi

# 移除旧的 builder（如果存在）
echo "清理旧的 builder..."
docker buildx rm multiarch-builder 2>/dev/null || true

# 创建新的 buildx builder
echo "创建 buildx builder..."
docker buildx create --name multiarch-builder --driver docker-container --use

# 启动 builder
echo "启动 builder..."
docker buildx inspect --bootstrap

# 构建并推送多架构镜像
echo ""
echo "开始构建多架构镜像..."
echo "这可能需要几分钟时间，请耐心等待..."
echo ""

docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --tag ${IMAGE_NAME}:${VERSION} \
    --tag ${IMAGE_NAME}:latest \
    --push \
    --progress=plain \
    .

echo ""
echo "=================================================="
echo "构建完成!"
echo "镜像标签:"
echo "  - ${IMAGE_NAME}:${VERSION}"
echo "  - ${IMAGE_NAME}:latest"
echo "支持架构: linux/amd64, linux/arm64"
echo "=================================================="
echo ""
echo "验证镜像架构:"
docker buildx imagetools inspect ${IMAGE_NAME}:${VERSION}

echo ""
echo "验证 ARM64 架构是否存在:"
docker buildx imagetools inspect ${IMAGE_NAME}:${VERSION} | grep -i "arm64" && echo "✓ ARM64 架构已成功构建" || echo "✗ ARM64 架构构建失败"



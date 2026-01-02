#!/bin/bash
# 推送镜像到 Docker Hub

set -e

echo "========================================"
echo "  推送镜像到 Docker Hub"
echo "========================================"
echo ""

# 配置你的 Docker Hub 用户名
DOCKERHUB_USERNAME="你的dockerhub用户名"
IMAGE_NAME="quark-manager"
IMAGE_TAG="latest"

echo "请先确保:"
echo "1. 已在 Docker Hub 注册账号 (https://hub.docker.com)"
echo "2. 已修改本脚本中的 DOCKERHUB_USERNAME"
echo "3. 已生成加密配置文件 (backend/data/encrypted_config.dat)"
echo ""
read -p "按回车继续..."

# 检查加密配置文件
if [ ! -f "../backend/data/encrypted_config.dat" ]; then
    echo "❌ 错误: 加密配置文件不存在"
    echo "请先运行: python encrypt_config.py"
    exit 1
fi

echo "✅ 加密配置文件检查通过"
echo ""

# 登录 Docker Hub
echo "步骤 1/4: 登录 Docker Hub"
docker login -u "$DOCKERHUB_USERNAME"

echo ""
echo "✅ 登录成功"
echo ""

# 构建镜像
echo "步骤 2/4: 构建镜像"
cd ..
docker build -t "$IMAGE_NAME:$IMAGE_TAG" .

echo ""
echo "✅ 构建成功"
echo ""

# 打标签
echo "步骤 3/4: 打标签"
docker tag "$IMAGE_NAME:$IMAGE_TAG" "$DOCKERHUB_USERNAME/$IMAGE_NAME:$IMAGE_TAG"

echo "✅ 打标签成功"
echo ""

# 推送镜像
echo "步骤 4/4: 推送镜像到 Docker Hub"
echo "这可能需要几分钟，请耐心等待..."
docker push "$DOCKERHUB_USERNAME/$IMAGE_NAME:$IMAGE_TAG"

echo ""
echo "========================================"
echo "✅ 推送成功！"
echo "========================================"
echo ""
echo "镜像地址: $DOCKERHUB_USERNAME/$IMAGE_NAME:$IMAGE_TAG"
echo ""
echo "用户可以使用以下命令拉取镜像:"
echo "  docker pull $DOCKERHUB_USERNAME/$IMAGE_NAME:$IMAGE_TAG"
echo ""
echo "或者直接运行:"
echo "  docker run -d \\"
echo "    --name quark-manager \\"
echo "    -p 8520:80 \\"
echo "    -v \$(pwd)/data:/app/backend/data \\"
echo "    -v \$(pwd)/logs:/app/backend/logs \\"
echo "    -v \$(pwd)/downloads:/app/backend/downloads \\"
echo "    $DOCKERHUB_USERNAME/$IMAGE_NAME:$IMAGE_TAG"
echo ""
echo "========================================"

#!/bin/bash
# Quark Manager 启动脚本

set -e

echo "========================================"
echo "  Quark Manager 启动脚本"
echo "========================================"
echo ""

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: 未检测到 Docker"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查 Docker Compose 是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "❌ 错误: 未检测到 Docker Compose"
    echo "请先安装 Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker 环境检查通过"
echo ""

# 创建必要的目录
mkdir -p data logs downloads

echo "📦 正在启动容器..."
echo ""

# 启动容器
docker-compose up -d

echo ""
echo "========================================"
echo "✅ 启动成功！"
echo "========================================"
echo ""
echo "访问地址: http://localhost:8520"
echo "默认账号: admin"
echo "默认密码: admin123"
echo ""
echo "常用命令:"
echo "  查看日志: docker-compose logs -f"
echo "  停止服务: docker-compose down"
echo "  重启服务: docker-compose restart"
echo ""
echo "========================================"

#!/bin/bash
# Quark Manager 打包发布脚本

set -e

echo "========================================"
echo "  Quark Manager 打包发布脚本"
echo "========================================"
echo ""

# 检查加密配置文件
if [ ! -f "backend/data/encrypted_config.dat" ]; then
    echo "❌ 错误: 加密配置文件不存在"
    echo ""
    echo "请先运行以下命令生成加密配置:"
    echo "  cd .."
    echo "  python encrypt_config.py"
    echo ""
    exit 1
fi

echo "✅ 加密配置文件检查通过"
echo ""

# 设置发布目录
RELEASE_DIR="quark-manager-docker"
RELEASE_TAR="quark-manager-docker.tar.gz"

# 清理旧的发布目录
if [ -d "$RELEASE_DIR" ]; then
    echo "清理旧的发布目录..."
    rm -rf "$RELEASE_DIR"
fi

# 创建发布目录结构
echo "创建发布目录..."
mkdir -p "$RELEASE_DIR"/{backend,frontend,docker}

# 复制文件
echo "复制文件..."

# 复制后端代码
cp -r backend/* "$RELEASE_DIR/backend/"

# 复制前端代码
cp -r frontend/* "$RELEASE_DIR/frontend/"

# 复制 Docker 配置
cp docker-compose.yml Dockerfile .dockerignore requirements.txt "$RELEASE_DIR/"

# 复制 docker 目录
cp docker/* "$RELEASE_DIR/docker/"

# 复制启动脚本
cp start.bat start.sh stop.bat stop.sh "$RELEASE_DIR/"
chmod +x "$RELEASE_DIR/start.sh" "$RELEASE_DIR/stop.sh"

# 复制说明文档
cp docker/README.txt "$RELEASE_DIR/"

# 清理不需要的文件
echo "清理临时文件..."
find "$RELEASE_DIR/backend" -type f -name "*.pyc" -delete
find "$RELEASE_DIR/backend" -type f -name "*.pyo" -delete
find "$RELEASE_DIR/backend" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# 清理数据文件（运行时生成）
rm -f "$RELEASE_DIR/backend/data/"*.db 2>/dev/null || true
rm -f "$RELEASE_DIR/backend/logs/"* 2>/dev/null || true
rm -f "$RELEASE_DIR/backend/downloads/"* 2>/dev/null || true

# 压缩发布包
echo "压缩发布包..."
rm -f "$RELEASE_TAR"
tar -czf "$RELEASE_TAR" "$RELEASE_DIR"

echo ""
echo "========================================"
echo "✅ 打包完成！"
echo "========================================"
echo ""
echo "发布包: $RELEASE_TAR"
echo "大小: $(du -h "$RELEASE_TAR" | cut -f1)"
echo ""
echo "用户使用方法:"
echo "1. 解压 $RELEASE_TAR"
echo "2. 进入目录"
echo "3. 运行 start.bat (Windows) 或 ./start.sh (Linux)"
echo "4. 访问 http://localhost:8520"
echo ""
echo "========================================"

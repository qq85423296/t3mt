@echo off
chcp 65001 >nul
echo ========================================
echo   Quark Manager 启动脚本
echo ========================================
echo.

REM 检查 Docker 是否安装
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未检测到 Docker
    echo 请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM 检查 Docker Compose 是否安装
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未检测到 Docker Compose
    echo Docker Desktop 应该已包含 Docker Compose
    pause
    exit /b 1
)

echo ✅ Docker 环境检查通过
echo.

REM 创建必要的目录
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "downloads" mkdir downloads

echo 📦 正在拉取镜像并启动容器...
echo 首次运行需要下载镜像，请耐心等待...
echo.

REM 启动容器
docker-compose up -d

if errorlevel 1 (
    echo.
    echo ❌ 容器启动失败
    echo 请查看错误信息或运行 docker-compose logs 查看详细日志
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✅ 启动成功！
echo ========================================
echo.
echo 访问地址: http://localhost:8520
echo 默认账号: admin
echo 默认密码: admin123
echo.
echo 常用命令:
echo   查看日志: docker-compose logs -f
echo   停止服务: docker-compose down
echo   重启服务: docker-compose restart
echo.
echo ========================================

pause

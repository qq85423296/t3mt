@echo off
REM Docker 镜像构建脚本 (Windows)

echo ================================
echo 开始构建 Quark Manager Docker 镜像
echo ================================

REM 检查加密配置文件是否存在
if not exist "backend\data\encrypted_config.dat" (
    echo ❌ 错误: 加密配置文件不存在
    echo 请先运行 python encrypt_config.py 生成加密配置文件
    exit /b 1
)

REM 构建镜像
echo 正在构建镜像...
docker build -t quark-manager:latest .

echo.
echo ================================
echo ✅ 镜像构建完成
echo ================================
echo.
echo 使用以下命令启动容器:
echo   docker-compose up -d
echo.
echo 或者直接运行:
echo   docker run -d ^
echo     --name quark-manager ^
echo     -p 8520:80 ^
echo     -v %cd%\data:/app/backend/data ^
echo     -v %cd%\logs:/app/backend/logs ^
echo     -v %cd%\downloads:/app/backend/downloads ^
echo     quark-manager:latest
echo.

pause

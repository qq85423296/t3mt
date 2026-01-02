@echo off
chcp 65001 >nul
echo ========================================
echo   推送镜像到 Docker Hub
echo ========================================
echo.

REM 配置你的 Docker Hub 用户名
set DOCKERHUB_USERNAME=85423296@qq.com
set IMAGE_NAME=t3mt
set IMAGE_TAG=latest

echo 请先确保:
echo 1. 已在 Docker Hub 注册账号 (https://hub.docker.com)
echo 2. 已修改本脚本中的 DOCKERHUB_USERNAME
echo 3. 已生成加密配置文件 (backend/data/encrypted_config.dat)
echo.
pause

REM 检查加密配置文件
if not exist "..\backend\data\encrypted_config.dat" (
    echo ❌ 错误: 加密配置文件不存在
    echo 请先运行: python encrypt_config.py
    pause
    exit /b 1
)

echo ✅ 加密配置文件检查通过
echo.

REM 登录 Docker Hub
echo 步骤 1/4: 登录 Docker Hub
echo 请输入你的 Docker Hub 密码:
docker login -u %DOCKERHUB_USERNAME%

if errorlevel 1 (
    echo ❌ 登录失败
    pause
    exit /b 1
)

echo.
echo ✅ 登录成功
echo.

REM 构建镜像
echo 步骤 2/4: 构建镜像
cd ..
docker build -t %IMAGE_NAME%:%IMAGE_TAG% .

if errorlevel 1 (
    echo ❌ 构建失败
    pause
    exit /b 1
)

echo.
echo ✅ 构建成功
echo.

REM 打标签
echo 步骤 3/4: 打标签
docker tag %IMAGE_NAME%:%IMAGE_TAG% %DOCKERHUB_USERNAME%/%IMAGE_NAME%:%IMAGE_TAG%

if errorlevel 1 (
    echo ❌ 打标签失败
    pause
    exit /b 1
)

echo ✅ 打标签成功
echo.

REM 推送镜像
echo 步骤 4/4: 推送镜像到 Docker Hub
echo 这可能需要几分钟，请耐心等待...
docker push %DOCKERHUB_USERNAME%/%IMAGE_NAME%:%IMAGE_TAG%

if errorlevel 1 (
    echo ❌ 推送失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✅ 推送成功！
echo ========================================
echo.
echo 镜像地址: %DOCKERHUB_USERNAME%/%IMAGE_NAME%:%IMAGE_TAG%
echo.
echo 用户可以使用以下命令拉取镜像:
echo   docker pull %DOCKERHUB_USERNAME%/%IMAGE_NAME%:%IMAGE_TAG%
echo.
echo 或者直接运行:
echo   docker run -d \
echo     --name quark-manager \
echo     -p 8520:80 \
echo     -v ./data:/app/backend/data \
echo     -v ./logs:/app/backend/logs \
echo     -v ./downloads:/app/backend/downloads \
echo     %DOCKERHUB_USERNAME%/%IMAGE_NAME%:%IMAGE_TAG%
echo.
echo ========================================

pause

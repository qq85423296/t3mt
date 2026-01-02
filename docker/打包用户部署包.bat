@echo off
chcp 65001 >nul
echo ========================================
echo   打包用户部署包
echo ========================================
echo.

REM 设置变量（需要修改为你的 Docker Hub 用户名）
set DOCKERHUB_USERNAME=你的dockerhub用户名
set RELEASE_DIR=quark-manager-deploy
set RELEASE_ZIP=quark-manager-deploy.zip

echo 请确保已修改本脚本中的 DOCKERHUB_USERNAME
echo 当前设置: %DOCKERHUB_USERNAME%
echo.
pause

REM 清理旧的发布目录
if exist "%RELEASE_DIR%" (
    echo 清理旧的发布目录...
    rmdir /s /q "%RELEASE_DIR%"
)

REM 创建发布目录
echo 创建发布目录...
mkdir "%RELEASE_DIR%"

REM 复制 docker-compose 配置（使用在线镜像版本）
echo 复制配置文件...
copy /Y ..\docker-compose.online.yml "%RELEASE_DIR%\docker-compose.yml" >nul

REM 修改 docker-compose.yml 中的用户名
powershell -Command "(Get-Content '%RELEASE_DIR%\docker-compose.yml') -replace '你的dockerhub用户名', '%DOCKERHUB_USERNAME%' | Set-Content '%RELEASE_DIR%\docker-compose.yml'"

REM 复制启动脚本
copy /Y 用户部署包\start.bat "%RELEASE_DIR%\" >nul
copy /Y 用户部署包\start.sh "%RELEASE_DIR%\" >nul
copy /Y 用户部署包\stop.bat "%RELEASE_DIR%\" >nul
copy /Y 用户部署包\stop.sh "%RELEASE_DIR%\" >nul

REM 复制说明文档
copy /Y 用户部署包\README.txt "%RELEASE_DIR%\" >nul

REM 压缩发布包
echo 压缩发布包...
if exist "%RELEASE_ZIP%" del /q "%RELEASE_ZIP%"
powershell -command "Compress-Archive -Path '%RELEASE_DIR%' -DestinationPath '%RELEASE_ZIP%' -Force"

if errorlevel 1 (
    echo ❌ 压缩失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✅ 打包完成！
echo ========================================
echo.
echo 发布包: %RELEASE_ZIP%
echo 大小: 
for %%A in ("%RELEASE_ZIP%") do echo %%~zA 字节
echo.
echo 用户使用方法:
echo 1. 解压 %RELEASE_ZIP%
echo 2. 双击 start.bat (Windows) 或运行 ./start.sh (Linux)
echo 3. 访问 http://localhost:8520
echo.
echo 注意: 用户首次运行会自动从 Docker Hub 拉取镜像
echo       镜像地址: %DOCKERHUB_USERNAME%/quark-manager:latest
echo.
echo ========================================

pause

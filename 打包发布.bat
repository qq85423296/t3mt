@echo off
chcp 65001 >nul
echo ========================================
echo   Quark Manager 打包发布脚本
echo ========================================
echo.

REM 检查加密配置文件
if not exist "backend\data\encrypted_config.dat" (
    echo ❌ 错误: 加密配置文件不存在
    echo.
    echo 请先运行以下命令生成加密配置:
    echo   cd ..
    echo   python encrypt_config.py
    echo.
    pause
    exit /b 1
)

echo ✅ 加密配置文件检查通过
echo.

REM 设置发布目录
set RELEASE_DIR=quark-manager-docker
set RELEASE_ZIP=quark-manager-docker.zip

REM 清理旧的发布目录
if exist "%RELEASE_DIR%" (
    echo 清理旧的发布目录...
    rmdir /s /q "%RELEASE_DIR%"
)

REM 创建发布目录结构
echo 创建发布目录...
mkdir "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%\backend"
mkdir "%RELEASE_DIR%\frontend"
mkdir "%RELEASE_DIR%\docker"

REM 复制文件
echo 复制文件...

REM 复制后端代码
xcopy /E /I /Y backend "%RELEASE_DIR%\backend" >nul

REM 复制前端代码
xcopy /E /I /Y frontend "%RELEASE_DIR%\frontend" >nul

REM 复制 Docker 配置
copy /Y docker-compose.yml "%RELEASE_DIR%\" >nul
copy /Y Dockerfile "%RELEASE_DIR%\" >nul
copy /Y .dockerignore "%RELEASE_DIR%\" >nul
copy /Y requirements.txt "%RELEASE_DIR%\" >nul

REM 复制 docker 目录
copy /Y docker\*.* "%RELEASE_DIR%\docker\" >nul

REM 复制启动脚本
copy /Y start.bat "%RELEASE_DIR%\" >nul
copy /Y start.sh "%RELEASE_DIR%\" >nul
copy /Y stop.bat "%RELEASE_DIR%\" >nul
copy /Y stop.sh "%RELEASE_DIR%\" >nul

REM 复制说明文档
copy /Y docker\README.txt "%RELEASE_DIR%\" >nul

REM 清理不需要的文件
echo 清理临时文件...
del /s /q "%RELEASE_DIR%\backend\*.pyc" >nul 2>&1
del /s /q "%RELEASE_DIR%\backend\*.pyo" >nul 2>&1
for /d /r "%RELEASE_DIR%\backend" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"

REM 清理数据文件（运行时生成）
if exist "%RELEASE_DIR%\backend\data\*.db" del /q "%RELEASE_DIR%\backend\data\*.db" >nul 2>&1
if exist "%RELEASE_DIR%\backend\logs\*.*" del /q "%RELEASE_DIR%\backend\logs\*.*" >nul 2>&1
if exist "%RELEASE_DIR%\backend\downloads\*.*" del /q "%RELEASE_DIR%\backend\downloads\*.*" >nul 2>&1

REM 压缩发布包
echo 压缩发布包...
if exist "%RELEASE_ZIP%" del /q "%RELEASE_ZIP%"

REM 使用 PowerShell 压缩
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
echo 2. 进入目录
echo 3. 运行 start.bat (Windows) 或 ./start.sh (Linux)
echo 4. 访问 http://localhost:8520
echo.
echo ========================================

pause

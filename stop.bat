@echo off
chcp 65001 >nul
echo ========================================
echo   Quark Manager 停止脚本
echo ========================================
echo.

echo 正在停止容器...
docker-compose down

if errorlevel 1 (
    echo.
    echo ❌ 停止失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✅ 已停止服务
echo ========================================
echo.

pause

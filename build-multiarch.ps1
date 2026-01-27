# Docker 多架构镜像构建脚本 (PowerShell)
# 支持 AMD64 和 ARM64 架构

$ErrorActionPreference = "Stop"

# 配置变量
$IMAGE_NAME = "85423296/t3mt"
$VERSION = "latest"

# 尝试从 VERSION.md 读取版本号
if (Test-Path "VERSION.md") {
    $content = Get-Content "VERSION.md" -Raw
    if ($content -match '版本号：v(\d+\.\d+\.\d+)') {
        $VERSION = $matches[1]
    }
}

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Docker 多架构镜像构建脚本" -ForegroundColor Cyan
Write-Host "镜像名称: $IMAGE_NAME" -ForegroundColor Green
Write-Host "版本标签: $VERSION" -ForegroundColor Green
Write-Host "支持架构: linux/amd64, linux/arm64" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# 检查必要文件
Write-Host "检查必要文件..." -ForegroundColor Yellow
if (-not (Test-Path "backend/config.ini")) {
    Write-Host "错误: backend/config.ini 不存在" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "backend/config/encrypted_config.dat")) {
    Write-Host "错误: backend/config/encrypted_config.dat 不存在" -ForegroundColor Red
    exit 1
}

# 检查 Docker Buildx 是否可用
try {
    docker buildx version | Out-Null
} catch {
    Write-Host "错误: Docker Buildx 不可用" -ForegroundColor Red
    Write-Host "请升级 Docker Desktop 到最新版本" -ForegroundColor Yellow
    exit 1
}

# 移除旧的 builder（如果存在）
Write-Host "清理旧的 builder..." -ForegroundColor Yellow
try {
    docker buildx rm multiarch-builder 2>$null
} catch {
    # 忽略错误
}

# 创建新的 buildx builder
Write-Host "创建 buildx builder..." -ForegroundColor Yellow
docker buildx create --name multiarch-builder --driver docker-container --use

# 启动 builder
Write-Host "启动 builder..." -ForegroundColor Yellow
docker buildx inspect --bootstrap

# 构建并推送多架构镜像
Write-Host ""
Write-Host "开始构建多架构镜像..." -ForegroundColor Yellow
Write-Host "这可能需要几分钟时间，请耐心等待..." -ForegroundColor Yellow
Write-Host ""

docker buildx build `
    --platform linux/amd64,linux/arm64 `
    --tag "${IMAGE_NAME}:${VERSION}" `
    --tag "${IMAGE_NAME}:latest" `
    --push `
    --progress=plain `
    .

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "构建完成!" -ForegroundColor Green
Write-Host "镜像标签:" -ForegroundColor Green
Write-Host "  - ${IMAGE_NAME}:${VERSION}" -ForegroundColor White
Write-Host "  - ${IMAGE_NAME}:${VERSION}" -ForegroundColor White
Write-Host "支持架构: linux/amd64, linux/arm64" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "验证镜像架构:" -ForegroundColor Yellow
docker buildx imagetools inspect "${IMAGE_NAME}:${VERSION}"

Write-Host ""
Write-Host "验证 ARM64 架构是否存在:" -ForegroundColor Yellow
$inspectOutput = docker buildx imagetools inspect "${IMAGE_NAME}:${VERSION}" | Out-String
if ($inspectOutput -match "arm64") {
    Write-Host "✓ ARM64 架构已成功构建" -ForegroundColor Green
} else {
    Write-Host "✗ ARM64 架构构建失败" -ForegroundColor Red
}



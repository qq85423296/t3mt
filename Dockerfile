# 使用 Python 3.9 作为基础镜像（支持多架构）
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（兼容 ARM64 和 AMD64）
RUN apt-get update && apt-get install -y \
    nginx \
    supervisor \
    curl \
    ffmpeg \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# 复制后端代码
COPY backend/ /app/backend/

# 确保配置文件存在
RUN test -f /app/backend/config.ini || (echo "错误: config.ini 配置文件不存在" && exit 1)
RUN test -f /app/backend/config/encrypted_config.dat || (echo "错误: encrypted_config.dat 配置文件不存在" && exit 1)

# 安装 Python 依赖（优化 ARM64 兼容性）
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# 复制前端代码
COPY frontend/ /app/frontend/

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/sites-available/default

# 复制 Supervisor 配置
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 创建必要的目录
RUN mkdir -p /app/backend/data \
    /app/backend/logs \
    /app/backend/downloads \
    /var/log/supervisor

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 80

# 启动 Supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

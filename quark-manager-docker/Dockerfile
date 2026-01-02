# 使用 Python 3.9 作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# 复制后端代码和依赖
COPY backend/ /app/backend/
COPY requirements.txt /app/

# 安装 Python 依赖
RUN pip install --no-cache-dir -r /app/requirements.txt

# 复制前端代码
COPY frontend/ /app/frontend/

# 复制 Nginx 配置
COPY docker/nginx.conf /etc/nginx/sites-available/default

# 复制 Supervisor 配置
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 创建必要的目录
RUN mkdir -p /app/backend/data \
    /app/backend/logs \
    /app/backend/downloads \
    /var/log/supervisor

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    CONFIG_DECRYPTION_KEY=quark_transfer_master_key_2024

# 暴露端口
EXPOSE 80

# 启动 Supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

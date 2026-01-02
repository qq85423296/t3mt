========================================
  Quark Manager Docker 部署说明
========================================

【快速部署】

1. 确保已安装 Docker 和 Docker Compose
   - Windows: 安装 Docker Desktop
   - Linux: 安装 docker 和 docker-compose

2. 解压本压缩包到任意目录

3. 进入目录，运行启动脚本：
   Windows: 双击 start.bat
   Linux: 运行 ./start.sh

4. 等待容器启动完成（首次启动需要拉取镜像）

5. 浏览器访问: http://localhost:8520
   默认账号: admin
   默认密码: admin123

【目录说明】

client/
├── docker-compose.yml    # Docker编排配置
├── Dockerfile           # Docker镜像构建文件
├── start.bat           # Windows启动脚本
├── start.sh            # Linux启动脚本
├── stop.bat            # Windows停止脚本
├── stop.sh             # Linux停止脚本
├── backend/            # 后端代码
├── frontend/           # 前端代码
├── docker/             # Docker配置文件
├── data/               # 数据库文件（自动创建）
├── logs/               # 日志文件（自动创建）
└── downloads/          # 下载文件（自动创建）

【常用命令】

启动服务:
  docker-compose up -d

停止服务:
  docker-compose down

查看日志:
  docker-compose logs -f

重启服务:
  docker-compose restart

查看状态:
  docker-compose ps

【端口说明】

默认端口: 8520

如需修改端口，编辑 docker-compose.yml 文件:
  ports:
    - "8520:80"  # 改为 "你的端口:80"

【数据备份】

重要数据存储在以下目录，请定期备份:
  - data/quark_manager.db  (数据库)
  - logs/                  (日志)
  - downloads/             (下载文件)

【故障排查】

1. 端口被占用
   - 修改 docker-compose.yml 中的端口号

2. 容器启动失败
   - 运行: docker-compose logs
   - 查看错误信息

3. 无法访问
   - 检查防火墙设置
   - 确认容器正在运行: docker-compose ps

【技术支持】

如有问题请查看日志文件或联系技术支持

========================================

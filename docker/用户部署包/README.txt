========================================
  Quark Manager 快速部署指南
========================================

【系统要求】

- Windows 10/11 或 Linux
- 已安装 Docker Desktop (Windows) 或 Docker (Linux)
- 至少 2GB 可用内存
- 至少 5GB 可用磁盘空间

【快速开始】

1. 确保 Docker 已安装并运行
   Windows: 打开 Docker Desktop
   Linux: 运行 sudo systemctl start docker

2. 解压本压缩包到任意目录

3. 运行启动脚本:
   Windows: 双击 start.bat
   Linux: 运行 ./start.sh

4. 等待镜像下载和容器启动（首次运行需要几分钟）

5. 浏览器访问: http://localhost:8520
   默认账号: admin
   默认密码: admin123

【文件说明】

docker-compose.yml  - Docker 编排配置
start.bat          - Windows 启动脚本
start.sh           - Linux 启动脚本
stop.bat           - Windows 停止脚本
stop.sh            - Linux 停止脚本
README.txt         - 本说明文件

运行后会自动创建以下目录:
data/              - 数据库文件
logs/              - 日志文件
downloads/         - 下载文件

【常用操作】

启动服务:
  Windows: start.bat
  Linux: ./start.sh

停止服务:
  Windows: stop.bat
  Linux: ./stop.sh

查看日志:
  docker-compose logs -f

重启服务:
  docker-compose restart

更新镜像:
  docker-compose pull
  docker-compose up -d

【端口修改】

默认端口: 8520

如需修改，编辑 docker-compose.yml:
  ports:
    - "8520:80"  # 改为 "你的端口:80"

然后重启服务

【数据备份】

重要数据存储在以下目录:
  data/quark_manager.db  - 数据库（重要！）
  logs/                  - 日志文件
  downloads/             - 下载的文件

建议定期备份 data 目录

【故障排查】

1. 无法启动
   - 检查 Docker 是否运行
   - 检查端口 8520 是否被占用
   - 运行: docker-compose logs 查看错误

2. 无法访问
   - 确认容器正在运行: docker-compose ps
   - 检查防火墙设置
   - 尝试访问: http://127.0.0.1:8520

3. 忘记密码
   - 停止服务
   - 删除 data/quark_manager.db
   - 重新启动（会重置为默认密码）

【卸载】

1. 停止并删除容器:
   docker-compose down

2. 删除镜像:
   docker rmi 镜像名称

3. 删除本目录

【技术支持】

如有问题请查看日志文件或联系技术支持

========================================

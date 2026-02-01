# Aria2可执行文件说明

## 目录结构

```
bin/aria2/
├── windows/
│   └── aria2c.exe      # Windows版本（需要下载）
├── linux/
│   └── aria2c          # Linux版本（需要下载）
└── README.md           # 本文件
```

## 下载Aria2可执行文件

### Windows版本

1. 访问Aria2官方GitHub发布页：https://github.com/aria2/aria2/releases
2. 下载最新版本的 `aria2-x.xx.x-win-64bit-build1.zip`
3. 解压后将 `aria2c.exe` 复制到 `windows/` 目录

或者使用以下直接下载链接（版本1.37.0）：
```
https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip
```

### Linux版本

1. 访问Aria2官方GitHub发布页：https://github.com/aria2/aria2/releases
2. 下载最新版本的 `aria2-x.xx.x-linux-gnu-64bit-build1.tar.bz2`
3. 解压后将 `aria2c` 复制到 `linux/` 目录
4. 添加执行权限：`chmod +x linux/aria2c`

或者使用以下直接下载链接（版本1.37.0）：
```
https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-linux-gnu-64bit-build1.tar.bz2
```

## 验证安装

### Windows
```cmd
cd client\backend\bin\aria2\windows
aria2c.exe --version
```

### Linux
```bash
cd client/backend/bin/aria2/linux
./aria2c --version
```

## 注意事项

1. **文件大小**：
   - Windows版本约 4-5 MB
   - Linux版本约 4-5 MB

2. **版本要求**：
   - 建议使用 1.35.0 或更高版本
   - 支持 RPC 功能

3. **权限问题**：
   - Linux下需要确保文件有执行权限
   - Windows下无需特殊权限

4. **系统兼容性**：
   - Windows: 64位系统
   - Linux: 64位系统，GNU/Linux

## 自动降级

如果Aria2可执行文件不存在，系统会尝试：
1. 从系统PATH查找 `aria2c` 命令
2. 如果找不到，天翼云盘下载会自动降级到传统下载方式

## 配置说明

Aria2配置项存储在数据库 `system_config` 表中：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| aria2_max_concurrent_downloads | 最大并发下载任务数 | 3 |
| aria2_split | 每文件线程数 | 16 |
| aria2_min_split_size | 每线程分块大小 | 10M |
| aria2_max_connection_per_server | 每服务器最大连接数 | 16 |
| aria2_timeout | 请求超时时间（秒） | 60 |
| aria2_retry_wait | 重试等待时间（秒） | 5 |
| aria2_max_tries | 最大重试次数 | 5 |

## 故障排查

### Aria2启动失败

1. 检查可执行文件是否存在
2. 检查文件权限（Linux）
3. 检查端口6800是否被占用
4. 查看应用日志：`logs/app.log`

### 下载失败

1. 检查Aria2进程是否运行
2. 检查网络连接
3. 检查下载目录权限
4. 查看Aria2日志（控制台输出）

## 相关文档

- Aria2官方文档：https://aria2.github.io/
- Aria2 GitHub：https://github.com/aria2/aria2
- 需求文档：`docs/天翼云盘/07-后续需求/天翼云盘定时下载集成Aria2需求.md`

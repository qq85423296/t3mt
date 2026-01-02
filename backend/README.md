# T3MT - 后端服务

## 项目结构

```
backend/
├── api/                    # API接口层
│   ├── auth.py            # 认证接口
│   ├── accounts.py        # 账号管理接口
│   ├── quark.py           # 夸克网盘操作接口
│   ├── search.py          # 资源搜索接口
│   ├── transfer.py        # 转存任务接口
│   ├── download.py        # 下载任务接口
│   ├── logs.py            # 日志管理接口
│   └── config.py          # 系统配置接口
├── models/                 # 数据模型层
│   ├── user.py            # 用户模型
│   ├── account.py         # 账号模型
│   ├── transfer_task.py   # 转存任务模型
│   ├── download_task.py   # 下载任务模型
│   ├── log.py             # 日志模型
│   └── config.py          # 配置模型
├── services/               # 业务逻辑层
│   ├── account_service.py # 账号服务
│   ├── quark_service.py   # 夸克网盘服务
│   ├── transfer_service.py# 转存服务
│   ├── download_service.py# 下载服务
│   ├── log_service.py     # 日志服务
│   ├── email_service.py   # 邮件服务
│   └── search_service.py  # 搜索服务
├── tasks/                  # 任务调度层
│   └── scheduler.py       # 任务调度器
├── utils/                  # 工具类
│   ├── crypto.py          # 加密解密
│   ├── logger.py          # 日志工具
│   ├── cron_parser.py     # Cron解析
│   └── file_helper.py     # 文件操作
├── data/                   # 数据目录（自动创建）
│   └── quark_manager.db   # SQLite数据库
├── logs/                   # 日志目录（自动创建）
├── app.py                  # Flask应用主文件
├── config.py               # 配置文件
├── database.py             # 数据库初始化
├── init_db.py              # 数据库初始化脚本
├── start.py                # 启动脚本
└── requirements.txt        # 依赖清单
```

## 环境要求

- Python 3.8+
- pip包管理器

## 安装步骤

### 1. 创建虚拟环境（推荐）

```bash
python -m venv venv
```

### 2. 激活虚拟环境

Windows:
```bash
venv\Scripts\activate
```

Linux/Mac:
```bash
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 初始化数据库

```bash
python init_db.py
```

初始化完成后会创建：
- 默认管理员账号: `admin`
- 默认管理员密码: `admin123`

**重要：请登录后及时修改密码！**

### 5. 启动服务

```bash
python start.py
```

或者直接运行：
```bash
python app.py
```

服务启动后访问: http://localhost:5000

## 配置说明

### config.py 配置项

```python
# 应用配置
SECRET_KEY = '随机密钥'
DEBUG = False

# 数据库配置
DATABASE = 'data/quark_manager.db'

# 服务器配置
HOST = '127.0.0.1'
PORT = 5000

# 日志配置
LOG_LEVEL = 'INFO'
LOG_FILE = 'logs/app.log'
```

## API接口文档

### 认证接口

- `POST /api/auth/login` - 用户登录
- `POST /api/auth/logout` - 用户登出
- `GET /api/auth/check` - 检查登录状态

### 账号管理接口

- `GET /api/accounts` - 获取账号列表
- `POST /api/accounts` - 添加账号
- `POST /api/accounts/test` - 测试账号
- `PUT /api/accounts/{id}` - 更新账号
- `DELETE /api/accounts/{id}` - 删除账号
- `PUT /api/accounts/{id}/set-main` - 设为主账号

### 夸克网盘接口

- `GET /api/quark/files` - 获取文件列表
- `POST /api/quark/folder` - 创建文件夹
- `DELETE /api/quark/delete` - 删除文件
- `POST /api/quark/share` - 分享文件
- `GET /api/quark/download` - 获取下载链接
- `POST /api/quark/save-share` - 转存分享文件

### 资源搜索接口

- `GET /api/search` - 搜索资源
- `POST /api/search/check-validity` - 检测链接有效性

### 转存任务接口

- `GET /api/transfer/tasks` - 获取任务列表
- `POST /api/transfer/task` - 创建任务
- `GET /api/transfer/task/{id}` - 获取任务详情
- `PUT /api/transfer/task/{id}` - 更新任务
- `DELETE /api/transfer/task/{id}` - 删除任务
- `POST /api/transfer/task/{id}/toggle` - 暂停/启动任务
- `POST /api/transfer/task/{id}/execute` - 立即执行任务

### 下载任务接口

- `GET /api/download/tasks` - 获取任务列表
- `POST /api/download/task` - 创建任务
- `GET /api/download/task/{id}` - 获取任务详情
- `PUT /api/download/task/{id}` - 更新任务
- `DELETE /api/download/task/{id}` - 删除任务
- `POST /api/download/task/{id}/toggle` - 暂停/启动任务
- `POST /api/download/task/{id}/execute` - 立即执行任务
- `GET /api/download/task/{id}/progress` - 获取下载进度

### 日志管理接口

- `GET /api/logs` - 查询日志列表
- `DELETE /api/logs/clear` - 清空日志
- `POST /api/logs/auto-clean` - 自动清理日志
- `GET /api/logs/export` - 导出日志

### 系统配置接口

- `GET /api/config` - 获取所有配置
- `POST /api/config` - 保存配置
- `POST /api/config/email/test` - 测试邮件配置

## 开发说明

### 添加新的API接口

1. 在 `api/` 目录下创建新的蓝图文件
2. 在 `api/__init__.py` 中导入并导出
3. 在 `app.py` 中注册蓝图

### 添加新的服务

1. 在 `services/` 目录下创建服务类
2. 实现业务逻辑方法
3. 在API层调用服务方法

### 添加新的数据模型

1. 在 `models/` 目录下创建模型类
2. 在 `database.py` 中添加表结构
3. 实现CRUD方法

## 常见问题

### 1. 数据库文件在哪里？

数据库文件位于 `data/quark_manager.db`

### 2. 如何备份数据？

直接复制 `data/quark_manager.db` 文件即可

### 3. 如何重置数据库？

删除 `data/quark_manager.db` 文件，然后重新运行 `python init_db.py`

### 4. 日志文件在哪里？

日志文件位于 `logs/app.log`

### 5. 如何修改端口？

修改 `config.py` 中的 `PORT` 配置项

## 注意事项

1. 首次运行前必须执行数据库初始化
2. Cookie等敏感信息会加密存储
3. 建议在生产环境中修改SECRET_KEY
4. 定期备份数据库文件
5. 及时修改默认管理员密码

## 技术栈

- Flask 2.3.0 - Web框架
- APScheduler 3.10.0 - 任务调度
- SQLite 3 - 数据库
- Requests 2.31.0 - HTTP请求
- Cryptography 41.0.0 - 加密解密

## 许可证

MIT License

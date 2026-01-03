# T3MT

一个轻量级的夸克网盘管理工具,支持资源搜索、定时转存、定时下载等功能  。 

## 项目特点

- **轻量化**: 采用Python + Flask + SQLite技术栈,无需复杂配置
- **简单化**: 原生HTML/JS前端,无需构建工具
- **稳定化**: 成熟技术方案,代码结构清晰。


compose部署：
version: '3.8'

services:
  t3mt:
    image: 85423296/t3mt:latest
    container_name: t3mt
    restart: unless-stopped
    ports:
      - "8520:80"
    volumes:
      - ./data:/app/backend/data # 数据文件
      - ./logs:/app/backend/logs  # 日志
      - ./downloads:/app/backend/downloads # 下载目录 前面是本地 后面是docker
    environment:
      - TZ=Asia/Shanghai
      
## 功能特性

### 1. 资源搜索
- 集成盘搜API,搜索网盘资源
- 支持分类筛选
- 链接有效性检测
- 一键转存到夸克网盘

### 2. 夸克网盘管理
- 多账号管理
- 文件浏览和操作
- 文件分享和下载
- 目录导航

### 3. 定时转存
- 从分享链接自动转存
- 支持多链接备份
- 文件过滤和规则处理
- Cron定时执行

### 4. 定时下载
- 从网盘自动下载到本地
- 增量下载支持
- 断点续传
- 并发控制

### 5. 日志管理
- 任务执行日志
- 多条件筛选
- 自动清理

### 6. 系统配置
- 账号管理
- 下载配置
- 邮件提醒
- 盘搜API配置

## 技术栈

### 后端
- Python 3.8+
- Flask 2.3.0
- SQLite 3
- APScheduler 3.10.0

### 前端
- 原生HTML5
- 原生CSS3
- 原生JavaScript (ES6+)

## 项目结构

```
├── backend/                # 后端代码
│   ├── api/               # API接口层
│   ├── models/            # 数据模型层
│   ├── services/          # 业务逻辑层
│   ├── tasks/             # 任务调度层
│   ├── utils/             # 工具类
│   ├── app.py             # 应用入口
│   ├── config.py          # 配置文件
│   ├── database.py        # 数据库初始化
│   └── requirements.txt   # 依赖清单
├── frontend/              # 前端代码
│   ├── css/               # 样式文件
│   ├── js/                # JavaScript文件
│   ├── pages/             # 功能页面
│   ├── index.html         # 主框架
│   └── login.html         # 登录页面
├── docs/                  # 文档目录
│   ├── 功能需求/          # 功能需求文档
│   ├── 技术方案/          # 技术方案文档
│   ├── 夸克API/           # 夸克API文档
│   └── ui原型/            # UI原型文件
└── README.md              # 项目说明
```

## 快速开始

### 1. 环境要求

- Python 3.8+
- pip包管理器
- 现代浏览器

### 2. 安装后端

```bash
# 进入后端目录
cd backend

# 创建虚拟环境(推荐)
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python init_db.py

# 启动服务
python app.py
```

服务启动后访问: http://localhost:5000

### 3. 打开前端

方式一: 直接打开HTML文件
```bash
# 用浏览器打开
frontend/login.html
```

方式二: 使用HTTP服务器
```bash
# Python
cd frontend
python -m http.server 8080

# 访问: http://localhost:8080/login.html
```

### 4. 登录系统

默认账号: `admin`
默认密码: `admin123`

**重要**: 首次登录后请及时修改密码!

## 使用说明

### 1. 配置夸克账号

1. 登录后进入"系统配置"页面
2. 点击"添加账号"
3. 填写账号备注和Cookie
4. 点击"测试并保存"

**获取Cookie方法**:
1. 打开浏览器开发者工具(F12)
2. 访问夸克网盘并登录
3. 在Network标签中找到请求
4. 复制Cookie值

### 2. 配置盘搜API

1. 进入"系统配置"页面
2. 找到"盘搜地址配置"
3. 填写盘搜API地址
4. 保存配置

### 3. 创建转存任务

1. 进入"定时转存"页面
2. 点击"新建任务"
3. 填写任务信息
4. 设置执行时间
5. 保存任务

### 4. 创建下载任务

1. 进入"定时下载"页面
2. 点击"新建任务"
3. 选择网盘目录和本地目录
4. 设置执行时间
5. 保存任务

## 配置说明

### 后端配置 (backend/config.py)

```python
# 服务器配置
HOST = '127.0.0.1'
PORT = 5000

# 数据库配置
DATABASE = 'data/quark_manager.db'

# 日志配置
LOG_LEVEL = 'INFO'
LOG_FILE = 'logs/app.log'
```

### 前端配置 (frontend/js/api.js)

```javascript
// API基础URL
const API_BASE_URL = 'http://localhost:5000';
```

## 常见问题

### 1. 登录后跳转空白页

检查后端服务是否正常运行

### 2. API请求失败

检查前端API配置中的URL是否正确

### 3. Cookie失效

重新获取Cookie并更新账号配置

### 4. 任务不执行

检查任务状态是否为"运行中"

### 5. 下载失败

检查本地目录权限和磁盘空间

## 开发说明

### 添加新功能

1. 后端: 在对应层添加代码(models/services/api)
2. 前端: 在pages目录添加页面
3. 更新路由和导航

### 调试技巧

1. 查看后端日志: `backend/logs/app.log`
2. 查看浏览器控制台
3. 使用开发者工具调试

## 注意事项

1. Cookie包含敏感信息,请妥善保管
2. 定期备份数据库文件
3. 合理设置任务执行频率
4. 注意磁盘空间使用
5. 遵守网盘使用规则

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request

## 联系方式

如有问题请提交Issue

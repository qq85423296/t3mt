# T3MT - 前端

影视资源管理系统前端界面，提供直观的资源搜索、下载管理和任务调度功能。

## 核心功能

- **影视资源搜索**：快速搜索和筛选影视资源
- **资源下载管理**：可视化下载任务管理和进度监控
- **定时任务调度**：灵活配置自动化转存和下载任务
- **账号管理**：多账号支持和切换
- **日志查询**：完整的操作记录和日志追踪

## 项目结构

```
frontend/
├── css/                    # 样式文件
│   └── common.css         # 公共样式
├── js/                     # JavaScript文件
│   ├── api.js             # API调用封装
│   └── common.js          # 公共函数库
├── pages/                  # 功能页面
│   ├── search.html        # 影视资源搜索
│   ├── quark.html         # 网盘文件管理
│   ├── transfer.html      # 定时转存任务
│   ├── download.html      # 影视下载任务
│   ├── logs.html          # 日志管理
│   └── config.html        # 系统配置
├── index.html              # 主框架页面
├── login.html              # 登录页面
└── README.md               # 说明文档
```

## 技术栈

- 原生HTML5
- 原生CSS3
- 原生JavaScript (ES6+)
- Fetch API

## 特点

- 无需构建工具，直接打开HTML即可使用
- 轻量级，无第三方依赖
- 响应式设计，简约风格
- 模块化架构，易于维护

## 使用说明

### 1. 启动后端服务

确保后端服务已启动并运行在 `http://localhost:8520`

### 2. 访问前端页面

如果使用 Docker 部署，直接访问: http://localhost:8520

如果本地开发，可以使用简单的 HTTP 服务器:

```bash
# Python 3
python -m http.server 8080

# Node.js (需要安装http-server)
npx http-server -p 8080
```

然后访问: http://localhost:8080/login.html

### 3. 登录

默认账号: `admin`
默认密码: `admin123`

## 页面说明

### 登录页面 (login.html)
- 用户登录
- 表单验证
- 错误提示

### 主框架页面 (index.html)
- 左侧导航菜单
- 顶部标题栏
- 用户信息显示
- 动态加载子页面

### 影视资源搜索 (pages/search.html)
- 多源资源搜索引擎集成
- 影视资源分类筛选
- 搜索结果展示和排序
- 资源链接有效性检测
- 一键转存到网盘

### 网盘文件管理 (pages/quark.html)
- 文件和文件夹浏览
- 文件操作（创建、删除、分享、下载）
- 多账号管理和切换
- 面包屑导航

### 定时转存任务 (pages/transfer.html)
- 转存任务列表管理
- 创建和编辑定时任务
- Cron 表达式配置
- 任务状态监控
- 手动执行任务

### 影视下载任务 (pages/download.html)
- 下载任务列表管理
- 创建和编辑下载任务
- 实时下载进度显示
- 任务状态控制
- 断点续传支持

### 日志管理 (pages/logs.html)
- 日志查询
- 多条件筛选
- 分页显示
- 清空日志

### 系统配置 (pages/config.html)
- 网盘账号管理
- 日志配置
- 下载配置
- 邮件通知配置
- 资源搜索配置

## API配置

在 `js/api.js` 中修改API基础URL:

```javascript
const API_BASE_URL = 'http://localhost:8520';
```

## 开发说明

### 添加新页面

1. 在 `pages/` 目录创建HTML文件
2. 在 `index.html` 的 `pages` 对象中添加配置
3. 在左侧菜单添加导航项

### 调用API

使用封装好的API类:

```javascript
// 示例：获取账号列表
const result = await AccountAPI.getList();
if (result.code === 200) {
    console.log(result.data);
}
```

### 显示消息

```javascript
Message.success('操作成功');
Message.error('操作失败');
Message.warning('警告信息');
Message.info('提示信息');
```

### 模态框

```javascript
const modal = new Modal('modalId');
modal.show();
modal.hide();
```

## 浏览器兼容性

- Chrome 90+
- Edge 90+
- Firefox 88+
- Safari 14+

## 注意事项

1. 确保后端服务已启动（端口 8520）
2. 注意跨域问题（后端已配置CORS）
3. 使用现代浏览器以获得最佳体验
4. 首次使用需要在系统配置中添加网盘账号
5. Docker 部署时前后端已集成，无需单独配置

## 常见问题

### 1. 登录后跳转到空白页

检查后端服务是否正常运行

### 2. API请求失败

检查 `js/api.js` 中的 `API_BASE_URL` 配置是否正确

### 3. 页面加载失败

确保所有文件路径正确，使用HTTP服务器而不是直接打开文件

## 许可证

MIT License
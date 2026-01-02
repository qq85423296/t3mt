# T3MT - 前端

## 项目结构

```
frontend/
├── css/                    # 样式文件
│   └── common.css         # 公共样式
├── js/                     # JavaScript文件
│   ├── api.js             # API调用封装
│   └── common.js          # 公共函数库
├── pages/                  # 功能页面
│   ├── search.html        # 资源搜索
│   ├── quark.html         # 夸克网盘
│   ├── transfer.html      # 定时转存
│   ├── download.html      # 定时下载
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

确保后端服务已启动并运行在 `http://localhost:5000`

### 2. 打开前端页面

直接用浏览器打开 `login.html` 文件

或者使用简单的HTTP服务器:

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

### 资源搜索 (pages/search.html)
- 盘搜API集成
- 搜索结果展示
- 分类筛选
- 链接有效性检测
- 一键转存

### 夸克网盘 (pages/quark.html)
- 文件浏览
- 文件操作（创建、删除、分享、下载）
- 多账号切换
- 面包屑导航

### 定时转存 (pages/transfer.html)
- 任务列表
- 创建/编辑任务
- 任务执行
- 状态管理

### 定时下载 (pages/download.html)
- 任务列表
- 创建/编辑任务
- 下载进度
- 状态管理

### 日志管理 (pages/logs.html)
- 日志查询
- 多条件筛选
- 分页显示
- 清空日志

### 系统配置 (pages/config.html)
- 夸克账号管理
- 日志配置
- 下载配置
- 邮件配置
- 盘搜配置

## API配置

在 `js/api.js` 中修改API基础URL:

```javascript
const API_BASE_URL = 'http://localhost:5000';
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

1. 确保后端服务已启动
2. 注意跨域问题（后端需配置CORS）
3. 使用现代浏览器以获得最佳体验
4. 首次使用需要在系统配置中添加夸克账号

## 常见问题

### 1. 登录后跳转到空白页

检查后端服务是否正常运行

### 2. API请求失败

检查 `js/api.js` 中的 `API_BASE_URL` 配置是否正确

### 3. 页面加载失败

确保所有文件路径正确，使用HTTP服务器而不是直接打开文件

## 许可证

MIT License
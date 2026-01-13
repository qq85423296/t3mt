# 开发规范与质量保证规则

## 一、前端开发规范

### 1.1 脚本依赖管理
**问题根源**：修改代码时未考虑模块间的依赖关系，导致运行时错误。

**强制规则**：
- ✅ 在 `index.html` 中，所有被依赖的脚本必须在依赖它的脚本之前加载
- ✅ 例如：`api.js` 定义了 `RegexAPI`，则必须在 `regex-config.js` 之前加载
- ✅ 修改脚本时，必须检查是否有其他脚本依赖它
- ✅ 新增全局变量或API时，必须在文件顶部注释说明依赖关系

**检查清单**：
```javascript
// ❌ 错误示例
<script src="js/regex-config.js"></script>  // 使用 RegexAPI
<script src="js/api.js"></script>           // 定义 RegexAPI

// ✅ 正确示例
<script src="js/api.js"></script>           // 定义 RegexAPI
<script src="js/regex-config.js"></script>  // 使用 RegexAPI
```

### 1.2 数据类型防御性处理
**问题根源**：假设外部数据结构固定，未处理数据可能是数组、对象或字符串的情况。

**强制规则**：
- ✅ 处理外部API数据时，必须进行类型检查和转换
- ✅ 对于可能是数组的数据，使用 `Array.isArray()` 判断
- ✅ 对于可能是对象的数据，使用 `typeof` 和 `!== null` 判断
- ✅ 显示数据前必须确保是字符串类型

**检查清单**：
```javascript
// ❌ 错误示例
const link = playlinks[platform];
if (link) {
    display(link);  // link可能是对象，显示为 [object Object]
}

// ✅ 正确示例
let link = playlinks[platform];
// 处理数组
if (Array.isArray(link)) {
    link = link[0];
}
// 处理对象
if (typeof link === 'object' && link !== null) {
    link = link.url || link.link || '';
}
// 确保是字符串
if (link && typeof link === 'string') {
    display(link);
}
```

### 1.3 版本号管理
**强制规则**：
- ✅ 修改 JS/CSS 文件后，必须更新 HTML 中的版本号参数
- ✅ 版本号格式：`?v=YYYYMMDD` 或 `?v=YYYYMMDD[a-z]`
- ✅ 同一次修改的所有相关文件使用相同版本号

## 二、跨页面数据传递规范

### 2.1 SessionStorage 数据结构
**强制规则**：
- ✅ 存储前必须定义明确的数据结构并注释
- ✅ 读取时必须验证数据结构完整性
- ✅ 使用后必须立即清除，避免污染

**检查清单**：
```javascript
// ✅ 正确示例
// 存储端（search.html）
sessionStorage.setItem('pendingVideoTask', JSON.stringify({
    url: url,        // string: 影视URL
    title: title,    // string: 影视标题
    platform: platform  // string: 平台标识
}));

// 接收端（video.html）
const pendingTask = sessionStorage.getItem('pendingVideoTask');
if (pendingTask) {
    try {
        const taskData = JSON.parse(pendingTask);
        // 验证必需字段
        if (taskData.url && typeof taskData.url === 'string') {
            // 使用数据
        }
    } catch (error) {
        console.error('数据解析失败:', error);
    } finally {
        // 清除数据
        sessionStorage.removeItem('pendingVideoTask');
    }
}
```

## 三、修改代码前的检查流程

### 3.1 影响范围分析
**强制执行**：修改任何代码前必须完成以下检查

1. **依赖检查**
   - [ ] 该文件是否被其他文件引用？
   - [ ] 该函数/变量是否被其他模块使用？
   - [ ] 修改是否会影响全局作用域？

2. **数据流检查**
   - [ ] 数据从哪里来？（API、用户输入、其他页面）
   - [ ] 数据格式是否可能变化？（数组、对象、字符串）
   - [ ] 数据传递到哪里去？（其他函数、页面、存储）

3. **兼容性检查**
   - [ ] 是否会破坏现有功能？
   - [ ] 是否需要更新相关文档？
   - [ ] 是否需要数据库迁移？

### 3.2 测试清单
**修改后必须测试**：

**前端修改**：
- [ ] 在浏览器控制台检查是否有 JavaScript 错误
- [ ] 测试修改的功能是否正常工作
- [ ] 测试相关联的功能是否受影响
- [ ] 清除浏览器缓存后重新测试

**后端修改**：
- [ ] 检查 API 返回的数据结构
- [ ] 测试数据库操作是否正常
- [ ] 检查日志是否有错误信息
- [ ] 测试边界条件和异常情况

## 四、常见错误模式与预防

### 4.1 "undefined is not defined" 错误
**原因**：
- 脚本加载顺序错误
- 变量未声明就使用
- 异步加载导致时序问题

**预防**：
- 检查 HTML 中脚本加载顺序
- 使用 `typeof variable !== 'undefined'` 检查
- 异步操作使用 Promise 或 async/await

### 4.2 "[object Object]" 显示问题
**原因**：
- 直接显示对象而非字符串
- 未处理数据类型转换
- 模板字符串中嵌入对象

**预防**：
- 显示前检查数据类型
- 使用 `JSON.stringify()` 调试对象内容
- 提取对象中的字符串字段

### 4.3 数据库字段缺失错误
**原因**：
- 新增字段未创建迁移脚本
- 迁移脚本未在启动时执行
- 旧数据库未更新

**预防**：
- 新增字段必须创建迁移脚本
- 迁移脚本必须在 `run_migrations.py` 中注册
- 测试时使用旧数据库验证迁移

## 五、代码审查要点

### 5.1 自我审查清单
**提交代码前必须完成**：

- [ ] 代码是否有明显的逻辑错误？
- [ ] 是否处理了所有可能的数据类型？
- [ ] 是否添加了必要的错误处理？
- [ ] 是否更新了相关的版本号？
- [ ] 是否测试了修改的功能？
- [ ] 是否测试了相关联的功能？
- [ ] 是否检查了浏览器控制台的错误？
- [ ] 是否检查了后端日志的错误？

### 5.2 关键代码模式

**处理外部数据**：
```javascript
// 必须包含类型检查和默认值
function processExternalData(data) {
    // 1. 检查数据存在性
    if (!data) return defaultValue;
    
    // 2. 检查数据类型
    if (Array.isArray(data)) {
        data = data[0];
    }
    
    // 3. 提取字符串
    if (typeof data === 'object') {
        data = data.value || data.text || '';
    }
    
    // 4. 确保是字符串
    return String(data || '');
}
```

**跨页面传递数据**：
```javascript
// 发送端：明确数据结构
sessionStorage.setItem('key', JSON.stringify({
    field1: value1,  // 注释类型和用途
    field2: value2
}));

// 接收端：验证和清理
try {
    const data = JSON.parse(sessionStorage.getItem('key'));
    if (data && data.field1) {
        // 使用数据
    }
} catch (error) {
    console.error('数据解析失败:', error);
} finally {
    sessionStorage.removeItem('key');
}
```

## 六、紧急修复流程

**当发现线上问题时**：

1. **立即定位**
   - 查看浏览器控制台错误
   - 查看后端日志
   - 确认问题影响范围

2. **快速修复**
   - 修复核心问题
   - 添加防御性代码
   - 更新版本号

3. **验证测试**
   - 清除缓存测试
   - 测试相关功能
   - 检查是否有新错误

4. **提交部署**
   - 提交代码并说明问题
   - 更新版本号
   - 通知用户更新

## 七、持续改进

### 7.1 问题记录
**每次出现问题后**：
- 记录问题原因
- 分析根本原因
- 更新此规范文档
- 添加预防措施

### 7.2 定期审查
**每月进行**：
- 审查最近的问题
- 更新检查清单
- 优化开发流程
- 分享经验教训

---

**最后更新**: 2026-01-13
**维护者**: 开发团队

**重要提醒**：
- 这不是建议，是强制规则
- 违反规则导致的问题必须立即修复
- 重复违反规则需要重新学习此文档

# 插件模板

这是一个 T3MT 插件模板，用于快速创建新插件。

## 使用方法

1. 复制整个 `_template` 目录
2. 重命名为你的插件ID（如 `my_plugin`）
3. 修改 `plugin_meta.json` 中的插件信息
4. 在 `backend/main.py` 中实现你的逻辑
5. 打包为 .zip 文件并安装

## 文件说明

- `plugin_meta.json`: 插件元信息，定义插件ID、名称、版本、配置项等
- `backend/main.py`: 插件主代码，实现 `execute()` 方法
- `README.md`: 插件说明文档（可选）

## 配置项类型

- `string`: 文本输入
- `number`: 数字输入
- `boolean`: 开关
- `select`: 下拉选择（需配合 options）

## 任务上下文

插件执行时可以访问以下任务信息：

- `task_id`: 任务ID
- `task_name`: 任务名称
- `task_type`: 任务类型（transfer/download/video）
- `status`: 执行状态（success/failed/partial）
- `success_count`: 成功数
- `failed_count`: 失败数
- `target_path`: 目标路径

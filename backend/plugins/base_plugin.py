# -*- coding: utf-8 -*-
"""
插件基类 - 所有插件必须继承此类

使用示例：
    from plugins.base_plugin import BasePlugin
    
    class MyPlugin(BasePlugin):
        def execute(self) -> bool:
            self.log("开始执行")
            # 你的业务逻辑
            return True
    
    def register_plugin():
        return MyPlugin
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime


class BasePlugin(ABC):
    """
    插件基类
    
    所有T3MT插件必须继承此类并实现 execute() 方法。
    
    Attributes:
        plugin_config (dict): 插件配置参数，从数据库读取
        task_context (dict): 任务上下文参数，包含任务执行结果
    
    Example:
        >>> class MyPlugin(BasePlugin):
        ...     def execute(self) -> bool:
        ...         api_key = self.get_config('api_key')
        ...         task_name = self.get_task_param('task_name')
        ...         self.log(f"处理任务: {task_name}")
        ...         return True
    """
    
    def __init__(self, plugin_config: Dict[str, Any] = None, 
                 task_context: Dict[str, Any] = None):
        """
        初始化插件
        
        Args:
            plugin_config: 插件配置参数（从数据库读取的用户配置）
            task_context: 任务上下文参数（任务执行结果信息）
        """
        self.plugin_config = plugin_config or {}
        self.task_context = task_context or {}
        self._logs: List[Dict[str, str]] = []
    
    @abstractmethod
    def execute(self) -> bool:
        """
        插件核心执行逻辑
        
        子类必须实现此方法。此方法在任务执行完成后被调用。
        
        Returns:
            bool: 执行是否成功。返回 True 表示成功，False 表示失败。
        
        Raises:
            NotImplementedError: 如果子类未实现此方法
        
        Example:
            >>> def execute(self) -> bool:
            ...     try:
            ...         # 业务逻辑
            ...         self.log("执行成功", "success")
            ...         return True
            ...     except Exception as e:
            ...         self.log(f"执行失败: {e}", "error")
            ...         return False
        """
        raise NotImplementedError("子类必须实现 execute() 方法")
    
    def log(self, message: str, level: str = "info") -> None:
        """
        记录日志
        
        日志会被保存到数据库，并在任务详情页展示。
        
        Args:
            message: 日志内容
            level: 日志级别，可选值：
                - "info": 普通信息（默认）
                - "success": 成功信息
                - "warning": 警告信息
                - "error": 错误信息
        
        Example:
            >>> self.log("开始处理")
            >>> self.log("处理完成", "success")
            >>> self.log("配置缺失", "warning")
            >>> self.log("连接失败", "error")
        """
        timestamp = datetime.now().strftime('%H:%M:%S')
        self._logs.append({
            'timestamp': timestamp,
            'level': level.upper(),
            'message': message
        })
    
    def get_logs(self) -> str:
        """
        获取所有日志内容
        
        Returns:
            str: 格式化的日志字符串，每行一条日志
        
        Example:
            >>> logs = plugin.get_logs()
            >>> print(logs)
            [10:30:15][INFO] 开始执行
            [10:30:16][SUCCESS] 执行完成
        """
        return "\n".join([
            f"[{log['timestamp']}][{log['level']}] {log['message']}"
            for log in self._logs
        ])
    
    def get_logs_list(self) -> List[Dict[str, str]]:
        """
        获取日志列表
        
        Returns:
            list: 日志字典列表，每个字典包含 timestamp、level、message
        """
        return self._logs.copy()
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取插件配置项
        
        从 plugin_config 中获取指定的配置值。
        
        Args:
            key: 配置项键名（对应 plugin_meta.json 中的 param_key）
            default: 默认值，当配置项不存在时返回
        
        Returns:
            配置值，如果不存在则返回默认值
        
        Example:
            >>> smtp_host = self.get_config('smtp_host', 'smtp.163.com')
            >>> timeout = self.get_config('timeout', 30)
        """
        return self.plugin_config.get(key, default)
    
    def get_task_param(self, key: str, default: Any = None) -> Any:
        """
        获取任务上下文参数
        
        从 task_context 中获取任务执行信息。
        
        可用的参数：
            - task_id (int): 任务ID
            - task_name (str): 任务名称
            - task_type (str): 任务类型（transfer/download/video）
            - status (str): 执行状态（success/failed）
            - start_time (str): 开始时间
            - end_time (str): 结束时间
            - duration (int): 执行耗时（秒）
            - total_count (int): 总文件数
            - success_count (int): 成功数
            - failed_count (int): 失败数
            - total_size (int): 总大小（字节）
            - source_path (str): 源目录
            - target_path (str): 目标目录
            - error_message (str): 错误信息（失败时）
        
        Args:
            key: 参数键名
            default: 默认值，当参数不存在时返回
        
        Returns:
            参数值，如果不存在则返回默认值
        
        Example:
            >>> task_name = self.get_task_param('task_name', '未知任务')
            >>> status = self.get_task_param('status')
            >>> if status == 'success':
            ...     self.log("任务执行成功")
        """
        return self.task_context.get(key, default)
    
    def has_config(self, key: str) -> bool:
        """
        检查配置项是否存在
        
        Args:
            key: 配置项键名
        
        Returns:
            bool: 配置项是否存在
        """
        return key in self.plugin_config
    
    def has_task_param(self, key: str) -> bool:
        """
        检查任务参数是否存在
        
        Args:
            key: 参数键名
        
        Returns:
            bool: 参数是否存在
        """
        return key in self.task_context
    
    def is_task_success(self) -> bool:
        """
        检查任务是否执行成功
        
        Returns:
            bool: 任务是否成功
        """
        return self.get_task_param('status') == 'success'
    
    def is_task_failed(self) -> bool:
        """
        检查任务是否执行失败
        
        Returns:
            bool: 任务是否失败
        """
        return self.get_task_param('status') == 'failed'
    
    def format_size(self, size: int) -> str:
        """
        格式化文件大小
        
        将字节数转换为人类可读的格式。
        
        Args:
            size: 文件大小（字节）
        
        Returns:
            str: 格式化后的大小字符串
        
        Example:
            >>> self.format_size(1024)
            '1.00 KB'
            >>> self.format_size(1073741824)
            '1.00 GB'
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    def format_duration(self, seconds: int) -> str:
        """
        格式化时间长度
        
        将秒数转换为人类可读的格式。
        
        Args:
            seconds: 时间长度（秒）
        
        Returns:
            str: 格式化后的时间字符串
        
        Example:
            >>> self.format_duration(3661)
            '1小时1分1秒'
            >>> self.format_duration(65)
            '1分5秒'
        """
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}小时")
        if minutes > 0:
            parts.append(f"{minutes}分")
        if secs > 0 or not parts:
            parts.append(f"{secs}秒")
        
        return ''.join(parts)

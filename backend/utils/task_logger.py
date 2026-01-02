# -*- coding: utf-8 -*-
"""
任务日志工具
统一的日志格式管理
"""
from datetime import datetime
from typing import List, Dict, Callable, Optional


class TaskLogger:
    """任务日志记录器"""
    
    def __init__(self, update_callback: Optional[Callable] = None):
        """
        初始化日志记录器
        
        Args:
            update_callback: 日志更新回调函数，用于实时更新到数据库
        """
        self.logs: List[Dict] = []
        self.update_callback = update_callback
    
    def _add_log(self, message: str, log_type: str = 'info'):
        """
        添加日志
        
        Args:
            message: 日志消息
            log_type: 日志类型 (info/success/warning/error)
        """
        log_entry = {
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': message,
            'type': log_type
        }
        self.logs.append(log_entry)
        
        # 如果有回调函数，立即更新
        if self.update_callback:
            self.update_callback()
    
    def info(self, message: str):
        """记录信息日志"""
        self._add_log(message, 'info')
    
    def success(self, message: str):
        """记录成功日志"""
        self._add_log(message, 'success')
    
    def warning(self, message: str):
        """记录警告日志"""
        self._add_log(message, 'warning')
    
    def error(self, message: str):
        """记录错误日志"""
        self._add_log(message, 'error')
    
    def get_logs(self) -> List[Dict]:
        """获取所有日志"""
        return self.logs
    
    def get_logs_text(self) -> str:
        """
        获取日志的文本格式（用于兼容旧代码）
        
        Returns:
            格式化的日志文本，每行格式为: [HH:MM:SS] message
        """
        return '\n'.join([
            f"[{log['timestamp']}] {log['message']}"
            for log in self.logs
        ])
    
    def clear(self):
        """清空日志"""
        self.logs.clear()

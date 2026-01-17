# -*- coding: utf-8 -*-
"""
插件模板

复制此目录并修改为你的插件。
"""
import sys
import os

# 添加父目录到路径，以便导入 BasePlugin
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from plugins.base_plugin import BasePlugin


class MyPlugin(BasePlugin):
    """
    我的插件
    
    在这里实现你的插件逻辑。
    """
    
    def execute(self) -> bool:
        """
        执行插件逻辑
        
        此方法在任务执行完成后被调用。
        
        可用属性：
        - self.plugin_config: 插件配置字典
        - self.task_context: 任务上下文字典
        
        可用方法：
        - self.log(message, level='info'): 记录日志
        - self.get_logs(): 获取所有日志
        
        Returns:
            True 表示执行成功，False 表示执行失败
        """
        # 获取配置参数
        example_string = self.plugin_config.get('example_string', '')
        example_number = self.plugin_config.get('example_number', 10)
        example_boolean = self.plugin_config.get('example_boolean', True)
        
        # 获取任务上下文
        task_name = self.task_context.get('task_name', '未知任务')
        task_type = self.task_context.get('task_type', 'unknown')
        status = self.task_context.get('status', 'unknown')
        success_count = self.task_context.get('success_count', 0)
        failed_count = self.task_context.get('failed_count', 0)
        
        # 记录日志
        self.log(f"插件开始执行")
        self.log(f"任务名称: {task_name}")
        self.log(f"任务类型: {task_type}")
        self.log(f"执行状态: {status}")
        self.log(f"成功/失败: {success_count}/{failed_count}")
        
        try:
            # ========== 在这里实现你的逻辑 ==========
            
            # 示例：根据配置执行不同操作
            if example_boolean:
                self.log(f"配置参数: {example_string}, 数量: {example_number}")
            
            # 示例：根据任务状态执行不同操作
            if status == 'success':
                self.log("任务执行成功，执行成功后的操作...")
            elif status == 'failed':
                self.log("任务执行失败，执行失败后的操作...", level='warning')
            else:
                self.log("任务部分成功，执行部分成功后的操作...")
            
            # ========== 逻辑结束 ==========
            
            self.log("插件执行完成")
            return True
            
        except Exception as e:
            self.log(f"插件执行异常: {str(e)}", level='error')
            return False


def register_plugin():
    """
    注册插件
    
    此函数供插件管理器调用，返回插件类。
    """
    return MyPlugin

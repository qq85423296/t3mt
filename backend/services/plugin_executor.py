# -*- coding: utf-8 -*-
"""
插件执行器

负责在任务执行完成后调用关联的插件。
支持按顺序执行、延迟执行、错误隔离和日志记录。
"""
import time
import traceback
from typing import Dict, List, Optional
from datetime import datetime

from models.plugin import PluginInfo, TaskPluginRelation, PluginExecLog
from services.plugin_registry import PluginRegistry


class PluginExecutor:
    """
    插件执行器
    
    负责在任务执行完成后调用关联的插件。
    
    特性：
    - 按 sort_order 顺序执行插件
    - 支持延迟执行
    - 单个插件失败不影响其他插件
    - 记录执行日志
    """
    
    @classmethod
    def execute_plugins(cls, task_id: int, task_type: str, 
                       execution_id: int, task_context: dict) -> dict:
        """
        执行任务关联的所有插件
        
        Args:
            task_id: 任务ID
            task_type: 任务类型（transfer/download/video）
            execution_id: 执行记录ID
            task_context: 任务上下文数据，包含：
                - task_id: 任务ID
                - task_name: 任务名称
                - task_type: 任务类型
                - status: 执行状态（success/failed）
                - start_time: 开始时间
                - end_time: 结束时间
                - duration: 执行耗时（秒）
                - total_count: 总文件数
                - success_count: 成功数
                - failed_count: 失败数
                - total_size: 总大小（字节）
                - source_path: 源目录
                - target_path: 目标目录
                - error_message: 错误信息（失败时）
        
        Returns:
            {
                "total": int,      # 总插件数
                "success": int,    # 成功数
                "failed": int,     # 失败数
                "skipped": int,    # 跳过数（插件未启动）
                "logs": list       # 执行日志列表
            }
        """
        result = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "logs": []
        }
        
        # 获取任务关联的已启动插件（按顺序）
        relations = TaskPluginRelation.get_active_by_task(task_id, task_type)
        result["total"] = len(relations)
        
        if not relations:
            return result
        
        # 按顺序执行每个插件
        for relation in relations:
            plugin_id = relation.plugin_id
            plugin_name = getattr(relation, 'plugin_name', plugin_id)
            
            # 检查插件是否已注册
            if not PluginRegistry.is_registered(plugin_id):
                result["skipped"] += 1
                cls._save_execution_log(
                    execution_id=execution_id,
                    plugin_id=plugin_id,
                    plugin_name=plugin_name,
                    status=PluginExecLog.STATUS_FAILED,
                    log_content=f"插件 {plugin_id} 未启动，跳过执行",
                    duration=0
                )
                continue
            
            # 执行单个插件
            exec_result = cls._execute_single_plugin(
                plugin_id=plugin_id,
                plugin_name=plugin_name,
                relation=relation,
                task_context=task_context,
                execution_id=execution_id
            )
            
            if exec_result['success']:
                result["success"] += 1
            else:
                result["failed"] += 1
            
            result["logs"].append(exec_result)
        
        return result
    
    @classmethod
    def _execute_single_plugin(cls, plugin_id: str, plugin_name: str,
                               relation: TaskPluginRelation,
                               task_context: dict, execution_id: int) -> dict:
        """
        执行单个插件
        
        Args:
            plugin_id: 插件ID
            plugin_name: 插件名称
            relation: 任务插件关联对象
            task_context: 任务上下文
            execution_id: 执行记录ID
        
        Returns:
            {
                "plugin_id": str,
                "plugin_name": str,
                "success": bool,
                "log_content": str,
                "duration": int,
                "error": str
            }
        """
        result = {
            "plugin_id": plugin_id,
            "plugin_name": plugin_name,
            "success": False,
            "log_content": "",
            "duration": 0,
            "error": None
        }
        
        start_time = time.time()
        
        try:
            # 处理延迟执行
            delay_seconds = relation.delay_seconds or 0
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            
            # 获取插件配置
            # 优先使用任务级别的配置覆盖，否则使用插件全局配置
            plugin_config = relation.plugin_config or {}
            if not plugin_config:
                plugin_info = PluginInfo.get_by_plugin_id(plugin_id)
                if plugin_info:
                    plugin_config = plugin_info.config or {}
            
            # 构建传递给插件的上下文
            # 如果 pass_task_param 为 False，则不传递任务参数
            if relation.pass_task_param:
                # 根据 selected_params 过滤要传递的参数
                selected_params = relation.selected_params or []
                if selected_params:
                    # 只传递选中的参数
                    context_to_pass = {k: v for k, v in task_context.items() if k in selected_params}
                else:
                    # 如果没有选择参数，传递所有参数（向后兼容）
                    context_to_pass = task_context.copy()
            else:
                context_to_pass = {}
            
            # 创建插件实例
            plugin_instance = PluginRegistry.create_instance(
                plugin_id=plugin_id,
                plugin_config=plugin_config,
                task_context=context_to_pass
            )
            
            if plugin_instance is None:
                raise RuntimeError(f"无法创建插件实例: {plugin_id}")
            
            # 执行插件
            success = plugin_instance.execute()
            
            # 获取日志
            log_content = plugin_instance.get_logs()
            
            result["success"] = success
            result["log_content"] = log_content
            
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["log_content"] = f"插件执行异常: {str(e)}\n{traceback.format_exc()}"
        
        finally:
            # 计算耗时
            end_time = time.time()
            result["duration"] = int((end_time - start_time) * 1000)  # 毫秒
            
            # 保存执行日志
            cls._save_execution_log(
                execution_id=execution_id,
                plugin_id=plugin_id,
                plugin_name=plugin_name,
                status=PluginExecLog.STATUS_SUCCESS if result["success"] else PluginExecLog.STATUS_FAILED,
                log_content=result["log_content"],
                duration=result["duration"]
            )
        
        return result
    
    @classmethod
    def _save_execution_log(cls, execution_id: int, plugin_id: str,
                           plugin_name: str, status: str, 
                           log_content: str, duration: int) -> int:
        """
        保存插件执行日志
        
        Args:
            execution_id: 任务执行记录ID
            plugin_id: 插件ID
            plugin_name: 插件名称
            status: 执行状态（success/failed）
            log_content: 日志内容
            duration: 执行耗时（毫秒）
        
        Returns:
            日志记录ID
        """
        return PluginExecLog.create(
            execution_id=execution_id,
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            status=status,
            log_content=log_content,
            duration=duration
        )
    
    @classmethod
    def get_execution_logs(cls, execution_id: int) -> List[dict]:
        """
        获取执行记录的插件日志
        
        Args:
            execution_id: 任务执行记录ID
        
        Returns:
            日志列表
        """
        logs = PluginExecLog.get_by_execution(execution_id)
        return [log.to_dict() for log in logs]
    
    @classmethod
    def get_plugin_stats(cls, plugin_id: str) -> dict:
        """
        获取插件执行统计
        
        Args:
            plugin_id: 插件ID
        
        Returns:
            统计信息
        """
        return PluginExecLog.get_stats_by_plugin(plugin_id)
    
    @classmethod
    def test_plugin(cls, plugin_id: str, temp_config: dict = None) -> dict:
        """
        测试插件功能
        
        使用模拟的任务上下文执行插件，用于验证配置是否正确
        
        Args:
            plugin_id: 插件ID
            temp_config: 临时配置（用于测试未保存的配置）
        
        Returns:
            {"success": bool, "message": str, "logs": list}
        """
        result = {
            "success": False,
            "message": "",
            "logs": []
        }
        
        try:
            # 获取插件信息
            plugin_info = PluginInfo.get_by_plugin_id(plugin_id)
            if not plugin_info:
                result["message"] = f"插件 {plugin_id} 不存在"
                return result
            
            # 加载插件类
            from services.plugin_manager import PluginManager
            plugin_class = PluginManager._load_plugin_class(plugin_id)
            if plugin_class is None:
                result["message"] = f"无法加载插件 {plugin_id} 的代码"
                return result
            
            # 使用临时配置或已保存的配置
            plugin_config = temp_config if temp_config else (plugin_info.config or {})
            
            # 构建测试用的任务上下文
            test_context = {
                "task_id": 0,
                "task_name": "测试任务",
                "task_type": "transfer",
                "status": "success",
                "start_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "end_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "duration": 10,
                "total_count": 5,
                "success_count": 5,
                "failed_count": 0,
                "total_size": 1024000,
                "source_path": "/test/source",
                "target_path": "/test/target",
                "error_message": ""
            }
            
            # 创建插件实例
            plugin_instance = plugin_class(
                plugin_config=plugin_config,
                task_context=test_context
            )
            
            # 执行插件
            success = plugin_instance.execute()
            
            # 获取日志
            logs = plugin_instance.get_logs()
            result["logs"] = logs.split('\n') if logs else []
            
            if success:
                result["success"] = True
                result["message"] = "测试成功"
            else:
                result["message"] = "测试失败，请查看日志"
            
        except Exception as e:
            result["message"] = f"测试异常: {str(e)}"
            result["logs"] = [str(e), traceback.format_exc()]
        
        return result

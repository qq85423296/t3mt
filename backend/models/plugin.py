# -*- coding: utf-8 -*-
"""
插件系统数据模型

包含 PluginInfo、TaskPluginRelation、PluginExecLog 三个模型类
"""
import json
from datetime import datetime
from database import get_db


class PluginInfo:
    """插件信息模型"""
    
    # 插件状态常量
    STATUS_INSTALLED = 'installed'  # 已安装
    STATUS_STARTED = 'started'      # 已启动
    STATUS_STOPPED = 'stopped'      # 已停止
    
    def __init__(self, id=None, plugin_id=None, plugin_name=None, 
                 plugin_version=None, plugin_author=None, plugin_desc=None,
                 status=STATUS_INSTALLED, config=None, meta_json=None,
                 install_path=None, created_at=None, updated_at=None):
        self.id = id
        self.plugin_id = plugin_id
        self.plugin_name = plugin_name
        self.plugin_version = plugin_version
        self.plugin_author = plugin_author
        self.plugin_desc = plugin_desc
        self.status = status
        self.config = config if isinstance(config, dict) else {}
        self.meta_json = meta_json if isinstance(meta_json, dict) else {}
        self.install_path = install_path
        self.created_at = created_at
        self.updated_at = updated_at
    
    @staticmethod
    def get_all():
        """获取所有插件"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM plugin_info 
                ORDER BY created_at DESC
            ''')
            rows = cursor.fetchall()
            return [PluginInfo._from_row(row) for row in rows]
    
    @staticmethod
    def get_by_id(id):
        """根据数据库ID获取插件"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM plugin_info WHERE id = ?', (id,))
            row = cursor.fetchone()
            return PluginInfo._from_row(row) if row else None
    
    @staticmethod
    def get_by_plugin_id(plugin_id):
        """根据插件ID获取插件"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM plugin_info WHERE plugin_id = ?', (plugin_id,))
            row = cursor.fetchone()
            return PluginInfo._from_row(row) if row else None
    
    @staticmethod
    def get_by_status(status):
        """根据状态获取插件列表"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM plugin_info 
                WHERE status = ?
                ORDER BY created_at DESC
            ''', (status,))
            rows = cursor.fetchall()
            return [PluginInfo._from_row(row) for row in rows]
    
    @staticmethod
    def get_active_plugins():
        """获取所有已启动的插件"""
        return PluginInfo.get_by_status(PluginInfo.STATUS_STARTED)
    
    @staticmethod
    def create(plugin_id, plugin_name, plugin_version, meta_json,
               plugin_author=None, plugin_desc=None, config=None, 
               install_path=None, status=None):
        """创建插件记录"""
        if status is None:
            status = PluginInfo.STATUS_INSTALLED
            
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO plugin_info 
                (plugin_id, plugin_name, plugin_version, plugin_author, 
                 plugin_desc, status, config, meta_json, install_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                plugin_id,
                plugin_name,
                plugin_version,
                plugin_author,
                plugin_desc,
                status,
                json.dumps(config or {}, ensure_ascii=False),
                json.dumps(meta_json, ensure_ascii=False),
                install_path
            ))
            return cursor.lastrowid
    
    @staticmethod
    def update(plugin_id, **kwargs):
        """更新插件信息"""
        allowed_fields = [
            'plugin_name', 'plugin_version', 'plugin_author', 'plugin_desc',
            'status', 'config', 'meta_json', 'install_path'
        ]
        
        # 处理JSON字段
        if 'config' in kwargs and isinstance(kwargs['config'], dict):
            kwargs['config'] = json.dumps(kwargs['config'], ensure_ascii=False)
        if 'meta_json' in kwargs and isinstance(kwargs['meta_json'], dict):
            kwargs['meta_json'] = json.dumps(kwargs['meta_json'], ensure_ascii=False)
        
        # 过滤允许的字段
        update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not update_fields:
            return False
        
        # 构建SQL
        set_clause = ', '.join([f'{k} = ?' for k in update_fields.keys()])
        values = list(update_fields.values())
        values.append(plugin_id)
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE plugin_info 
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE plugin_id = ?
            ''', values)
            return cursor.rowcount > 0
    
    @staticmethod
    def update_status(plugin_id, status):
        """更新插件状态"""
        return PluginInfo.update(plugin_id, status=status)
    
    @staticmethod
    def update_config(plugin_id, config):
        """更新插件配置"""
        return PluginInfo.update(plugin_id, config=config)
    
    @staticmethod
    def delete(plugin_id):
        """删除插件记录"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM plugin_info WHERE plugin_id = ?', (plugin_id,))
            return cursor.rowcount > 0
    
    @staticmethod
    def exists(plugin_id):
        """检查插件是否存在"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) FROM plugin_info WHERE plugin_id = ?', 
                (plugin_id,)
            )
            return cursor.fetchone()[0] > 0
    
    @staticmethod
    def _from_row(row):
        """从数据库行创建对象"""
        config = {}
        meta_json = {}
        
        if row['config']:
            try:
                config = json.loads(row['config'])
            except (json.JSONDecodeError, TypeError):
                pass
        
        if row['meta_json']:
            try:
                meta_json = json.loads(row['meta_json'])
            except (json.JSONDecodeError, TypeError):
                pass
        
        return PluginInfo(
            id=row['id'],
            plugin_id=row['plugin_id'],
            plugin_name=row['plugin_name'],
            plugin_version=row['plugin_version'],
            plugin_author=row['plugin_author'],
            plugin_desc=row['plugin_desc'],
            status=row['status'],
            config=config,
            meta_json=meta_json,
            install_path=row['install_path'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'plugin_id': self.plugin_id,
            'plugin_name': self.plugin_name,
            'plugin_version': self.plugin_version,
            'plugin_author': self.plugin_author,
            'plugin_desc': self.plugin_desc,
            'status': self.status,
            'config': self.config,
            'meta_json': self.meta_json,
            'install_path': self.install_path,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }



class TaskPluginRelation:
    """任务插件关联模型"""
    
    # 任务类型常量
    TASK_TYPE_TRANSFER = 'transfer'  # 定时转存
    TASK_TYPE_DOWNLOAD = 'download'  # 定时下载
    TASK_TYPE_VIDEO = 'video'        # 影视下载
    
    def __init__(self, id=None, task_id=None, task_type=None, plugin_id=None,
                 sort_order=0, pass_task_param=1, delay_seconds=0,
                 plugin_config=None, selected_params=None, created_at=None):
        self.id = id
        self.task_id = task_id
        self.task_type = task_type
        self.plugin_id = plugin_id
        self.sort_order = sort_order
        self.pass_task_param = pass_task_param
        self.delay_seconds = delay_seconds
        self.plugin_config = plugin_config if isinstance(plugin_config, dict) else {}
        self.selected_params = selected_params if isinstance(selected_params, list) else []
        self.created_at = created_at
    
    @staticmethod
    def get_by_task(task_id, task_type):
        """获取任务关联的所有插件（按执行顺序排序）"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT tpr.*, pi.plugin_name, pi.status as plugin_status
                FROM task_plugin_relation tpr
                LEFT JOIN plugin_info pi ON tpr.plugin_id = pi.plugin_id
                WHERE tpr.task_id = ? AND tpr.task_type = ?
                ORDER BY tpr.sort_order ASC
            ''', (task_id, task_type))
            rows = cursor.fetchall()
            return [TaskPluginRelation._from_row(row) for row in rows]
    
    @staticmethod
    def get_active_by_task(task_id, task_type):
        """获取任务关联的已启动插件（按执行顺序排序）"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT tpr.*, pi.plugin_name, pi.status as plugin_status
                FROM task_plugin_relation tpr
                INNER JOIN plugin_info pi ON tpr.plugin_id = pi.plugin_id
                WHERE tpr.task_id = ? AND tpr.task_type = ? AND pi.status = ?
                ORDER BY tpr.sort_order ASC
            ''', (task_id, task_type, PluginInfo.STATUS_STARTED))
            rows = cursor.fetchall()
            return [TaskPluginRelation._from_row(row) for row in rows]
    
    @staticmethod
    def get_by_plugin(plugin_id):
        """获取使用指定插件的所有任务关联"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM task_plugin_relation 
                WHERE plugin_id = ?
            ''', (plugin_id,))
            rows = cursor.fetchall()
            return [TaskPluginRelation._from_row(row) for row in rows]
    
    @staticmethod
    def create(task_id, task_type, plugin_id, sort_order=0, 
               pass_task_param=1, delay_seconds=0, plugin_config=None, selected_params=None):
        """创建任务插件关联"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO task_plugin_relation 
                (task_id, task_type, plugin_id, sort_order, pass_task_param, 
                 delay_seconds, plugin_config, selected_params)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task_id,
                task_type,
                plugin_id,
                sort_order,
                pass_task_param,
                delay_seconds,
                json.dumps(plugin_config or {}, ensure_ascii=False),
                json.dumps(selected_params or [], ensure_ascii=False)
            ))
            return cursor.lastrowid
    
    @staticmethod
    def update(id, **kwargs):
        """更新任务插件关联"""
        allowed_fields = [
            'sort_order', 'pass_task_param', 'delay_seconds', 'plugin_config', 'selected_params'
        ]
        
        # 处理JSON字段
        if 'plugin_config' in kwargs and isinstance(kwargs['plugin_config'], dict):
            kwargs['plugin_config'] = json.dumps(kwargs['plugin_config'], ensure_ascii=False)
        if 'selected_params' in kwargs and isinstance(kwargs['selected_params'], list):
            kwargs['selected_params'] = json.dumps(kwargs['selected_params'], ensure_ascii=False)
        
        # 过滤允许的字段
        update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not update_fields:
            return False
        
        # 构建SQL
        set_clause = ', '.join([f'{k} = ?' for k in update_fields.keys()])
        values = list(update_fields.values())
        values.append(id)
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE task_plugin_relation 
                SET {set_clause}
                WHERE id = ?
            ''', values)
            return cursor.rowcount > 0
    
    @staticmethod
    def delete(id):
        """删除单个关联记录"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM task_plugin_relation WHERE id = ?', (id,))
            return cursor.rowcount > 0
    
    @staticmethod
    def delete_by_task(task_id, task_type):
        """删除任务的所有插件关联"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM task_plugin_relation 
                WHERE task_id = ? AND task_type = ?
            ''', (task_id, task_type))
            return cursor.rowcount
    
    @staticmethod
    def delete_by_plugin(plugin_id):
        """删除插件的所有任务关联（级联删除用）"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM task_plugin_relation 
                WHERE plugin_id = ?
            ''', (plugin_id,))
            return cursor.rowcount
    
    @staticmethod
    def save_task_plugins(task_id, task_type, plugins):
        """
        保存任务的插件关联（先删除旧的，再创建新的）
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
            plugins: 插件列表，每项包含 plugin_id, sort_order, pass_task_param, 
                     delay_seconds, plugin_config, selected_params
        """
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 删除旧的关联
            cursor.execute('''
                DELETE FROM task_plugin_relation 
                WHERE task_id = ? AND task_type = ?
            ''', (task_id, task_type))
            
            # 创建新的关联
            for idx, plugin in enumerate(plugins):
                cursor.execute('''
                    INSERT INTO task_plugin_relation 
                    (task_id, task_type, plugin_id, sort_order, pass_task_param, 
                     delay_seconds, plugin_config, selected_params)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    task_id,
                    task_type,
                    plugin.get('plugin_id'),
                    plugin.get('sort_order', idx),
                    plugin.get('pass_task_param', 1),
                    plugin.get('delay_seconds', 0),
                    json.dumps(plugin.get('plugin_config', {}), ensure_ascii=False),
                    json.dumps(plugin.get('selected_params', []), ensure_ascii=False)
                ))
            
            return len(plugins)
    
    @staticmethod
    def count_by_plugin(plugin_id):
        """统计使用指定插件的任务数量"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM task_plugin_relation 
                WHERE plugin_id = ?
            ''', (plugin_id,))
            return cursor.fetchone()[0]
    
    @staticmethod
    def _from_row(row):
        """从数据库行创建对象"""
        plugin_config = {}
        selected_params = []
        
        if 'plugin_config' in row.keys() and row['plugin_config']:
            try:
                plugin_config = json.loads(row['plugin_config'])
            except (json.JSONDecodeError, TypeError):
                pass
        
        if 'selected_params' in row.keys() and row['selected_params']:
            try:
                selected_params = json.loads(row['selected_params'])
            except (json.JSONDecodeError, TypeError):
                pass
        
        relation = TaskPluginRelation(
            id=row['id'],
            task_id=row['task_id'],
            task_type=row['task_type'],
            plugin_id=row['plugin_id'],
            sort_order=row['sort_order'],
            pass_task_param=row['pass_task_param'],
            delay_seconds=row['delay_seconds'],
            plugin_config=plugin_config,
            selected_params=selected_params,
            created_at=row['created_at']
        )
        
        # 添加关联查询的额外字段
        if 'plugin_name' in row.keys():
            relation.plugin_name = row['plugin_name']
        if 'plugin_status' in row.keys():
            relation.plugin_status = row['plugin_status']
        
        return relation
    
    def to_dict(self):
        """转换为字典"""
        result = {
            'id': self.id,
            'task_id': self.task_id,
            'task_type': self.task_type,
            'plugin_id': self.plugin_id,
            'sort_order': self.sort_order,
            'pass_task_param': self.pass_task_param,
            'delay_seconds': self.delay_seconds,
            'plugin_config': self.plugin_config,
            'selected_params': self.selected_params,
            'created_at': self.created_at
        }
        
        # 添加关联查询的额外字段
        if hasattr(self, 'plugin_name'):
            result['plugin_name'] = self.plugin_name
        if hasattr(self, 'plugin_status'):
            result['plugin_status'] = self.plugin_status
        
        return result



class PluginExecLog:
    """插件执行日志模型"""
    
    # 执行状态常量
    STATUS_SUCCESS = 'success'  # 执行成功
    STATUS_FAILED = 'failed'    # 执行失败
    
    def __init__(self, id=None, execution_id=None, plugin_id=None, 
                 plugin_name=None, status=None, log_content=None,
                 duration=None, created_at=None):
        self.id = id
        self.execution_id = execution_id
        self.plugin_id = plugin_id
        self.plugin_name = plugin_name
        self.status = status
        self.log_content = log_content
        self.duration = duration  # 执行耗时（毫秒）
        self.created_at = created_at
    
    @staticmethod
    def get_by_execution(execution_id):
        """获取执行记录的所有插件日志"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM plugin_exec_log 
                WHERE execution_id = ?
                ORDER BY created_at ASC
            ''', (execution_id,))
            rows = cursor.fetchall()
            return [PluginExecLog._from_row(row) for row in rows]
    
    @staticmethod
    def get_by_plugin(plugin_id, limit=100):
        """获取插件的执行日志"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM plugin_exec_log 
                WHERE plugin_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (plugin_id, limit))
            rows = cursor.fetchall()
            return [PluginExecLog._from_row(row) for row in rows]
    
    @staticmethod
    def get_recent(limit=100):
        """获取最近的插件执行日志"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM plugin_exec_log 
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            return [PluginExecLog._from_row(row) for row in rows]
    
    @staticmethod
    def create(execution_id, plugin_id, status, log_content=None, 
               plugin_name=None, duration=None):
        """创建插件执行日志"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO plugin_exec_log 
                (execution_id, plugin_id, plugin_name, status, log_content, duration)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                execution_id,
                plugin_id,
                plugin_name,
                status,
                log_content,
                duration
            ))
            return cursor.lastrowid
    
    @staticmethod
    def delete_by_execution(execution_id):
        """删除执行记录的所有插件日志"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM plugin_exec_log 
                WHERE execution_id = ?
            ''', (execution_id,))
            return cursor.rowcount
    
    @staticmethod
    def delete_by_plugin(plugin_id):
        """删除插件的所有执行日志（级联删除用）"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM plugin_exec_log 
                WHERE plugin_id = ?
            ''', (plugin_id,))
            return cursor.rowcount
    
    @staticmethod
    def delete_before(before_date):
        """删除指定日期之前的日志（清理用）"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM plugin_exec_log 
                WHERE created_at < ?
            ''', (before_date,))
            return cursor.rowcount
    
    @staticmethod
    def count_by_plugin(plugin_id):
        """统计插件的执行日志数量"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM plugin_exec_log 
                WHERE plugin_id = ?
            ''', (plugin_id,))
            return cursor.fetchone()[0]
    
    @staticmethod
    def get_stats_by_plugin(plugin_id):
        """获取插件的执行统计"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as failed_count,
                    AVG(duration) as avg_duration
                FROM plugin_exec_log 
                WHERE plugin_id = ?
            ''', (PluginExecLog.STATUS_SUCCESS, PluginExecLog.STATUS_FAILED, plugin_id))
            row = cursor.fetchone()
            return {
                'total': row[0] or 0,
                'success_count': row[1] or 0,
                'failed_count': row[2] or 0,
                'avg_duration': row[3] or 0
            }
    
    @staticmethod
    def _from_row(row):
        """从数据库行创建对象"""
        return PluginExecLog(
            id=row['id'],
            execution_id=row['execution_id'],
            plugin_id=row['plugin_id'],
            plugin_name=row['plugin_name'],
            status=row['status'],
            log_content=row['log_content'],
            duration=row['duration'],
            created_at=row['created_at']
        )
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'execution_id': self.execution_id,
            'plugin_id': self.plugin_id,
            'plugin_name': self.plugin_name,
            'status': self.status,
            'log_content': self.log_content,
            'duration': self.duration,
            'created_at': self.created_at
        }


# 级联删除辅助函数
def cascade_delete_plugin(plugin_id):
    """
    级联删除插件相关的所有数据
    
    Args:
        plugin_id: 插件ID
        
    Returns:
        dict: 删除统计 {relations: int, logs: int, plugin: bool}
    """
    # 删除任务插件关联
    relations_deleted = TaskPluginRelation.delete_by_plugin(plugin_id)
    
    # 删除执行日志
    logs_deleted = PluginExecLog.delete_by_plugin(plugin_id)
    
    # 删除插件记录
    plugin_deleted = PluginInfo.delete(plugin_id)
    
    return {
        'relations': relations_deleted,
        'logs': logs_deleted,
        'plugin': plugin_deleted
    }

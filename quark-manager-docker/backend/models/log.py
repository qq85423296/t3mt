# -*- coding: utf-8 -*-
"""
日志模型
"""
from database import get_db
from datetime import datetime, timedelta


class Log:
    """日志模型"""
    
    @staticmethod
    def create(task_type, task_name, log_level, log_content, task_id=None,
               execution_time=None, file_count=None, file_size=None, error_message=None):
        """创建日志"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO log_records 
                (task_type, task_id, task_name, log_level, log_content,
                 execution_time, file_count, file_size, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (task_type, task_id, task_name, log_level, log_content,
                  execution_time, file_count, file_size, error_message))
            
            return cursor.lastrowid
    
    @staticmethod
    def get_list(task_type=None, log_level=None, start_date=None, end_date=None,
                 page=1, page_size=20):
        """获取日志列表"""
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 构建查询条件
            conditions = []
            params = []
            
            if task_type and task_type != 'all':
                conditions.append('task_type = ?')
                params.append(task_type)
            
            if log_level and log_level != 'all':
                conditions.append('log_level = ?')
                params.append(log_level)
            
            if start_date:
                conditions.append('date(created_at) >= ?')
                params.append(start_date)
            
            if end_date:
                conditions.append('date(created_at) <= ?')
                params.append(end_date)
            
            where_clause = ' AND '.join(conditions) if conditions else '1=1'
            
            # 查询总数
            cursor.execute(
                f'SELECT COUNT(*) as total FROM log_records WHERE {where_clause}',
                params
            )
            total = cursor.fetchone()['total']
            
            # 查询列表
            offset = (page - 1) * page_size
            params.extend([page_size, offset])
            
            cursor.execute(f'''
                SELECT * FROM log_records 
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', params)
            
            logs = cursor.fetchall()
            
            return {
                'total': total,
                'page': page,
                'page_size': page_size,
                'logs': [dict(log) for log in logs]
            }
    
    @staticmethod
    def clear_all():
        """清空所有日志"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM log_records')
            return cursor.rowcount
    
    @staticmethod
    def auto_clean(retention_days):
        """自动清理过期日志"""
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime('%Y-%m-%d')
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM log_records WHERE date(created_at) < ?',
                (cutoff_date,)
            )
            return cursor.rowcount
    
    @staticmethod
    def get_by_task(task_id, task_type):
        """获取指定任务的日志"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM log_records 
                WHERE task_id = ? AND task_type = ?
                ORDER BY created_at DESC
            ''', (task_id, task_type))
            
            logs = cursor.fetchall()
            return [dict(log) for log in logs]

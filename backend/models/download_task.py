# -*- coding: utf-8 -*-
"""
下载任务模型
"""
from database import get_db
from datetime import datetime


class DownloadTask:
    """下载任务模型"""
    
    @staticmethod
    def get_all():
        """获取所有任务"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.*, a.remark as account_remark
                FROM download_tasks t
                LEFT JOIN quark_accounts a ON t.source_account_id = a.id
                ORDER BY t.created_at DESC
            ''')
            tasks = cursor.fetchall()
            return [dict(task) for task in tasks]
    
    @staticmethod
    def get_by_id(task_id):
        """根据ID获取任务"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.*, a.remark as account_remark, a.cookie
                FROM download_tasks t
                LEFT JOIN quark_accounts a ON t.source_account_id = a.id
                WHERE t.id = ?
            ''', (task_id,))
            task = cursor.fetchone()
            return dict(task) if task else None
    
    @staticmethod
    def get_active_tasks():
        """获取所有活动任务（用于调度）"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.*, a.cookie, a.remark as account_remark
                FROM download_tasks t
                LEFT JOIN quark_accounts a ON t.source_account_id = a.id
                WHERE t.status = 'running'
            ''')
            tasks = cursor.fetchall()
            return [dict(task) for task in tasks]
    
    @staticmethod
    def create(name, source_account_id, source_path, target_path, cron_expression,
               filter_extensions=None, include_extensions=None, only_new_files=1,
               keep_structure=1, delete_after_download=0, exclude_keywords=None):
        """创建任务"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO download_tasks 
                (name, source_account_id, source_path, target_path, cron_expression,
                 filter_extensions, include_extensions, only_new_files,
                 keep_structure, delete_after_download, exclude_keywords)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, source_account_id, source_path, target_path, cron_expression,
                  filter_extensions, include_extensions, only_new_files,
                  keep_structure, delete_after_download, exclude_keywords))
            
            return cursor.lastrowid
    
    @staticmethod
    def update(task_id, **kwargs):
        """更新任务"""
        kwargs['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        fields = ', '.join([f'{k} = ?' for k in kwargs.keys()])
        values = list(kwargs.values()) + [task_id]
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f'UPDATE download_tasks SET {fields} WHERE id = ?',
                values
            )
            return cursor.rowcount > 0
    
    @staticmethod
    def delete(task_id):
        """删除任务"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM download_tasks WHERE id = ?', (task_id,))
            return cursor.rowcount > 0
    
    @staticmethod
    def update_status(task_id, status):
        """更新任务状态"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE download_tasks SET status = ?, updated_at = ? WHERE id = ?',
                (status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), task_id)
            )
            return cursor.rowcount > 0
    
    @staticmethod
    def update_progress(task_id, progress):
        """更新任务进度"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE download_tasks SET progress = ?, updated_at = ? WHERE id = ?',
                (progress, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), task_id)
            )
            return cursor.rowcount > 0
    
    @staticmethod
    def update_execute_time(task_id, last_time=None, next_time=None):
        """更新执行时间"""
        with get_db() as conn:
            cursor = conn.cursor()
            if last_time and next_time:
                cursor.execute('''
                    UPDATE download_tasks 
                    SET last_execute_time = ?, next_execute_time = ?, updated_at = ?
                    WHERE id = ?
                ''', (last_time, next_time, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), task_id))
            elif next_time:
                cursor.execute('''
                    UPDATE download_tasks 
                    SET next_execute_time = ?, updated_at = ?
                    WHERE id = ?
                ''', (next_time, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), task_id))
            return cursor.rowcount > 0

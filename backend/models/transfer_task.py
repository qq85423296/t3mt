# -*- coding: utf-8 -*-
"""
转存任务模型
"""
import json
from database import get_db
from datetime import datetime


class TransferTask:
    """转存任务模型"""
    
    @staticmethod
    def get_all():
        """获取所有任务"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.*, a.remark as account_remark
                FROM transfer_tasks t
                LEFT JOIN quark_accounts a ON t.target_account_id = a.id
                ORDER BY t.created_at DESC
            ''')
            tasks = cursor.fetchall()
            result = []
            for task in tasks:
                task_dict = dict(task)
                # 解析JSON字段
                if task_dict.get('share_urls'):
                    task_dict['share_urls'] = json.loads(task_dict['share_urls'])
                if task_dict.get('rules'):
                    task_dict['rules'] = json.loads(task_dict['rules'])
                result.append(task_dict)
            return result
    
    @staticmethod
    def get_by_id(task_id):
        """根据ID获取任务"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.*, a.remark as account_remark
                FROM transfer_tasks t
                LEFT JOIN quark_accounts a ON t.target_account_id = a.id
                WHERE t.id = ?
            ''', (task_id,))
            task = cursor.fetchone()
            if task:
                task_dict = dict(task)
                if task_dict.get('share_urls'):
                    task_dict['share_urls'] = json.loads(task_dict['share_urls'])
                if task_dict.get('rules'):
                    task_dict['rules'] = json.loads(task_dict['rules'])
                return task_dict
            return None
    
    @staticmethod
    def get_active_tasks():
        """获取所有活动任务（用于调度）"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.*, a.cookie, a.remark as account_remark
                FROM transfer_tasks t
                LEFT JOIN quark_accounts a ON t.target_account_id = a.id
                WHERE t.status = 'running'
                AND (t.end_date IS NULL OR t.end_date >= date('now'))
            ''')
            tasks = cursor.fetchall()
            result = []
            for task in tasks:
                task_dict = dict(task)
                if task_dict.get('share_urls'):
                    task_dict['share_urls'] = json.loads(task_dict['share_urls'])
                if task_dict.get('rules'):
                    task_dict['rules'] = json.loads(task_dict['rules'])
                result.append(task_dict)
            return result
    
    @staticmethod
    def create(name, share_urls, target_account_id, target_path, cron_expression,
               rules=None, filter_extensions=None, include_extensions=None,
               update_dirs=None, overwrite_mode=0, end_date=None,
               regex_pattern=None, replacement_pattern=None, check_mode='replaced'):
        """创建任务"""
        # 序列化JSON字段
        share_urls_json = json.dumps(share_urls, ensure_ascii=False)
        rules_json = json.dumps(rules, ensure_ascii=False) if rules else None
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transfer_tasks 
                (name, share_urls, target_account_id, target_path, cron_expression,
                 rules, filter_extensions, include_extensions, update_dirs,
                 overwrite_mode, end_date, regex_pattern, replacement_pattern, check_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, share_urls_json, target_account_id, target_path, cron_expression,
                  rules_json, filter_extensions, include_extensions, update_dirs,
                  overwrite_mode, end_date, regex_pattern, replacement_pattern, check_mode))
            
            return cursor.lastrowid
    
    @staticmethod
    def update(task_id, **kwargs):
        """更新任务"""
        # 序列化JSON字段
        if 'share_urls' in kwargs:
            kwargs['share_urls'] = json.dumps(kwargs['share_urls'], ensure_ascii=False)
        if 'rules' in kwargs and kwargs['rules']:
            kwargs['rules'] = json.dumps(kwargs['rules'], ensure_ascii=False)
        
        kwargs['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        fields = ', '.join([f'{k} = ?' for k in kwargs.keys()])
        values = list(kwargs.values()) + [task_id]
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f'UPDATE transfer_tasks SET {fields} WHERE id = ?',
                values
            )
            return cursor.rowcount > 0
    
    @staticmethod
    def delete(task_id):
        """删除任务"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM transfer_tasks WHERE id = ?', (task_id,))
            return cursor.rowcount > 0
    
    @staticmethod
    def update_status(task_id, status):
        """更新任务状态"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE transfer_tasks SET status = ?, updated_at = ? WHERE id = ?',
                (status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), task_id)
            )
            return cursor.rowcount > 0
    
    @staticmethod
    def update_execute_time(task_id, last_time=None, next_time=None):
        """更新执行时间"""
        with get_db() as conn:
            cursor = conn.cursor()
            if last_time and next_time:
                cursor.execute('''
                    UPDATE transfer_tasks 
                    SET last_execute_time = ?, next_execute_time = ?, updated_at = ?
                    WHERE id = ?
                ''', (last_time, next_time, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), task_id))
            elif next_time:
                cursor.execute('''
                    UPDATE transfer_tasks 
                    SET next_execute_time = ?, updated_at = ?
                    WHERE id = ?
                ''', (next_time, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), task_id))
            return cursor.rowcount > 0

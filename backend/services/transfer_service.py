# -*- coding: utf-8 -*-
"""
转存任务服务
"""
import json
from datetime import datetime
from database import get_db
from utils.logger import logger


class TransferService:
    """转存任务服务类"""
    
    @staticmethod
    def get_all_tasks():
        """获取所有转存任务"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT t.*, a.remark as account_remark, a.account_name
                    FROM transfer_tasks t
                    LEFT JOIN quark_accounts a ON t.target_account_id = a.id
                    ORDER BY t.created_at DESC
                """)
                tasks = cursor.fetchall()
                
                result = []
                for task in tasks:
                    task_dict = dict(task)
                    # 解析JSON字段
                    if task_dict['share_urls']:
                        task_dict['share_urls'] = json.loads(task_dict['share_urls'])
                    if task_dict['rules']:
                        task_dict['rules'] = json.loads(task_dict['rules'])
                    result.append(task_dict)
                
                return result
        except Exception as e:
            logger.error(f"获取转存任务列表失败: {e}")
            raise
    
    @staticmethod
    def get_task_by_id(task_id):
        """根据ID获取转存任务"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT t.*, a.remark as account_remark
                    FROM transfer_tasks t
                    LEFT JOIN quark_accounts a ON t.target_account_id = a.id
                    WHERE t.id = ?
                """, (task_id,))
                task = cursor.fetchone()
                
                if task:
                    task_dict = dict(task)
                    # 解析JSON字段
                    if task_dict['share_urls']:
                        task_dict['share_urls'] = json.loads(task_dict['share_urls'])
                    if task_dict['rules']:
                        task_dict['rules'] = json.loads(task_dict['rules'])
                    return task_dict
                return None
        except Exception as e:
            logger.error(f"获取转存任务失败: {e}")
            raise
    
    @staticmethod
    def create_task(task_data):
        """创建转存任务"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # 转换JSON字段
                share_urls_json = json.dumps(task_data.get('share_urls', []))
                rules_json = json.dumps(task_data.get('rules', [])) if task_data.get('rules') else None
                
                cursor.execute("""
                    INSERT INTO transfer_tasks (
                        name, share_urls, target_account_id, target_path,
                        save_mode, target_folder_name,
                        rules, filter_extensions, include_extensions,
                        update_dirs, file_start_date, overwrite_mode, end_date,
                        cron_expression, regex_pattern, replacement_pattern, check_mode,
                        status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task_data['name'],
                    share_urls_json,
                    task_data['target_account_id'],
                    task_data['target_path'],
                    task_data.get('save_mode', 'current'),
                    task_data.get('target_folder_name', ''),
                    rules_json,
                    task_data.get('filter_extensions'),
                    task_data.get('include_extensions'),
                    task_data.get('update_dirs'),
                    task_data.get('file_start_date'),
                    task_data.get('overwrite_mode', 0),
                    task_data.get('end_date'),
                    task_data['cron_expression'],
                    task_data.get('regex_pattern'),
                    task_data.get('replacement_pattern'),
                    task_data.get('check_mode', 'replaced'),
                    'running',
                    datetime.now(),
                    datetime.now()
                ))
                
                conn.commit()
                task_id = cursor.lastrowid
                
                logger.info(f"创建转存任务成功: {task_data['name']} (ID: {task_id})")
                return task_id
        except Exception as e:
            logger.error(f"创建转存任务失败: {e}")
            raise
    
    @staticmethod
    def update_task(task_id, task_data):
        """更新转存任务"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # 转换JSON字段
                share_urls_json = json.dumps(task_data.get('share_urls', []))
                rules_json = json.dumps(task_data.get('rules', [])) if task_data.get('rules') else None
                
                cursor.execute("""
                    UPDATE transfer_tasks SET
                        name = ?, share_urls = ?, target_account_id = ?,
                        target_path = ?, save_mode = ?, target_folder_name = ?,
                        rules = ?, filter_extensions = ?,
                        include_extensions = ?, update_dirs = ?,
                        file_start_date = ?, overwrite_mode = ?, end_date = ?,
                        cron_expression = ?, regex_pattern = ?, replacement_pattern = ?,
                        check_mode = ?, updated_at = ?
                    WHERE id = ?
                """, (
                    task_data['name'],
                    share_urls_json,
                    task_data['target_account_id'],
                    task_data['target_path'],
                    task_data.get('save_mode', 'current'),
                    task_data.get('target_folder_name', ''),
                    rules_json,
                    task_data.get('filter_extensions'),
                    task_data.get('include_extensions'),
                    task_data.get('update_dirs'),
                    task_data.get('file_start_date'),
                    task_data.get('overwrite_mode', 0),
                    task_data.get('end_date'),
                    task_data['cron_expression'],
                    task_data.get('regex_pattern'),
                    task_data.get('replacement_pattern'),
                    task_data.get('check_mode', 'replaced'),
                    datetime.now(),
                    task_id
                ))
                
                conn.commit()
                logger.info(f"更新转存任务成功: ID {task_id}")
                return True
        except Exception as e:
            logger.error(f"更新转存任务失败: {e}")
            raise
    
    @staticmethod
    def delete_task(task_id):
        """删除转存任务"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM transfer_tasks WHERE id = ?", (task_id,))
                conn.commit()
                
                logger.info(f"删除转存任务成功: ID {task_id}")
                return True
        except Exception as e:
            logger.error(f"删除转存任务失败: {e}")
            raise
    
    @staticmethod
    def toggle_task_status(task_id):
        """切换任务状态（运行/暂停）"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # 获取当前状态
                cursor.execute("SELECT status FROM transfer_tasks WHERE id = ?", (task_id,))
                result = cursor.fetchone()
                
                if not result:
                    raise ValueError(f"任务不存在: ID {task_id}")
                
                current_status = result['status']
                new_status = 'paused' if current_status == 'running' else 'running'
                
                cursor.execute("""
                    UPDATE transfer_tasks SET status = ?, updated_at = ?
                    WHERE id = ?
                """, (new_status, datetime.now(), task_id))
                
                conn.commit()
                logger.info(f"切换任务状态成功: ID {task_id}, {current_status} -> {new_status}")
                return new_status
        except Exception as e:
            logger.error(f"切换任务状态失败: {e}")
            raise
    
    @staticmethod
    def update_task_status(task_id, status):
        """更新任务状态"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE transfer_tasks SET status = ?, updated_at = ?
                    WHERE id = ?
                """, (status, datetime.now(), task_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")
            raise

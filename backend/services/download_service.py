# -*- coding: utf-8 -*-
"""
下载任务服务
"""
from datetime import datetime
from database import get_db
from utils.logger import logger


class DownloadService:
    """下载任务服务类"""
    
    @staticmethod
    def get_all_tasks():
        """获取所有下载任务"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT d.*, a.remark as account_remark
                    FROM download_tasks d
                    LEFT JOIN quark_accounts a ON d.source_account_id = a.id
                    ORDER BY d.created_at DESC
                """)
                tasks = cursor.fetchall()
                return [dict(task) for task in tasks]
        except Exception as e:
            logger.error(f"获取下载任务列表失败: {e}")
            raise
    
    @staticmethod
    def get_task_by_id(task_id):
        """根据ID获取下载任务"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT d.*, a.remark as account_remark
                    FROM download_tasks d
                    LEFT JOIN quark_accounts a ON d.source_account_id = a.id
                    WHERE d.id = ?
                """, (task_id,))
                task = cursor.fetchone()
                return dict(task) if task else None
        except Exception as e:
            logger.error(f"获取下载任务失败: {e}")
            raise
    
    @staticmethod
    def create_task(task_data):
        """创建下载任务"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO download_tasks (
                        name, source_account_id, source_path, target_path,
                        cron_expression, filter_extensions, include_extensions,
                        only_new_files, keep_structure, delete_after_download,
                        regex_pattern, replacement_pattern,
                        status, progress, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task_data['name'],
                    task_data['source_account_id'],
                    task_data['source_path'],
                    task_data['target_path'],
                    task_data['cron_expression'],
                    task_data.get('filter_extensions'),
                    task_data.get('include_extensions'),
                    task_data.get('only_new_files', 1),
                    task_data.get('keep_structure', 1),
                    task_data.get('delete_after_download', 0),
                    task_data.get('regex_pattern'),
                    task_data.get('replacement_pattern'),
                    'running',
                    0,
                    datetime.now(),
                    datetime.now()
                ))
                
                conn.commit()
                task_id = cursor.lastrowid
                
                logger.info(f"创建下载任务成功: {task_data['name']} (ID: {task_id})")
                return task_id
        except Exception as e:
            logger.error(f"创建下载任务失败: {e}")
            raise
    
    @staticmethod
    def update_task(task_id, task_data):
        """更新下载任务"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE download_tasks SET
                        name = ?, source_account_id = ?, source_path = ?,
                        target_path = ?, cron_expression = ?,
                        filter_extensions = ?, include_extensions = ?,
                        only_new_files = ?, keep_structure = ?,
                        delete_after_download = ?,
                        regex_pattern = ?, replacement_pattern = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    task_data['name'],
                    task_data['source_account_id'],
                    task_data['source_path'],
                    task_data['target_path'],
                    task_data['cron_expression'],
                    task_data.get('filter_extensions'),
                    task_data.get('include_extensions'),
                    task_data.get('only_new_files', 1),
                    task_data.get('keep_structure', 1),
                    task_data.get('delete_after_download', 0),
                    task_data.get('regex_pattern'),
                    task_data.get('replacement_pattern'),
                    datetime.now(),
                    task_id
                ))
                
                conn.commit()
                logger.info(f"更新下载任务成功: ID {task_id}")
                return True
        except Exception as e:
            logger.error(f"更新下载任务失败: {e}")
            raise
    
    @staticmethod
    def delete_task(task_id):
        """删除下载任务"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM download_tasks WHERE id = ?", (task_id,))
                conn.commit()
                
                logger.info(f"删除下载任务成功: ID {task_id}")
                return True
        except Exception as e:
            logger.error(f"删除下载任务失败: {e}")
            raise
    
    @staticmethod
    def toggle_task_status(task_id):
        """切换任务状态（运行/暂停）"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # 获取当前状态
                cursor.execute("SELECT status FROM download_tasks WHERE id = ?", (task_id,))
                result = cursor.fetchone()
                
                if not result:
                    raise ValueError(f"任务不存在: ID {task_id}")
                
                current_status = result['status']
                new_status = 'paused' if current_status == 'running' else 'running'
                
                cursor.execute("""
                    UPDATE download_tasks SET status = ?, updated_at = ?
                    WHERE id = ?
                """, (new_status, datetime.now(), task_id))
                
                conn.commit()
                logger.info(f"切换任务状态成功: ID {task_id}, {current_status} -> {new_status}")
                return new_status
        except Exception as e:
            logger.error(f"切换任务状态失败: {e}")
            raise
    
    @staticmethod
    def update_progress(task_id, progress):
        """更新任务进度"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE download_tasks SET progress = ?, updated_at = ?
                    WHERE id = ?
                """, (progress, datetime.now(), task_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"更新任务进度失败: {e}")
            raise
    
    @staticmethod
    def update_execute_time(task_id, last_time=None, next_time=None):
        """更新任务执行时间"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                if last_time and next_time:
                    cursor.execute("""
                        UPDATE download_tasks 
                        SET last_execute_time = ?, next_execute_time = ?, updated_at = ?
                        WHERE id = ?
                    """, (last_time, next_time, datetime.now(), task_id))
                elif last_time:
                    cursor.execute("""
                        UPDATE download_tasks 
                        SET last_execute_time = ?, updated_at = ?
                        WHERE id = ?
                    """, (last_time, datetime.now(), task_id))
                elif next_time:
                    cursor.execute("""
                        UPDATE download_tasks 
                        SET next_execute_time = ?, updated_at = ?
                        WHERE id = ?
                    """, (next_time, datetime.now(), task_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"更新任务执行时间失败: {e}")
            raise

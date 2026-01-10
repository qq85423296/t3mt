# -*- coding: utf-8 -*-
"""
剧集失败记录模型
"""
from datetime import datetime
from database import get_db


class EpisodeFailureRecord:
    """剧集失败记录"""
    
    def __init__(self, record_id=None, task_id=None, episode_url=None, 
                 episode_name=None, failure_count=1, last_failure_time=None,
                 last_failure_reason=None, created_at=None, updated_at=None):
        self.id = record_id
        self.task_id = task_id
        self.episode_url = episode_url
        self.episode_name = episode_name
        self.failure_count = failure_count
        self.last_failure_time = last_failure_time
        self.last_failure_reason = last_failure_reason
        self.created_at = created_at
        self.updated_at = updated_at
    
    @staticmethod
    def create(task_id, episode_url, episode_name, failure_reason):
        """创建失败记录
        
        Args:
            task_id: 任务ID
            episode_url: 剧集URL
            episode_name: 剧集名称
            failure_reason: 失败原因
            
        Returns:
            记录ID
        """
        with get_db() as conn:
            cursor = conn.cursor()
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT INTO episode_failure_records 
                (task_id, episode_url, episode_name, failure_count, 
                 last_failure_time, last_failure_reason)
                VALUES (?, ?, ?, 1, ?, ?)
            ''', (task_id, episode_url, episode_name, now, failure_reason))
            
            return cursor.lastrowid
    
    @staticmethod
    def get_by_task_and_url(task_id, episode_url):
        """根据任务ID和剧集URL获取失败记录
        
        Args:
            task_id: 任务ID
            episode_url: 剧集URL
            
        Returns:
            EpisodeFailureRecord对象或None
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM episode_failure_records 
                WHERE task_id = ? AND episode_url = ?
            ''', (task_id, episode_url))
            
            row = cursor.fetchone()
            if row:
                return EpisodeFailureRecord._from_row(row)
            return None
    
    @staticmethod
    def update_failure_count(task_id, episode_url, episode_name, failure_reason):
        """更新失败次数
        
        如果记录不存在则创建，如果存在则增加失败次数
        
        Args:
            task_id: 任务ID
            episode_url: 剧集URL
            episode_name: 剧集名称
            failure_reason: 失败原因
            
        Returns:
            更新后的失败次数
        """
        with get_db() as conn:
            cursor = conn.cursor()
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 尝试更新现有记录
            cursor.execute('''
                UPDATE episode_failure_records 
                SET failure_count = failure_count + 1,
                    last_failure_time = ?,
                    last_failure_reason = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE task_id = ? AND episode_url = ?
            ''', (now, failure_reason, task_id, episode_url))
            
            if cursor.rowcount == 0:
                # 记录不存在，创建新记录
                cursor.execute('''
                    INSERT INTO episode_failure_records 
                    (task_id, episode_url, episode_name, failure_count, 
                     last_failure_time, last_failure_reason)
                    VALUES (?, ?, ?, 1, ?, ?)
                ''', (task_id, episode_url, episode_name, now, failure_reason))
                return 1
            else:
                # 获取更新后的失败次数
                cursor.execute('''
                    SELECT failure_count FROM episode_failure_records 
                    WHERE task_id = ? AND episode_url = ?
                ''', (task_id, episode_url))
                row = cursor.fetchone()
                return row['failure_count'] if row else 1
    
    @staticmethod
    def delete(task_id, episode_url):
        """删除失败记录
        
        Args:
            task_id: 任务ID
            episode_url: 剧集URL
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM episode_failure_records 
                WHERE task_id = ? AND episode_url = ?
            ''', (task_id, episode_url))
    
    @staticmethod
    def delete_by_task(task_id):
        """删除任务的所有失败记录
        
        Args:
            task_id: 任务ID
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM episode_failure_records 
                WHERE task_id = ?
            ''', (task_id,))
    
    @staticmethod
    def get_failed_episodes(task_id, max_retry_count=None):
        """获取任务的失败剧集列表
        
        Args:
            task_id: 任务ID
            max_retry_count: 最大重试次数，如果提供则只返回未达上限的剧集
            
        Returns:
            失败记录列表
        """
        with get_db() as conn:
            cursor = conn.cursor()
            
            if max_retry_count is not None:
                # 只返回未达最大重试次数的剧集
                cursor.execute('''
                    SELECT * FROM episode_failure_records 
                    WHERE task_id = ? AND failure_count < ?
                    ORDER BY last_failure_time ASC
                ''', (task_id, max_retry_count))
            else:
                # 返回所有失败剧集
                cursor.execute('''
                    SELECT * FROM episode_failure_records 
                    WHERE task_id = ?
                    ORDER BY last_failure_time ASC
                ''', (task_id,))
            
            rows = cursor.fetchall()
            return [EpisodeFailureRecord._from_row(row) for row in rows]
    
    @staticmethod
    def get_all_by_task(task_id):
        """获取任务的所有失败记录（包括已达上限的）
        
        Args:
            task_id: 任务ID
            
        Returns:
            失败记录列表
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM episode_failure_records 
                WHERE task_id = ?
                ORDER BY failure_count DESC, last_failure_time DESC
            ''', (task_id,))
            
            rows = cursor.fetchall()
            return [EpisodeFailureRecord._from_row(row) for row in rows]
    
    @staticmethod
    def _from_row(row):
        """从数据库行创建对象"""
        return EpisodeFailureRecord(
            record_id=row['id'],
            task_id=row['task_id'],
            episode_url=row['episode_url'],
            episode_name=row['episode_name'],
            failure_count=row['failure_count'],
            last_failure_time=row['last_failure_time'],
            last_failure_reason=row['last_failure_reason'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'episode_url': self.episode_url,
            'episode_name': self.episode_name,
            'failure_count': self.failure_count,
            'last_failure_time': self.last_failure_time,
            'last_failure_reason': self.last_failure_reason,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

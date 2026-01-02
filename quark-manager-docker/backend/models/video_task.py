# -*- coding: utf-8 -*-
"""
影视下载任务模型
"""
import json
from datetime import datetime
from database import get_db


class VideoTask:
    """影视下载任务"""
    
    def __init__(self, task_id=None, name=None, website_url=None, video_id=None, 
                 clip_id=None, save_directory=None, cron_expression=None,
                 episodes=None, video_info=None, status='waiting', progress=0,
                 downloaded_episodes=0, create_subfolder=0, platform='mango',
                 video_type='电视剧', created_at=None, updated_at=None):
        self.id = task_id
        self.name = name
        self.website_url = website_url
        self.video_id = video_id
        self.clip_id = clip_id
        self.save_directory = save_directory
        self.cron_expression = cron_expression
        self.episodes = episodes or []
        self.video_info = video_info or {}
        self.status = status
        self.progress = progress
        self.downloaded_episodes = downloaded_episodes
        self.create_subfolder = create_subfolder
        self.platform = platform  # 视频平台：mango（芒果TV）、tencent（腾讯视频）
        self.video_type = video_type  # 影视类型：电视剧、电影、综艺、动漫、其他
        self.created_at = created_at
        self.updated_at = updated_at
    
    @staticmethod
    def create(name, website_url, video_id, clip_id, save_directory, 
               cron_expression, episodes, video_info, create_subfolder=0, 
               selected_episodes=None, platform='mango', video_type='电视剧'):
        """创建任务"""
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 如果没有提供selected_episodes，默认选择所有剧集
            if selected_episodes is None:
                selected_episodes = list(range(len(episodes)))
            
            cursor.execute('''
                INSERT INTO video_tasks 
                (name, website_url, video_id, clip_id, save_directory, 
                 cron_expression, episodes_json, video_info_json, status, 
                 progress, downloaded_episodes, create_subfolder, 
                 selected_episodes, last_downloaded_episode, platform, video_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'waiting', 0, 0, ?, ?, 0, ?, ?)
            ''', (
                name, website_url, video_id, clip_id, save_directory,
                cron_expression, 
                json.dumps(episodes, ensure_ascii=False),
                json.dumps(video_info, ensure_ascii=False),
                create_subfolder,
                json.dumps(selected_episodes, ensure_ascii=False),  # 保存选中的剧集索引
                platform,
                video_type
            ))
            return cursor.lastrowid
    
    @staticmethod
    def get_by_id(task_id):
        """根据ID获取任务"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM video_tasks WHERE id = ?', (task_id,))
            row = cursor.fetchone()
            
            if row:
                return VideoTask._from_row(row)
            return None
    
    @staticmethod
    def get_all():
        """获取所有任务"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM video_tasks ORDER BY created_at DESC')
            rows = cursor.fetchall()
            return [VideoTask._from_row(row) for row in rows]
    
    @staticmethod
    def update(task_id, **kwargs):
        """更新任务"""
        allowed_fields = [
            'name', 'website_url', 'video_id', 'clip_id', 'save_directory',
            'cron_expression', 'episodes_json', 'video_info_json', 'status',
            'progress', 'downloaded_episodes', 'create_subfolder',
            'selected_episodes', 'last_downloaded_episode', 'platform', 'video_type'
        ]
        
        # 处理episodes和video_info的JSON序列化
        if 'episodes' in kwargs:
            episodes = kwargs.pop('episodes')
            kwargs['episodes_json'] = json.dumps(episodes, ensure_ascii=False)
        if 'video_info' in kwargs:
            kwargs['video_info_json'] = json.dumps(kwargs.pop('video_info'), ensure_ascii=False)
        if 'selected_episodes' in kwargs:
            # selected_episodes应该是索引列表，直接序列化
            kwargs['selected_episodes'] = json.dumps(kwargs['selected_episodes'], ensure_ascii=False)
        
        # 过滤允许的字段
        update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not update_fields:
            return
        
        # 构建SQL
        set_clause = ', '.join([f'{k} = ?' for k in update_fields.keys()])
        values = list(update_fields.values())
        values.append(task_id)
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE video_tasks 
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', values)
    
    @staticmethod
    def delete(task_id):
        """删除任务"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM video_tasks WHERE id = ?', (task_id,))
    
    @staticmethod
    def _from_row(row):
        """从数据库行创建对象"""
        episodes = []
        video_info = {}
        selected_episodes = []
        
        if row['episodes_json']:
            try:
                episodes = json.loads(row['episodes_json'])
            except:
                pass
        
        if row['video_info_json']:
            try:
                video_info = json.loads(row['video_info_json'])
            except:
                pass
        
        # 解析selected_episodes字段
        if 'selected_episodes' in row.keys() and row['selected_episodes']:
            try:
                selected_episodes = json.loads(row['selected_episodes'])
            except:
                pass
        
        # 创建任务对象
        task = VideoTask(
            task_id=row['id'],
            name=row['name'],
            website_url=row['website_url'],
            video_id=row['video_id'],
            clip_id=row['clip_id'],
            save_directory=row['save_directory'],
            cron_expression=row['cron_expression'],
            episodes=episodes,
            video_info=video_info,
            status=row['status'],
            progress=row['progress'],
            downloaded_episodes=row['downloaded_episodes'],
            create_subfolder=row['create_subfolder'] if 'create_subfolder' in row.keys() else 0,
            platform=row['platform'] if 'platform' in row.keys() else 'mango',
            video_type=row['video_type'] if 'video_type' in row.keys() else '电视剧',
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
        # 添加额外字段
        task.selected_episodes = selected_episodes
        task.last_downloaded_episode = row['last_downloaded_episode'] if 'last_downloaded_episode' in row.keys() else 0
        return task
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'website_url': self.website_url,
            'video_id': self.video_id,
            'clip_id': self.clip_id,
            'save_directory': self.save_directory,
            'cron_expression': self.cron_expression,
            'episodes': self.episodes,
            'video_info': self.video_info,
            'status': self.status,
            'progress': self.progress,
            'downloaded_episodes': self.downloaded_episodes,
            'create_subfolder': self.create_subfolder,
            'platform': self.platform,
            'video_type': self.video_type,
            'selected_episodes': getattr(self, 'selected_episodes', []),
            'last_downloaded_episode': getattr(self, 'last_downloaded_episode', 0),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


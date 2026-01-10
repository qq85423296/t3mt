# -*- coding: utf-8 -*-
"""
数据库迁移脚本: 添加文件大小限制和失败重试配置

迁移内容:
1. 为video_tasks表添加5个新字段:
   - enable_file_size_check: 是否启用文件大小检查 (0=禁用, 1=启用)
   - min_file_size: 最小文件大小(MB)
   - enable_retry: 是否启用失败重试 (0=禁用, 1=启用)
   - max_retry_count: 最大重试次数(1-10)
   - retry_interval: 重试间隔(分钟)

2. 创建episode_failure_records表用于记录剧集失败信息
"""
from database import get_db


def upgrade():
    """升级数据库"""
    print("开始执行数据库迁移: 添加文件大小限制和失败重试配置...")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 检查video_tasks表的现有字段
        cursor.execute("PRAGMA table_info(video_tasks)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        # 添加新字段到video_tasks表
        new_fields = {
            'enable_file_size_check': 'INTEGER DEFAULT 0',
            'min_file_size': 'INTEGER DEFAULT 100',
            'enable_retry': 'INTEGER DEFAULT 0',
            'max_retry_count': 'INTEGER DEFAULT 3',
            'retry_interval': 'INTEGER DEFAULT 5'
        }
        
        for field_name, field_type in new_fields.items():
            if field_name not in existing_columns:
                print(f"  添加字段: {field_name}")
                cursor.execute(f'''
                    ALTER TABLE video_tasks 
                    ADD COLUMN {field_name} {field_type}
                ''')
            else:
                print(f"  字段已存在: {field_name}")
        
        # 创建episode_failure_records表
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='episode_failure_records'
        """)
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            print("  创建表: episode_failure_records")
            cursor.execute('''
                CREATE TABLE episode_failure_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    episode_url TEXT NOT NULL,
                    episode_name TEXT NOT NULL,
                    failure_count INTEGER DEFAULT 1,
                    last_failure_time TEXT NOT NULL,
                    last_failure_reason TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(task_id, episode_url),
                    FOREIGN KEY (task_id) REFERENCES video_tasks(id) ON DELETE CASCADE
                )
            ''')
            
            # 创建索引
            print("  创建索引: idx_episode_failure_task")
            cursor.execute('''
                CREATE INDEX idx_episode_failure_task 
                ON episode_failure_records(task_id)
            ''')
            
            print("  创建索引: idx_episode_failure_url")
            cursor.execute('''
                CREATE INDEX idx_episode_failure_url 
                ON episode_failure_records(episode_url)
            ''')
        else:
            print("  表已存在: episode_failure_records")
        
        conn.commit()
    
    print("✅ 数据库迁移完成!")


def downgrade():
    """降级数据库
    
    注意: SQLite不支持DROP COLUMN，因此降级操作需要重建表
    这里提供简化的降级方案，仅删除episode_failure_records表
    """
    print("开始执行数据库降级...")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 删除episode_failure_records表
        cursor.execute("DROP TABLE IF EXISTS episode_failure_records")
        print("  删除表: episode_failure_records")
        
        # 注意: 由于SQLite限制，无法直接删除video_tasks表的字段
        # 如需完全回滚，需要备份数据后重建表
        print("  警告: video_tasks表的新增字段无法自动删除")
        print("  如需完全回滚，请手动备份数据后重建表")
        
        conn.commit()
    
    print("✅ 数据库降级完成!")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'downgrade':
        downgrade()
    else:
        upgrade()

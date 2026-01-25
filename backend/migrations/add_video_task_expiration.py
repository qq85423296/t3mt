# -*- coding: utf-8 -*-
"""
数据库迁移脚本: 添加影视任务自动失效功能

迁移内容:
1. 为video_tasks表添加last_episode_update_time字段
2. 为现有记录初始化该字段为created_at值
3. 在system_config表中插入默认配置项
4. 创建索引优化查询性能
"""
from database import get_db


def upgrade():
    """升级数据库"""
    print("开始执行数据库迁移: 添加影视任务自动失效功能...")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. 检查video_tasks表的现有字段
        cursor.execute("PRAGMA table_info(video_tasks)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        # 2. 添加last_episode_update_time字段
        if 'last_episode_update_time' not in existing_columns:
            print("  添加字段: last_episode_update_time")
            cursor.execute('''
                ALTER TABLE video_tasks 
                ADD COLUMN last_episode_update_time TEXT
            ''')
            
            # 3. 为现有记录初始化该字段为created_at值
            print("  初始化现有记录的last_episode_update_time字段...")
            cursor.execute('''
                UPDATE video_tasks 
                SET last_episode_update_time = created_at 
                WHERE last_episode_update_time IS NULL
            ''')
            updated_count = cursor.rowcount
            print(f"  已初始化 {updated_count} 条记录")
        else:
            print("  字段已存在: last_episode_update_time")
        
        # 4. 创建索引优化查询性能
        # 检查索引是否已存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_video_tasks_last_update'
        """)
        index_exists = cursor.fetchone() is not None
        
        if not index_exists:
            print("  创建索引: idx_video_tasks_last_update")
            cursor.execute('''
                CREATE INDEX idx_video_tasks_last_update 
                ON video_tasks(last_episode_update_time, status)
            ''')
        else:
            print("  索引已存在: idx_video_tasks_last_update")
        
        # 5. 插入默认配置项到system_config表
        print("  插入默认配置项...")
        
        # 检查配置是否已存在
        cursor.execute("""
            SELECT config_key FROM system_config 
            WHERE config_key IN ('video_auto_expiration_enabled', 'video_auto_expiration_days')
        """)
        existing_configs = [row[0] for row in cursor.fetchall()]
        
        # 插入启用开关配置
        if 'video_auto_expiration_enabled' not in existing_configs:
            cursor.execute('''
                INSERT INTO system_config 
                (config_key, config_value, config_type, description)
                VALUES ('video_auto_expiration_enabled', '1', 'video', '影视任务自动失效功能启用开关')
            ''')
            print("  已插入配置: video_auto_expiration_enabled")
        else:
            print("  配置已存在: video_auto_expiration_enabled")
        
        # 插入超时天数配置
        if 'video_auto_expiration_days' not in existing_configs:
            cursor.execute('''
                INSERT INTO system_config 
                (config_key, config_value, config_type, description)
                VALUES ('video_auto_expiration_days', '7', 'video', '影视任务自动失效超时天数')
            ''')
            print("  已插入配置: video_auto_expiration_days")
        else:
            print("  配置已存在: video_auto_expiration_days")
        
        conn.commit()
    
    print("✅ 数据库迁移完成!")


def downgrade():
    """降级数据库
    
    注意: SQLite不支持DROP COLUMN，因此降级操作仅删除配置项和索引
    """
    print("开始执行数据库降级...")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 删除配置项
        cursor.execute("""
            DELETE FROM system_config 
            WHERE config_key IN ('video_auto_expiration_enabled', 'video_auto_expiration_days')
        """)
        print("  删除配置项: video_auto_expiration_enabled, video_auto_expiration_days")
        
        # 删除索引
        cursor.execute("DROP INDEX IF EXISTS idx_video_tasks_last_update")
        print("  删除索引: idx_video_tasks_last_update")
        
        # 注意: 由于SQLite限制，无法直接删除video_tasks表的字段
        print("  警告: video_tasks表的last_episode_update_time字段无法自动删除")
        print("  如需完全回滚，请手动备份数据后重建表")
        
        conn.commit()
    
    print("✅ 数据库降级完成!")


def get_migration_info():
    """返回迁移信息"""
    return {
        'version': '20260124_001',
        'description': '添加影视任务自动失效功能(last_episode_update_time字段和配置项)',
        'author': 'system',
        'date': '2026-01-24'
    }


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'downgrade':
        downgrade()
    else:
        upgrade()

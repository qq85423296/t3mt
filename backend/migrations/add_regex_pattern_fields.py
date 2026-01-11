# -*- coding: utf-8 -*-
"""
数据库迁移：添加正则替换字段

为 transfer_tasks、download_tasks、video_tasks 表添加正则替换相关字段
"""
import os
import sys
import sqlite3

# 添加父目录到路径以便导入config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


def get_table_columns(cursor, table_name):
    """获取表的所有列名"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def upgrade():
    """执行迁移：添加正则替换字段"""
    db_path = Config.DATABASE_PATH
    
    if not os.path.exists(db_path):
        print("数据库文件不存在，跳过迁移")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. 为 transfer_tasks 表添加字段
        columns = get_table_columns(cursor, 'transfer_tasks')
        
        if 'regex_pattern' not in columns:
            cursor.execute("ALTER TABLE transfer_tasks ADD COLUMN regex_pattern TEXT")
            print("  ✅ transfer_tasks 表已添加 regex_pattern 字段")
        
        if 'replacement_pattern' not in columns:
            cursor.execute("ALTER TABLE transfer_tasks ADD COLUMN replacement_pattern TEXT")
            print("  ✅ transfer_tasks 表已添加 replacement_pattern 字段")
        
        if 'check_mode' not in columns:
            cursor.execute("ALTER TABLE transfer_tasks ADD COLUMN check_mode VARCHAR(20) DEFAULT 'replaced'")
            print("  ✅ transfer_tasks 表已添加 check_mode 字段")
        
        # 2. 为 download_tasks 表添加字段
        columns = get_table_columns(cursor, 'download_tasks')
        
        if 'regex_pattern' not in columns:
            cursor.execute("ALTER TABLE download_tasks ADD COLUMN regex_pattern TEXT")
            print("  ✅ download_tasks 表已添加 regex_pattern 字段")
        
        if 'replacement_pattern' not in columns:
            cursor.execute("ALTER TABLE download_tasks ADD COLUMN replacement_pattern TEXT")
            print("  ✅ download_tasks 表已添加 replacement_pattern 字段")
        
        # 3. 为 video_tasks 表添加字段
        columns = get_table_columns(cursor, 'video_tasks')
        
        if 'regex_pattern' not in columns:
            cursor.execute("ALTER TABLE video_tasks ADD COLUMN regex_pattern TEXT")
            print("  ✅ video_tasks 表已添加 regex_pattern 字段")
        
        if 'replacement_pattern' not in columns:
            cursor.execute("ALTER TABLE video_tasks ADD COLUMN replacement_pattern TEXT")
            print("  ✅ video_tasks 表已添加 replacement_pattern 字段")
        
        conn.commit()
        print("✅ 正则替换字段迁移完成")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 迁移失败: {str(e)}")
        raise
    finally:
        conn.close()


def downgrade():
    """回滚迁移（SQLite不支持删除列，此处仅作占位）"""
    print("⚠️ SQLite不支持删除列，无法回滚此迁移")


if __name__ == '__main__':
    upgrade()

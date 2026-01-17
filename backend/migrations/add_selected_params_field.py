# -*- coding: utf-8 -*-
"""
数据库迁移：为 task_plugin_relation 表添加 selected_params 字段

用于存储任务传递给插件的参数选择
"""
import os
import sys
import sqlite3

# 添加父目录到路径以便导入config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


def column_exists(cursor, table_name, column_name):
    """检查列是否存在"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def upgrade():
    """执行迁移：添加 selected_params 字段"""
    db_path = Config.DATABASE_PATH
    
    if not os.path.exists(db_path):
        print("数据库文件不存在，跳过迁移")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查 task_plugin_relation 表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='task_plugin_relation'
        """)
        if not cursor.fetchone():
            print("  ⏭️ task_plugin_relation 表不存在，跳过迁移")
            return
        
        # 添加 selected_params 字段
        if not column_exists(cursor, 'task_plugin_relation', 'selected_params'):
            cursor.execute('''
                ALTER TABLE task_plugin_relation 
                ADD COLUMN selected_params TEXT
            ''')
            print("  ✅ 已添加 selected_params 字段")
        else:
            print("  ⏭️ selected_params 字段已存在，跳过")
        
        conn.commit()
        print("✅ selected_params 字段迁移完成")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 迁移失败: {str(e)}")
        raise
    finally:
        conn.close()


def downgrade():
    """回滚迁移：SQLite 不支持删除列，需要重建表"""
    print("⚠️ SQLite 不支持直接删除列，如需回滚请手动处理")


if __name__ == '__main__':
    upgrade()

# -*- coding: utf-8 -*-
"""
数据库迁移：添加插件系统相关表

创建 plugin_info、task_plugin_relation、plugin_exec_log 三张表
"""
import os
import sys
import sqlite3

# 添加父目录到路径以便导入config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


def get_table_exists(cursor, table_name):
    """检查表是否存在"""
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?
    """, (table_name,))
    return cursor.fetchone() is not None


def upgrade():
    """执行迁移：创建插件系统相关表"""
    db_path = Config.DATABASE_PATH
    
    if not os.path.exists(db_path):
        print("数据库文件不存在，跳过迁移")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. 创建 plugin_info 表（插件基本信息和配置）
        if not get_table_exists(cursor, 'plugin_info'):
            cursor.execute('''
                CREATE TABLE plugin_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plugin_id VARCHAR(50) NOT NULL UNIQUE,
                    plugin_name VARCHAR(100) NOT NULL,
                    plugin_version VARCHAR(20) NOT NULL,
                    plugin_author VARCHAR(50),
                    plugin_desc TEXT,
                    status VARCHAR(20) DEFAULT 'installed',
                    config TEXT,
                    meta_json TEXT NOT NULL,
                    install_path VARCHAR(200),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            print("  ✅ 已创建 plugin_info 表")
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX idx_plugin_status ON plugin_info(status)
            ''')
            cursor.execute('''
                CREATE INDEX idx_plugin_id ON plugin_info(plugin_id)
            ''')
            print("  ✅ 已创建 plugin_info 表索引")
        else:
            print("  ⏭️ plugin_info 表已存在，跳过创建")
        
        # 2. 创建 task_plugin_relation 表（任务与插件的关联关系）
        if not get_table_exists(cursor, 'task_plugin_relation'):
            cursor.execute('''
                CREATE TABLE task_plugin_relation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    task_type VARCHAR(20) NOT NULL,
                    plugin_id VARCHAR(50) NOT NULL,
                    sort_order INTEGER DEFAULT 0,
                    pass_task_param TINYINT DEFAULT 1,
                    delay_seconds INTEGER DEFAULT 0,
                    plugin_config TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(task_id, task_type, plugin_id)
                )
            ''')
            print("  ✅ 已创建 task_plugin_relation 表")
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX idx_task_plugin ON task_plugin_relation(task_id, task_type)
            ''')
            cursor.execute('''
                CREATE INDEX idx_relation_plugin_id ON task_plugin_relation(plugin_id)
            ''')
            print("  ✅ 已创建 task_plugin_relation 表索引")
        else:
            print("  ⏭️ task_plugin_relation 表已存在，跳过创建")
        
        # 3. 创建 plugin_exec_log 表（插件执行日志）
        if not get_table_exists(cursor, 'plugin_exec_log'):
            cursor.execute('''
                CREATE TABLE plugin_exec_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id INTEGER NOT NULL,
                    plugin_id VARCHAR(50) NOT NULL,
                    plugin_name VARCHAR(100),
                    status VARCHAR(20) NOT NULL,
                    log_content TEXT,
                    duration INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            print("  ✅ 已创建 plugin_exec_log 表")
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX idx_plugin_exec ON plugin_exec_log(execution_id)
            ''')
            cursor.execute('''
                CREATE INDEX idx_plugin_exec_time ON plugin_exec_log(created_at)
            ''')
            cursor.execute('''
                CREATE INDEX idx_exec_log_plugin_id ON plugin_exec_log(plugin_id)
            ''')
            print("  ✅ 已创建 plugin_exec_log 表索引")
        else:
            print("  ⏭️ plugin_exec_log 表已存在，跳过创建")
        
        conn.commit()
        print("✅ 插件系统表迁移完成")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 迁移失败: {str(e)}")
        raise
    finally:
        conn.close()


def downgrade():
    """回滚迁移：删除插件系统相关表"""
    db_path = Config.DATABASE_PATH
    
    if not os.path.exists(db_path):
        print("数据库文件不存在，跳过回滚")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 按依赖顺序删除表
        cursor.execute("DROP TABLE IF EXISTS plugin_exec_log")
        print("  ✅ 已删除 plugin_exec_log 表")
        
        cursor.execute("DROP TABLE IF EXISTS task_plugin_relation")
        print("  ✅ 已删除 task_plugin_relation 表")
        
        cursor.execute("DROP TABLE IF EXISTS plugin_info")
        print("  ✅ 已删除 plugin_info 表")
        
        conn.commit()
        print("✅ 插件系统表回滚完成")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 回滚失败: {str(e)}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    upgrade()

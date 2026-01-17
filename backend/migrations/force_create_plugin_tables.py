# -*- coding: utf-8 -*-
"""
强制创建插件表的迁移脚本

用于修复已有数据库缺少插件表的问题
可以在容器中直接执行：python migrations/force_create_plugin_tables.py
"""
import os
import sys

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from database import get_db
from utils.logger import logger


def check_and_create_plugin_tables():
    """检查并创建插件表"""
    db_path = Config.DATABASE_PATH
    
    logger.info("=" * 80)
    logger.info("开始检查并创建插件表...")
    logger.info(f"数据库路径: {db_path}")
    logger.info("=" * 80)
    
    if not os.path.exists(db_path):
        logger.error("数据库文件不存在！")
        return False
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 检查表是否存在
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('plugin_info', 'task_plugin_relation', 'plugin_exec_log')
            """)
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            logger.info(f"已存在的插件表: {existing_tables}")
            
            # 1. 创建 plugin_info 表
            if 'plugin_info' not in existing_tables:
                logger.info("创建 plugin_info 表...")
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
                
                cursor.execute('''
                    CREATE INDEX idx_plugin_status ON plugin_info(status)
                ''')
                cursor.execute('''
                    CREATE INDEX idx_plugin_id ON plugin_info(plugin_id)
                ''')
                logger.info("✅ plugin_info 表创建成功")
            else:
                logger.info("⏭️ plugin_info 表已存在")
            
            # 2. 创建 task_plugin_relation 表
            if 'task_plugin_relation' not in existing_tables:
                logger.info("创建 task_plugin_relation 表...")
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
                
                cursor.execute('''
                    CREATE INDEX idx_task_plugin ON task_plugin_relation(task_id, task_type)
                ''')
                cursor.execute('''
                    CREATE INDEX idx_relation_plugin_id ON task_plugin_relation(plugin_id)
                ''')
                logger.info("✅ task_plugin_relation 表创建成功")
            else:
                logger.info("⏭️ task_plugin_relation 表已存在")
            
            # 3. 创建 plugin_exec_log 表
            if 'plugin_exec_log' not in existing_tables:
                logger.info("创建 plugin_exec_log 表...")
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
                
                cursor.execute('''
                    CREATE INDEX idx_plugin_exec ON plugin_exec_log(execution_id)
                ''')
                cursor.execute('''
                    CREATE INDEX idx_plugin_exec_time ON plugin_exec_log(created_at)
                ''')
                cursor.execute('''
                    CREATE INDEX idx_exec_log_plugin_id ON plugin_exec_log(plugin_id)
                ''')
                logger.info("✅ plugin_exec_log 表创建成功")
            else:
                logger.info("⏭️ plugin_exec_log 表已存在")
            
            # 4. 检查 selected_params 字段
            cursor.execute("PRAGMA table_info(task_plugin_relation)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'selected_params' not in columns:
                logger.info("添加 selected_params 字段...")
                cursor.execute('''
                    ALTER TABLE task_plugin_relation 
                    ADD COLUMN selected_params TEXT
                ''')
                logger.info("✅ selected_params 字段添加成功")
            else:
                logger.info("⏭️ selected_params 字段已存在")
            
            conn.commit()
            
            # 记录迁移
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration_name VARCHAR(255) NOT NULL UNIQUE,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                INSERT OR IGNORE INTO schema_migrations (migration_name) 
                VALUES ('add_plugin_tables'), ('add_selected_params_field')
            """)
            
            conn.commit()
            
            logger.info("=" * 80)
            logger.info("✅ 插件表创建完成！")
            logger.info("=" * 80)
            return True
            
    except Exception as e:
        logger.error(f"❌ 创建插件表失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = check_and_create_plugin_tables()
    sys.exit(0 if success else 1)

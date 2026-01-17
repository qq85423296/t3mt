# -*- coding: utf-8 -*-
"""
强制执行插件系统表迁移

用于手动修复迁移问题
"""
import os
import sys

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from database import get_db


def force_migrate():
    """强制执行插件表迁移"""
    print("=" * 80)
    print("强制执行插件系统表迁移")
    print("=" * 80)
    
    db_path = Config.DATABASE_PATH
    
    if not os.path.exists(db_path):
        print("❌ 数据库文件不存在")
        return False
    
    print(f"数据库路径: {db_path}")
    
    try:
        # 检查表是否存在
        with get_db() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('plugin_info', 'task_plugin_relation', 'plugin_exec_log')
            """)
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            print(f"\n当前已存在的插件表: {existing_tables}")
        
        # 执行迁移
        print("\n开始执行迁移...")
        from migrations.add_plugin_tables import upgrade
        upgrade()
        
        # 记录迁移
        print("\n记录迁移状态...")
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 确保迁移记录表存在
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration_name VARCHAR(255) NOT NULL UNIQUE,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 记录迁移
            cursor.execute("""
                INSERT OR IGNORE INTO schema_migrations (migration_name) 
                VALUES ('add_plugin_tables')
            """)
            
            conn.commit()
        
        print("\n✅ 插件系统表迁移完成")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n❌ 迁移失败: {str(e)}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = force_migrate()
    sys.exit(0 if success else 1)

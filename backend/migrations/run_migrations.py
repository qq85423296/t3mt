# -*- coding: utf-8 -*-
"""
数据库迁移执行器

在应用启动时自动检查并执行所需的数据库迁移
"""
import os
import sys
import sqlite3

# 添加父目录到路径以便导入config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from database import get_db


class MigrationRunner:
    """迁移执行器"""
    
    def __init__(self):
        self.db_path = Config.DATABASE_PATH
        self.migrations_dir = os.path.dirname(os.path.abspath(__file__))
        
    def _get_applied_migrations(self):
        """获取已应用的迁移列表"""
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 检查迁移记录表是否存在
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='schema_migrations'
            """)
            
            if not cursor.fetchone():
                # 创建迁移记录表
                cursor.execute('''
                    CREATE TABLE schema_migrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        migration_name VARCHAR(255) NOT NULL UNIQUE,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
                return []
            
            # 获取已应用的迁移
            cursor.execute("SELECT migration_name FROM schema_migrations ORDER BY id")
            return [row[0] for row in cursor.fetchall()]
    
    def _record_migration(self, migration_name):
        """记录已应用的迁移"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO schema_migrations (migration_name) VALUES (?)",
                (migration_name,)
            )
            conn.commit()
    
    def _get_table_columns(self, table_name):
        """获取表的所有列名"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            return [row[1] for row in cursor.fetchall()]
    
    def _check_file_size_retry_migration_needed(self):
        """检查是否需要执行文件大小和重试功能的迁移"""
        migration_name = 'add_file_size_and_retry_config'
        applied_migrations = self._get_applied_migrations()
        
        if migration_name in applied_migrations:
            return False
        
        # 检查字段是否已存在（可能是手动添加的）
        columns = self._get_table_columns('video_tasks')
        
        # 检查关键字段
        if 'enable_file_size_check' in columns and 'enable_retry' in columns:
            # 字段已存在，记录迁移但不执行
            print(f"  迁移 {migration_name} 的字段已存在，跳过执行")
            self._record_migration(migration_name)
            return False
        
        return True
    
    def _check_regex_pattern_migration_needed(self):
        """检查是否需要执行正则替换字段的迁移"""
        migration_name = 'add_regex_pattern_fields'
        applied_migrations = self._get_applied_migrations()
        
        if migration_name in applied_migrations:
            return False
        
        # 检查 transfer_tasks 表的字段是否已存在
        columns = self._get_table_columns('transfer_tasks')
        
        if 'regex_pattern' in columns and 'replacement_pattern' in columns and 'check_mode' in columns:
            # 字段已存在，记录迁移但不执行
            print(f"  迁移 {migration_name} 的字段已存在，跳过执行")
            self._record_migration(migration_name)
            return False
        
        return True
    
    def _check_cloud_type_migration_needed(self):
        """检查是否需要执行cloud_type字段的迁移"""
        migration_name = 'add_cloud_type_field'
        applied_migrations = self._get_applied_migrations()
        
        if migration_name in applied_migrations:
            return False
        
        # 检查 quark_accounts 表的字段是否已存在
        columns = self._get_table_columns('quark_accounts')
        
        if 'cloud_type' in columns:
            # 字段已存在，记录迁移但不执行
            print(f"  迁移 {migration_name} 的字段已存在，跳过执行")
            self._record_migration(migration_name)
            return False
        
        return True
    
    def run_migrations(self):
        """执行所有待执行的迁移"""
        print("=" * 80)
        print("开始检查数据库迁移...")
        print("=" * 80)
        
        # 检查数据库是否存在
        if not os.path.exists(self.db_path):
            print("数据库文件不存在，将在应用启动时自动创建")
            return True
        
        try:
            migrations_executed = False
            
            # 迁移1：文件大小和重试功能
            if self._check_file_size_retry_migration_needed():
                print("\n检测到需要执行迁移: add_file_size_and_retry_config")
                print("正在执行迁移...")
                
                from migrations.add_file_size_and_retry_config import upgrade
                upgrade()
                
                self._record_migration('add_file_size_and_retry_config')
                print("✅ 迁移 add_file_size_and_retry_config 执行成功")
                migrations_executed = True
            
            # 迁移2：正则替换字段
            if self._check_regex_pattern_migration_needed():
                print("\n检测到需要执行迁移: add_regex_pattern_fields")
                print("正在执行迁移...")
                
                from migrations.add_regex_pattern_fields import upgrade
                upgrade()
                
                self._record_migration('add_regex_pattern_fields')
                print("✅ 迁移 add_regex_pattern_fields 执行成功")
                migrations_executed = True
            
            # 迁移3：cloud_type字段（多云盘支持）
            if self._check_cloud_type_migration_needed():
                print("\n检测到需要执行迁移: add_cloud_type_field")
                print("正在执行迁移...")
                
                from migrations.add_cloud_type_field import migrate_add_cloud_type
                migrate_add_cloud_type()
                
                self._record_migration('add_cloud_type_field')
                print("✅ 迁移 add_cloud_type_field 执行成功")
                migrations_executed = True
            
            if not migrations_executed:
                print("✅ 所有迁移已是最新状态")
            
            print("=" * 80)
            return True
            
        except Exception as e:
            print(f"❌ 迁移执行失败: {str(e)}")
            print("=" * 80)
            import traceback
            traceback.print_exc()
            return False


def run_migrations():
    """执行迁移的便捷函数"""
    runner = MigrationRunner()
    return runner.run_migrations()


if __name__ == '__main__':
    success = run_migrations()
    sys.exit(0 if success else 1)

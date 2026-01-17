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
    
    def _check_table_exists(self, table_name):
        """检查表是否存在"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table_name,))
            return cursor.fetchone() is not None
    
    def _check_plugin_tables_migration_needed(self):
        """检查是否需要执行插件系统表的迁移"""
        from utils.logger import logger
        
        migration_name = 'add_plugin_tables'
        applied_migrations = self._get_applied_migrations()
        
        if migration_name in applied_migrations:
            logger.info(f"  迁移 {migration_name} 已在迁移记录中")
            return False
        
        # 检查三张表是否都已存在
        plugin_info_exists = self._check_table_exists('plugin_info')
        task_plugin_relation_exists = self._check_table_exists('task_plugin_relation')
        plugin_exec_log_exists = self._check_table_exists('plugin_exec_log')
        
        logger.info(f"  插件表检查: plugin_info={plugin_info_exists}, task_plugin_relation={task_plugin_relation_exists}, plugin_exec_log={plugin_exec_log_exists}")
        
        if plugin_info_exists and task_plugin_relation_exists and plugin_exec_log_exists:
            # 表已存在，记录迁移但不执行
            logger.info(f"  迁移 {migration_name} 的表已存在，跳过执行")
            self._record_migration(migration_name)
            return False
        
        # 如果部分表存在，说明之前迁移失败，需要重新执行
        if plugin_info_exists or task_plugin_relation_exists or plugin_exec_log_exists:
            logger.warning(f"  警告: 插件表部分存在，将重新执行完整迁移")
        
        return True
    
    def _check_selected_params_migration_needed(self):
        """检查是否需要执行 selected_params 字段的迁移"""
        migration_name = 'add_selected_params_field'
        applied_migrations = self._get_applied_migrations()
        
        if migration_name in applied_migrations:
            return False
        
        # 检查 task_plugin_relation 表是否存在
        if not self._check_table_exists('task_plugin_relation'):
            return False
        
        # 检查字段是否已存在
        columns = self._get_table_columns('task_plugin_relation')
        
        if 'selected_params' in columns:
            # 字段已存在，记录迁移但不执行
            print(f"  迁移 {migration_name} 的字段已存在，跳过执行")
            self._record_migration(migration_name)
            return False
        
        return True
    
    def run_migrations(self):
        """执行所有待执行的迁移"""
        from utils.logger import logger
        
        logger.info("=" * 80)
        logger.info("开始检查数据库迁移...")
        logger.info("=" * 80)
        
        # 检查数据库是否存在
        if not os.path.exists(self.db_path):
            logger.info("数据库文件不存在，将在应用启动时自动创建")
            return True
        
        logger.info(f"数据库路径: {self.db_path}")
        
        try:
            migrations_executed = False
            
            # 迁移1：文件大小和重试功能
            if self._check_file_size_retry_migration_needed():
                logger.info("检测到需要执行迁移: add_file_size_and_retry_config")
                logger.info("正在执行迁移...")
                
                from migrations.add_file_size_and_retry_config import upgrade
                upgrade()
                
                self._record_migration('add_file_size_and_retry_config')
                logger.info("✅ 迁移 add_file_size_and_retry_config 执行成功")
                migrations_executed = True
            
            # 迁移2：正则替换字段
            if self._check_regex_pattern_migration_needed():
                logger.info("检测到需要执行迁移: add_regex_pattern_fields")
                logger.info("正在执行迁移...")
                
                from migrations.add_regex_pattern_fields import upgrade
                upgrade()
                
                self._record_migration('add_regex_pattern_fields')
                logger.info("✅ 迁移 add_regex_pattern_fields 执行成功")
                migrations_executed = True
            
            # 迁移3：cloud_type字段（多云盘支持）
            if self._check_cloud_type_migration_needed():
                logger.info("检测到需要执行迁移: add_cloud_type_field")
                logger.info("正在执行迁移...")
                
                from migrations.add_cloud_type_field import migrate_add_cloud_type
                migrate_add_cloud_type()
                
                self._record_migration('add_cloud_type_field')
                logger.info("✅ 迁移 add_cloud_type_field 执行成功")
                migrations_executed = True
            
            # 迁移4：插件系统表
            if self._check_plugin_tables_migration_needed():
                logger.info("检测到需要执行迁移: add_plugin_tables")
                logger.info("正在执行迁移...")
                
                try:
                    from migrations.add_plugin_tables import upgrade
                    upgrade()
                    
                    self._record_migration('add_plugin_tables')
                    logger.info("✅ 迁移 add_plugin_tables 执行成功")
                    migrations_executed = True
                except Exception as e:
                    logger.error(f"❌ 迁移 add_plugin_tables 执行失败: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    # 插件表迁移失败，返回False
                    return False
            
            # 迁移5：插件参数选择字段
            if self._check_selected_params_migration_needed():
                logger.info("检测到需要执行迁移: add_selected_params_field")
                logger.info("正在执行迁移...")
                
                from migrations.add_selected_params_field import upgrade
                upgrade()
                
                self._record_migration('add_selected_params_field')
                logger.info("✅ 迁移 add_selected_params_field 执行成功")
                migrations_executed = True
            
            if not migrations_executed:
                logger.info("✅ 所有迁移已是最新状态")
            
            logger.info("=" * 80)
            return True
            
        except Exception as e:
            logger.error(f"❌ 迁移执行失败: {str(e)}")
            logger.info("=" * 80)
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

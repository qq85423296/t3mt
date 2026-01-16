# -*- coding: utf-8 -*-
"""
数据库迁移脚本 - 添加cloud_type字段
为所有云盘相关表添加cloud_type字段以支持多云盘类型
"""
import sys
import os

# 添加父目录到路径以便导入database模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from utils.logger import logger


def migrate_add_cloud_type():
    """为所有相关表添加cloud_type字段"""
    
    tables = [
        'quark_accounts',
        'transfer_tasks', 
        'download_tasks',
        'video_tasks'
    ]
    
    logger.info("开始数据库迁移：添加cloud_type字段")
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            for table in tables:
                # 检查表是否存在
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name=?
                """, (table,))
                
                if not cursor.fetchone():
                    logger.warning(f"表 {table} 不存在，跳过")
                    continue
                
                # 检查字段是否已存在
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]
                
                if 'cloud_type' in columns:
                    logger.info(f"✅ 表 {table} 的cloud_type字段已存在")
                    continue
                
                # 添加cloud_type字段
                logger.info(f"正在为表 {table} 添加cloud_type字段...")
                cursor.execute(f"""
                    ALTER TABLE {table} 
                    ADD COLUMN cloud_type VARCHAR(20) DEFAULT 'quark'
                """)
                
                # 更新现有数据
                cursor.execute(f"""
                    UPDATE {table} 
                    SET cloud_type = 'quark' 
                    WHERE cloud_type IS NULL
                """)
                
                # 创建索引
                index_name = f"idx_{table}_cloud_type"
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS {index_name}
                    ON {table}(cloud_type)
                """)
                
                conn.commit()
                logger.info(f"✅ 表 {table} 的cloud_type字段添加成功")
            
            logger.info("数据库迁移完成！")
            return True
            
    except Exception as e:
        logger.error(f"数据库迁移失败: {e}", exc_info=True)
        return False


if __name__ == '__main__':
    success = migrate_add_cloud_type()
    if success:
        print("\n✅ 数据库迁移成功完成")
        sys.exit(0)
    else:
        print("\n❌ 数据库迁移失败")
        sys.exit(1)

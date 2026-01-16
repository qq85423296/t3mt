# -*- coding: utf-8 -*-
"""
数据库迁移验证工具
验证迁移是否成功完成
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from utils.logger import logger


def verify_migration():
    """验证数据库迁移结果"""
    
    tables = [
        'quark_accounts',
        'transfer_tasks',
        'download_tasks', 
        'video_tasks'
    ]
    
    logger.info("开始验证数据库迁移...")
    all_passed = True
    
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
                    logger.warning(f"⚠️  表 {table} 不存在")
                    continue
                
                # 检查cloud_type字段
                cursor.execute(f"PRAGMA table_info({table})")
                columns = {row[1]: row for row in cursor.fetchall()}
                
                if 'cloud_type' not in columns:
                    logger.error(f"❌ 表 {table} 缺少cloud_type字段")
                    all_passed = False
                    continue
                
                # 验证默认值
                column_info = columns['cloud_type']
                default_value = column_info[4]
                
                if default_value != "'quark'":
                    logger.warning(f"⚠️  表 {table} 的cloud_type默认值不是'quark': {default_value}")
                
                # 检查索引
                cursor.execute(f"PRAGMA index_list({table})")
                indexes = [row[1] for row in cursor.fetchall()]
                index_name = f"idx_{table}_cloud_type"
                
                if index_name not in indexes:
                    logger.warning(f"⚠️  表 {table} 缺少索引 {index_name}")
                
                # 检查数据
                cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                total_count = cursor.fetchone()[0]
                
                cursor.execute(f"SELECT COUNT(*) as count FROM {table} WHERE cloud_type = 'quark'")
                quark_count = cursor.fetchone()[0]
                
                logger.info(f"✅ 表 {table}: cloud_type字段存在, 总记录数={total_count}, quark记录数={quark_count}")
            
            if all_passed:
                logger.info("✅ 数据库迁移验证通过！")
            else:
                logger.error("❌ 数据库迁移验证失败")
            
            return all_passed
            
    except Exception as e:
        logger.error(f"验证过程出错: {e}", exc_info=True)
        return False


if __name__ == '__main__':
    success = verify_migration()
    if success:
        print("\n✅ 数据库迁移验证通过")
        sys.exit(0)
    else:
        print("\n❌ 数据库迁移验证失败")
        sys.exit(1)

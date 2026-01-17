# -*- coding: utf-8 -*-
"""
数据库迁移：为账号表添加用户名和密码字段
用于支持天翼云盘等需要账号密码登录的云盘自动重新登录
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from database import get_db
from utils.logger import logger


def upgrade():
    """执行迁移：添加username和password字段"""
    db_path = Config.DATABASE_PATH
    
    logger.info(f"数据库路径: {db_path}")
    
    if not os.path.exists(db_path):
        logger.info("数据库文件不存在，跳过迁移")
        return
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 检查字段是否已存在
            cursor.execute("PRAGMA table_info(quark_accounts)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # 添加username字段
            if 'username' not in columns:
                logger.info("添加username字段...")
                cursor.execute('''
                    ALTER TABLE quark_accounts 
                    ADD COLUMN username VARCHAR(100)
                ''')
                logger.info("✅ username字段添加成功")
            else:
                logger.info("⏭️ username字段已存在")
            
            # 添加password字段（加密存储）
            if 'password' not in columns:
                logger.info("添加password字段...")
                cursor.execute('''
                    ALTER TABLE quark_accounts 
                    ADD COLUMN password VARCHAR(255)
                ''')
                logger.info("✅ password字段添加成功")
            else:
                logger.info("⏭️ password字段已存在")
            
            conn.commit()
            logger.info("✅ 账号凭证字段迁移完成")
            
    except Exception as e:
        logger.error(f"❌ 迁移失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def downgrade():
    """回滚迁移：删除username和password字段"""
    # SQLite不支持直接删除列，需要重建表
    logger.warning("SQLite不支持直接删除列，回滚操作跳过")


if __name__ == '__main__':
    upgrade()

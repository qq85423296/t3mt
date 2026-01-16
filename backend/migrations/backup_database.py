# -*- coding: utf-8 -*-
"""
数据库备份工具
在执行迁移前自动备份数据库
"""
import sys
import os
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import logger


def backup_database(db_path='data/quark_manager.db'):
    """
    备份数据库文件
    
    Args:
        db_path: 数据库文件路径
    
    Returns:
        str: 备份文件路径，失败返回None
    """
    try:
        if not os.path.exists(db_path):
            logger.error(f"数据库文件不存在: {db_path}")
            return None
        
        # 创建备份目录
        backup_dir = 'data/backups'
        os.makedirs(backup_dir, exist_ok=True)
        
        # 生成备份文件名（带时间戳）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"quark_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # 复制数据库文件
        shutil.copy2(db_path, backup_path)
        
        file_size = os.path.getsize(backup_path) / 1024  # KB
        logger.info(f"✅ 数据库备份成功: {backup_path} ({file_size:.2f} KB)")
        
        return backup_path
        
    except Exception as e:
        logger.error(f"数据库备份失败: {e}", exc_info=True)
        return None


if __name__ == '__main__':
    backup_path = backup_database()
    if backup_path:
        print(f"\n✅ 数据库备份成功: {backup_path}")
        sys.exit(0)
    else:
        print("\n❌ 数据库备份失败")
        sys.exit(1)

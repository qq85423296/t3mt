# -*- coding: utf-8 -*-
"""
添加Aria2配置项到system_config表
"""
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from utils.logger import logger


def migrate():
    """执行迁移"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 定义Aria2配置项
            aria2_configs = [
                ('aria2_max_concurrent_downloads', '3', 'aria2', 'Aria2最大并发下载任务数'),
                ('aria2_split', '16', 'aria2', 'Aria2每文件线程数'),
                ('aria2_min_split_size', '10M', 'aria2', 'Aria2最小分块大小'),
                ('aria2_max_connection_per_server', '16', 'aria2', 'Aria2单服务器最大连接数'),
                ('aria2_timeout', '60', 'aria2', 'Aria2请求超时时间（秒）'),
                ('aria2_retry_wait', '5', 'aria2', 'Aria2重试等待时间（秒）'),
                ('aria2_max_tries', '5', 'aria2', 'Aria2最大重试次数'),
            ]
            
            # 插入配置项（如果不存在）
            for config_key, config_value, config_type, description in aria2_configs:
                cursor.execute("""
                    INSERT OR IGNORE INTO system_config 
                    (config_key, config_value, config_type, description)
                    VALUES (?, ?, ?, ?)
                """, (config_key, config_value, config_type, description))
                
                logger.info(f"✅ 添加Aria2配置: {config_key} = {config_value}")
            
            conn.commit()
            logger.info("✅ Aria2配置迁移完成")
            return True
            
    except Exception as e:
        logger.error(f"❌ Aria2配置迁移失败: {e}", exc_info=True)
        return False


if __name__ == '__main__':
    migrate()

# -*- coding: utf-8 -*-
"""
添加 daily_usage_stats 表
用于记录每日使用统计（解析次数、4K画质使用次数等）
"""
from database import get_db
from utils.logger import logger


def migrate():
    """执行迁移"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 检查表是否已存在
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='daily_usage_stats'
            """)
            
            if cursor.fetchone():
                logger.info("daily_usage_stats 表已存在，跳过创建")
                return True
            
            # 创建 daily_usage_stats 表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_usage_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stat_date DATE NOT NULL,
                    usage_type VARCHAR(50) NOT NULL,
                    parse_count INTEGER DEFAULT 0,
                    quality_4k_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                    UNIQUE(stat_date, usage_type)
                )
            ''')
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_daily_usage_date 
                ON daily_usage_stats(stat_date)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_daily_usage_type 
                ON daily_usage_stats(usage_type)
            ''')
            
            conn.commit()
            logger.info("✅ daily_usage_stats 表创建成功")
            return True
            
    except Exception as e:
        logger.error(f"❌ 创建 daily_usage_stats 表失败: {e}", exc_info=True)
        return False


if __name__ == '__main__':
    print("开始迁移：添加 daily_usage_stats 表...")
    success = migrate()
    if success:
        print("✅ 迁移成功")
    else:
        print("❌ 迁移失败")

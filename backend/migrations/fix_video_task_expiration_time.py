# -*- coding: utf-8 -*-
"""
数据库迁移脚本: 修复影视任务自动失效时间数据

修复内容:
1. 修复被错误初始化为created_at的last_episode_update_time字段
2. 将所有过早的时间重置为当前时间，避免误判为超时
"""
from database import get_db
from utils.logger import logger


def upgrade():
    """修复数据库"""
    print("开始执行数据修复: 修复影视任务的last_episode_update_time数据...")
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 修复所有last_episode_update_time过早的active任务
            # 将30天前的时间重置为当前时间，避免误判为超时
            print("  修复过早的last_episode_update_time数据...")
            cursor.execute('''
                UPDATE video_tasks 
                SET last_episode_update_time = datetime('now')
                WHERE status = 'active' 
                  AND last_episode_update_time IS NOT NULL
                  AND last_episode_update_time < datetime('now', '-30 days')
            ''')
            
            updated_count = cursor.rowcount
            conn.commit()
            
            if updated_count > 0:
                print(f"  ✅ 已修复 {updated_count} 个任务的时间数据")
            else:
                print("  ✅ 无需修复的数据")
        
        print("✅ 数据修复完成!")
        return True
        
    except Exception as e:
        print(f"❌ 数据修复失败: {e}")
        logger.error(f"修复影视任务时间数据失败: {e}", exc_info=True)
        return False


def get_migration_info():
    """返回迁移信息"""
    return {
        'version': '20260201_001',
        'description': '修复影视任务自动失效时间数据(last_episode_update_time字段)',
        'author': 'system',
        'date': '2026-02-01'
    }


if __name__ == '__main__':
    upgrade()

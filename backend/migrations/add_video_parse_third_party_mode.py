# -*- coding: utf-8 -*-
"""
迁移脚本: 添加第三方解析模式配置
"""
from database import get_db
from utils.logger import logger


def upgrade():
    """添加第三方解析模式配置"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 检查配置是否已存在
            cursor.execute(
                "SELECT COUNT(*) as count FROM system_config WHERE config_key = 'video_parse_third_party_mode'"
            )
            result = cursor.fetchone()
            
            if result['count'] == 0:
                # 插入默认配置
                cursor.execute('''
                    INSERT INTO system_config 
                    (config_key, config_value, config_type, description, created_at, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (
                    'video_parse_third_party_mode',
                    '1',
                    'video_parse',
                    '是否启用第三方资源解析，1=启用，0=禁用'
                ))
                logger.info("✓ 已添加第三方解析模式配置")
            else:
                logger.info("✓ 第三方解析模式配置已存在，跳过")
                
    except Exception as e:
        logger.error(f"✗ 添加第三方解析模式配置失败: {e}")
        raise


def downgrade():
    """回滚: 删除第三方解析模式配置"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM system_config WHERE config_key = 'video_parse_third_party_mode'"
            )
            logger.info("✓ 已删除第三方解析模式配置")
    except Exception as e:
        logger.error(f"✗ 删除第三方解析模式配置失败: {e}")
        raise


if __name__ == '__main__':
    # 测试迁移
    print("执行迁移...")
    upgrade()
    print("迁移完成")

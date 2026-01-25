# -*- coding: utf-8 -*-
"""
数据库初始化和迁移脚本
"""
import sqlite3
import os
from database import get_db


def init_default_configs():
    """初始化默认配置
    
    确保首次启动时创建默认配置，不覆盖已存在的配置
    """
    print("开始初始化默认配置...")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 检查system_config表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='system_config'
        """)
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            print("⚠️  system_config表不存在，跳过配置初始化")
            return
        
        # 定义默认配置项
        default_configs = [
            {
                'config_key': 'video_auto_expiration_enabled',
                'config_value': '1',
                'config_type': 'video',
                'description': '影视任务自动失效功能启用开关'
            },
            {
                'config_key': 'video_auto_expiration_days',
                'config_value': '7',
                'config_type': 'video',
                'description': '影视任务自动失效超时天数'
            }
        ]
        
        # 检查并插入配置项
        for config in default_configs:
            config_key = config['config_key']
            
            # 检查配置是否已存在
            cursor.execute("""
                SELECT config_key FROM system_config 
                WHERE config_key = ?
            """, (config_key,))
            exists = cursor.fetchone() is not None
            
            if not exists:
                # 插入新配置
                cursor.execute('''
                    INSERT INTO system_config 
                    (config_key, config_value, config_type, description)
                    VALUES (?, ?, ?, ?)
                ''', (
                    config['config_key'],
                    config['config_value'],
                    config['config_type'],
                    config['description']
                ))
                print(f"  ✅ 已创建配置: {config_key} = {config['config_value']}")
            else:
                print(f"  ℹ️  配置已存在，跳过: {config_key}")
        
        conn.commit()
    
    print("✅ 默认配置初始化完成!")


def check_and_migrate():
    """检查并迁移数据库"""
    print("开始检查数据库...")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 检查video_tasks表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='video_tasks'
        """)
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            print("❌ video_tasks表不存在!")
            print("请先运行应用程序初始化数据库")
            return
        
        # 检查video_tasks表的字段
        cursor.execute("PRAGMA table_info(video_tasks)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"当前表字段: {', '.join(columns)}")
        
        if 'video_type' not in columns:
            print("检测到缺少video_type字段,正在添加...")
            try:
                cursor.execute('''
                    ALTER TABLE video_tasks 
                    ADD COLUMN video_type VARCHAR(20) DEFAULT '电视剧'
                ''')
                conn.commit()
                print("✅ video_type字段添加成功")
            except Exception as e:
                print(f"❌ 添加video_type字段失败: {e}")
        else:
            print("✅ video_type字段已存在")
        
        # 检查其他可能缺失的字段
        required_fields = {
            'platform': "VARCHAR(20) DEFAULT 'mango'",
            'selected_episodes': "TEXT",
            'last_downloaded_episode': "INTEGER DEFAULT 0"
        }
        
        for field, field_type in required_fields.items():
            if field not in columns:
                print(f"检测到缺少{field}字段,正在添加...")
                try:
                    cursor.execute(f'''
                        ALTER TABLE video_tasks 
                        ADD COLUMN {field} {field_type}
                    ''')
                    conn.commit()
                    print(f"✅ {field}字段添加成功")
                except Exception as e:
                    print(f"❌ 添加{field}字段失败: {e}")
            else:
                print(f"✅ {field}字段已存在")
    
    print("数据库检查完成!")
    
    # 初始化默认配置
    init_default_configs()


if __name__ == '__main__':
    check_and_migrate()

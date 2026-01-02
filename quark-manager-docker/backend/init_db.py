# -*- coding: utf-8 -*-
"""
数据库初始化和迁移脚本
"""
import sqlite3
import os
from database import get_db

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

if __name__ == '__main__':
    check_and_migrate()

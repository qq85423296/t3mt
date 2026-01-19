#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
添加文件夹ID字段迁移脚本
为 transfer_tasks 和 download_tasks 表添加 folder_id 字段,用于快速定位目录
"""
import sqlite3
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def upgrade(conn):
    """
    升级数据库：添加文件夹ID字段
    """
    cursor = conn.cursor()
    
    # 1. 为 transfer_tasks 表添加 target_folder_id 字段
    try:
        cursor.execute("SELECT target_folder_id FROM transfer_tasks LIMIT 1")
        print("✓ transfer_tasks.target_folder_id 字段已存在")
    except sqlite3.OperationalError:
        # 字段不存在，需要添加
        cursor.execute("ALTER TABLE transfer_tasks ADD COLUMN target_folder_id VARCHAR(100)")
        print("✅ transfer_tasks 表已添加 target_folder_id 字段")
    
    # 2. 为 download_tasks 表添加 source_folder_id 字段
    try:
        cursor.execute("SELECT source_folder_id FROM download_tasks LIMIT 1")
        print("✓ download_tasks.source_folder_id 字段已存在")
    except sqlite3.OperationalError:
        # 字段不存在，需要添加
        cursor.execute("ALTER TABLE download_tasks ADD COLUMN source_folder_id VARCHAR(100)")
        print("✅ download_tasks 表已添加 source_folder_id 字段")
    
    conn.commit()
    print("✅ 文件夹ID字段迁移完成")


def downgrade(conn):
    """
    降级数据库：移除文件夹ID字段
    注意：SQLite 不支持 DROP COLUMN，所以降级需要重建表
    """
    # SQLite 不支持 DROP COLUMN，通常不实现降级
    print("⚠️  SQLite 不支持 DROP COLUMN，跳过降级")
    pass


def get_migration_info():
    """
    返回迁移信息
    """
    return {
        'version': '20260119_001',
        'description': '添加文件夹ID字段(target_folder_id, source_folder_id)',
        'author': 'system',
        'date': '2026-01-19'
    }


if __name__ == '__main__':
    # 测试迁移
    from database import get_db
    
    print("=" * 80)
    print("测试迁移：添加文件夹ID字段")
    print("=" * 80)
    
    try:
        with get_db() as conn:
            upgrade(conn)
        print("\n✅ 迁移测试成功")
    except Exception as e:
        print(f"\n❌ 迁移测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

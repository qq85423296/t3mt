# -*- coding: utf-8 -*-
"""
数据库备份工具

用于在执行迁移前备份数据库
"""
import os
import shutil
from datetime import datetime
import sys

# 添加父目录到路径以便导入config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


def backup_database():
    """备份数据库文件"""
    db_path = Config.DATABASE_PATH
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False
    
    # 创建备份目录
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        print(f"✅ 创建备份目录: {backup_dir}")
    
    # 生成备份文件名（包含时间戳）
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'quark_manager_backup_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        # 复制数据库文件
        shutil.copy2(db_path, backup_path)
        file_size = os.path.getsize(backup_path) / 1024  # KB
        print(f"✅ 数据库备份成功!")
        print(f"   原文件: {db_path}")
        print(f"   备份文件: {backup_path}")
        print(f"   文件大小: {file_size:.2f} KB")
        return True
    except Exception as e:
        print(f"❌ 数据库备份失败: {str(e)}")
        return False


def list_backups():
    """列出所有备份文件"""
    db_path = Config.DATABASE_PATH
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    
    if not os.path.exists(backup_dir):
        print("没有找到备份目录")
        return
    
    backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.db')]
    
    if not backup_files:
        print("没有找到备份文件")
        return
    
    print(f"\n找到 {len(backup_files)} 个备份文件:")
    print("-" * 80)
    
    for filename in sorted(backup_files, reverse=True):
        filepath = os.path.join(backup_dir, filename)
        file_size = os.path.getsize(filepath) / 1024  # KB
        mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
        print(f"  {filename}")
        print(f"    大小: {file_size:.2f} KB")
        print(f"    时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'list':
        list_backups()
    else:
        backup_database()

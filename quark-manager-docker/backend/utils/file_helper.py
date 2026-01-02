# -*- coding: utf-8 -*-
"""
文件操作辅助工具
"""
import os
import re


class FileHelper:
    """文件操作辅助类"""
    
    @staticmethod
    def format_size(size_bytes):
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        units = ('B', 'KB', 'MB', 'GB', 'TB', 'PB')
        idx = 0
        size = float(size_bytes)
        
        while size >= 1024 and idx < len(units) - 1:
            size /= 1024
            idx += 1
        
        return f"{size:.2f} {units[idx]}"
    
    @staticmethod
    def parse_size(size_str):
        """解析文件大小字符串为字节数"""
        size_str = size_str.strip().upper()
        match = re.match(r'([\d.]+)\s*([KMGTP]?B?)', size_str)
        
        if not match:
            return 0
        
        number = float(match.group(1))
        unit = match.group(2)
        
        units = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 ** 2,
            'GB': 1024 ** 3,
            'TB': 1024 ** 4,
            'PB': 1024 ** 5
        }
        
        return int(number * units.get(unit, 1))
    
    @staticmethod
    def ensure_dir(path):
        """确保目录存在"""
        if not os.path.exists(path):
            os.makedirs(path)
        return path
    
    @staticmethod
    def get_extension(filename):
        """获取文件扩展名"""
        _, ext = os.path.splitext(filename)
        return ext.lower()
    
    @staticmethod
    def match_extensions(filename, extensions):
        """检查文件是否匹配扩展名列表"""
        if not extensions:
            return True
        
        ext = FileHelper.get_extension(filename)
        ext_list = [e.strip().lower() for e in extensions.split(',')]
        
        # 确保扩展名以.开头
        ext_list = [e if e.startswith('.') else f'.{e}' for e in ext_list]
        
        return ext in ext_list
    
    @staticmethod
    def sanitize_filename(filename):
        """清理文件名中的非法字符"""
        # Windows非法字符
        illegal_chars = r'[<>:"/\\|?*]'
        filename = re.sub(illegal_chars, '_', filename)
        
        # 移除前后空格
        filename = filename.strip()
        
        # 限制长度
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:255-len(ext)] + ext
        
        return filename
    
    @staticmethod
    def join_path(*paths):
        """安全地连接路径"""
        return os.path.normpath(os.path.join(*paths))

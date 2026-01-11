# -*- coding: utf-8 -*-
"""
文件名正则替换工具
"""
import re
import os


class FilenameReplacer:
    """文件名正则替换工具类"""
    
    @staticmethod
    def apply_regex_replacement(filename, regex_pattern, replacement_pattern):
        """
        应用正则替换规则到文件名
        
        参数:
            filename: 原文件名(包含扩展名)
            regex_pattern: 正则表达式
            replacement_pattern: 替换表达式
            
        返回:
            (success: bool, new_filename: str, message: str)
            - success: 是否替换成功
            - new_filename: 替换后的文件名
            - message: 处理消息
        """
        if not regex_pattern or not replacement_pattern:
            return False, filename, "正则表达式或替换表达式为空"
        
        # 1. 分离文件名和扩展名
        name, ext = os.path.splitext(filename)
        
        # 2. 编译正则表达式
        try:
            pattern = re.compile(regex_pattern)
        except re.error as e:
            return False, filename, f"正则语法错误: {str(e)}"
        
        # 3. 尝试匹配
        match = pattern.match(name)
        if not match:
            return False, filename, "文件名不匹配正则,保留原名"
        
        # 4. 执行替换
        try:
            new_name = pattern.sub(replacement_pattern, name)
        except Exception as e:
            return False, filename, f"替换失败: {str(e)}"
        
        # 5. 清理非法字符
        new_name = FilenameReplacer.sanitize_filename(new_name)
        
        # 6. 重新组合文件名和扩展名
        new_filename = new_name + ext
        
        return True, new_filename, "替换成功"
    
    @staticmethod
    def validate_regex(pattern):
        """
        验证正则表达式语法
        
        参数:
            pattern: 正则表达式
            
        返回:
            (valid: bool, error_message: str)
        """
        if not pattern:
            return False, "正则表达式不能为空"
        
        try:
            re.compile(pattern)
            return True, ""
        except re.error as e:
            return False, f"正则语法错误: {str(e)}"
    
    @staticmethod
    def sanitize_filename(filename):
        """
        清理文件名中的非法字符
        
        参数:
            filename: 文件名
            
        返回:
            清理后的文件名
        """
        # Windows非法字符: / \ : * ? " < > |
        illegal_chars = r'[/\\:*?"<>|]'
        filename = re.sub(illegal_chars, '_', filename)
        
        # 移除前后空格
        filename = filename.strip()
        
        # 限制长度(Windows文件名最大255字符)
        if len(filename) > 255:
            filename = filename[:255]
        
        return filename
    
    @staticmethod
    def generate_unique_filename(base_filename, existing_files):
        """
        生成唯一文件名(处理重名)
        
        参数:
            base_filename: 基础文件名
            existing_files: 已存在的文件名列表
            
        返回:
            唯一的文件名
        """
        if base_filename not in existing_files:
            return base_filename
        
        name, ext = os.path.splitext(base_filename)
        counter = 1
        
        while True:
            new_filename = f"{name}({counter}){ext}"
            if new_filename not in existing_files:
                return new_filename
            counter += 1
            
            # 防止无限循环
            if counter > 10000:
                raise ValueError("无法生成唯一文件名,已尝试10000次")

# -*- coding: utf-8 -*-
"""
日志格式迁移工具
将旧的字符串格式日志转换为新的对象格式
"""
import re


def convert_log_append_to_task_logger(content: str) -> str:
    """
    将 logs.append(f"[{timestamp}] message") 转换为 task_logger.info("message")
    
    Args:
        content: 文件内容
        
    Returns:
        转换后的内容
    """
    # 模式1: logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] message")
    pattern1 = r'logs\.append\(f"\[{datetime\.now\(\)\.strftime\(\'%H:%M:%S\'\)}\] ([^"]+)"\)'
    
    def replace_func(match):
        message = match.group(1)
        
        # 判断日志类型
        if '✓' in message or '成功' in message or '完成' in message:
            return f'task_logger.success("{message}")'
        elif '✗' in message or '失败' in message or '错误' in message:
            return f'task_logger.error("{message}")'
        elif '⊙' in message or '跳过' in message or '警告' in message:
            return f'task_logger.warning("{message}")'
        else:
            return f'task_logger.info("{message}")'
    
    content = re.sub(pattern1, replace_func, content)
    
    # 模式2: lambda msg: (logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"), update_logs_to_db())
    pattern2 = r'lambda msg: \(logs\.append\(f"\[{datetime\.now\(\)\.strftime\(\'%H:%M:%S\'\)}\] {msg}"\), update_logs_to_db\(\)\)'
    content = re.sub(pattern2, 'lambda msg: task_logger.info(msg)', content)
    
    return content


def add_task_logger_import(content: str) -> str:
    """
    添加TaskLogger导入
    
    Args:
        content: 文件内容
        
    Returns:
        添加导入后的内容
    """
    # 检查是否已经有导入
    if 'from utils.task_logger import TaskLogger' in content:
        return content
    
    # 在函数内部添加导入
    # 查找 def download_thread(): 后面添加
    pattern = r'(def download_thread\(\):)\n(\s+)'
    replacement = r'\1\n\2from utils.task_logger import TaskLogger\n\2'
    content = re.sub(pattern, replacement, content, count=1)
    
    return content


if __name__ == '__main__':
    # 示例用法
    test_code = '''
    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 开始执行任务")
    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ 下载成功")
    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✗ 下载失败")
    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⊙ 文件已存在")
    lambda msg: (logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"), update_logs_to_db())
    '''
    
    result = convert_log_append_to_task_logger(test_code)
    print(result)

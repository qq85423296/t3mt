# -*- coding: utf-8 -*-
"""
反调试和代码保护模块
检测调试器、虚拟机等异常环境
"""
import sys
import os
import platform
import psutil
import hashlib
from datetime import datetime


class AntiDebug:
    """反调试检测"""
    
    @staticmethod
    def check_debugger():
        """检测调试器"""
        # 检查是否在调试模式
        if sys.gettrace() is not None:
            return True, "检测到Python调试器"
        
        # 检查环境变量
        debug_vars = ['PYTHONDEBUG', 'PYDEBUG', 'DEBUG']
        for var in debug_vars:
            if os.getenv(var):
                return True, f"检测到调试环境变量: {var}"
        
        # 检查进程名称
        try:
            current_process = psutil.Process()
            process_name = current_process.name().lower()
            
            debug_processes = ['pycharm', 'vscode', 'idle', 'debugpy', 'pydevd']
            for debug_proc in debug_processes:
                if debug_proc in process_name:
                    return True, f"检测到调试进程: {process_name}"
        except:
            pass
        
        return False, None
    
    @staticmethod
    def check_virtual_machine():
        """检测虚拟机环境"""
        try:
            # 检查系统信息
            system_info = platform.uname()
            
            vm_indicators = [
                'vmware', 'virtualbox', 'qemu', 'kvm', 
                'xen', 'hyper-v', 'parallels', 'virtual'
            ]
            
            # 检查系统名称
            system_str = str(system_info).lower()
            for indicator in vm_indicators:
                if indicator in system_str:
                    return True, f"检测到虚拟机环境: {indicator}"
            
            # 检查MAC地址（虚拟机通常有特定的MAC地址前缀）
            import uuid
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                           for elements in range(0, 2*6, 2)][::-1])
            
            vm_mac_prefixes = ['00:05:69', '00:0c:29', '00:1c:14', '00:50:56', '08:00:27']
            for prefix in vm_mac_prefixes:
                if mac.startswith(prefix):
                    return True, f"检测到虚拟机MAC地址: {mac}"
            
        except:
            pass
        
        return False, None
    
    @staticmethod
    def check_code_integrity():
        """检查代码完整性"""
        try:
            # 计算关键文件的哈希值
            critical_files = [
                'utils/license_manager.py',
                'utils/machine_id.py',
                'utils/feature_gate.py'
            ]
            
            for file_path in critical_files:
                full_path = os.path.join(os.path.dirname(__file__), '..', file_path)
                if os.path.exists(full_path):
                    with open(full_path, 'rb') as f:
                        content = f.read()
                        file_hash = hashlib.sha256(content).hexdigest()
                        # 这里可以与预存的哈希值比对
                        # 如果不匹配，说明文件被篡改
        except:
            pass
        
        return False, None
    
    @staticmethod
    def check_time_manipulation():
        """检测时间篡改"""
        try:
            # 检查系统时间是否合理
            now = datetime.now()
            
            # 检查是否在合理的时间范围内（2024-2030）
            if now.year < 2024 or now.year > 2030:
                return True, f"检测到异常系统时间: {now}"
            
        except:
            pass
        
        return False, None
    
    @staticmethod
    def perform_checks():
        """执行所有检查"""
        checks = [
            ('调试器检测', AntiDebug.check_debugger),
            ('虚拟机检测', AntiDebug.check_virtual_machine),
            ('代码完整性检测', AntiDebug.check_code_integrity),
            ('时间篡改检测', AntiDebug.check_time_manipulation)
        ]
        
        for check_name, check_func in checks:
            detected, message = check_func()
            if detected:
                return True, f"{check_name}: {message}"
        
        return False, None


def protect_execution():
    """
    保护执行环境
    在关键代码执行前调用此函数
    """
    detected, message = AntiDebug.perform_checks()
    
    if detected:
        from utils.logger import logger
        logger.error(f"安全检测失败: {message}")
        
        # 可以选择：
        # 1. 直接退出
        # sys.exit(1)
        
        # 2. 返回错误
        return False, message
        
        # 3. 降级到社区版
        # return False, "检测到异常环境，已降级到社区版"
    
    return True, None

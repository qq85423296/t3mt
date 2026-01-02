# -*- coding: utf-8 -*-
"""
机器码生成模块
基于硬件信息生成唯一机器标识
"""
import hashlib
import platform
import uuid
import subprocess
import os


class MachineID:
    """机器码生成器"""
    
    @staticmethod
    def get_machine_id():
        """
        生成机器唯一标识
        综合多个硬件信息，确保唯一性和稳定性
        """
        components = []
        
        # 1. CPU信息
        try:
            if platform.system() == 'Windows':
                cpu_info = subprocess.check_output('wmic cpu get ProcessorId', shell=True).decode()
                cpu_id = cpu_info.split('\n')[1].strip()
                components.append(cpu_id)
            elif platform.system() == 'Linux':
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'Serial' in line:
                            components.append(line.split(':')[1].strip())
                            break
        except:
            pass
        
        # 2. 主板序列号
        try:
            if platform.system() == 'Windows':
                board_info = subprocess.check_output('wmic baseboard get SerialNumber', shell=True).decode()
                board_id = board_info.split('\n')[1].strip()
                components.append(board_id)
            elif platform.system() == 'Linux':
                result = subprocess.check_output(['dmidecode', '-s', 'baseboard-serial-number']).decode()
                components.append(result.strip())
        except:
            pass
        
        # 3. MAC地址
        try:
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                           for elements in range(0, 2*6, 2)][::-1])
            components.append(mac)
        except:
            pass
        
        # 4. 系统UUID
        try:
            if platform.system() == 'Windows':
                uuid_info = subprocess.check_output('wmic csproduct get UUID', shell=True).decode()
                system_uuid = uuid_info.split('\n')[1].strip()
                components.append(system_uuid)
            elif platform.system() == 'Linux':
                result = subprocess.check_output(['dmidecode', '-s', 'system-uuid']).decode()
                components.append(result.strip())
        except:
            pass
        
        # 5. 硬盘序列号
        try:
            if platform.system() == 'Windows':
                disk_info = subprocess.check_output('wmic diskdrive get SerialNumber', shell=True).decode()
                disk_id = disk_info.split('\n')[1].strip()
                components.append(disk_id)
        except:
            pass
        
        # 如果所有方法都失败，使用系统信息作为后备
        if not components:
            components.append(platform.node())
            components.append(platform.machine())
            components.append(platform.processor())
        
        # 组合所有信息并生成哈希
        machine_string = '|'.join(filter(None, components))
        machine_hash = hashlib.sha256(machine_string.encode()).hexdigest()
        
        # 返回格式化的机器码（分段显示更友好）
        return '-'.join([machine_hash[i:i+4] for i in range(0, 16, 4)])
    
    @staticmethod
    def get_machine_info():
        """获取机器详细信息（用于显示）"""
        return {
            'system': platform.system(),
            'node': platform.node(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor()
        }

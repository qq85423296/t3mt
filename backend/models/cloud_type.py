# -*- coding: utf-8 -*-
"""
云盘类型枚举
定义系统支持的云盘类型常量
"""


class CloudType:
    """云盘类型枚举类"""
    
    # 云盘类型常量
    QUARK = 'quark'          # 夸克网盘
    CLOUD189 = 'cloud189'    # 天翼189云盘
    
    # 所有支持的云盘类型
    ALL_TYPES = [QUARK, CLOUD189]
    
    # 云盘类型显示名称映射
    TYPE_NAMES = {
        QUARK: '夸克网盘',
        CLOUD189: '天翼189云盘'
    }
    
    @classmethod
    def is_valid(cls, cloud_type):
        """
        验证云盘类型是否有效
        
        Args:
            cloud_type: 云盘类型字符串
        
        Returns:
            bool: 是否为有效的云盘类型
        """
        return cloud_type in cls.ALL_TYPES
    
    @classmethod
    def get_default(cls):
        """
        获取默认云盘类型
        
        Returns:
            str: 默认云盘类型（quark）
        """
        return cls.QUARK
    
    @classmethod
    def get_display_name(cls, cloud_type):
        """
        获取云盘类型的显示名称
        
        Args:
            cloud_type: 云盘类型
        
        Returns:
            str: 显示名称
        """
        return cls.TYPE_NAMES.get(cloud_type, cloud_type)

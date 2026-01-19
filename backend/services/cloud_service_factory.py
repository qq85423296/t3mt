# -*- coding: utf-8 -*-
"""
云盘服务工厂
根据云盘类型创建对应的服务实例
"""
from models.cloud_type import CloudType
from utils.logger import logger


class CloudServiceFactory:
    """云盘服务工厂类"""
    
    @staticmethod
    def create_service(cloud_type, credential, username=None, password=None):
        """
        创建云盘服务实例
        
        Args:
            cloud_type: 云盘类型 (quark/cloud189)
            credential: 登录凭证 (cookie/token)
            username: 用户名（可选，用于天翼云盘自动刷新Cookie）
            password: 密码（可选，用于天翼云盘自动刷新Cookie）
        
        Returns:
            ICloudService: 云盘服务实例
        
        Raises:
            ValueError: 不支持的云盘类型
        """
        if not CloudType.is_valid(cloud_type):
            raise ValueError(f"不支持的云盘类型: {cloud_type}")
        
        if cloud_type == CloudType.QUARK:
            from services.quark_service import QuarkService
            logger.debug(f"创建夸克网盘服务实例")
            return QuarkService(credential)
        
        elif cloud_type == CloudType.CLOUD189:
            from services.cloud189_service import Cloud189Service
            logger.debug(f"创建天翼189云盘服务实例")
            # 传入 username 和 password 以支持 Cookie 自动更新
            return Cloud189Service(
                cookie=credential,
                username=username,
                password=password
            )
        
        else:
            raise ValueError(f"不支持的云盘类型: {cloud_type}")
    
    @staticmethod
    def get_supported_types():
        """
        获取所有支持的云盘类型
        
        Returns:
            list: 云盘类型列表
        """
        return CloudType.ALL_TYPES

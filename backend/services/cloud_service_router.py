# -*- coding: utf-8 -*-
"""
云盘服务路由器
根据cloud_type参数路由请求到对应的云盘服务
"""
from models.cloud_type import CloudType
from services.cloud_service_factory import CloudServiceFactory
from utils.logger import logger


class CloudServiceRouter:
    """云盘服务路由器"""
    
    @staticmethod
    def route_request(cloud_type, cookie=None, account_id=None, operation=None, **kwargs):
        """
        路由云盘操作请求
        
        Args:
            cloud_type: 云盘类型
            cookie: 登录凭证（可选，与account_id二选一）
            account_id: 账号ID（可选，与cookie二选一）
            operation: 操作名称 (get_file_list, mkdir, delete等)
            **kwargs: 操作参数
        
        Returns:
            操作结果
        
        Raises:
            ValueError: 参数错误或账号不存在
            AttributeError: 操作方法不存在
        """
        # 如果提供了account_id，从数据库获取cookie
        if account_id:
            from services.account_service import AccountService
            account = AccountService.get_account(account_id)
            if not account:
                raise ValueError(f"账号不存在: {account_id}")
            
            # 验证云盘类型匹配
            account_cloud_type = account.get('cloud_type', CloudType.QUARK)
            if account_cloud_type != cloud_type:
                raise ValueError(
                    f"账号类型不匹配: 期望{cloud_type}, 实际{account_cloud_type}"
                )
            
            cookie = account['cookie']
        
        # 必须提供cookie或account_id之一
        if not cookie:
            raise ValueError("必须提供cookie或account_id参数")
        
        # 创建服务实例
        service = CloudServiceFactory.create_service(cloud_type, cookie)
        
        # 执行操作
        if not hasattr(service, operation):
            raise AttributeError(f"服务不支持操作: {operation}")
        
        method = getattr(service, operation)
        
        logger.info(
            f"路由请求: cloud_type={cloud_type}, operation={operation}"
        )
        
        return method(**kwargs)

# -*- coding: utf-8 -*-
"""
文件服务 - 支持多云盘类型的统一文件操作接口
"""
from services.cloud_service_router import CloudServiceRouter
from services.account_service import AccountService
from utils.logger import logger


class FileService:
    """统一的文件服务类"""
    
    @staticmethod
    def get_files(account_id, folder_id='0', page=1, size=50):
        """
        获取文件列表
        
        Args:
            account_id: 账号ID
            folder_id: 文件夹ID
            page: 页码
            size: 每页数量
        
        Returns:
            dict: 文件列表响应
        """
        try:
            # 获取账号信息
            account = AccountService.get_account(account_id)
            if not account:
                return {
                    'code': -1,
                    'message': '账号不存在'
                }
            
            cloud_type = account.get('cloud_type', 'quark')
            cookie = account['cookie']
            
            # 路由到对应的云盘服务
            result = CloudServiceRouter.route_request(
                cloud_type=cloud_type,
                cookie=cookie,
                operation='get_file_list',
                folder_id=folder_id,
                page=page,
                size=size
            )
            
            return result
            
        except Exception as e:
            logger.error(f"获取文件列表失败: {e}")
            return {
                'code': -1,
                'message': f'获取文件列表失败: {str(e)}'
            }
    
    @staticmethod
    def create_folder(account_id, folder_name, parent_id='0'):
        """
        创建文件夹
        
        Args:
            account_id: 账号ID
            folder_name: 文件夹名称
            parent_id: 父文件夹ID
        
        Returns:
            dict: 创建结果
        """
        try:
            # 获取账号信息
            account = AccountService.get_account(account_id)
            if not account:
                return {
                    'code': -1,
                    'message': '账号不存在'
                }
            
            cloud_type = account.get('cloud_type', 'quark')
            cookie = account['cookie']
            
            # 路由到对应的云盘服务
            result = CloudServiceRouter.route_request(
                cloud_type=cloud_type,
                cookie=cookie,
                operation='mkdir',
                folder_name=folder_name,
                parent_id=parent_id
            )
            
            return result
            
        except Exception as e:
            logger.error(f"创建文件夹失败: {e}")
            return {
                'code': -1,
                'message': f'创建文件夹失败: {str(e)}'
            }
    
    @staticmethod
    def delete_files(account_id, file_ids):
        """
        删除文件/文件夹
        
        Args:
            account_id: 账号ID
            file_ids: 文件ID列表
        
        Returns:
            dict: 删除结果
        """
        try:
            # 获取账号信息
            account = AccountService.get_account(account_id)
            if not account:
                return {
                    'code': -1,
                    'message': '账号不存在'
                }
            
            cloud_type = account.get('cloud_type', 'quark')
            cookie = account['cookie']
            
            # 路由到对应的云盘服务
            result = CloudServiceRouter.route_request(
                cloud_type=cloud_type,
                cookie=cookie,
                operation='delete',
                file_ids=file_ids
            )
            
            return result
            
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return {
                'code': -1,
                'message': f'删除文件失败: {str(e)}'
            }
    
    @staticmethod
    def share_files(account_id, file_ids, expire_days=7, need_password=False, password=None):
        """
        分享文件/文件夹
        
        Args:
            account_id: 账号ID
            file_ids: 文件ID列表
            expire_days: 有效期天数
            need_password: 是否需要密码
            password: 分享密码
        
        Returns:
            dict: 分享链接信息
        """
        try:
            # 获取账号信息
            account = AccountService.get_account(account_id)
            if not account:
                return {
                    'code': -1,
                    'message': '账号不存在'
                }
            
            cloud_type = account.get('cloud_type', 'quark')
            cookie = account['cookie']
            
            # 路由到对应的云盘服务
            result = CloudServiceRouter.route_request(
                cloud_type=cloud_type,
                cookie=cookie,
                operation='create_share',
                file_ids=file_ids,
                expire_days=expire_days,
                need_password=need_password,
                password=password
            )
            
            return result
            
        except Exception as e:
            logger.error(f"分享文件失败: {e}")
            return {
                'code': -1,
                'message': f'分享文件失败: {str(e)}'
            }
    
    @staticmethod
    def get_download_url(account_id, file_ids):
        """
        获取下载链接
        
        Args:
            account_id: 账号ID
            file_ids: 文件ID列表
        
        Returns:
            tuple: (result_dict, cookie_str)
        """
        try:
            # 获取账号信息
            account = AccountService.get_account(account_id)
            if not account:
                return {
                    'code': -1,
                    'message': '账号不存在'
                }, ''
            
            cloud_type = account.get('cloud_type', 'quark')
            cookie = account['cookie']
            
            # 路由到对应的云盘服务
            result, new_cookie = CloudServiceRouter.route_request(
                cloud_type=cloud_type,
                cookie=cookie,
                operation='get_download_url',
                file_ids=file_ids
            )
            
            return result, new_cookie
            
        except Exception as e:
            logger.error(f"获取下载链接失败: {e}")
            return {
                'code': -1,
                'message': f'获取下载链接失败: {str(e)}'
            }, ''

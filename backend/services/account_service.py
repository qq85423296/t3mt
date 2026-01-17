# -*- coding: utf-8 -*-
"""
账号服务 - 支持多云盘类型
"""
from models.account import Account
from models.cloud_type import CloudType
from services.cloud_service_factory import CloudServiceFactory
from utils.logger import logger
from utils.file_helper import FileHelper


class AccountService:
    """账号服务类"""
    
    @staticmethod
    def get_all_accounts(cloud_type=None):
        """
        获取所有账号
        
        Args:
            cloud_type: 云盘类型过滤，None表示获取所有
        
        Returns:
            list: 账号列表
        """
        accounts = Account.get_all(cloud_type)
        
        # 格式化存储大小
        for account in accounts:
            account['total_size_text'] = FileHelper.format_size(account.get('total_size', 0))
            account['used_size_text'] = FileHelper.format_size(account.get('used_size', 0))
        
        return accounts
    
    @staticmethod
    def get_account(account_id):
        """
        根据ID获取账号
        
        Args:
            account_id: 账号ID
        
        Returns:
            dict: 账号信息
        """
        return Account.get_by_id(account_id)
    
    @staticmethod
    def create_account(remark, cookie, cloud_type=CloudType.QUARK, username=None, password=None):
        """
        创建账号
        
        Args:
            remark: 账号备注
            cookie: 登录凭证
            cloud_type: 云盘类型
            username: 用户名（可选，用于自动重新登录）
            password: 密码（可选，用于自动重新登录）
        
        Returns:
            int: 账号ID
        """
        # 验证云盘类型
        if not CloudType.is_valid(cloud_type):
            raise ValueError(f"无效的云盘类型: {cloud_type}")
        
        # 获取账号信息
        try:
            service = CloudServiceFactory.create_service(cloud_type, cookie)
            account_info = service.get_account_info()
            
            if not account_info:
                raise ValueError("无法获取账号信息，请检查Cookie是否有效")
            
            # 加密密码（如果提供）
            encrypted_password = None
            if password:
                from utils.crypto import CryptoUtil
                encrypted_password = CryptoUtil.encrypt_password(password)
            
            # 保存到数据库
            account_id = Account.create(
                remark=remark,
                cookie=cookie,
                cloud_type=cloud_type,
                account_name=account_info.get('nickname', ''),
                total_size=account_info.get('total_capacity', 0),
                used_size=account_info.get('use_capacity', 0),
                is_vip=account_info.get('is_vip', 0),
                member_type=account_info.get('member_type', ''),
                username=username,
                password=encrypted_password
            )
            
            logger.info(f"创建{CloudType.get_display_name(cloud_type)}账号成功: {remark} (ID: {account_id})")
            return account_id
            
        except Exception as e:
            logger.error(f"创建账号失败: {e}")
            raise
    
    @staticmethod
    def verify_account(account_id, auto_relogin=True):
        """
        验证账号有效性
        
        Args:
            account_id: 账号ID
            auto_relogin: Cookie失效时是否自动重新登录（仅天翼云盘支持）
        
        Returns:
            dict: {is_valid: bool, message: str, account_info: dict, relogin: bool}
        """
        account = AccountService.get_account(account_id)
        if not account:
            return {'is_valid': False, 'message': '账号不存在', 'relogin': False}
        
        cloud_type = account.get('cloud_type', CloudType.QUARK)
        
        try:
            service = CloudServiceFactory.create_service(cloud_type, account['cookie'])
            account_info = service.get_account_info()
            
            if account_info:
                return {
                    'is_valid': True,
                    'message': '账号有效',
                    'account_info': account_info,
                    'relogin': False
                }
            else:
                # Cookie失效，尝试自动重新登录
                if auto_relogin and cloud_type == CloudType.CLOUD189:
                    username = account.get('username')
                    encrypted_password = account.get('password')
                    
                    if username and encrypted_password:
                        logger.info(f"账号 {account_id} Cookie失效，尝试使用账号密码重新登录...")
                        
                        try:
                            from utils.crypto import CryptoUtil
                            password = CryptoUtil.decrypt_password(encrypted_password)
                            
                            from services.cloud189_service import Cloud189Service
                            login_result = Cloud189Service.login(username, password)
                            
                            if login_result.get('success'):
                                new_cookie = login_result.get('cookies', '')
                                
                                # 更新Cookie
                                Account.update(account_id, cookie=new_cookie)
                                logger.info(f"账号 {account_id} 自动重新登录成功")
                                
                                # 重新获取账号信息
                                service = CloudServiceFactory.create_service(cloud_type, new_cookie)
                                account_info = service.get_account_info()
                                
                                return {
                                    'is_valid': True,
                                    'message': '账号有效（已自动重新登录）',
                                    'account_info': account_info,
                                    'relogin': True
                                }
                            else:
                                logger.warning(f"账号 {account_id} 自动重新登录失败: {login_result.get('message')}")
                        except Exception as relogin_e:
                            logger.error(f"账号 {account_id} 自动重新登录异常: {relogin_e}")
                
                return {
                    'is_valid': False,
                    'message': 'Cookie已失效',
                    'relogin': False
                }
        except Exception as e:
            return {
                'is_valid': False,
                'message': f'账号验证失败: {str(e)}',
                'relogin': False
            }
    
    @staticmethod
    def update_account(account_id, **kwargs):
        """
        更新账号信息
        
        Args:
            account_id: 账号ID
            **kwargs: 更新的字段
        
        Returns:
            bool: 是否成功
        """
        return Account.update(account_id, **kwargs)
    
    @staticmethod
    def delete_account(account_id):
        """
        删除账号
        
        Args:
            account_id: 账号ID
        
        Returns:
            bool: 是否成功
        """
        return Account.delete(account_id)
    
    @staticmethod
    def set_main_account(account_id, cloud_type=None):
        """
        设置主账号（同类型云盘中只能有一个主账号）
        
        Args:
            account_id: 账号ID
            cloud_type: 云盘类型
        
        Returns:
            bool: 是否成功
        """
        try:
            # 先取消同类型云盘的其他主账号
            Account.clear_main_account(cloud_type)
            
            # 设置当前账号为主账号
            return Account.update(account_id, is_main=1)
        except Exception as e:
            logger.error(f"设置主账号失败: {e}")
            return False

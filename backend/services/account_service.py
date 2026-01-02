# -*- coding: utf-8 -*-
"""
账号管理服务
"""
from models.account import Account
from services.quark_service import QuarkService
from utils.logger import logger
from utils.file_helper import FileHelper


class AccountService:
    """账号管理服务类"""
    
    @staticmethod
    def get_all_accounts():
        """获取所有账号"""
        accounts = Account.get_all()
        
        # 格式化存储空间
        for account in accounts:
            if account.get('total_size'):
                account['total_size_text'] = FileHelper.format_size(account['total_size'])
            if account.get('used_size'):
                account['used_size_text'] = FileHelper.format_size(account['used_size'])
        
        return accounts
    
    @staticmethod
    def get_account_by_id(account_id):
        """根据ID获取账号详情"""
        return Account.get_by_id(account_id)
    
    @staticmethod
    def get_account(account_id):
        """获取账号详情（别名方法）"""
        return Account.get_by_id(account_id)
    
    @staticmethod
    def get_main_account():
        """获取主账号"""
        return Account.get_main_account()
    
    @staticmethod
    def test_account(cookie):
        """测试账号有效性"""
        try:
            quark = QuarkService(cookie)
            account_info = quark.get_account_info()
            
            if account_info:
                return {
                    'valid': True,
                    'account_name': account_info.get('nickname', ''),
                    'is_vip': account_info.get('is_vip', 0),
                    'member_type': account_info.get('member_type_raw', ''),
                    'member_type_text': account_info.get('member_type_text', '普通用户'),
                    'member_exp_at': account_info.get('exp_at', ''),
                    'total_size': account_info.get('total_capacity', 0),
                    'used_size': account_info.get('use_capacity', 0),
                }
            else:
                return {'valid': False, 'message': 'Cookie无效或已过期'}
        
        except Exception as e:
            logger.error(f"测试账号失败: {e}")
            return {'valid': False, 'message': str(e)}
    
    @staticmethod
    def add_account(remark, cookie, is_main=0):
        """添加账号"""
        # 先测试账号
        test_result = AccountService.test_account(cookie)
        
        if not test_result['valid']:
            return {'success': False, 'message': test_result['message']}
        
        # 创建账号
        account_id = Account.create(
            remark=remark,
            cookie=cookie,
            account_name=test_result.get('account_name', ''),
            is_vip=test_result.get('is_vip', 0),
            member_type=test_result.get('member_type', ''),
            member_exp_at=test_result.get('member_exp_at', ''),
            total_size=test_result.get('total_size', 0),
            used_size=test_result.get('used_size', 0),
            is_main=is_main
        )
        
        return {
            'success': True,
            'account_id': account_id,
            'account_info': test_result
        }
    
    @staticmethod
    def update_account(account_id, **kwargs):
        """更新账号"""
        # 如果更新Cookie，先测试并获取最新信息
        if 'cookie' in kwargs:
            test_result = AccountService.test_account(kwargs['cookie'])
            if not test_result['valid']:
                return {'success': False, 'message': test_result['message']}
            
            # 更新账号信息（从API自动获取）
            kwargs['account_name'] = test_result.get('account_name', '')
            kwargs['is_vip'] = test_result.get('is_vip', 0)
            kwargs['member_type'] = test_result.get('member_type', '')
            kwargs['member_exp_at'] = test_result.get('member_exp_at', '')
            kwargs['total_size'] = test_result.get('total_size', 0)
            kwargs['used_size'] = test_result.get('used_size', 0)
        
        success = Account.update(account_id, **kwargs)
        return {'success': success}
    
    @staticmethod
    def delete_account(account_id):
        """删除账号"""
        # TODO: 检查是否有任务在使用此账号
        success = Account.delete(account_id)
        return {'success': success}
    
    @staticmethod
    def set_main_account(account_id):
        """设置主账号"""
        success = Account.set_main(account_id)
        return {'success': success}
    
    @staticmethod
    def refresh_account_info(account_id):
        """刷新账号信息"""
        account = Account.get_by_id(account_id)
        if not account:
            return {'success': False, 'message': '账号不存在'}
        
        test_result = AccountService.test_account(account['cookie'])
        if not test_result['valid']:
            # 标记账号为失效
            Account.update(account_id, status=0)
            return {'success': False, 'message': test_result['message']}
        
        # 更新账号信息
        Account.update(
            account_id,
            account_name=test_result.get('account_name', ''),
            is_vip=test_result.get('is_vip', 0),
            member_type=test_result.get('member_type', ''),
            member_exp_at=test_result.get('member_exp_at', ''),
            total_size=test_result.get('total_size', 0),
            used_size=test_result.get('used_size', 0),
            status=1
        )
        
        return {'success': True, 'account_info': test_result}

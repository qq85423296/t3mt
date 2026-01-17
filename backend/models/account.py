# -*- coding: utf-8 -*-
"""
夸克账号模型
"""
from database import get_db
from utils.crypto import CryptoUtil
from datetime import datetime


class Account:
    """夸克账号模型"""
    
    @staticmethod
    def get_all(cloud_type=None):
        """
        获取所有账号
        
        Args:
            cloud_type: 云盘类型过滤，None表示获取所有
        """
        with get_db() as conn:
            cursor = conn.cursor()
            if cloud_type:
                cursor.execute('''
                    SELECT id, remark, account_name, is_vip, member_type, member_exp_at,
                           total_size, used_size, is_main, status, cloud_type, created_at, updated_at
                    FROM quark_accounts
                    WHERE cloud_type = ?
                    ORDER BY is_main DESC, created_at DESC
                ''', (cloud_type,))
            else:
                cursor.execute('''
                    SELECT id, remark, account_name, is_vip, member_type, member_exp_at,
                           total_size, used_size, is_main, status, cloud_type, created_at, updated_at
                    FROM quark_accounts
                    ORDER BY cloud_type, is_main DESC, created_at DESC
                ''')
            accounts = cursor.fetchall()
            return [dict(account) for account in accounts]
    
    @staticmethod
    def get_by_id(account_id):
        """根据ID获取账号"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, remark, cookie, account_name, is_vip, member_type, member_exp_at,
                       total_size, used_size, is_main, status, cloud_type, created_at, updated_at
                FROM quark_accounts WHERE id = ?
            ''', (account_id,))
            account = cursor.fetchone()
            if account:
                account_dict = dict(account)
                # 解密Cookie
                account_dict['cookie'] = CryptoUtil.decrypt(account_dict['cookie'])
                # 确保cloud_type字段存在
                if 'cloud_type' not in account_dict or not account_dict['cloud_type']:
                    account_dict['cloud_type'] = 'quark'
                return account_dict
            return None
    
    @staticmethod
    def get_main_account():
        """获取主账号"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, remark, cookie, account_name, is_vip, member_type, member_exp_at,
                       total_size, used_size, is_main, status, created_at, updated_at
                FROM quark_accounts WHERE is_main = 1
            ''')
            account = cursor.fetchone()
            if account:
                account_dict = dict(account)
                account_dict['cookie'] = CryptoUtil.decrypt(account_dict['cookie'])
                return account_dict
            return None
    
    @staticmethod
    def create(remark, cookie, account_name=None, is_vip=0, member_type='', 
               member_exp_at='', total_size=0, used_size=0, is_main=0, cloud_type='quark',
               username=None, password=None):
        """创建账号"""
        encrypted_cookie = CryptoUtil.encrypt(cookie)
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 如果设置为主账号，先取消其他主账号
            if is_main:
                cursor.execute('UPDATE quark_accounts SET is_main = 0')
            
            cursor.execute('''
                INSERT INTO quark_accounts 
                (remark, cookie, account_name, is_vip, member_type, member_exp_at, 
                 total_size, used_size, is_main, cloud_type, username, password)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (remark, encrypted_cookie, account_name, is_vip, member_type, 
                  member_exp_at, total_size, used_size, is_main, cloud_type, username, password))
            
            return cursor.lastrowid
    
    @staticmethod
    def update(account_id, **kwargs):
        """更新账号信息"""
        # 加密Cookie
        if 'cookie' in kwargs:
            kwargs['cookie'] = CryptoUtil.encrypt(kwargs['cookie'])
        
        # 更新时间
        kwargs['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 如果设置为主账号，先取消其他主账号
        if kwargs.get('is_main'):
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE quark_accounts SET is_main = 0')
        
        # 构建更新语句
        fields = ', '.join([f'{k} = ?' for k in kwargs.keys()])
        values = list(kwargs.values()) + [account_id]
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f'UPDATE quark_accounts SET {fields} WHERE id = ?',
                values
            )
            return cursor.rowcount > 0
    
    @staticmethod
    def delete(account_id):
        """删除账号"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM quark_accounts WHERE id = ?', (account_id,))
            return cursor.rowcount > 0
    
    @staticmethod
    def set_main(account_id):
        """设置为主账号"""
        with get_db() as conn:
            cursor = conn.cursor()
            # 先取消所有主账号
            cursor.execute('UPDATE quark_accounts SET is_main = 0')
            # 设置新的主账号
            cursor.execute(
                'UPDATE quark_accounts SET is_main = 1 WHERE id = ?',
                (account_id,)
            )
            return cursor.rowcount > 0
    
    @staticmethod
    def clear_main_account(cloud_type=None):
        """
        清除主账号标记
        
        Args:
            cloud_type: 云盘类型，None表示清除所有
        """
        with get_db() as conn:
            cursor = conn.cursor()
            if cloud_type:
                cursor.execute(
                    'UPDATE quark_accounts SET is_main = 0 WHERE cloud_type = ?',
                    (cloud_type,)
                )
            else:
                cursor.execute('UPDATE quark_accounts SET is_main = 0')
            return cursor.rowcount >= 0
    
    @staticmethod
    def count():
        """获取账号总数"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM quark_accounts')
            result = cursor.fetchone()
            return result['count'] if result else 0

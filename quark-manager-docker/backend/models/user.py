# -*- coding: utf-8 -*-
"""
用户模型
"""
from database import get_db
from utils.crypto import CryptoUtil


class User:
    """用户模型"""
    
    @staticmethod
    def authenticate(username, password):
        """用户认证"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, username, password FROM users WHERE username = ?',
                (username,)
            )
            user = cursor.fetchone()
            
            if user and CryptoUtil.verify_password(password, user['password']):
                return {
                    'id': user['id'],
                    'username': user['username']
                }
            return None
    
    @staticmethod
    def get_by_id(user_id):
        """根据ID获取用户"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, username, created_at FROM users WHERE id = ?',
                (user_id,)
            )
            user = cursor.fetchone()
            return dict(user) if user else None
    
    @staticmethod
    def get_by_username(username):
        """根据用户名获取用户"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, username, created_at FROM users WHERE username = ?',
                (username,)
            )
            user = cursor.fetchone()
            return dict(user) if user else None
    
    @staticmethod
    def create(username, password):
        """创建用户"""
        hashed_password = CryptoUtil.hash_password(password)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (username, password) VALUES (?, ?)',
                (username, hashed_password)
            )
            return cursor.lastrowid
    
    @staticmethod
    def update_password(user_id, new_password):
        """更新密码"""
        hashed_password = CryptoUtil.hash_password(new_password)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE users SET password = ? WHERE id = ?',
                (hashed_password, user_id)
            )
            return cursor.rowcount > 0
    
    @staticmethod
    def change_password(username, new_password):
        """修改密码(通过用户名)"""
        hashed_password = CryptoUtil.hash_password(new_password)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE users SET password = ? WHERE username = ?',
                (hashed_password, username)
            )
            return cursor.rowcount > 0

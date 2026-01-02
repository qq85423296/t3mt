# -*- coding: utf-8 -*-
"""
加密解密工具
"""
import bcrypt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64


class CryptoUtil:
    """加密解密工具类"""
    
    # 使用固定的盐值（实际项目中应该从配置文件读取）
    SALT = b'quark_manager_salt_2024'
    
    @staticmethod
    def generate_key():
        """生成加密密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=CryptoUtil.SALT,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(b'quark_manager_secret_key'))
        return key
    
    @staticmethod
    def encrypt(text):
        """加密文本"""
        if not text:
            return ''
        key = CryptoUtil.generate_key()
        f = Fernet(key)
        encrypted = f.encrypt(text.encode())
        return encrypted.decode()
    
    @staticmethod
    def decrypt(encrypted_text):
        """解密文本"""
        if not encrypted_text:
            return ''
        try:
            key = CryptoUtil.generate_key()
            f = Fernet(key)
            decrypted = f.decrypt(encrypted_text.encode())
            return decrypted.decode()
        except Exception as e:
            print(f"解密失败: {e}")
            return ''
    
    @staticmethod
    def hash_password(password):
        """密码哈希"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode(), salt)
        return hashed.decode()
    
    @staticmethod
    def verify_password(password, hashed):
        """验证密码"""
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode())
        except Exception:
            return False

# -*- coding: utf-8 -*-
"""
配置加密管理模块
用于加密存储敏感API配置
"""
import json
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
from utils.logger import logger


class ConfigCrypto:
    """配置加密管理器"""
    
    # 加密配置文件路径（使用绝对路径）
    ENCRYPTED_CONFIG_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config',
        'encrypted_config.dat'
    )
    
    def __init__(self):
        self._cipher = None
        self._decryption_key = None
        self._config_cache = None
        self._cache_timestamp = None
        self._cache_ttl = 24 * 3600  # 缓存有效期24小时
        
        # 尝试从环境变量读取解密密钥(用于开发环境)
        env_key = os.environ.get('CONFIG_DECRYPTION_KEY')
        if env_key:
            self.set_decryption_key(env_key)
            logger.info("从环境变量加载解密密钥")
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """从密码派生加密密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def set_decryption_key(self, decryption_key: str):
        """设置解密密钥(从许可证服务器获取)"""
        try:
            # 使用固定的salt(实际部署时应该从服务器获取)
            salt = b'quark_transfer_salt_2024'
            key = self._derive_key(decryption_key, salt)
            self._cipher = Fernet(key)
            self._decryption_key = decryption_key
            logger.info("解密密钥设置成功")
            return True
        except Exception as e:
            logger.error(f"设置解密密钥失败: {e}")
            return False
    
    def encrypt_config(self, config_data: dict, password: str) -> bool:
        """加密配置数据并保存到文件"""
        try:
            # 生成salt
            salt = b'quark_transfer_salt_2024'
            key = self._derive_key(password, salt)
            cipher = Fernet(key)
            
            # 加密配置
            config_json = json.dumps(config_data, ensure_ascii=False)
            encrypted_data = cipher.encrypt(config_json.encode())
            
            # 保存到文件
            os.makedirs(os.path.dirname(self.ENCRYPTED_CONFIG_PATH), exist_ok=True)
            with open(self.ENCRYPTED_CONFIG_PATH, 'wb') as f:
                f.write(encrypted_data)
            
            logger.info("配置加密保存成功")
            return True
        except Exception as e:
            logger.error(f"加密配置失败: {e}")
            return False
    
    def decrypt_config(self) -> dict:
        """解密配置数据"""
        try:
            # 检查缓存
            import time
            if self._config_cache and self._cache_timestamp:
                if time.time() - self._cache_timestamp < self._cache_ttl:
                    logger.debug("使用缓存的配置数据")
                    return self._config_cache
            
            # 检查解密密钥
            if not self._cipher:
                logger.error("解密密钥未设置")
                return self._get_default_config()
            
            # 检查加密文件是否存在
            if not os.path.exists(self.ENCRYPTED_CONFIG_PATH):
                logger.warning("加密配置文件不存在,使用默认配置")
                return self._get_default_config()
            
            # 读取并解密
            with open(self.ENCRYPTED_CONFIG_PATH, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self._cipher.decrypt(encrypted_data)
            config_data = json.loads(decrypted_data.decode())
            
            # 更新缓存
            self._config_cache = config_data
            self._cache_timestamp = time.time()
            
            logger.info("配置解密成功")
            return config_data
            
        except Exception as e:
            logger.error(f"解密配置失败: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> dict:
        """获取默认配置(降级方案) - 返回空配置,不提供任何默认URL"""
        logger.warning("配置解密失败,返回空配置")
        return {
            'quark_api': {},
            'search_engines': {},
            'video_parse': {},
            'license_server': {
                'url': '',
                'heartbeat_interval': 86400  # 24小时
            }
        }
    
    def get_config(self, key_path: str, default=None):
        """获取配置项(支持点号分隔的路径)"""
        try:
            config = self.decrypt_config()
            keys = key_path.split('.')
            value = config
            for key in keys:
                value = value.get(key)
                if value is None:
                    return default
            return value
        except Exception as e:
            logger.error(f"获取配置失败: {e}")
            return default
    
    def clear_cache(self):
        """清除缓存"""
        self._config_cache = None
        self._cache_timestamp = None
        logger.info("配置缓存已清除")


# 全局配置加密管理器实例
config_crypto = ConfigCrypto()

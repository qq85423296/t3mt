# -*- coding: utf-8 -*-
"""
许可证管理模块
负责许可证的在线验证、试用版管理
"""
import json
import requests
from datetime import datetime, timedelta
import os

from database import get_db
from utils.machine_id import MachineID
from utils.logger import logger
from utils.anti_debug import protect_execution


class LicenseType:
    """许可证类型"""
    COMMUNITY = 'community'  # 社区版
    PRO = 'pro'  # 付费版
    TRIAL = 'trial'  # 试用版


class LicenseManager:
    """许可证管理器（在线验证版本）"""
    
    def __init__(self):
        self._last_heartbeat = None
        self._cached_license = None
        self._decryption_key = None
        self._decryption_key_timestamp = None
        
        import base64
        encoded_url = 'aHR0cDovL2xpY2Vuc2UuMjJsMi5jb20='
        self.license_server_url = base64.b64decode(encoded_url).decode('utf-8')
        self.heartbeat_interval = 86400
        
        logger.info(f"许可证管理器初始化完成,服务器: {self.license_server_url}")
        
        # 执行安全检查
        is_safe, error = protect_execution()
        if not is_safe:
            logger.warning(f"安全检查警告: {error}")
            # 可以选择降级或限制功能
    
    def _get_decryption_key_from_server(self):
        """从许可证服务器获取解密密钥"""
        try:
            machine_id = MachineID.get_machine_id()
            
            response = requests.post(
                f"{self.license_server_url}/api/get-decryption-key",
                json={'machine_id': machine_id},
                timeout=10
            )
            
            result = response.json()
            
            if result['code'] == 200:
                self._decryption_key = result['data']['decryption_key']
                self._decryption_key_timestamp = datetime.now()
                
                # 设置到配置加密管理器
                from utils.config_crypto import config_crypto
                config_crypto.set_decryption_key(self._decryption_key)
                
                logger.info("解密密钥获取成功")
                return True
            else:
                logger.error(f"获取解密密钥失败: {result.get('message')}")
                return False
                
        except Exception as e:
            logger.error(f"获取解密密钥失败: {e}")
            return False
    
    def ensure_decryption_key(self):
        """确保解密密钥可用"""
        # 检查是否已有密钥且未过期(24小时)
        if self._decryption_key and self._decryption_key_timestamp:
            elapsed = (datetime.now() - self._decryption_key_timestamp).total_seconds()
            if elapsed < 86400:  # 24小时内有效
                return True
        
        # 尝试从服务器获取
        return self._get_decryption_key_from_server()
    
    def activate_trial(self):
        """激活试用版"""
        try:
            machine_id = MachineID.get_machine_id()
            
            response = requests.post(
                f"{self.license_server_url}/api/trial/activate",
                json={'machine_id': machine_id},
                timeout=10
            )
            
            result = response.json()
            
            if result['code'] == 200:
                # 保存试用信息到本地
                with get_db() as conn:
                    cursor = conn.cursor()
                    
                    # 先将旧的许可证标记为已替换
                    cursor.execute('''
                        UPDATE licenses 
                        SET status = 'replaced' 
                        WHERE machine_id = ? AND status = 'active'
                    ''', (machine_id,))
                    
                    # 插入试用版许可证
                    cursor.execute('''
                        INSERT INTO licenses 
                        (license_key, license_type, machine_id, issue_time, expire_time, features, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        'TRIAL',
                        LicenseType.TRIAL,
                        machine_id,
                        datetime.now().isoformat(),
                        result['data']['expire_time'],
                        json.dumps(self._get_default_features(LicenseType.PRO)),
                        'active'
                    ))
                    conn.commit()
                
                logger.info("试用版激活成功")
                return True, result['data']
            else:
                return False, result.get('message', '激活失败')
                
        except Exception as e:
            logger.error(f"激活试用版失败: {e}")
            return False, f'激活失败: {str(e)}'
    
    def check_trial_status(self):
        """检查试用版状态"""
        try:
            machine_id = MachineID.get_machine_id()
            
            response = requests.post(
                f"{self.license_server_url}/api/trial/check",
                json={'machine_id': machine_id},
                timeout=10
            )
            
            result = response.json()
            
            if result['code'] == 200:
                return result['data']
            else:
                return {'trial_active': False, 'trial_available': False}
                
        except Exception as e:
            logger.error(f"检查试用状态失败: {e}")
            return {'trial_active': False, 'trial_available': False}
    
    def activate_license_online(self, license_key):
        """在线激活许可证"""
        try:
            machine_id = MachineID.get_machine_id()
            
            response = requests.post(
                f"{self.license_server_url}/api/license/activate",
                json={
                    'license_key': license_key,
                    'machine_id': machine_id
                },
                timeout=10
            )
            
            result = response.json()
            
            if result['code'] == 200:
                # 保存到本地数据库
                with get_db() as conn:
                    cursor = conn.cursor()
                    
                    # 先将旧的许可证标记为已替换
                    cursor.execute('''
                        UPDATE licenses 
                        SET status = 'replaced' 
                        WHERE machine_id = ? AND status = 'active'
                    ''', (machine_id,))
                    
                    # 插入新许可证
                    cursor.execute('''
                        INSERT INTO licenses 
                        (license_key, license_type, machine_id, issue_time, expire_time, features, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        license_key,
                        result['data']['license_type'],
                        machine_id,
                        datetime.now().isoformat(),
                        result['data']['expire_time'],
                        json.dumps(result['data']['features']),
                        'active'
                    ))
                    conn.commit()
                
                logger.info(f"许可证激活成功: {result['data']['license_type']}")
                return True, '许可证激活成功'
            else:
                return False, result.get('message', '激活失败')
                
        except Exception as e:
            logger.error(f"在线激活失败: {e}")
            return False, f'激活失败: {str(e)}'
    
    def verify_license_online(self, license_key=None):
        """在线验证许可证（心跳检查）"""
        try:
            machine_id = MachineID.get_machine_id()
            
            # 如果没有提供license_key，从数据库获取
            if not license_key:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT license_key FROM licenses 
                        WHERE status = 'active' AND license_type != 'trial'
                        ORDER BY created_at DESC LIMIT 1
                    ''')
                    row = cursor.fetchone()
                    if not row:
                        return False, None, '未找到许可证'
                    license_key = row[0]
            
            # 检查心跳间隔
            if self._last_heartbeat:
                elapsed = (datetime.now() - self._last_heartbeat).total_seconds()
                if elapsed < self.heartbeat_interval and self._cached_license:
                    return True, self._cached_license, None
            
            response = requests.post(
                f"{self.license_server_url}/api/license/verify",
                json={
                    'license_key': license_key,
                    'machine_id': machine_id
                },
                timeout=10
            )
            
            result = response.json()
            
            if result['code'] == 200 and result['data']['valid']:
                self._last_heartbeat = datetime.now()
                self._cached_license = result['data']
                return True, result['data'], None
            else:
                return False, None, result.get('message', '验证失败')
                
        except Exception as e:
            logger.error(f"在线验证失败: {e}")
            # 网络错误时使用本地缓存
            if self._cached_license:
                logger.warning("使用本地缓存的许可证信息")
                return True, self._cached_license, None
            return False, None, f'验证失败: {str(e)}'
    
    def _get_default_features(self, license_type):
        """获取默认功能配置"""
        if license_type == LicenseType.COMMUNITY:
            return {
                'max_accounts': 1,  # 最大账号数
                'max_video_tasks': 3,  # 最大影视任务数
                'custom_parse_api': False,  # 自定义解析接口
                'video_quality': '360p',  # 视频画质
                'video_quality_4k_trial': 3,  # 4K体验次数
                'daily_parse_limit': 10  # 每日解析次数
            }
        elif license_type == LicenseType.PRO:
            return {
                'max_accounts': -1,  # -1表示无限制
                'max_video_tasks': -1,
                'custom_parse_api': True,
                'video_quality': '4k',
                'video_quality_4k_trial': -1,
                'daily_parse_limit': 200
            }
        return {}
    
    def save_license(self, license_key):
        """保存许可证到数据库（在线激活）"""
        return self.activate_license_online(license_key)
    
    def get_current_license(self):
        """获取当前激活的许可证"""
        try:
            # 确保解密密钥可用
            self.ensure_decryption_key()
            
            # 默认返回体验版配置(到期时间2999-12-31)
            default_experience_license = {
                'type': 'experience',  # 体验版
                'features': {
                    'max_accounts': -1,  # 无限制
                    'max_video_tasks': -1,
                    'custom_parse_api': True,
                    'video_quality': '4k',
                    'video_quality_4k_trial': -1,
                    'daily_parse_limit': 999999
                },
                'expire_time': '2999-12-31T23:59:59',
                'is_trial': False,
                'is_experience': True
            }
            
            # 向许可证服务器报告心跳(用于统计)
            try:
                machine_id = MachineID.get_machine_id()
                
                # 检查心跳间隔
                if self._last_heartbeat:
                    elapsed = (datetime.now() - self._last_heartbeat).total_seconds()
                    if elapsed < self.heartbeat_interval:
                        return default_experience_license
                
                requests.post(
                    f"{self.license_server_url}/api/heartbeat",
                    json={'machine_id': machine_id, 'license_type': 'experience'},
                    timeout=5
                )
                self._last_heartbeat = datetime.now()
            except:
                pass  # 心跳失败不影响使用
            
            return default_experience_license
                
        except Exception as e:
            logger.error(f"获取许可证失败: {e}")
            # 出错时也返回体验版配置
            return {
                'type': 'experience',
                'features': {
                    'max_accounts': -1,
                    'max_video_tasks': -1,
                    'custom_parse_api': True,
                    'video_quality': '4k',
                    'video_quality_4k_trial': -1,
                    'daily_parse_limit': 999999
                },
                'expire_time': '2999-12-31T23:59:59',
                'is_trial': False,
                'is_experience': True
            }
    
    def check_feature(self, feature_name):
        """检查功能是否可用"""
        license_info = self.get_current_license()
        features = license_info.get('features', {})
        return features.get(feature_name, False)
    
    def get_feature_limit(self, feature_name):
        """获取功能限制值"""
        license_info = self.get_current_license()
        features = license_info.get('features', {})
        return features.get(feature_name, 0)


# 全局许可证管理器实例
license_manager = LicenseManager()

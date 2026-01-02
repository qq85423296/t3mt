# -*- coding: utf-8 -*-
"""
系统配置模型
"""
import json
from database import _get_db_instance
from datetime import datetime


class SystemConfig:
    """系统配置模型"""
    
    @staticmethod
    def get_all():
        """获取所有配置"""
        with _get_db_instance().get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM system_config')
            configs = cursor.fetchall()
            
            # 按类型分组
            result = {}
            for config in configs:
                config_type = config['config_type']
                if config_type not in result:
                    result[config_type] = {}
                
                key = config['config_key'].replace(f'{config_type}_', '')
                result[config_type][key] = config['config_value']
            
            return result
    
    @staticmethod
    def get_by_key(config_key):
        """根据键获取配置"""
        with _get_db_instance().get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT config_value FROM system_config WHERE config_key = ?',
                (config_key,)
            )
            config = cursor.fetchone()
            return config['config_value'] if config else None
    
    @staticmethod
    def get_by_type(config_type):
        """根据类型获取配置"""
        with _get_db_instance().get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM system_config WHERE config_type = ?',
                (config_type,)
            )
            configs = cursor.fetchall()
            
            result = {}
            for config in configs:
                key = config['config_key'].replace(f'{config_type}_', '')
                result[key] = config['config_value']
            
            return result
    
    @staticmethod
    def set(config_key, config_value, config_type=None, description=None):
        """设置配置"""
        with _get_db_instance().get_connection() as conn:
            cursor = conn.cursor()
            
            # 检查是否存在
            cursor.execute(
                'SELECT id FROM system_config WHERE config_key = ?',
                (config_key,)
            )
            existing = cursor.fetchone()
            
            if existing:
                # 更新
                cursor.execute('''
                    UPDATE system_config 
                    SET config_value = ?, updated_at = ?
                    WHERE config_key = ?
                ''', (config_value, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), config_key))
            else:
                # 插入
                cursor.execute('''
                    INSERT INTO system_config 
                    (config_key, config_value, config_type, description)
                    VALUES (?, ?, ?, ?)
                ''', (config_key, config_value, config_type, description))
            
            return True
    
    @staticmethod
    def set_batch(configs):
        """批量设置配置"""
        with _get_db_instance().get_connection() as conn:
            cursor = conn.cursor()
            
            for config_key, config_value in configs.items():
                cursor.execute('''
                    UPDATE system_config 
                    SET config_value = ?, updated_at = ?
                    WHERE config_key = ?
                ''', (config_value, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), config_key))
            
            return True
    
    @staticmethod
    def delete(config_key):
        """删除配置"""
        with _get_db_instance().get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM system_config WHERE config_key = ?', (config_key,))
            return cursor.rowcount > 0


# 便捷方法类
class ConfigModel:
    """配置模型便捷方法封装"""
    
    @staticmethod
    def get_config(key, default=None):
        """获取配置值"""
        value = SystemConfig.get_by_key(key)
        return value if value is not None else default
    
    @staticmethod
    def set_config(key, value, config_type=None):
        """设置配置值"""
        return SystemConfig.set(key, value, config_type)
    
    @staticmethod
    def get_config_list(key):
        """获取配置列表(JSON格式)"""
        value = SystemConfig.get_by_key(key)
        if value:
            try:
                return json.loads(value)
            except:
                return []
        return []
    
    @staticmethod
    def set_config_list(key, value_list, config_type=None):
        """设置配置列表(JSON格式)"""
        value = json.dumps(value_list, ensure_ascii=False)
        return SystemConfig.set(key, value, config_type)

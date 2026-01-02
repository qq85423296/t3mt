# -*- coding: utf-8 -*-
"""
搜索服务示例
演示如何使用加密配置
"""
import requests
from utils.config_crypto import config_crypto
from utils.logger import logger


class SearchService:
    """搜索服务类"""
    
    def __init__(self):
        # 从加密配置中获取API信息
        self.pan_search_config = config_crypto.get_config('search_engines.pan_search', {})
        self.aliyun_search_config = config_crypto.get_config('search_engines.aliyun_search', {})
    
    def search_pan(self, keyword: str):
        """使用盘搜API搜索"""
        try:
            if not self.pan_search_config.get('enabled'):
                logger.warning("盘搜API未启用")
                return {'code': 400, 'message': '盘搜API未启用'}
            
            api_url = self.pan_search_config.get('api_url')
            api_key = self.pan_search_config.get('api_key')
            
            if not api_url or not api_key:
                logger.error("盘搜API配置不完整")
                return {'code': 400, 'message': 'API配置不完整'}
            
            # 调用API
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{api_url}/search",
                params={'keyword': keyword},
                headers=headers,
                timeout=10
            )
            
            return response.json()
            
        except Exception as e:
            logger.error(f"盘搜API调用失败: {e}")
            return {'code': 500, 'message': f'搜索失败: {str(e)}'}
    
    def search_aliyun(self, keyword: str):
        """使用阿里云盘搜索API"""
        try:
            if not self.aliyun_search_config.get('enabled'):
                logger.warning("阿里云盘搜索API未启用")
                return {'code': 400, 'message': '阿里云盘搜索API未启用'}
            
            api_url = self.aliyun_search_config.get('api_url')
            api_key = self.aliyun_search_config.get('api_key')
            
            if not api_url or not api_key:
                logger.error("阿里云盘搜索API配置不完整")
                return {'code': 400, 'message': 'API配置不完整'}
            
            # 调用API
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{api_url}/search",
                params={'keyword': keyword},
                headers=headers,
                timeout=10
            )
            
            return response.json()
            
        except Exception as e:
            logger.error(f"阿里云盘搜索API调用失败: {e}")
            return {'code': 500, 'message': f'搜索失败: {str(e)}'}


# 全局搜索服务实例
search_service = SearchService()

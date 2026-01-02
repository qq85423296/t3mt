# -*- coding: utf-8 -*-
"""
影视解析服务
用于通过第三方API解析影视真实下载地址
"""
import os
import requests
from typing import Dict, Optional
from config import Config
from models.config import ConfigModel
from utils.logger import logger


class VideoParseService:
    """影视解析服务类"""
    
    def __init__(self):
        # 影视解析超时时间(秒)
        self.timeout = 30
        # 延迟导入，避免循环依赖
        self._mango_service = None
        self._tencent_service = None
        self._iqiyi_service = None
        self._youku_service = None
    
    @property
    def mango_service(self):
        """懒加载芒果TV服务"""
        if self._mango_service is None:
            from services.mango_service import mango_service
            self._mango_service = mango_service
        return self._mango_service
    
    @property
    def tencent_service(self):
        """懒加载腾讯视频服务"""
        if self._tencent_service is None:
            from services.tencent_service import tencent_service
            self._tencent_service = tencent_service
        return self._tencent_service
    
    @property
    def iqiyi_service(self):
        """懒加载爱奇艺服务"""
        if self._iqiyi_service is None:
            from services.iqiyi_service import iqiyi_service
            self._iqiyi_service = iqiyi_service
        return self._iqiyi_service
    
    @property
    def youku_service(self):
        """懒加载优酷服务"""
        if self._youku_service is None:
            from services.youku_service import youku_service
            self._youku_service = youku_service
        return self._youku_service
    
    def detect_platform(self, url: str) -> str:
        """
        根据URL自动识别平台
        
        Args:
            url: 官网地址
            
        Returns:
            平台标识: 'mango'、'tencent'、'iqiyi' 或 'youku'
        """
        if 'mgtv.com' in url:
            return 'mango'
        elif 'qq.com' in url or 'v.qq.com' in url:
            return 'tencent'
        elif 'iqiyi.com' in url:
            return 'iqiyi'
        elif 'youku.com' in url:
            return 'youku'
        else:
            # 默认返回芒果TV
            logger.warning(f"无法识别平台: {url}，默认使用芒果TV")
            return 'mango'
    
    def read_website(self, url: str, platform: str = None) -> Dict:
        """
        读取官网地址，获取影视信息和剧集列表
        支持自动识别平台或手动指定平台
        
        Args:
            url: 官网地址
            platform: 平台标识（可选），如果不指定则自动识别
            
        Returns:
            包含影视信息和剧集列表的字典
        """
        # 如果没有指定平台，自动识别
        if not platform:
            platform = self.detect_platform(url)
        
        logger.info(f"读取官网信息，平台: {platform}, URL: {url}")
        
        # 根据平台调用对应的服务
        if platform == 'tencent':
            return self.tencent_service.read_website(url)
        elif platform == 'iqiyi':
            return self.iqiyi_service.read_website(url)
        elif platform == 'youku':
            return self.youku_service.read_website(url)
        else:
            return self.mango_service.read_website(url)
    
    def _get_config(self):
        """从数据库获取解析配置(支持多接口)"""
        apis = []
        
        # 1. 首先添加加密配置中的默认接口
        try:
            from utils.config_crypto import config_crypto
            default_api = config_crypto.get_config('video_parse.default_parse_api', {})
            if default_api and default_api.get('api_url'):
                apis.append({
                    'api_url': default_api['api_url'],
                    'url_path': default_api.get('url_path', 'final_url'),
                    'code_path': default_api.get('code_path', 'code'),
                    'success_code': default_api.get('success_code', '200'),
                    'is_default': True
                })
                logger.info(f"已加载默认解析接口")
        except Exception as e:
            logger.warning(f"加载默认解析接口失败: {e}")
        
        # 2. 然后添加用户自定义的接口
        user_apis = ConfigModel.get_config_list('video_parse_apis')
        if user_apis and len(user_apis) > 0:
            apis.extend(user_apis)
        
        return apis if len(apis) > 0 else []
    
    def _get_nested_value(self, data: dict, path: str, default=None):
        """
        从嵌套字典中获取值
        支持两种路径格式：
        1. 点号分隔：data.url
        2. 箭头分隔：data->url
        
        Args:
            data: 字典数据
            path: 路径，如 'url' 或 'data.url' 或 'data->url'
            default: 默认值
            
        Returns:
            获取到的值或默认值
        """
        if not path:
            return default
        
        # 支持两种分隔符
        if '->' in path:
            keys = path.split('->')
        else:
            keys = path.split('.')
        
        value = data
        
        for key in keys:
            key = key.strip()  # 去除空格
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def parse_video_url(self, video_url: str) -> Dict:
        """
        解析影视地址,获取真实下载地址
        支持多接口自动故障转移:第一个接口失败自动尝试下一个
        
        Args:
            video_url: 影视官网地址（如芒果TV地址）
            
        Returns:
            包含解析结果的字典
            {
                'success': True/False,
                'title': '剧集标题',
                'download_url': '真实下载地址',
                'type': 'hls/mp4',
                'message': '消息',
                'used_api_index': 使用的接口索引
            }
        """
        # 获取所有配置的接口
        apis = self._get_config()
        
        if not apis or len(apis) == 0:
            logger.error("未配置解析接口")
            return {
                'success': False,
                'message': '未配置解析接口'
            }
        
        logger.info(f"开始解析影视地址: {video_url}, 共有 {len(apis)} 个接口可用")
        
        # 记录所有接口的错误信息
        all_errors = []
        
        # 按顺序尝试每个接口
        for index, api_config in enumerate(apis):
            api_url = api_config.get('api_url', '')
            url_path = api_config.get('url_path', 'final_url')
            code_path = api_config.get('code_path', 'code')
            success_code = api_config.get('success_code', '200')
            
            # 转换success_code类型
            if isinstance(success_code, str):
                try:
                    success_code = int(success_code)
                except:
                    pass
            
            if not api_url:
                logger.warning(f"接口 #{index+1} 配置不完整,跳过")
                all_errors.append(f"接口 #{index+1}: 配置不完整")
                continue
            
            try:
                # 构建完整URL
                full_url = f"{api_url}{video_url}"
                
                logger.info(f"尝试接口 #{index+1}: {api_url}")
                logger.info(f"配置 - 下载地址路径: {url_path}, 状态码路径: {code_path}, 成功状态码: {success_code}")
                
                # 配置代理（如果环境变量中有配置）
                proxies = None
                http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
                https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
                if http_proxy or https_proxy:
                    proxies = {
                        'http': http_proxy,
                        'https': https_proxy
                    }
                
                # 发送请求
                response = requests.get(
                    full_url,
                    timeout=self.timeout,
                    proxies=proxies
                )
                
                # 检查HTTP状态码
                if response.status_code >= 500:
                    error_msg = f"接口 #{index+1} 返回服务器错误: HTTP {response.status_code}"
                    logger.warning(error_msg)
                    all_errors.append(error_msg)
                    # 500错误,尝试下一个接口
                    continue
                
                response.raise_for_status()
                
                # 解析响应
                data = response.json()
                logger.info(f"接口 #{index+1} 响应: {data}")
                
                # 根据配置的路径提取数据
                code = self._get_nested_value(data, code_path)
                
                # 比较状态码（支持字符串和数字）
                code_match = False
                if isinstance(success_code, int):
                    code_match = (code == success_code or str(code) == str(success_code))
                else:
                    code_match = (str(code) == str(success_code))
                
                if code_match:
                    download_url = self._get_nested_value(data, url_path)
                    
                    if not download_url:
                        error_msg = f"接口 #{index+1} 未找到下载地址（路径: {url_path}）"
                        logger.warning(error_msg)
                        all_errors.append(error_msg)
                        # 尝试下一个接口
                        continue
                    
                    # 解析成功
                    result = {
                        'success': True,
                        'title': self._get_nested_value(data, 'title', ''),
                        'download_url': download_url,
                        'type': self._get_nested_value(data, 'type', 'unknown'),
                        'message': f'解析成功（使用接口 #{index+1}）',
                        'used_api_index': index,
                        'raw_data': data
                    }
                    
                    logger.info(f"✓ 接口 #{index+1} 解析成功: {video_url} -> {download_url}")
                    return result
                else:
                    message = self._get_nested_value(data, 'msg', self._get_nested_value(data, 'message', '解析失败'))
                    error_msg = f"接口 #{index+1} 状态码不匹配 (期望: {success_code}, 实际: {code}): {message}"
                    logger.warning(error_msg)
                    all_errors.append(error_msg)
                    # 尝试下一个接口
                    continue
                    
            except requests.Timeout:
                error_msg = f"接口 #{index+1} 请求超时"
                logger.warning(error_msg)
                all_errors.append(error_msg)
                # 超时,尝试下一个接口
                continue
                
            except requests.RequestException as e:
                error_msg = f"接口 #{index+1} 请求失败: {str(e)}"
                logger.warning(error_msg)
                all_errors.append(error_msg)
                # 请求失败,尝试下一个接口
                continue
                
            except Exception as e:
                error_msg = f"接口 #{index+1} 解析异常: {str(e)}"
                logger.warning(error_msg)
                all_errors.append(error_msg)
                # 异常,尝试下一个接口
                continue
        
        # 所有接口都失败了
        error_summary = '; '.join(all_errors)
        logger.error(f"所有解析接口均失败: {video_url}")
        logger.error(f"错误汇总: {error_summary}")
        
        return {
            'success': False,
            'message': f'所有解析接口均失败。{error_summary}',
            'errors': all_errors
        }
    
    def parse_episode(self, episode_url: str, episode_name: str = '') -> Dict:
        """
        解析单集地址
        
        Args:
            episode_url: 单集官网地址
            episode_name: 集数名称（用于日志）
            
        Returns:
            解析结果
        """
        logger.info(f"解析剧集: {episode_name} - {episode_url}")
        return self.parse_video_url(episode_url)
    
    def batch_parse_episodes(self, episodes: list) -> Dict:
        """
        批量解析剧集
        
        Args:
            episodes: 剧集列表，每个元素包含 url 和 name
            
        Returns:
            批量解析结果
            {
                'success': True/False,
                'total': 总数,
                'success_count': 成功数,
                'failed_count': 失败数,
                'results': [解析结果列表]
            }
        """
        results = []
        success_count = 0
        failed_count = 0
        
        for episode in episodes:
            url = episode.get('url', '')
            name = episode.get('name', '')
            
            if not url:
                failed_count += 1
                results.append({
                    'name': name,
                    'success': False,
                    'message': '缺少URL'
                })
                continue
            
            result = self.parse_episode(url, name)
            result['name'] = name
            result['original_url'] = url
            
            if result.get('success'):
                success_count += 1
            else:
                failed_count += 1
            
            results.append(result)
        
        return {
            'success': success_count > 0,
            'total': len(episodes),
            'success_count': success_count,
            'failed_count': failed_count,
            'results': results
        }


# 创建全局实例
video_parse_service = VideoParseService()

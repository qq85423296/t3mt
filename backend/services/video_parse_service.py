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
            平台标识: 'mango'、'tencent'、'iqiyi'、'youku' 或 'unknown'
        """
        url_lower = url.lower()
        
        if 'mgtv.com' in url_lower:
            logger.info(f"识别平台为芒果TV: {url}")
            return 'mango'
        elif '.qq.com' in url_lower:
            logger.info(f"识别平台为腾讯视频: {url}")
            return 'tencent'
        elif '.iqiyi.com' in url_lower:
            logger.info(f"识别平台为爱奇艺: {url}")
            return 'iqiyi'
        elif '.youku.com' in url_lower:
            logger.info(f"识别平台为优酷: {url}")
            return 'youku'
        else:
            # 返回unknown而不是默认值
            logger.warning(f"无法识别平台: {url}，不支持的平台")
            return 'unknown'
    
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
        
        # 验证平台是否支持
        if platform == 'unknown':
            logger.error(f"不支持的平台: {url}")
            return {
                'success': False,
                'error': '目前仅支持腾讯、爱奇艺、优酷、芒果平台'
            }
        
        logger.info(f"读取官网信息，平台: {platform}, URL: {url}")
        
        # 根据平台调用对应的服务
        if platform == 'tencent':
            result = self.tencent_service.read_website(url)
        elif platform == 'iqiyi':
            result = self.iqiyi_service.read_website(url)
        elif platform == 'youku':
            result = self.youku_service.read_website(url)
        else:
            result = self.mango_service.read_website(url)
        
        # 在返回结果前，添加视频类型识别
        if result.get('success'):
            video_info = result.get('video_info', {})
            video_type = self.detect_video_type(platform, video_info)
            result['video_type'] = video_type
            logger.info(f"识别视频类型: {video_type}")
        
        return result
    
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
                
                logger.info(f"尝试接口 #{index+1}: {'默认接口' if api_config.get('is_default') else '自定义接口'}")
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
    
    def detect_video_type(self, platform: str, video_info: Dict) -> str:
        """
        根据平台和视频信息识别视频类型
        
        Args:
            platform: 平台标识 ('mango', 'tencent', 'iqiyi', 'youku')
            video_info: 视频信息字典
            
        Returns:
            视频类型: '电视剧', '电影', '综艺', '动漫', '其他'
        """
        logger.info(f"开始识别视频类型，平台: {platform}")
        
        if platform == 'tencent':
            return self._detect_tencent_type(video_info)
        elif platform == 'iqiyi':
            return self._detect_iqiyi_type(video_info)
        elif platform == 'mango':
            return self._detect_mango_type(video_info)
        elif platform == 'youku':
            return self._detect_youku_type(video_info)
        else:
            logger.warning(f"未知平台: {platform}, 使用默认类型")
            return '其他'
    
    def _detect_tencent_type(self, video_info: Dict) -> str:
        """
        识别腾讯视频类型
        基于businessInfo.video_category字段
        1=电影, 2=电视剧, 3=综艺, 4=动漫
        
        Args:
            video_info: 视频信息字典
            
        Returns:
            视频类型
        """
        try:
            business_info = video_info.get('businessInfo', {})
            
            # 处理businessInfo可能是JSON字符串的情况
            if isinstance(business_info, str):
                import json
                business_info = json.loads(business_info)
            
            video_category = business_info.get('video_category')
            
            # 类型映射
            type_mapping = {
                1: '电影',
                2: '电视剧',
                3: '综艺',
                4: '动漫'
            }
            
            video_type = type_mapping.get(video_category, '其他')
            logger.info(f"腾讯视频类型识别: category={video_category}, type={video_type}")
            return video_type
            
        except Exception as e:
            logger.warning(f"腾讯视频类型识别失败: {str(e)}, 使用默认类型")
            return '其他'
    
    def _detect_iqiyi_type(self, video_info: Dict) -> str:
        """
        识别爱奇艺视频类型
        基于channelId字段: 1=电影, 2=电视剧, 4=动漫, 6=综艺
        
        Args:
            video_info: 视频信息字典
            
        Returns:
            视频类型
        """
        try:
            channel_id = video_info.get('channelId')
            
            # 类型映射
            type_mapping = {
                1: '电影',
                2: '电视剧',
                4: '动漫',
                6: '综艺'
            }
            
            video_type = type_mapping.get(channel_id, '其他')
            logger.info(f"爱奇艺类型识别: channelId={channel_id}, type={video_type}")
            return video_type
                
        except Exception as e:
            logger.warning(f"爱奇艺类型识别失败: {str(e)}, 使用默认类型")
            return '其他'
    
    def _detect_mango_type(self, video_info: Dict) -> str:
        """
        识别芒果TV视频类型
        基于type和kind字段
        
        Args:
            video_info: 视频信息字典
            
        Returns:
            视频类型
        """
        try:
            type_str = video_info.get('type', '').lower()
            kind_str = video_info.get('kind', '').lower()
            
            # 合并两个字段进行匹配
            combined = f"{type_str} {kind_str}"
            
            if '电视剧' in combined or '剧集' in combined:
                logger.info(f"芒果TV类型识别: type={type_str}, kind={kind_str}, result=电视剧")
                return '电视剧'
            elif '电影' in combined:
                logger.info(f"芒果TV类型识别: type={type_str}, kind={kind_str}, result=电影")
                return '电影'
            elif '综艺' in combined:
                logger.info(f"芒果TV类型识别: type={type_str}, kind={kind_str}, result=综艺")
                return '综艺'
            elif '动漫' in combined or '动画' in combined:
                logger.info(f"芒果TV类型识别: type={type_str}, kind={kind_str}, result=动漫")
                return '动漫'
            else:
                logger.warning(f"芒果TV类型无法识别: type={type_str}, kind={kind_str}, 使用默认类型")
                return '其他'
                
        except Exception as e:
            logger.warning(f"芒果TV类型识别失败: {str(e)}, 使用默认类型")
            return '其他'
    
    def _detect_youku_type(self, video_info: Dict) -> str:
        """
        识别优酷视频类型
        基于category和show_type字段
        
        Args:
            video_info: 视频信息字典
            
        Returns:
            视频类型
        """
        try:
            category = video_info.get('category', '').lower()
            show_type = video_info.get('show_type', '').lower()
            
            # 合并两个字段进行匹配
            combined = f"{category} {show_type}"
            
            if '电视剧' in combined or '剧集' in combined:
                logger.info(f"优酷类型识别: category={category}, show_type={show_type}, result=电视剧")
                return '电视剧'
            elif '电影' in combined:
                logger.info(f"优酷类型识别: category={category}, show_type={show_type}, result=电影")
                return '电影'
            elif '综艺' in combined:
                logger.info(f"优酷类型识别: category={category}, show_type={show_type}, result=综艺")
                return '综艺'
            elif '动漫' in combined or '动画' in combined:
                logger.info(f"优酷类型识别: category={category}, show_type={show_type}, result=动漫")
                return '动漫'
            else:
                logger.warning(f"优酷类型无法识别: category={category}, show_type={show_type}, 使用默认类型")
                return '其他'
                
        except Exception as e:
            logger.warning(f"优酷类型识别失败: {str(e)}, 使用默认类型")
            return '其他'
    
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

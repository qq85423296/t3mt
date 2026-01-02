# -*- coding: utf-8 -*-
"""
优酷服务
用于读取优酷影视信息和剧集列表
"""
import re
import requests
from typing import Dict, List, Optional
from utils.logger import logger
from utils.config_crypto import config_crypto


class YoukuService:
    """优酷服务类"""
    
    def __init__(self):
        # 从加密配置中获取优酷API配置
        self.config = config_crypto.get_config('video_parse.youku', {})
        
        # 如果配置未加载,抛出错误
        if not self.config or not self.config.get('enabled'):
            logger.error("优酷配置未加载或未启用")
            raise RuntimeError("优酷服务配置缺失,请联系管理员")
        
        self.client_id = self.config.get('client_id')
        self.api_url = self.config.get('api_url')
        self.base_url = self.config.get('base_url')
        
        self.headers = {
            'User-Agent': self.config.get('user_agent'),
            'Referer': self.base_url + '/'
        }
    
    def extract_video_id_from_url(self, url: str) -> Optional[str]:
        """
        从官网地址提取video_id
        例如: http://v.youku.com/v_show/id_XNjUwODQwNDg5Ng==.html -> XNjUwODQwNDg5Ng==
        """
        try:
            # 模式1: /id_XXX.html
            match = re.search(r'/id_([^/.]+)', url)
            if match:
                video_id = match.group(1)
                logger.info(f"从URL中提取到video_id: {video_id}")
                return video_id
            
            # 模式2: video_id=XXX
            match = re.search(r'video_id=([^&]+)', url)
            if match:
                video_id = match.group(1)
                logger.info(f"从URL参数中提取到video_id: {video_id}")
                return video_id
            
            logger.error(f"无法从URL中提取video_id: {url}")
            return None
            
        except Exception as e:
            logger.error(f"提取video_id失败: {str(e)}")
            return None
    
    def get_video_info(self, video_id: str) -> Dict:
        """
        获取视频详细信息
        
        Args:
            video_id: 视频ID
            
        Returns:
            包含视频信息的字典
        """
        # 使用加密配置中的API地址
        url = f"{self.api_url}/videos/show.json"
        params = {
            'video_id': video_id,
            'client_id': self.client_id,
            'ext': 'show'
        }
        
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'error' in data:
                return {
                    'success': False,
                    'error': data.get('error_description', '获取视频信息失败')
                }
            
            # 提取show信息
            show_info = data.get('show', {})
            
            return {
                'success': True,
                'video_id': data.get('id', ''),
                'title': data.get('title', ''),
                'show_id': show_info.get('id', ''),
                'show_name': show_info.get('name', ''),
                'show_link': show_info.get('link', ''),
                'show_type': show_info.get('type', ''),
                'show_seq': show_info.get('seq', ''),
                'show_stage': show_info.get('stage', ''),
                'paid': show_info.get('paid', 0),
                'pay_type': show_info.get('pay_type', []),
                'thumbnail': data.get('thumbnail', ''),
                'big_thumbnail': data.get('bigThumbnail', ''),
                'duration': data.get('duration', ''),
                'category': data.get('category', ''),
                'description': data.get('description', ''),
                'published': data.get('published', ''),
                'user': data.get('user', {}),
                'view_count': data.get('view_count', 0)
            }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }
    
    def get_show_videos(self, show_id: str, page: int = 1, count: int = 100) -> Dict:
        """
        获取剧集列表
        
        Args:
            show_id: 剧集ID
            page: 页码
            count: 每页数量
            
        Returns:
            包含剧集列表的字典
        """
        # 使用加密配置中的API地址
        url = f"{self.api_url}/shows/videos.json"
        params = {
            'show_id': show_id,
            'show_videotype': '正片',
            'client_id': self.client_id,
            'page': page,
            'count': count,
            'package': 'com.huawei.hwvplayer.youku'
        }
        
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'error' in data:
                return {
                    'success': False,
                    'error': data.get('error_description', '获取剧集列表失败')
                }
            
            videos = data.get('videos', [])
            total = int(data.get('total', 0))
            
            # 解析剧集信息
            episodes = []
            for video in videos:
                # 只保留正常状态的视频
                if video.get('state') not in ['normal', 'limited']:
                    continue
                
                # 提取集数
                seq = video.get('seq', '')
                stage = video.get('stage', '')
                episode_name = f"第{seq}集" if seq else f"第{stage}集"
                
                # 提取副标题
                rc_title = video.get('rc_title', '')
                
                # 判断是否VIP
                is_vip = video.get('paid', 0) == 1
                
                episodes.append({
                    'name': episode_name,  # 集数名称，统一格式为"第X集"
                    'title': rc_title,  # 集标题
                    'url': video.get('link', ''),  # 播放页面URL
                    'video_id': video.get('id', ''),
                    'duration': video.get('duration', ''),  # 时长（秒）
                    'is_vip': is_vip,
                    'image': video.get('thumbnail', ''),
                    'big_image': video.get('bigthumbnail', ''),
                    'published': video.get('published', ''),
                    'seq': seq,
                    'stage': stage,
                    'state': video.get('state', '')
                })
            
            return {
                'success': True,
                'episodes': episodes,
                'total': total
            }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }
    
    def get_all_show_videos(self, show_id: str) -> Dict:
        """
        获取所有剧集（自动处理分页）
        
        Args:
            show_id: 剧集ID
            
        Returns:
            包含所有剧集的字典
        """
        all_episodes = []
        page = 1
        count = 100  # 每页100条
        
        while True:
            logger.info(f"获取优酷剧集列表，show_id: {show_id}, 页码: {page}")
            
            result = self.get_show_videos(show_id, page=page, count=count)
            
            if not result.get('success'):
                # 如果第一页就失败，返回错误
                if page == 1:
                    return result
                # 如果不是第一页失败，返回已获取的数据
                break
            
            episodes = result.get('episodes', [])
            total = result.get('total', 0)
            
            if not episodes:
                break
            
            all_episodes.extend(episodes)
            
            logger.info(f"第{page}页获取到 {len(episodes)} 集，累计 {len(all_episodes)} 集")
            
            # 如果已获取的剧集数量达到总数，停止
            if len(all_episodes) >= total:
                break
            
            # 如果本页获取的数量少于count，说明是最后一页
            if len(episodes) < count:
                break
            
            page += 1
        
        logger.info(f"优酷剧集列表获取完成，共 {len(all_episodes)} 集")
        
        return {
            'success': True,
            'episodes': all_episodes,
            'total': len(all_episodes)
        }
    
    def read_website(self, url: str) -> Dict:
        """
        读取官网地址，获取影视信息和剧集列表
        
        Args:
            url: 优酷官网地址
            
        Returns:
            包含影视信息和剧集列表的字典
        """
        # 提取video_id
        video_id = self.extract_video_id_from_url(url)
        if not video_id:
            return {
                'success': False,
                'error': '无效的优酷地址或无法提取video_id'
            }
        
        logger.info(f"提取到video_id: {video_id}")
        
        # 获取视频信息
        video_info = self.get_video_info(video_id)
        if not video_info.get('success'):
            return video_info
        
        # 检查是否有show_id
        show_id = video_info.get('show_id')
        if not show_id:
            return {
                'success': False,
                'error': '该视频不属于任何剧集'
            }
        
        logger.info(f"提取到show_id: {show_id}")
        
        # 获取所有剧集（自动分页）
        episodes_result = self.get_all_show_videos(show_id)
        if not episodes_result.get('success'):
            return episodes_result
        
        # 构建更新信息
        total = episodes_result.get('total', 0)
        show_content = f"共{total}集"
        
        # 检查是否有付费信息
        update_strategy = ''
        if video_info.get('paid') == 1:
            pay_types = video_info.get('pay_type', [])
            if 'mon' in pay_types:
                update_strategy = 'VIP会员观看'
        
        # 合并结果
        return {
            'success': True,
            'video_info': {
                'title': video_info.get('show_name') or video_info.get('title'),
                'show_name': video_info.get('show_name'),
                'show_id': show_id,
                'category': video_info.get('category'),
                'description': video_info.get('description'),
                'thumbnail': video_info.get('big_thumbnail') or video_info.get('thumbnail'),
                'album_image_url': video_info.get('big_thumbnail') or video_info.get('thumbnail'),
                'published': video_info.get('published'),
                'video_count': total,
                'show_content': show_content,
                'update_strategy': update_strategy,
                'paid': video_info.get('paid', 0),
                'view_count': video_info.get('view_count', 0)
            },
            'episodes': episodes_result['episodes'],
            'total_episodes': total,
            'platform': 'youku'  # 返回平台标识
        }


# 全局实例(延迟初始化)
_youku_service = None

def get_youku_service():
    """获取优酷服务实例(单例模式)"""
    global _youku_service
    if _youku_service is None:
        _youku_service = YoukuService()
    return _youku_service

class _YoukuServiceProxy:
    def __getattr__(self, name):
        return getattr(get_youku_service(), name)

youku_service = _YoukuServiceProxy()

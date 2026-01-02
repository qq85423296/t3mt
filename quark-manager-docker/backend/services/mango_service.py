# -*- coding: utf-8 -*-
"""
芒果TV服务
用于读取芒果TV影视信息和剧集列表
"""
import re
import requests
from typing import Dict, List, Optional
from utils.logger import logger
from utils.config_crypto import config_crypto


class MangoService:
    """芒果TV服务类"""
    
    def __init__(self):
        # 从加密配置中获取芒果TV API配置
        self.config = config_crypto.get_config('video_parse.mango', {})
        
        # 配置缺失时抛出错误,不提供默认值
        if not self.config:
            error_msg = "芒果TV配置未加载,请联系管理员获取配置"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 验证必需的配置项
        required_keys = ['base_url', 'api_url', 'user_agent']
        missing_keys = [key for key in required_keys if key not in self.config]
        if missing_keys:
            error_msg = f"芒果TV配置缺少必需项: {', '.join(missing_keys)},请联系管理员"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        self.base_url = self.config['base_url']
        self.api_url = self.config['api_url']
        
        self.headers = {
            'User-Agent': self.config['user_agent'],
            'Referer': self.base_url + '/'
        }
    
    def extract_vid_from_url(self, url: str) -> Optional[str]:
        """
        从官网地址提取vid
        例如: https://www.mgtv.com/b/821148/23953889.html -> 23953889
        """
        pattern = r'/b/\d+/(\d+)\.html'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None
    
    def get_video_info(self, vid: str) -> Dict:
        """
        获取影视详细信息
        
        Args:
            vid: 视频ID
            
        Returns:
            包含影视信息的字典
        """
        # 使用加密配置中的API地址
        url = f"{self.api_url}/video/info"
        params = {
            'allowedRC': '1',
            'vid': vid
        }
        
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 200 and data.get('data'):
                info = data['data'].get('info', {})
                detail = info.get('detail', {})
                
                return {
                    'success': True,
                    'title': info.get('title', ''),
                    'clip_name': info.get('clipName', ''),
                    'video_id': info.get('videoId', ''),
                    'clip_id': info.get('clipId', ''),
                    'clip_image': info.get('clipImage', ''),
                    'type': info.get('fstlvlType', ''),
                    'area': detail.get('area', ''),
                    'update_info': detail.get('updateInfo', ''),
                    'leader': detail.get('leader', ''),
                    'play_count': detail.get('playCnt', ''),
                    'kind': detail.get('kind', ''),
                    'language': detail.get('language', ''),
                    'story': detail.get('story', ''),
                    'desc': info.get('desc', ''),
                    'release_time': detail.get('releaseTime', ''),
                    'director': detail.get('director', '')
                }
            else:
                return {
                    'success': False,
                    'error': data.get('msg', '获取影视信息失败')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }
    
    def get_episode_list(self, video_id: str, page: int = 1, size: int = 30) -> Dict:
        """
        获取剧集列表
        
        Args:
            video_id: 视频ID
            page: 页码
            size: 每页数量
            
        Returns:
            包含剧集列表的字典
        """
        # 使用加密配置中的API地址
        url = f"{self.api_url}/episode/list"
        params = {
            'version': '5.5.35',
            'video_id': video_id,
            'page': page,
            'size': size,
            'platform': '4',
            'src': 'mgtv'
        }
        
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 200 and data.get('data'):
                result_data = data['data']
                episode_list = result_data.get('list', [])
                
                # 解析剧集信息
                episodes = []
                for ep in episode_list:
                    # 跳过预告片（isIntact=3表示预告）
                    if ep.get('isIntact') == '3':
                        continue
                    
                    # 获取标题用于过滤
                    title = ep.get('t2', '')
                    
                    # 过滤预告片/花絮关键词
                    # 只根据标题关键词判断，不使用时长判断（因为有些正片本身就很短）
                    preview_keywords = [
                        '幕后', '纪录片', '畅谈', '揭秘', '挑战', '先导', 
                        '花絮', '特辑', '预告', '片花', '采访', '访谈',
                        '拍摄', '制作', '幕后花絮', '独家', '精彩看点',
                        '绕口令', '憋笑', '爆改', '劝和', '命题', '看点',
                        '彩蛋', '番外', '剧透', '解说', '盘点', '合集'
                    ]
                    
                    # 检查标题是否包含预告关键词
                    is_preview = any(keyword in title for keyword in preview_keywords)
                    
                    # 如果是预告片，跳过
                    if is_preview:
                        continue
                    
                    episodes.append({
                        'name': ep.get('t4', ''),  # 集数名称
                        'title': ep.get('t2', ''),  # 集标题
                        'url': f"{self.base_url}{ep.get('url', '')}",  # 完整URL
                        'video_id': ep.get('video_id', ''),
                        'time': ep.get('time', ''),  # 时长
                        'update_time': ep.get('ts', ''),  # 更新时间
                        'is_vip': ep.get('isvip', '0') == '1',  # 是否VIP
                        'image': ep.get('img', ''),
                        'play_count': ep.get('playcnt', '')
                    })
                
                return {
                    'success': True,
                    'episodes': episodes,
                    'total': result_data.get('count', 0),
                    'total_page': result_data.get('total_page', 1),
                    'current_page': result_data.get('current_page', 1),
                    'info': result_data.get('info', {})
                }
            else:
                return {
                    'success': False,
                    'error': data.get('msg', '获取剧集列表失败')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }
    
    def get_all_episodes(self, video_id: str) -> Dict:
        """
        获取所有剧集（自动处理分页）
        
        Args:
            video_id: 视频ID
            
        Returns:
            包含所有剧集的字典
        """
        all_episodes = []
        page = 1
        
        # 获取第一页
        result = self.get_episode_list(video_id, page=page)
        if not result.get('success'):
            return result
        
        all_episodes.extend(result['episodes'])
        total_page = result['total_page']
        
        # 如果有多页，继续获取
        while page < total_page:
            page += 1
            result = self.get_episode_list(video_id, page=page)
            if result.get('success'):
                all_episodes.extend(result['episodes'])
            else:
                break
        
        return {
            'success': True,
            'episodes': all_episodes,
            'total': len(all_episodes),
            'info': result.get('info', {})
        }
    
    def read_website(self, url: str) -> Dict:
        """
        读取官网地址，获取影视信息和剧集列表
        
        Args:
            url: 芒果TV官网地址
            
        Returns:
            包含影视信息和剧集列表的字典
        """
        # 提取vid
        vid = self.extract_vid_from_url(url)
        if not vid:
            return {
                'success': False,
                'error': '无效的芒果TV地址'
            }
        
        # 获取影视信息
        video_info = self.get_video_info(vid)
        if not video_info.get('success'):
            return video_info
        
        # 获取所有剧集
        episodes_result = self.get_all_episodes(vid)
        if not episodes_result.get('success'):
            return episodes_result
        
        # 合并结果
        return {
            'success': True,
            'video_info': video_info,
            'episodes': episodes_result['episodes'],
            'total_episodes': episodes_result['total'],
            'platform': 'mango'  # 返回平台标识
        }


# 全局实例(延迟初始化)
_mango_service = None

def get_mango_service():
    """获取芒果TV服务实例(单例模式)"""
    global _mango_service
    if _mango_service is None:
        _mango_service = MangoService()
    return _mango_service

# 为了兼容性,保留原有的访问方式
class _MangoServiceProxy:
    def __getattr__(self, name):
        return getattr(get_mango_service(), name)

mango_service = _MangoServiceProxy()

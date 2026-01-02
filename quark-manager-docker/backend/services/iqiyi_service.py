# -*- coding: utf-8 -*-
"""
爱奇艺服务
用于读取爱奇艺影视信息和剧集列表
"""
import re
import requests
from typing import Dict, List, Optional
from utils.logger import logger
from utils.config_crypto import config_crypto


class IqiyiService:
    """爱奇艺服务类"""
    
    def __init__(self):
        # 从加密配置中获取爱奇艺API配置
        self.config = config_crypto.get_config('video_parse.iqiyi', {})
        
        # 如果配置未加载,抛出错误,不提供默认值
        if not self.config or not self.config.get('enabled'):
            logger.error("爱奇艺配置未加载或未启用,无法使用爱奇艺服务")
            raise RuntimeError("爱奇艺服务配置缺失,请联系管理员")
        
        self.headers = {
            'User-Agent': self.config.get('user_agent'),
            'Referer': self.config.get('base_url') + '/'
        }
        
        self.base_url = self.config.get('base_url')
        self.miniapp_api = self.config.get('miniapp_api')
        self.accelerator_js = self.config.get('accelerator_js')
    
    def extract_tvid_from_url(self, url: str) -> Optional[str]:
        """
        从官网地址提取tvid
        方法1: 直接从URL中提取（如果URL包含tvid参数）
        方法2: 请求accelerator.js获取tvid
        方法3: 请求页面，从JavaScript中提取tvid
        
        例如: https://www.iqiyi.com/v_1o68nz8spzc.html
        """
        try:
            # 方法1: 尝试从URL参数中提取
            if 'tvid=' in url:
                match = re.search(r'tvid=(\d+)', url)
                if match:
                    tvid = match.group(1)
                    logger.info(f"从URL参数中提取到tvid: {tvid}")
                    return tvid
            
            # 方法2: 根据文档，先请求accelerator.js获取tvid
            logger.info(f"尝试从accelerator.js获取tvid: {url}")
            try:
                # 构建accelerator.js的URL(从加密配置获取)
                js_url = f"{self.accelerator_js}?apiVer=3&lwaver=14.011.24181&appver=14.011.24181"
                
                # 设置Referer为视频页面
                js_headers = self.headers.copy()
                js_headers['Referer'] = url
                
                js_response = requests.get(js_url, headers=js_headers, timeout=10)
                js_response.raise_for_status()
                
                js_content = js_response.text
                
                # 从JS内容中提取tvid
                # 查找 window.QiyiPlayerProphetData = {"tvid":6125839769481700
                match = re.search(r'window\.QiyiPlayerProphetData\s*=\s*\{[^}]*["\']tvid["\']\s*:\s*(\d+)', js_content)
                if match:
                    tvid = match.group(1)
                    logger.info(f"从accelerator.js中提取到tvid: {tvid}")
                    return tvid
            except Exception as e:
                logger.warning(f"从accelerator.js提取tvid失败: {str(e)}")
            
            # 方法3: 请求页面获取JavaScript中的tvid
            logger.info(f"请求爱奇艺页面获取tvid: {url}")
            
            # 请求页面
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            page_content = response.text
            
            # 尝试多种模式提取tvid
            patterns = [
                # 模式1: window.QiyiPlayerProphetData = {"tvid":6125839769481700
                r'window\.QiyiPlayerProphetData\s*=\s*\{[^}]*["\']tvid["\']\s*:\s*(\d+)',
                # 模式2: "tvId":6125839769481700
                r'["\']tvId["\']\s*:\s*(\d+)',
                # 模式3: tvid:6125839769481700
                r'tvid\s*:\s*(\d+)',
                # 模式4: data-player-tvid="6125839769481700"
                r'data-player-tvid\s*=\s*["\'](\d+)["\']',
                # 模式5: tvId=6125839769481700
                r'tvId\s*=\s*["\']?(\d+)["\']?',
                # 模式6: "tvid":"6125839769481700"
                r'["\']tvid["\']\s*:\s*["\'](\d+)["\']',
                # 模式7: param['tvid'] = 6125839769481700
                r'param\[["\']tvid["\']\]\s*=\s*["\']?(\d+)["\']?',
                # 模式8: tvid = "6125839769481700"
                r'tvid\s*=\s*["\'](\d+)["\']'
            ]
            
            for i, pattern in enumerate(patterns, 1):
                match = re.search(pattern, page_content, re.IGNORECASE)
                if match:
                    tvid = match.group(1)
                    logger.info(f"使用模式{i}从页面中提取到tvid: {tvid}")
                    return tvid
            
            # 如果所有模式都失败，尝试查找页面中所有的数字ID（作为最后的尝试）
            # 查找类似 6125839769481700 这样的长数字（通常tvid是13-16位）
            long_numbers = re.findall(r'\b(\d{13,16})\b', page_content)
            if long_numbers:
                # 取第一个找到的长数字
                tvid = long_numbers[0]
                logger.warning(f"使用备用方法提取到可能的tvid: {tvid}")
                return tvid
            
            logger.error(f"无法从页面中提取tvid，尝试的所有模式都失败")
            # 输出页面的前1000个字符用于调试
            logger.debug(f"页面内容前1000字符: {page_content[:1000]}")
            return None
            
        except requests.Timeout:
            logger.error(f"请求超时: {url}")
            return None
        except requests.RequestException as e:
            logger.error(f"请求失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"提取tvid失败: {str(e)}", exc_info=True)
            return None
    
    def get_video_info(self, tvid: str) -> Dict:
        """
        获取影视详细信息
        
        Args:
            tvid: 视频ID
            
        Returns:
            包含影视信息的字典
        """
        # 使用加密配置中的API地址
        url = f"{self.miniapp_api}/{tvid}/"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 'A00000' and data.get('data'):
                play_info = data['data'].get('playInfo', {})
                video_list = data['data'].get('videoList', {})
                
                return {
                    'success': True,
                    'title': play_info.get('albumName', ''),
                    'album_id': play_info.get('albumId', ''),
                    'directors': play_info.get('directors', ''),
                    'main_actors': play_info.get('mainActors', ''),
                    'tags': play_info.get('tags', ''),
                    'desc_tags': play_info.get('descTags', []),
                    'video_count': play_info.get('videoCount', 0),
                    'update_strategy': play_info.get('updateStrategy', ''),
                    'album_image_url': play_info.get('albumImageUrl', ''),
                    'latest_video_order': play_info.get('latestVideoOrder', 0),
                    'album_desc': play_info.get('albumDesc', ''),
                    'album_year': play_info.get('albumYear', ''),
                    'is_vip': play_info.get('isVip', False),
                    'hot_num': play_info.get('hotNum', ''),
                    'show_content': video_list.get('showContent', ''),
                    'total_sets': video_list.get('sets', 0),
                    'total_videos': video_list.get('total', 0)
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
    
    def get_episode_list(self, tvid: str) -> Dict:
        """
        获取剧集列表
        
        Args:
            tvid: 视频ID
            
        Returns:
            包含剧集列表的字典
        """
        # 使用加密配置中的API地址
        url = f"{self.miniapp_api}/{tvid}/"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 'A00000' and data.get('data'):
                video_list = data['data'].get('videoList', {})
                videos = video_list.get('videos', [])
                
                # 解析剧集信息
                episodes = []
                for video in videos:
                    # 过滤掉花絮、预告等非正片内容
                    # type=1表示正片，type=3表示花絮/预告
                    if video.get('type') != 1:
                        continue
                    
                    # 检查标题是否包含预告关键词
                    title = video.get('subTitle', '')
                    short_title = video.get('shortTitle', '')
                    
                    preview_keywords = [
                        '幕后', '纪录片', '畅谈', '揭秘', '挑战', '先导', 
                        '花絮', '特辑', '预告', '片花', '采访', '访谈',
                        '拍摄', '制作', '幕后花絮', '独家', '精彩看点',
                        '绕口令', '憋笑', '爆改', '劝和', '命题', '看点',
                        '彩蛋', '番外', '剧透', '解说', '盘点', '合集',
                        '专访', '超前看'
                    ]
                    
                    # 检查标题是否包含预告关键词
                    is_preview = any(keyword in title for keyword in preview_keywords) or \
                                any(keyword in short_title for keyword in preview_keywords)
                    
                    # 如果是预告片，跳过
                    if is_preview:
                        continue
                    
                    # 提取集数，格式化为"第X集"
                    pd = video.get('pd', 0)
                    episode_name = f"第{pd}集"
                    
                    episodes.append({
                        'name': episode_name,  # 集数名称，统一格式为"第X集"
                        'title': title,  # 集标题，如"秦枫目睹胡小跃跳楼"
                        'url': video.get('pageUrl', ''),  # 播放页面URL
                        'video_id': str(video.get('id', '')),
                        'qipu_id': str(video.get('qipuId', '')),
                        'vid': video.get('vid', ''),
                        'duration': video.get('duration', ''),  # 时长
                        'time_length': video.get('timeLength', 0),  # 时长（秒）
                        'is_vip': video.get('payMark') == 1,  # 是否VIP
                        'image': video.get('imageUrl', ''),
                        'period': video.get('period', ''),  # 发布日期
                        'pd': pd  # 集数序号
                    })
                
                # 按集数序号排序
                episodes.sort(key=lambda x: x.get('pd', 0))
                
                return {
                    'success': True,
                    'episodes': episodes,
                    'total': len(episodes)
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
    
    def read_website(self, url: str) -> Dict:
        """
        读取官网地址，获取影视信息和剧集列表
        
        Args:
            url: 爱奇艺官网地址
            
        Returns:
            包含影视信息和剧集列表的字典
        """
        # 提取tvid
        tvid = self.extract_tvid_from_url(url)
        if not tvid:
            return {
                'success': False,
                'error': '无效的爱奇艺地址或无法提取tvid'
            }
        
        logger.info(f"提取到tvid: {tvid}")
        
        # 获取影视信息
        video_info = self.get_video_info(tvid)
        if not video_info.get('success'):
            return video_info
        
        # 获取剧集列表
        episodes_result = self.get_episode_list(tvid)
        if not episodes_result.get('success'):
            return episodes_result
        
        # 合并结果
        return {
            'success': True,
            'video_info': video_info,
            'episodes': episodes_result['episodes'],
            'total_episodes': episodes_result['total'],
            'platform': 'iqiyi'  # 返回平台标识
        }


# 全局实例(延迟初始化)
_iqiyi_service = None

def get_iqiyi_service():
    """获取爱奇艺服务实例(单例模式)"""
    global _iqiyi_service
    if _iqiyi_service is None:
        _iqiyi_service = IqiyiService()
    return _iqiyi_service

class _IqiyiServiceProxy:
    def __getattr__(self, name):
        return getattr(get_iqiyi_service(), name)

iqiyi_service = _IqiyiServiceProxy()

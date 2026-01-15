# -*- coding: utf-8 -*-
"""
爱奇艺服务
用于读取爱奇艺影视信息和剧集列表
"""
import re
import json
import requests
from typing import Dict, List, Optional
from utils.logger import logger
from utils.config_crypto import config_crypto


class IqiyiService:
    """爱奇艺服务类"""
    
    def __init__(self):
        # 从加密配置中获取爱奇艺API配置
        self.config = config_crypto.get_config('video_parse.iqiyi', {})
        
        # 延迟检查配置，不在初始化时抛出异常
        self._config_checked = False
        
        # 如果配置存在，初始化相关属性
        if self.config and self.config.get('enabled'):
            self.headers = {
                'User-Agent': self.config.get('user_agent'),
                'Referer': self.config.get('base_url') + '/'
            }
            
            self.base_url = self.config.get('base_url')
            self.miniapp_api = self.config.get('miniapp_api')
            self.accelerator_js = self.config.get('accelerator_js')
            self._config_checked = True
        else:
            # 配置不存在时，设置为None
            self.headers = None
            self.base_url = None
            self.miniapp_api = None
            self.accelerator_js = None
    
    def _check_config(self):
        """检查配置是否可用，在实际调用方法时才检查"""
        if not self._config_checked:
            logger.error("爱奇艺配置未加载或未启用,无法使用爱奇艺服务")
            raise RuntimeError("爱奇艺服务配置缺失,请联系管理员")
    
    def extract_tvid_from_url(self, url: str) -> Optional[str]:
        """
        从官网地址提取tvid
        方法1: 直接从URL中提取（如果URL包含tvid参数）
        方法2: 请求accelerator.js获取tvid
        方法3: 请求页面，从JavaScript中提取tvid
        
        例如: https://www.iqiyi.com/v_1o68nz8spzc.html
        """
        # 检查配置
        self._check_config()
        
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
        # 检查配置
        self._check_config()
        
        # 使用加密配置中的API地址
        url = f"{self.miniapp_api}/{tvid}/"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 'A00000' and data.get('data'):
                play_info = data['data'].get('playInfo', {})
                video_list = data['data'].get('videoList', {})
                
                # 处理videoList可能是空字符串的情况(电影类型)
                if not isinstance(video_list, dict):
                    video_list = {}
                
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
    
    def get_channel_id_from_mobile(self, url: str) -> Optional[int]:
        """
        从手机版页面获取channelId用于类型识别
        channelId映射: 1=电影, 2=电视剧, 4=动漫, 6=综艺
        
        Args:
            url: 爱奇艺官网地址
            
        Returns:
            channelId或None
        """
        # 检查配置
        self._check_config()
        
        try:
            # 将www替换为m，构建手机版URL
            mobile_url = url.replace('www.iqiyi.com', 'm.iqiyi.com')
            
            logger.info(f"请求手机版页面获取channelId: {mobile_url}")
            
            # 使用手机版User-Agent
            mobile_headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
                'Referer': self.base_url + '/'
            }
            
            # 请求手机版页面
            response = requests.get(mobile_url, headers=mobile_headers, timeout=15)
            response.raise_for_status()
            
            page_content = response.text
            
            # 从页面中提取channelId
            # 查找 "channelId":6 或 "channelId": 6
            match = re.search(r'"channelId"\s*:\s*(\d+)', page_content)
            if match:
                channel_id = int(match.group(1))
                logger.info(f"从手机版页面提取到channelId: {channel_id}")
                return channel_id
            
            logger.warning(f"无法从手机版页面提取channelId")
            return None
            
        except Exception as e:
            logger.warning(f"获取channelId失败: {str(e)}")
            return None
    
    def get_episode_list(self, tvid: str, url: str = None) -> Dict:
        """
        获取剧集列表
        
        Args:
            tvid: 视频ID
            url: 原始URL(用于电影类型返回当前地址)
            
        Returns:
            包含剧集列表的字典
        """
        # 检查配置
        self._check_config()
        
        # 方案A: 尝试使用API获取（支持分页）
        result = self._get_episode_list_from_api(tvid, url)
        
        # 检查数据完整性
        if result.get('success'):
            episodes = result.get('episodes', [])
            expected_count = result.get('expected_count', 0)
            
            # 如果API返回的集数少于预期，尝试使用HTML解析作为备用方案
            if expected_count > 0 and len(episodes) < expected_count:
                logger.warning(f"API返回集数不完整: 期望{expected_count}集，实际{len(episodes)}集，尝试HTML解析")
                
                # 方案B: 使用HTML解析作为备用
                if url:
                    html_result = self._get_episode_list_from_html(url, tvid)
                    if html_result.get('success') and len(html_result.get('episodes', [])) > len(episodes):
                        logger.info(f"HTML解析成功，获取到{len(html_result.get('episodes', []))}集")
                        return html_result
        
        return result
    
    def _get_episode_list_from_api(self, tvid: str, url: str = None) -> Dict:
        """
        从API获取剧集列表（支持按月份获取综艺）
        
        Args:
            tvid: 视频ID
            url: 原始URL(用于电影类型返回当前地址)
            
        Returns:
            包含剧集列表的字典
        """
        # 使用加密配置中的API地址
        api_url = f"{self.miniapp_api}/{tvid}/"
        
        try:
            response = requests.get(api_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 'A00000' and data.get('data'):
                play_info = data['data'].get('playInfo', {})
                video_list = data['data'].get('videoList', {})
                
                # 获取预期的总集数
                expected_count = play_info.get('videoCount', 0)
                
                # 处理videoList可能是空字符串的情况(电影类型)
                if not isinstance(video_list, dict):
                    logger.info("videoList为空或非字典类型,可能是电影类型,返回当前URL作为剧集")
                    
                    # 电影类型:返回当前URL作为唯一剧集
                    if url:
                        episodes = [{
                            'name': '正片',
                            'title': '',
                            'url': url.replace('www.iqiyi.com', 'm.iqiyi.com'),  # 转换为手机版URL
                            'video_id': str(tvid),
                            'qipu_id': str(tvid),
                            'vid': '',
                            'duration': '',
                            'time_length': 0,
                            'is_vip': False,
                            'image': '',
                            'period': '',
                            'pd': 1
                        }]
                        return {
                            'success': True,
                            'episodes': episodes,
                            'total': 1,
                            'expected_count': 1
                        }
                    else:
                        return {
                            'success': True,
                            'episodes': [],
                            'total': 0,
                            'expected_count': 0
                        }
                
                # 获取当前月份的视频
                videos = video_list.get('videos', [])
                
                # 检查是否有summary字段（综艺按月份分组的标志）
                summary = video_list.get('summary', [])
                
                # 如果有summary且集数不完整，说明是综艺，需要按月份获取
                if summary and expected_count > len(videos):
                    logger.info(f"检测到综艺按月份分组，summary: {summary}")
                    videos = self._fetch_all_episodes_by_month(tvid, summary, videos, expected_count)
                # 否则尝试传统分页方式
                elif expected_count > len(videos) and len(videos) > 0:
                    logger.info(f"检测到集数不完整（{len(videos)}/{expected_count}），尝试分页获取")
                    videos = self._fetch_all_episodes_with_pagination(tvid, videos, expected_count)
                
                # 解析剧集信息
                episodes = self._parse_episodes(videos)
                
                # 数据完整性检查
                if expected_count > 0 and len(episodes) < expected_count:
                    logger.warning(f"集数获取不完整: 期望{expected_count}集，实际获取{len(episodes)}集")
                
                return {
                    'success': True,
                    'episodes': episodes,
                    'total': len(episodes),
                    'expected_count': expected_count
                }
            else:
                return {
                    'success': False,
                    'error': data.get('msg', '获取剧集列表失败')
                }
                
        except Exception as e:
            logger.error(f"API获取剧集列表失败: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }
    
    def _fetch_all_episodes_by_month(self, tvid: str, summary: List, initial_videos: List, expected_count: int) -> List:
        """
        按月份获取所有集数（综艺专用）
        使用sdvlist API获取指定年月的视频列表
        
        Args:
            tvid: 视频ID
            summary: 月份摘要列表，格式: [{'year': '2026', 'monthList': ['01']}, ...]
            initial_videos: 初始获取的视频列表（当前月份）
            expected_count: 预期的总集数
            
        Returns:
            完整的视频列表
        """
        all_videos = []
        
        # 首先需要获取albumQipuId
        api_url = f"{self.miniapp_api}/{tvid}/"
        
        try:
            response = requests.get(api_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') != 'A00000' or not data.get('data'):
                logger.error("无法获取albumQipuId")
                return initial_videos
            
            play_info = data['data'].get('playInfo', {})
            
            # 从playInfo中获取albumQipuId
            album_qipu_id = play_info.get('albumQipuId') or play_info.get('albumId')
            
            if not album_qipu_id:
                logger.warning("未找到albumQipuId，无法使用sdvlist API")
                return initial_videos
            
            logger.info(f"获取到albumQipuId: {album_qipu_id}")
            
            # 提取当前已有视频的ID，用于去重
            existing_ids = set()
            
            # 遍历所有年份和月份，使用sdvlist API获取数据
            for year_data in summary:
                year = year_data.get('year')
                month_list = year_data.get('monthList', [])
                
                for month in month_list:
                    logger.info(f"获取月份 {year}-{month} 的视频")
                    
                    # 使用sdvlist API
                    sdvlist_url = f"https://miniapp.iqiyi.com/h5/mina/sdvlist/{album_qipu_id}/{year}/{month}/"
                    
                    try:
                        response = requests.get(sdvlist_url, headers=self.headers, timeout=10)
                        response.raise_for_status()
                        data = response.json()
                        
                        if data.get('code') == 'A00000' and data.get('data'):
                            month_videos = data['data'].get('videos', [])
                            
                            logger.info(f"月份 {year}-{month} 获取到 {len(month_videos)} 个视频")
                            
                            # 添加新视频（去重）
                            new_count = 0
                            for video in month_videos:
                                video_id = video.get('id')
                                if video_id and video_id not in existing_ids:
                                    all_videos.append(video)
                                    existing_ids.add(video_id)
                                    new_count += 1
                            
                            if new_count > 0:
                                logger.info(f"月份 {year}-{month} 新增 {new_count} 个视频，当前总数: {len(all_videos)}")
                        else:
                            logger.warning(f"月份 {year}-{month} 获取失败: {data.get('msg', '未知错误')}")
                            
                    except Exception as e:
                        logger.warning(f"获取月份 {year}-{month} 失败: {str(e)}")
                        continue
            
            logger.info(f"按月份获取完成，共获取 {len(all_videos)} 个视频")
            return all_videos if all_videos else initial_videos
            
        except Exception as e:
            logger.error(f"按月份获取失败: {str(e)}", exc_info=True)
            return initial_videos
    
    def _fetch_all_episodes_with_pagination(self, tvid: str, initial_videos: List, expected_count: int) -> List:
        """
        尝试通过分页获取所有集数
        
        Args:
            tvid: 视频ID
            initial_videos: 初始获取的视频列表
            expected_count: 预期的总集数
            
        Returns:
            完整的视频列表
        """
        all_videos = initial_videos.copy()
        api_url = f"{self.miniapp_api}/{tvid}/"
        
        # 尝试不同的分页参数组合
        pagination_strategies = [
            # 策略1: page + pageSize
            lambda page: {'page': page, 'pageSize': 50},
            # 策略2: pageNum + pageSize
            lambda page: {'pageNum': page, 'pageSize': 50},
            # 策略3: offset + limit
            lambda page: {'offset': page * 50, 'limit': 50},
        ]
        
        for strategy_idx, strategy in enumerate(pagination_strategies):
            logger.info(f"尝试分页策略 {strategy_idx + 1}")
            temp_videos = initial_videos.copy()
            
            # 从第2页开始请求（第1页已经有了）
            page = 2
            max_pages = 10  # 最多尝试10页，避免无限循环
            
            while len(temp_videos) < expected_count and page <= max_pages:
                try:
                    params = strategy(page)
                    logger.debug(f"请求第{page}页，参数: {params}")
                    
                    response = requests.get(api_url, headers=self.headers, params=params, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    
                    if data.get('code') == 'A00000' and data.get('data'):
                        video_list = data['data'].get('videoList', {})
                        if isinstance(video_list, dict):
                            new_videos = video_list.get('videos', [])
                            
                            if not new_videos:
                                # 没有更多数据了
                                logger.debug(f"第{page}页无数据，停止分页")
                                break
                            
                            # 去重：检查是否有新的视频
                            existing_ids = {v.get('id') for v in temp_videos}
                            new_count = 0
                            for video in new_videos:
                                if video.get('id') not in existing_ids:
                                    temp_videos.append(video)
                                    new_count += 1
                            
                            logger.debug(f"第{page}页获取到{new_count}个新集数")
                            
                            if new_count == 0:
                                # 没有新数据，说明分页参数无效
                                logger.debug(f"第{page}页无新数据，分页参数可能无效")
                                break
                            
                            page += 1
                        else:
                            break
                    else:
                        logger.debug(f"第{page}页请求失败: {data.get('msg', '未知错误')}")
                        break
                        
                except Exception as e:
                    logger.debug(f"第{page}页请求异常: {str(e)}")
                    break
            
            # 如果这个策略成功获取到更多数据，使用它
            if len(temp_videos) > len(all_videos):
                logger.info(f"分页策略 {strategy_idx + 1} 成功，获取到{len(temp_videos)}集")
                all_videos = temp_videos
                
                # 如果已经获取到足够的数据，不再尝试其他策略
                if len(all_videos) >= expected_count:
                    break
        
        return all_videos
    
    def _parse_episodes(self, videos: List) -> List[Dict]:
        """
        解析视频列表为剧集信息
        
        Args:
            videos: 原始视频列表
            
        Returns:
            解析后的剧集列表
        """
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
        
        return episodes
    
    def _get_episode_list_from_html(self, url: str, tvid: str) -> Dict:
        """
        从HTML页面解析剧集列表（备用方案）
        
        Args:
            url: 爱奇艺官网地址
            tvid: 视频ID
            
        Returns:
            包含剧集列表的字典
        """
        try:
            logger.info(f"尝试从HTML解析剧集列表: {url}")
            
            # 请求页面
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            page_content = response.text
            
            # 方法1: 从JavaScript变量中提取剧集数据
            # 查找 window.Q.PageInfo.playPageData 或类似的数据结构
            
            # 尝试提取JSON数据
            patterns = [
                r'window\.Q\.PageInfo\.playPageData\s*=\s*({.+?});',
                r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                r'__NEXT_DATA__\s*=\s*({.+?})</script>',
            ]
            
            episodes_data = None
            for pattern in patterns:
                match = re.search(pattern, page_content, re.DOTALL)
                if match:
                    try:
                        json_str = match.group(1)
                        data = json.loads(json_str)
                        
                        # 尝试从不同的路径提取剧集列表
                        possible_paths = [
                            ['videoList', 'videos'],
                            ['albumInfo', 'videos'],
                            ['episodeList'],
                            ['data', 'videoList', 'videos'],
                        ]
                        
                        for path in possible_paths:
                            temp_data = data
                            for key in path:
                                if isinstance(temp_data, dict) and key in temp_data:
                                    temp_data = temp_data[key]
                                else:
                                    temp_data = None
                                    break
                            
                            if temp_data and isinstance(temp_data, list):
                                episodes_data = temp_data
                                logger.info(f"从HTML中提取到剧集数据，路径: {' -> '.join(path)}")
                                break
                        
                        if episodes_data:
                            break
                            
                    except json.JSONDecodeError:
                        continue
            
            if episodes_data:
                # 解析剧集信息
                episodes = self._parse_episodes(episodes_data)
                
                return {
                    'success': True,
                    'episodes': episodes,
                    'total': len(episodes),
                    'source': 'html'
                }
            else:
                logger.warning("无法从HTML中提取剧集数据，HTML解析方案不适用于此页面")
                return {
                    'success': False,
                    'error': '无法从HTML中提取剧集数据'
                }
                
        except Exception as e:
            logger.error(f"HTML解析失败: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'HTML解析失败: {str(e)}'
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
        
        # 获取channelId用于类型识别
        channel_id = self.get_channel_id_from_mobile(url)
        if channel_id:
            video_info['channelId'] = channel_id
        
        # 获取剧集列表(传递URL用于电影类型)
        episodes_result = self.get_episode_list(tvid, url)
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

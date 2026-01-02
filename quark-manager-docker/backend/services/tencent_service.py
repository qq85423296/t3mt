# -*- coding: utf-8 -*-
"""
腾讯视频服务
用于读取腾讯视频影视信息和剧集列表
"""
import re
import requests
import json
from typing import Dict, List, Optional
from datetime import datetime
from utils.logger import logger
from utils.config_crypto import config_crypto


class TencentService:
    """腾讯视频服务类"""
    
    def __init__(self):
        # 从加密配置中获取腾讯视频API配置
        self.config = config_crypto.get_config('video_parse.tencent', {})
        
        # 如果配置未加载,抛出错误
        if not self.config or not self.config.get('enabled'):
            logger.error("腾讯视频配置未加载或未启用")
            raise RuntimeError("腾讯视频服务配置缺失,请联系管理员")
        
        self.api_url = self.config.get('api_url')
        self.share_info_api = self.config.get('share_info_api')
        self.base_url = self.config.get('base_url')
        
        self.headers = {
            'User-Agent': self.config.get('user_agent'),
            'Referer': self.config.get('referer'),
            'Content-Type': 'application/json',
            'Origin': self.config.get('origin')
        }
        
        # GetPageData接口固定URL参数
        self.page_data_params = {
            'appid': '3000002',
            'video_appid': '3000002',
            'guid': 'dc986f55336177f11766922177172',
            'vplatform': '3',
            'callerid': '3000002'
        }
        
        # share_info接口固定URL参数
        self.share_info_params = {
            'raw': '1',
            'vappid': '11333374',
            'vsecret': '45ce5b9d91f29688f832ad435ea227cf719a29571257d447',
            'video_appid': '3000002',
            'vplatform': '9',
            'guid': 'dc986f55336177f11766922177172'
        }
    
    def extract_cid_from_url(self, url: str) -> Optional[str]:
        """
        从官网地址提取cid
        例如: https://v.qq.com/x/cover/mzc00200znyfa5u.html -> mzc00200znyfa5u
        或: https://v.qq.com/x/cover/mzc00200znyfa5u/p41012tc2si.html -> mzc00200znyfa5u
        """
        pattern = r'/cover/([a-z0-9]+)'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None
    
    def get_video_title(self, cid: str) -> Dict:
        """
        通过share_info接口获取视频标题
        
        Args:
            cid: 综艺唯一标识
            
        Returns:
            包含标题和封面的字典
        """
        try:
            payload = {
                "dataKey": f"cid={cid}",
                "scene": 1
            }
            
            response = requests.post(
                self.share_info_api,
                params=self.share_info_params,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"share_info API响应: {json.dumps(data, ensure_ascii=False)}")
            
            if data.get('ret') == 0 and data.get('data'):
                share_item = data['data'].get('shareItem', {})
                title = share_item.get('shareTitle', '')
                cover_url = share_item.get('shareImgUrl', '')
                
                return {
                    'success': True,
                    'title': title,
                    'cover_url': cover_url
                }
            else:
                return {
                    'success': False,
                    'error': data.get('msg', '获取标题失败')
                }
                
        except Exception as e:
            logger.error(f"获取腾讯视频标题失败: {e}")
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }
    
    def get_episode_list(self, cid: str, page_context: str = None) -> Dict:
        """
        获取剧集列表（支持分页）
        
        Args:
            cid: 综艺唯一标识
            page_context: 分页上下文（可选）
            
        Returns:
            包含剧集列表的字典
        """
        # 构建请求体 - 使用你提供的接口格式
        payload = {
            "page_params": {
                "cid": cid,
                "vid": "",
                "page_type": "video_detail",
                "new_mark_label_enabled": "1"
            },
            "page_context": {
                "rec_req_num": "100"  # 每页返回100条数据
            },
            "new_mark_label_enabled": "1"
        }
        
        # 如果有分页上下文，解析并添加到payload
        if page_context:
            page_context_dict = {}
            for item in page_context.split('&'):
                if '=' in item:
                    key, value = item.split('=', 1)
                    page_context_dict[key] = value
            # 合并page_context，保留rec_req_num
            payload["page_context"].update(page_context_dict)
            logger.info(f"使用分页上下文: {payload['page_context']}")
        
        # 添加Cookie头
        cookie_headers = self.headers.copy()
        cookie_headers['Cookie'] = f'video_appid=3000002;video_platform=3;video_guid=dc986f55336177f11766922177172;vversion_name=8.9.16.0;new_mark_label_enabled=1'
        cookie_headers['xweb_xhr'] = '1'
        
        try:
            logger.info(f"请求参数: {json.dumps(payload, ensure_ascii=False)}")
            
            response = requests.post(
                self.api_url,
                params=self.page_data_params,
                json=payload,
                headers=cookie_headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            # 添加调试日志
            logger.info(f"GetPageData API完整响应: {json.dumps(data, ensure_ascii=False)}")
            
            # 检查返回数据结构
            if not data:
                return {
                    'success': False,
                    'error': 'API返回空数据'
                }
            
            # 腾讯接口返回格式：顶层有 data 字段
            result_data = data.get('data')
            if not result_data:
                # 如果没有data字段，检查是否有错误信息
                error_msg = data.get('msg', '未知错误')
                return {
                    'success': False,
                    'error': f'API返回错误: {error_msg}'
                }
            
            # 提取剧集列表
            episodes = []
            module_list = result_data.get('module_list_datas', [])
            
            # 遍历所有模块，找到剧集列表模块
            for module_group in module_list:
                module_datas = module_group.get('module_datas', [])
                for module in module_datas:
                    module_params = module.get('module_params', {})
                    module_type = module_params.get('module_type', '')
                    
                    # 找到剧集列表模块（episode_list）
                    if module_type == 'episode_list':
                        item_data_lists = module.get('item_data_lists', {})
                        item_datas = item_data_lists.get('item_datas', [])
                        
                        # 第一步：找到"正片"tab的索引
                        main_tab_index = -1
                        for i, item in enumerate(item_datas):
                            item_type = item.get('item_type', '')
                            # item_type=60 是二级tab（正片、直拍、直播、特辑）
                            if item_type == '60':
                                item_params = item.get('item_params', {})
                                tab_title = item_params.get('title', '')
                                if tab_title == '正片':
                                    main_tab_index = i
                                    logger.info(f"找到正片tab，索引: {i}")
                                    break
                        
                        # 第二步：提取正片tab之后、下一个tab之前的所有剧集
                        if main_tab_index >= 0:
                            # 找到下一个tab的索引
                            next_tab_index = len(item_datas)
                            for i in range(main_tab_index + 1, len(item_datas)):
                                if item_datas[i].get('item_type', '') == '60':
                                    next_tab_index = i
                                    break
                            
                            logger.info(f"正片范围: {main_tab_index + 1} 到 {next_tab_index - 1}")
                            
                            # 如果范围无效（tab后面没有剧集），说明剧集可能在tab之前
                            if main_tab_index + 1 >= next_tab_index:
                                logger.warning("正片tab后没有剧集，尝试提取tab之前的所有剧集")
                                main_tab_index = -1  # 重置，使用fallback逻辑
                            logger.info(f"正片范围: {main_tab_index + 1} 到 {next_tab_index - 1}")
                            
                            # 如果范围无效（tab后面没有剧集），说明剧集可能在tab之前
                            if main_tab_index + 1 >= next_tab_index:
                                logger.warning("正片tab后没有剧集，尝试提取tab之前的所有剧集")
                                main_tab_index = -1  # 重置，使用fallback逻辑
                            else:
                                # 提取正片范围内的剧集
                                for i in range(main_tab_index + 1, next_tab_index):
                                    item = item_datas[i]
                                    item_type = item.get('item_type', '')
                                    
                                    # 只处理正片（item_type=1）
                                    if item_type != '1':
                                        continue
                                    
                                    item_params = item.get('item_params', {})
                                    vid = item_params.get('vid', '')
                                    play_title = item_params.get('play_title', '')
                                    title = item_params.get('title', '')
                                    publish_date = item_params.get('publish_date', '')
                                    
                                    # 过滤预告片
                                    if '预告' in play_title or '预告' in title:
                                        continue
                                    
                                    # 提取发布日期（YYYY-MM-DD格式）
                                    date_str = ''
                                    if publish_date:
                                        try:
                                            date_obj = datetime.strptime(publish_date, '%Y-%m-%d %H:%M:%S')
                                            date_str = date_obj.strftime('%Y-%m-%d')
                                        except:
                                            date_str = publish_date.split(' ')[0] if ' ' in publish_date else publish_date
                                    
                                    # 使用play_title作为剧集名称
                                    episode_name = play_title if play_title else title
                                    
                                    # 格式化时长（秒转为分:秒格式）
                                    duration_str = ''
                                    duration_seconds = item_params.get('duration', 0)
                                    if duration_seconds:
                                        try:
                                            duration_int = int(duration_seconds)
                                            minutes = duration_int // 60
                                            seconds = duration_int % 60
                                            duration_str = f"{minutes}:{seconds:02d}"
                                        except:
                                            duration_str = str(duration_seconds)
                                    
                                    # 检查是否VIP
                                    imgtag_all = item_params.get('imgtag_all', '')
                                    uni_imgtag = item_params.get('uni_imgtag', '')
                                    is_vip = 'VIP' in imgtag_all or 'VIP' in uni_imgtag
                                    
                                    episodes.append({
                                        'name': episode_name,
                                        'title': '',  # 副标题留空
                                        'url': f"{self.base_url}/x/cover/{cid}/{vid}.html",
                                        'vid': vid,
                                        'publish_date': date_str,
                                        'time': duration_str,
                                        'image': item_params.get('image_url', ''),
                                        'is_vip': is_vip
                                    })
                        
                        # 如果没有找到"正片"tab或范围无效，提取所有item_type=1的剧集
                        if main_tab_index < 0:
                            for item in item_datas:
                                item_type = item.get('item_type', '')
                                
                                # 跳过tab标签
                                if item_type in ['28', '60', '23', '13']:
                                    continue
                                
                                # 只处理正片（item_type=1）
                                if item_type != '1':
                                    continue
                                
                                item_params = item.get('item_params', {})
                                vid = item_params.get('vid', '')
                                play_title = item_params.get('play_title', '')
                                title = item_params.get('title', '')
                                publish_date = item_params.get('publish_date', '')
                                
                                # 过滤预告片
                                if '预告' in play_title or '预告' in title:
                                    continue
                                
                                # 提取发布日期（YYYY-MM-DD格式）
                                date_str = ''
                                if publish_date:
                                    try:
                                        date_obj = datetime.strptime(publish_date, '%Y-%m-%d %H:%M:%S')
                                        date_str = date_obj.strftime('%Y-%m-%d')
                                    except:
                                        date_str = publish_date.split(' ')[0] if ' ' in publish_date else publish_date
                                
                                # 使用play_title作为剧集名称
                                episode_name = play_title if play_title else title
                                
                                # 格式化时长（秒转为分:秒格式）
                                duration_str = ''
                                duration_seconds = item_params.get('duration', 0)
                                if duration_seconds:
                                    try:
                                        duration_int = int(duration_seconds)
                                        minutes = duration_int // 60
                                        seconds = duration_int % 60
                                        duration_str = f"{minutes}:{seconds:02d}"
                                    except:
                                        duration_str = str(duration_seconds)
                                
                                # 检查是否VIP
                                imgtag_all = item_params.get('imgtag_all', '')
                                uni_imgtag = item_params.get('uni_imgtag', '')
                                is_vip = 'VIP' in imgtag_all or 'VIP' in uni_imgtag
                                
                                episodes.append({
                                    'name': episode_name,
                                    'title': '',  # 副标题留空
                                    'url': f"{self.base_url}/x/cover/{cid}/{vid}.html",
                                    'vid': vid,
                                    'publish_date': date_str,
                                    'time': duration_str,
                                    'image': item_params.get('image_url', ''),
                                    'is_vip': is_vip
                                })
            
            # 检查是否有下一页
            has_next_page = result_data.get('has_next_page', False)
            next_page_context = result_data.get('next_page_context', {})
            
            return {
                'success': True,
                'episodes': episodes,
                'has_next_page': has_next_page,
                'next_page_context': next_page_context
            }
                
        except Exception as e:
            logger.error(f"获取腾讯视频剧集列表失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }
    
    def get_all_episodes(self, cid: str, video_type: str = '') -> Dict:
        """
        获取所有剧集（自动处理分页）
        
        Args:
            cid: 综艺唯一标识
            video_type: 视频类型（如'综艺'），用于判断是否需要在名称前加日期
            
        Returns:
            包含所有剧集的字典
        """
        logger.info(f"获取腾讯视频所有剧集，cid: {cid}, 类型: {video_type}")
        
        all_episodes = []
        page_context = None
        page_num = 1
        
        # 判断是否为综艺类型
        is_variety_show = '综艺' in video_type if video_type else False
        
        # 用于检测重复的集合（存储vid）
        seen_vids = set()
        
        while True:
            logger.info(f"正在获取第 {page_num} 页剧集...")
            result = self.get_episode_list(cid, page_context)
            
            if not result.get('success'):
                if page_num == 1:
                    # 第一页失败，直接返回错误
                    return result
                else:
                    # 后续页失败，返回已获取的剧集
                    logger.warning(f"第 {page_num} 页获取失败，返回已获取的 {len(all_episodes)} 集")
                    break
            
            episodes = result.get('episodes', [])
            
            # 检测本页是否有新剧集（通过vid判断）
            new_episodes = []
            duplicate_count = 0
            
            for episode in episodes:
                vid = episode.get('vid', '')
                if vid and vid not in seen_vids:
                    # 新剧集
                    seen_vids.add(vid)
                    new_episodes.append(episode)
                else:
                    # 重复剧集
                    duplicate_count += 1
            
            # 如果本页没有任何剧集数据，说明已经到达推荐内容区域，停止获取
            if len(episodes) == 0:
                logger.info(f"第 {page_num} 页没有剧集数据，停止获取")
                logger.info(f"已获取所有剧集，共 {len(all_episodes)} 集")
                break
            
            # 如果本页全是重复剧集，说明已经获取完所有剧集
            if duplicate_count == len(episodes):
                logger.info(f"第 {page_num} 页全部为重复剧集（{duplicate_count}个），停止获取")
                logger.info(f"已获取所有剧集，共 {len(all_episodes)} 集")
                break
            
            # 如果是综艺类型，在剧集名称前加上日期
            if is_variety_show:
                for episode in new_episodes:
                    publish_date = episode.get('publish_date', '')
                    if publish_date:
                        # 如果名称中还没有日期，就加上
                        name = episode.get('name', '')
                        if not name.startswith(publish_date):
                            episode['name'] = f"{publish_date} {name}"
            
            all_episodes.extend(new_episodes)
            logger.info(f"第 {page_num} 页获取到 {len(episodes)} 集，新增 {len(new_episodes)} 集，重复 {duplicate_count} 集，累计 {len(all_episodes)} 集")
            
            # 检查是否有下一页
            has_next_page = result.get('has_next_page', False)
            if not has_next_page:
                logger.info(f"已获取所有剧集，共 {len(all_episodes)} 集")
                break
            
            # 获取下一页的page_context
            next_page_context = result.get('next_page_context', {})
            if not next_page_context:
                logger.warning("没有下一页上下文，停止分页")
                break
            
            # 构建下一页的page_context字符串
            page_context_parts = []
            for key, value in next_page_context.items():
                page_context_parts.append(f"{key}={value}")
            page_context = "&".join(page_context_parts)
            
            page_num += 1
            
            # 防止无限循环
            if page_num > 100:
                logger.warning("分页超过100页，停止获取")
                break
        
        return {
            'success': True,
            'episodes': all_episodes,
            'total': len(all_episodes)
        }
    
    def read_website(self, url: str) -> Dict:
        """
        读取官网地址，获取影视信息和剧集列表
        
        Args:
            url: 腾讯视频官网地址
            
        Returns:
            包含影视信息和剧集列表的字典
        """
        # 提取cid
        cid = self.extract_cid_from_url(url)
        if not cid:
            return {
                'success': False,
                'error': '无效的腾讯视频地址'
            }
        
        logger.info(f"开始读取腾讯视频，cid: {cid}")
        
        # 1. 获取视频标题和封面
        title_result = self.get_video_title(cid)
        if not title_result.get('success'):
            logger.warning(f"获取标题失败: {title_result.get('error')}")
            video_title = f'腾讯视频_{cid}'
            cover_url = ''
        else:
            video_title = title_result.get('title', f'腾讯视频_{cid}')
            cover_url = title_result.get('cover_url', '')
        
        logger.info(f"视频标题: {video_title}")
        
        # 2. 获取所有剧集（传入类型信息，综艺类型会在名称前加日期）
        episodes_result = self.get_all_episodes(cid, video_type='综艺')
        if not episodes_result.get('success'):
            return episodes_result
        
        episodes = episodes_result['episodes']
        logger.info(f"共获取 {len(episodes)} 集")
        
        # 3. 构建影视信息
        video_info = {
            'success': True,
            'title': video_title,
            'clip_name': video_title,
            'sub_title': '',
            'description': '',
            'area': '',
            'year': '',
            'publish_date': '',
            'opinion_score': '',
            'leading_actor_names': [],
            'directors': [],
            'type_name': '综艺',
            'cover_url': cover_url,
            'clip_image': cover_url,
            'video_id': cid,
            'clip_id': cid
        }
        
        # 4. 合并结果
        return {
            'success': True,
            'video_info': video_info,
            'episodes': episodes,
            'total_episodes': episodes_result['total'],
            'platform': 'tencent'
        }


# 全局实例(延迟初始化)
_tencent_service = None

def get_tencent_service():
    """获取腾讯视频服务实例(单例模式)"""
    global _tencent_service
    if _tencent_service is None:
        _tencent_service = TencentService()
    return _tencent_service

class _TencentServiceProxy:
    def __getattr__(self, name):
        return getattr(get_tencent_service(), name)

tencent_service = _TencentServiceProxy()

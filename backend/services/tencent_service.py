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
        
        # web_vsite API固定URL参数
        self.page_data_params = {
            'video_appid': '3000010',
            'vplatform': '2',
            'vdevice_guid': '5bfc7b85c2c3a2b1',
            'vversion_name': '8.2.96',
            'vversion_platform': '2'
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
    
    def get_video_detail_and_episodes(self, cid: str) -> Dict:
        """
        获取视频详情和剧集列表（使用web_vsite API，支持分页获取所有剧集）
        
        Args:
            cid: 视频唯一标识
            
        Returns:
            包含视频详情和剧集列表的字典
        """
        all_episodes = []
        video_info = {}
        seen_vids = set()
        
        try:
            logger.info(f"获取腾讯视频详情，cid: {cid}")
            
            # 第一步：使用share_info API获取基本视频详情（标题、封面）
            detail_result = self.get_video_title(cid)
            if detail_result.get('success'):
                video_info = {
                    'title': detail_result.get('title', ''),
                    'cover_url': detail_result.get('cover_url', ''),
                    'cover_vt': '',  # share_info不提供竖版封面
                    'description': '',  # share_info不提供简介
                    'episode_all': '',  # 后续补充
                    'update_info': '',  # share_info不提供更新周期
                    'year': '',
                    'area': '',
                    'main_genres': '',
                    'sub_genre': '',
                    'score': '',
                    'score_count': '',
                    'rank_info': '',
                    'hotval': '',
                    'broadcast_time': '',
                    'tag_text': '',
                    'cid': cid
                }
                logger.info(f"从share_info API获取到视频标题: {video_info.get('title')}")
            else:
                logger.warning(f"share_info API获取失败: {detail_result.get('error')}")
            
            # 第二步：使用web_vsite API获取剧集列表
            detail_payload = {
                "page_params": {
                    "req_from": "web_vsite",
                    "page_id": "vsite_episode_list",
                    "page_type": "detail_operation",
                    "id_type": "1",
                    "page_size": "50",
                    "cid": cid,
                    "vid": "",
                    "lid": "",
                    "page_num": "",
                    "page_context": "",
                    "detail_page_type": "1"
                },
                "has_cache": 1
            }
            
            response = requests.post(
                self.api_url,
                params=self.page_data_params,
                json=detail_payload,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            result_data = data.get('data', {})
            module_list = result_data.get('module_list_datas', [])
            
            # 解析tabs分页信息和第一批剧集
            tabs = []
            for module_group in module_list:
                module_datas = module_group.get('module_datas', [])
                for module in module_datas:
                    module_params = module.get('module_params', {})
                    desk_module_type = module_params.get('desk_module_type', '')
                    
                    if desk_module_type == 'episode_list':
                        # 从模块参数中提取更新信息
                        if not video_info.get('update_info'):
                            video_info['update_info'] = module_params.get('sub_title', '')
                        
                        # 解析tabs分页信息
                        tabs_str = module_params.get('tabs', '')
                        if tabs_str:
                            try:
                                tabs = json.loads(tabs_str)
                                logger.info(f"发现 {len(tabs)} 个分页tab")
                            except:
                                pass
                        
                        # 解析当前页剧集
                        item_data_lists = module.get('item_data_lists', {})
                        item_datas = item_data_lists.get('item_datas', [])
                        
                        # 从第一个剧集中提取businessInfo用于类型识别
                        if not video_info.get('businessInfo') and len(item_datas) > 0:
                            first_item = item_datas[0]
                            item_params = first_item.get('item_params', {})
                            business_info_str = item_params.get('businessInfo', '')
                            if business_info_str:
                                try:
                                    # businessInfo是JSON字符串,需要解析
                                    if isinstance(business_info_str, str):
                                        business_info = json.loads(business_info_str)
                                    else:
                                        business_info = business_info_str
                                    
                                    # 将businessInfo添加到video_info中供类型识别使用
                                    video_info['businessInfo'] = business_info
                                    logger.info(f"提取到businessInfo: video_category={business_info.get('video_category')}")
                                except Exception as e:
                                    logger.warning(f"解析businessInfo失败: {e}")
                        
                        episodes = self._parse_episodes(item_datas, cid, seen_vids)
                        all_episodes.extend(episodes)
                        logger.info(f"首次请求获取到 {len(episodes)} 集")
            
            # 第三步：遍历所有tabs获取完整剧集列表
            for i, tab in enumerate(tabs):
                if tab.get('selected'):
                    # 已经获取过的tab跳过
                    continue
                    
                page_context = tab.get('page_context', '')
                if not page_context:
                    continue
                
                begin = tab.get('begin', 0)
                end = tab.get('end', 0)
                logger.info(f"获取第 {i+1} 个tab的剧集 ({begin}-{end}集)...")
                
                result = self._get_episode_page(cid, page_context)
                if result.get('success'):
                    episodes = result.get('episodes', [])
                    new_episodes = []
                    for ep in episodes:
                        vid = ep.get('vid', '')
                        if vid and vid not in seen_vids:
                            seen_vids.add(vid)
                            new_episodes.append(ep)
                    all_episodes.extend(new_episodes)
                    logger.info(f"Tab {i+1} 获取到 {len(new_episodes)} 集新剧集")
                else:
                    logger.warning(f"Tab {i+1} 获取失败: {result.get('error')}")
            
            # 补充cid和总集数
            video_info['cid'] = cid
            video_info['episode_all'] = str(len(all_episodes))
            
            # 按集数排序
            all_episodes.sort(key=lambda x: self._extract_episode_number(x.get('name', '')))
            
            logger.info(f"已获取所有剧集，共 {len(all_episodes)} 集")
            
            return {
                'success': True,
                'video_info': video_info,
                'episodes': all_episodes,
                'total': len(all_episodes)
            }
            
        except Exception as e:
            logger.error(f"获取腾讯视频详情失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }
    
    def _extract_episode_number(self, name: str) -> int:
        """从剧集名称中提取集数用于排序"""
        import re
        match = re.search(r'第(\d+)集', name)
        if match:
            return int(match.group(1))
        # 尝试匹配纯数字
        match = re.search(r'(\d+)', name)
        if match:
            return int(match.group(1))
        return 0

    def _parse_episodes(self, item_datas: List, cid: str, seen_vids: set) -> List[Dict]:
        """解析剧集列表"""
        episodes = []
        
        for item in item_datas:
            item_type = item.get('item_type', '')
            
            # 只处理正片（item_type=1）
            if item_type != '1':
                continue
            
            item_params = item.get('item_params', {})
            vid = item_params.get('vid', '')
            
            if not vid or vid in seen_vids:
                continue
            
            seen_vids.add(vid)
            
            # 获取剧集标题
            play_title = item_params.get('play_title', '')
            title = item_params.get('title', '')
            video_subtitle = item_params.get('video_subtitle', '')  # 剧集副标题/简介
            
            # 处理play_title：去掉前面的剧名部分
            # 格式通常是：剧名 第X集 详细标题
            # 我们需要去掉剧名，只保留：第X集 详细标题
            episode_name = play_title
            if play_title:
                # 尝试匹配"第X集"或"第X话"或"第X期"的位置
                import re
                match = re.search(r'第\d+[集话期]', play_title)
                if match:
                    # 从"第X集"开始截取，去掉前面的剧名
                    episode_name = play_title[match.start():]
                else:
                    # 如果没有匹配到标准格式，保持原样
                    episode_name = play_title
            
            # 综艺节目特殊处理：添加日期前缀
            # 检查是否为综艺节目（video_category=3）
            business_info_str = item_params.get('businessInfo', '')
            is_variety_show = False
            if business_info_str:
                try:
                    import json
                    business_info = json.loads(business_info_str) if isinstance(business_info_str, str) else business_info_str
                    video_category = business_info.get('video_category', 0)
                    is_variety_show = (video_category == 3)
                except:
                    pass
            
            # 如果是综艺节目且有日期信息，添加日期前缀
            if is_variety_show:
                tag_right_text = item_params.get('tag_right_text', '')
                if tag_right_text:
                    # 格式：日期 + 原名称
                    episode_name = f"{tag_right_text} {episode_name}"
            
            # 获取时长（秒）
            duration_seconds = item_params.get('duration', 0)
            try:
                duration_int = int(duration_seconds)
            except:
                duration_int = 0
            
            # 获取标签信息
            imgtag_all = item_params.get('imgtag_all', '')
            uni_imgtag = item_params.get('uni_imgtag', '')
            
            # 用于标记是否需要过滤
            should_filter = False
            
            # 过滤非正片内容
            # 1. 过滤预告片
            # 1.1 检查标题中是否包含"预告"
            if '预告' in play_title or '预告' in title or '预告' in video_subtitle:
                logger.debug(f"过滤预告片（标题包含'预告'）: {play_title}")
                continue
            
            # 1.2 检查uni_imgtag标签中是否标记为预告
            if uni_imgtag:
                # uni_imgtag可能是字符串或字典
                try:
                    if isinstance(uni_imgtag, str):
                        import json
                        uni_imgtag_obj = json.loads(uni_imgtag)
                    else:
                        uni_imgtag_obj = uni_imgtag
                    
                    # 检查所有tag中是否有"预告"标识
                    for tag_key, tag_value in uni_imgtag_obj.items():
                        if isinstance(tag_value, dict):
                            tag_text = tag_value.get('text', '')
                            if '预告' in tag_text:
                                logger.debug(f"过滤预告片（uni_imgtag标记为'{tag_text}'）: {play_title}")
                                should_filter = True
                                break
                    
                    if should_filter:
                        continue
                except:
                    pass
            
            # 1.3 检查imgtag_all标签中是否标记为预告
            if imgtag_all:
                try:
                    if isinstance(imgtag_all, str):
                        import json
                        imgtag_all_obj = json.loads(imgtag_all)
                    else:
                        imgtag_all_obj = imgtag_all
                    
                    # 检查所有tag中是否有"预告"或"预"标识
                    for tag_key, tag_value in imgtag_all_obj.items():
                        if isinstance(tag_value, dict):
                            tag_text = tag_value.get('text', '')
                            if '预告' in tag_text or tag_text.startswith('预-'):
                                logger.debug(f"过滤预告片（imgtag_all标记为'{tag_text}'）: {play_title}")
                                should_filter = True
                                break
                    
                    if should_filter:
                        continue
                except:
                    pass
            
            # 2. 过滤标题中包含特定关键词的非正片内容
            filter_keywords = [
                '花絮', '片段', '特辑', '精彩', '看点', '幕后', 
                '采访', '访谈', '彩蛋', '番外', '剧透', '解说',
                '片花', '集锦', '混剪', '速看', '回顾', '盘点',
                '导视', '片尾曲', '片头曲', '主题曲', '插曲'
            ]
            
            for keyword in filter_keywords:
                if keyword in play_title or keyword in video_subtitle:
                    logger.debug(f"过滤非正片内容（包含'{keyword}'）: {play_title}")
                    should_filter = True
                    break
            
            if should_filter:
                continue
            
            # 3. 标题格式检查：只保留标准正片格式
            # 允许的格式：
            # - 第X集、第X话、第X期（如：第01集、第1集、第02话）
            # - 纯数字（如：01、02、1、2）
            # - 包含"集"、"话"、"期"的（如：01集、02话）
            import re
            
            # 检查是否是标准正片格式
            is_valid_format = False
            
            # 格式1：第X集/话/期
            if re.search(r'第\d+[集话期]', play_title):
                is_valid_format = True
            # 格式2：纯数字（01、02、1、2等）
            elif re.match(r'^\d+$', play_title.strip()):
                is_valid_format = True
            # 格式3：数字+集/话/期（01集、02话等）
            elif re.match(r'^\d+[集话期]$', play_title.strip()):
                is_valid_format = True
            # 格式4：包含"第"和数字的（第一集、第二话等）
            elif re.search(r'第[一二三四五六七八九十百千万\d]+[集话期]', play_title):
                is_valid_format = True
            
            if not is_valid_format:
                logger.debug(f"过滤非标准格式: {play_title}")
                continue
            
            # 格式化时长（秒转为分:秒格式）
            duration_str = ''
            if duration_int > 0:
                minutes = duration_int // 60
                seconds = duration_int % 60
                duration_str = f"{minutes}:{seconds:02d}"
            
            # 检查是否VIP（使用前面已获取的变量）
            is_vip = 'VIP' in imgtag_all or 'VIP' in uni_imgtag
            
            # 获取发布日期
            date_str = item_params.get('date', '')
            
            # 如果date字段为空，尝试从其他字段获取日期
            if not date_str:
                # 尝试从update_time字段获取
                date_str = item_params.get('update_time', '')
                if not date_str:
                    # 尝试从online_time字段获取
                    date_str = item_params.get('online_time', '')
                if not date_str:
                    # 尝试从publish_time字段获取
                    date_str = item_params.get('publish_time', '')
            
            if date_str:
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    date_str = date_obj.strftime('%Y-%m-%d')
                except:
                    date_str = date_str.split(' ')[0] if ' ' in date_str else date_str
            
            # 调试日志：输出所有可能的日期字段
            if not date_str:
                logger.debug(f"剧集 {episode_name}: 未找到日期信息。item_params中的所有字段: {list(item_params.keys())}")
            
            episodes.append({
                'name': episode_name if episode_name else f"第{title}集",
                'title': video_subtitle,  # 剧集副标题
                'url': f"{self.base_url}/x/cover/{cid}/{vid}.html",
                'vid': vid,
                'publish_date': date_str,
                'time': duration_str,
                'image': item_params.get('image_url', ''),
                'is_vip': is_vip
            })
        
        return episodes

    def _get_episode_page(self, cid: str, page_context: str) -> Dict:
        """
        获取指定分页的剧集列表
        
        Args:
            cid: 视频唯一标识
            page_context: 分页上下文（从tabs中获取）
            
        Returns:
            包含剧集列表的字典
        """
        # 使用web_vsite接口获取分页剧集
        payload = {
            "page_params": {
                "req_from": "web_vsite",
                "page_id": "vsite_episode_list",
                "page_type": "detail_operation",
                "id_type": "1",
                "page_size": "50",
                "cid": cid,
                "vid": "",
                "lid": "",
                "page_num": "",
                "page_context": page_context,
                "detail_page_type": "1"
            },
            "has_cache": 1
        }
        
        try:
            response = requests.post(
                self.api_url,
                params=self.page_data_params,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            episodes = []
            seen_vids = set()
            result_data = data.get('data', {})
            module_list = result_data.get('module_list_datas', [])
            
            for module_group in module_list:
                module_datas = module_group.get('module_datas', [])
                for module in module_datas:
                    module_params = module.get('module_params', {})
                    desk_module_type = module_params.get('desk_module_type', '')
                    
                    if desk_module_type == 'episode_list':
                        item_data_lists = module.get('item_data_lists', {})
                        item_datas = item_data_lists.get('item_datas', [])
                        
                        episodes = self._parse_episodes(item_datas, cid, seen_vids)
            
            return {
                'success': True,
                'episodes': episodes
            }
            
        except Exception as e:
            logger.error(f"获取分页剧集失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_video_title(self, cid: str) -> Dict:
        """
        通过share_info接口获取视频标题（备用方法）
        
        Args:
            cid: 视频唯一标识
            
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

    def read_website(self, url: str) -> Dict:
        """
        读取腾讯视频网站信息（主入口方法）
        
        Args:
            url: 腾讯视频官网地址
            
        Returns:
            标准格式的视频信息和剧集列表
        """
        # 从URL提取cid
        cid = self.extract_cid_from_url(url)
        if not cid:
            return {
                'success': False,
                'error': '无法从URL中提取视频ID，请检查URL格式'
            }
        
        logger.info(f"开始读取腾讯视频，URL: {url}, CID: {cid}")
        
        # 获取视频详情和剧集列表
        result = self.get_video_detail_and_episodes(cid)
        
        if not result.get('success'):
            return result
        
        video_info = result.get('video_info', {})
        episodes = result.get('episodes', [])
        
        # 构建标准返回格式（与mango_service保持一致）
        return {
            'success': True,
            'video_info': {
                'title': video_info.get('title', ''),
                'cover_url': video_info.get('cover_url', ''),
                'cover_vt': video_info.get('cover_vt', ''),
                'description': video_info.get('description', ''),
                'episode_all': video_info.get('episode_all', ''),
                'update_info': video_info.get('update_info', ''),
                'year': video_info.get('year', ''),
                'area': video_info.get('area', ''),
                'main_genres': video_info.get('main_genres', ''),
                'sub_genre': video_info.get('sub_genre', ''),
                'score': video_info.get('score', ''),
                'score_count': video_info.get('score_count', ''),
                'rank_info': video_info.get('rank_info', ''),
                'hotval': video_info.get('hotval', ''),
                'broadcast_time': video_info.get('broadcast_time', ''),
                'tag_text': video_info.get('tag_text', ''),
                'cid': cid,
                'businessInfo': video_info.get('businessInfo', {})  # 添加businessInfo用于类型识别
            },
            'episodes': episodes,
            'total_episodes': len(episodes),
            'platform': 'tencent'
        }
    
    def get_all_episodes(self, url: str) -> Dict:
        """
        获取所有剧集列表（兼容旧接口）
        
        Args:
            url: 腾讯视频官网地址
            
        Returns:
            剧集列表
        """
        return self.read_website(url)


# 全局单例实例
_tencent_service: Optional[TencentService] = None


def get_tencent_service() -> TencentService:
    """获取腾讯视频服务单例"""
    global _tencent_service
    if _tencent_service is None:
        _tencent_service = TencentService()
    return _tencent_service


class _TencentServiceProxy:
    """腾讯视频服务代理类，用于延迟初始化"""
    
    def __getattr__(self, name):
        return getattr(get_tencent_service(), name)


# 导出代理对象，支持延迟初始化
tencent_service = _TencentServiceProxy()

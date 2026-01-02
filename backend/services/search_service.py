# -*- coding: utf-8 -*-
"""
资源搜索服务
"""
import requests
from utils.logger import logger


class SearchService:
    """资源搜索服务类"""
    
    def __init__(self, api_url, api_key=None):
        """
        初始化搜索服务
        
        Args:
            api_url: 盘搜API地址
            api_key: API密钥（可选）
        """
        self.api_url = api_url
        self.api_key = api_key
        self.session = requests.Session()
        
        if api_key:
            self.session.headers.update({'Authorization': f'Bearer {api_key}'})
    
    def search(self, keyword, disk_type=None, page=1, page_size=20, refresh=False):
        """
        搜索资源
        
        Args:
            keyword: 搜索关键词
            disk_type: 网盘类型（可选，默认返回所有类型）
            page: 页码
            page_size: 每页数量
            refresh: 是否刷新缓存
        
        Returns:
            搜索结果字典
        """
        import time
        start_time = time.time()
        
        try:
            # 盘搜API参数格式（参考实际请求）
            params = {
                'kw': keyword,
                'res': 'merge',
                'src': 'all'  # 搜索所有来源
            }
            
            # 如果需要刷新缓存
            if refresh:
                params['refresh'] = 'true'
            
            # 盘搜API路径
            url = f"{self.api_url.rstrip('/')}/api/search"
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            # 计算耗时（毫秒）
            elapsed_time = int((time.time() - start_time) * 1000)
            
            # 解析盘搜API返回格式
            if result.get('code') == 0:
                data = result.get('data', {})
                merged_by_type = data.get('merged_by_type', {})
                
                logger.info(f"盘搜API返回的网盘类型: {list(merged_by_type.keys())}")
                
                # 合并所有网盘类型的结果
                all_results = []
                for platform, disk_results in merged_by_type.items():
                    if isinstance(disk_results, list):
                        # 为每个结果添加platform字段
                        for item in disk_results:
                            item['platform'] = platform
                        all_results.extend(disk_results)
                
                logger.info(f"合并后的结果数量: {len(all_results)}")
                
                # 如果指定了网盘类型，只返回该类型的结果
                if disk_type:
                    all_results = [item for item in all_results if item.get('platform') == disk_type]
                    logger.info(f"筛选{disk_type}后的结果数量: {len(all_results)}")
                
                # 格式化结果
                formatted_results = self._format_search_results(all_results)
                
                logger.info(f"搜索成功: {keyword}, 格式化后结果数: {len(formatted_results)}, API总数: {data.get('total', 0)}, 耗时: {elapsed_time}ms")
                
                return {
                    'total': data.get('total', len(formatted_results)),
                    'page': page,
                    'page_size': page_size,
                    'time': elapsed_time,
                    'results': formatted_results
                }
            else:
                logger.warning(f"搜索返回错误: {result}")
                return {
                    'total': 0,
                    'page': page,
                    'page_size': page_size,
                    'time': elapsed_time,
                    'results': []
                }
                
        except requests.exceptions.Timeout:
            elapsed_time = int((time.time() - start_time) * 1000)
            logger.error(f"搜索超时: {keyword}")
            raise Exception("搜索请求超时，请稍后重试")
        except requests.exceptions.RequestException as e:
            elapsed_time = int((time.time() - start_time) * 1000)
            logger.error(f"搜索失败: {e}")
            raise Exception(f"搜索失败: {str(e)}")
        except Exception as e:
            elapsed_time = int((time.time() - start_time) * 1000)
            logger.error(f"搜索异常: {e}", exc_info=True)
            raise
    
    def _format_search_results(self, search_results):
        """
        格式化搜索结果
        
        Args:
            search_results: 盘搜API返回的原始结果列表（已包含platform字段）
        
        Returns:
            格式化后的结果列表
        """
        import re
        from datetime import datetime
        
        # 匹配标题和描述的正则表达式
        pattern = (
            r'^(.*?)'
            r'(?:'
            r'[【\[]?'
            r'(?:简介|介绍|描述)'
            r'[】\]]?'
            r'[:：]?'
            r')'
            r'(.*)'
        )
        
        formatted_results = []
        link_array = []
        
        for item in search_results:
            url = item.get('url', '')
            note = item.get('note', '')
            password = item.get('password', '')
            tm = item.get('datetime', '')
            images = item.get('images', [])
            platform = item.get('platform', 'unknown')
            
            # 转换时间格式
            if tm and tm != '0001-01-01T00:00:00Z':
                try:
                    # ISO格式转换为本地时间
                    dt = datetime.fromisoformat(tm.replace('Z', '+00:00'))
                    tm = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    tm = ''
            else:
                tm = ''
            
            # 解析标题和描述
            match = re.search(pattern, note)
            if match:
                title = match.group(1).strip()
                content = match.group(2).strip()
            else:
                title = note
                content = ''
            
            # 去重
            if url and url not in link_array:
                link_array.append(url)
                result_item = {
                    'share_url': url,
                    'title': title,
                    'description': content,
                    'datetime': tm,
                    'source': item.get('source', ''),
                    'platform': platform
                }
                
                # 添加提取码（如果有）
                if password:
                    result_item['password'] = password
                
                # 添加封面图（如果有）
                if images and len(images) > 0:
                    result_item['cover'] = images[0]
                
                formatted_results.append(result_item)
        
        return formatted_results
    
    @staticmethod
    def check_quark_share_validity(share_url, quark_service):
        """
        检测夸克分享链接有效性
        
        Args:
            share_url: 分享链接
            quark_service: 夸克服务实例
        
        Returns:
            有效性结果字典
        """
        try:
            # 调用夸克服务检测链接
            result = quark_service.check_share_link(share_url)
            
            if result['is_valid']:
                logger.info(f"链接有效: {share_url}")
                return {
                    'is_valid': True,
                    'message': '链接有效',
                    'file_count': result.get('file_count'),
                    'total_size': result.get('total_size')
                }
            else:
                logger.warning(f"链接失效: {share_url}")
                return {
                    'is_valid': False,
                    'message': '链接已失效或不存在'
                }
        except Exception as e:
            logger.error(f"检测链接有效性失败: {e}")
            return {
                'is_valid': False,
                'message': f'检测失败: {str(e)}'
            }

# -*- coding: utf-8 -*-
"""
资源搜索服务
"""
import requests
import hashlib
import json
from datetime import datetime, timedelta
from database import get_db
from utils.logger import logger


class SearchService:
    """资源搜索服务类"""
    
    # 缓存有效期（24小时）
    CACHE_EXPIRE_HOURS = 24
    
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
        
        # 初始化缓存表
        self._init_cache_table()
    
    def _init_cache_table(self):
        """初始化搜索缓存表"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS search_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cache_key TEXT NOT NULL UNIQUE,
                        keyword TEXT NOT NULL,
                        disk_type TEXT,
                        result_data TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL
                    )
                ''')
                
                # 创建索引加速查询
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_search_cache_key 
                    ON search_cache(cache_key)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_search_cache_expires 
                    ON search_cache(expires_at)
                ''')
                
                conn.commit()
        except Exception as e:
            logger.error(f"初始化搜索缓存表失败: {e}")
    
    def _get_cache_key(self, keyword, disk_type=None):
        """
        生成缓存键
        
        Args:
            keyword: 搜索关键词
            disk_type: 网盘类型
        
        Returns:
            缓存键（MD5哈希）
        """
        cache_str = f"{keyword}_{disk_type or 'all'}"
        return hashlib.md5(cache_str.encode('utf-8')).hexdigest()
    
    def _get_cached_result(self, cache_key):
        """
        从缓存获取搜索结果
        
        Args:
            cache_key: 缓存键
        
        Returns:
            缓存的搜索结果，如果不存在或已过期则返回None
        """
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT result_data, expires_at 
                    FROM search_cache 
                    WHERE cache_key = ?
                ''', (cache_key,))
                
                row = cursor.fetchone()
                if row:
                    result_data = row[0]
                    expires_at = datetime.fromisoformat(row[1])
                    
                    # 检查是否过期
                    if datetime.now() < expires_at:
                        logger.info(f"命中搜索缓存: {cache_key}")
                        return json.loads(result_data)
                    else:
                        # 删除过期缓存
                        cursor.execute('DELETE FROM search_cache WHERE cache_key = ?', (cache_key,))
                        conn.commit()
                        logger.info(f"搜索缓存已过期: {cache_key}")
                
                return None
        except Exception as e:
            logger.error(f"获取搜索缓存失败: {e}")
            return None
    
    def _save_to_cache(self, cache_key, keyword, disk_type, result_data):
        """
        保存搜索结果到缓存
        
        Args:
            cache_key: 缓存键
            keyword: 搜索关键词
            disk_type: 网盘类型
            result_data: 搜索结果数据
        """
        try:
            expires_at = datetime.now() + timedelta(hours=self.CACHE_EXPIRE_HOURS)
            result_json = json.dumps(result_data, ensure_ascii=False)
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO search_cache 
                    (cache_key, keyword, disk_type, result_data, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (cache_key, keyword, disk_type, result_json, datetime.now(), expires_at))
                conn.commit()
                
            logger.info(f"搜索结果已缓存: {cache_key}, 过期时间: {expires_at}")
        except Exception as e:
            logger.error(f"保存搜索缓存失败: {e}")
    
    def _clean_expired_cache(self):
        """清理过期的缓存"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM search_cache 
                    WHERE expires_at < ?
                ''', (datetime.now(),))
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"清理了 {deleted_count} 条过期搜索缓存")
        except Exception as e:
            logger.error(f"清理过期缓存失败: {e}")
    
    def search(self, keyword, disk_type=None, page=1, page_size=20, refresh=False):
        """
        搜索资源（支持24小时缓存）
        
        Args:
            keyword: 搜索关键词
            disk_type: 网盘类型（可选，默认返回所有类型）
            page: 页码
            page_size: 每页数量
            refresh: 是否刷新缓存（强制重新搜索）
        
        Returns:
            搜索结果字典
        """
        import time
        start_time = time.time()
        
        # 生成缓存键
        cache_key = self._get_cache_key(keyword, disk_type)
        
        # 如果不是强制刷新，先尝试从缓存获取
        if not refresh:
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                # 添加缓存标识
                cached_result['from_cache'] = True
                cached_result['cache_time'] = int((time.time() - start_time) * 1000)
                return cached_result
        
        # 定期清理过期缓存（10%概率执行）
        import random
        if random.random() < 0.1:
            self._clean_expired_cache()
        
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
                
                result_data = {
                    'total': data.get('total', len(formatted_results)),
                    'page': page,
                    'page_size': page_size,
                    'time': elapsed_time,
                    'results': formatted_results,
                    'from_cache': False
                }
                
                # 保存到缓存
                self._save_to_cache(cache_key, keyword, disk_type, result_data)
                
                return result_data
            else:
                logger.warning(f"搜索返回错误: {result}")
                result_data = {
                    'total': 0,
                    'page': page,
                    'page_size': page_size,
                    'time': elapsed_time,
                    'results': [],
                    'from_cache': False
                }
                
                # 即使是空结果也缓存，避免频繁请求
                self._save_to_cache(cache_key, keyword, disk_type, result_data)
                
                return result_data
                
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

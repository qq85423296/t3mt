# -*- coding: utf-8 -*-
"""
影视排行榜API
"""
from flask import Blueprint, jsonify, request, Response
import requests
import logging
import json
import hashlib
from datetime import datetime, timedelta
from database import get_db

logger = logging.getLogger(__name__)

video_ranking_bp = Blueprint('video_ranking', __name__, url_prefix='/api/video_ranking')

# 缓存有效期（24小时）
CACHE_EXPIRE_HOURS = 24


def _init_ranking_cache_table():
    """初始化排行榜缓存表"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ranking_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT NOT NULL UNIQUE,
                    platform TEXT NOT NULL,
                    result_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            ''')
            
            # 创建索引加速查询
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_ranking_cache_key 
                ON ranking_cache(cache_key)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_ranking_cache_expires 
                ON ranking_cache(expires_at)
            ''')
            
            conn.commit()
    except Exception as e:
        logger.error(f"初始化排行榜缓存表失败: {e}")


def _get_cache_key(platform):
    """
    生成缓存键
    
    Args:
        platform: 平台名称（quark/360/douban）
    
    Returns:
        缓存键（MD5哈希）
    """
    cache_str = f"ranking_{platform}"
    return hashlib.md5(cache_str.encode('utf-8')).hexdigest()


def _get_cached_ranking(cache_key):
    """
    从缓存获取排行榜数据
    
    Args:
        cache_key: 缓存键
    
    Returns:
        缓存的排行榜数据，如果不存在或已过期则返回None
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT result_data, expires_at 
                FROM ranking_cache 
                WHERE cache_key = ?
            ''', (cache_key,))
            
            row = cursor.fetchone()
            if row:
                result_data = row[0]
                expires_at = datetime.fromisoformat(row[1])
                
                # 检查是否过期
                if datetime.now() < expires_at:
                    logger.info(f"命中排行榜缓存: {cache_key}")
                    return json.loads(result_data)
                else:
                    # 删除过期缓存
                    cursor.execute('DELETE FROM ranking_cache WHERE cache_key = ?', (cache_key,))
                    conn.commit()
                    logger.info(f"排行榜缓存已过期: {cache_key}")
            
            return None
    except Exception as e:
        logger.error(f"获取排行榜缓存失败: {e}")
        return None


def _save_ranking_to_cache(cache_key, platform, result_data):
    """
    保存排行榜数据到缓存
    
    Args:
        cache_key: 缓存键
        platform: 平台名称
        result_data: 排行榜数据
    """
    try:
        expires_at = datetime.now() + timedelta(hours=CACHE_EXPIRE_HOURS)
        result_json = json.dumps(result_data, ensure_ascii=False)
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO ranking_cache 
                (cache_key, platform, result_data, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (cache_key, platform, result_json, datetime.now(), expires_at))
            conn.commit()
            
        logger.info(f"排行榜数据已缓存: {platform}, 过期时间: {expires_at}")
    except Exception as e:
        logger.error(f"保存排行榜缓存失败: {e}")


def _clean_expired_ranking_cache():
    """清理过期的排行榜缓存"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM ranking_cache 
                WHERE expires_at < ?
            ''', (datetime.now(),))
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"清理了 {deleted_count} 条过期排行榜缓存")
    except Exception as e:
        logger.error(f"清理过期排行榜缓存失败: {e}")


# 初始化缓存表
_init_ranking_cache_table()


@video_ranking_bp.route('/quark', methods=['GET'])
def get_quark_ranking():
    """获取夸克影视排行榜（支持24小时缓存）"""
    try:
        # 检查是否强制刷新
        refresh = request.args.get('refresh', 'false').lower() == 'true'
        
        # 生成缓存键
        cache_key = _get_cache_key('quark')
        
        # 如果不是强制刷新，先尝试从缓存获取
        if not refresh:
            cached_result = _get_cached_ranking(cache_key)
            if cached_result:
                cached_result['from_cache'] = True
                return jsonify(cached_result)
        
        # 定期清理过期缓存（10%概率执行）
        import random
        if random.random() < 0.1:
            _clean_expired_ranking_cache()
        
        # 从API获取数据
        # 夸克API基础URL
        base_url = 'https://biz.quark.cn/api/trending/ranking/getYingshiRanking'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.quark.cn/',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Origin': 'https://www.quark.cn'
        }
        
        # 定义分类映射
        categories = {
            'movie': '电影',
            'tv': '电视剧',
            'variety': '综艺',
            'anime': '动漫'
        }
        
        result = {
            'movie': [],
            'tv': [],
            'variety': [],
            'anime': []
        }
        
        # 分别获取每个分类的数据
        for category_key, channel_name in categories.items():
            try:
                logger.info(f"正在获取夸克{channel_name}排行榜...")
                
                # 调用夸克API，传入channel参数
                response = requests.get(
                    base_url, 
                    headers=headers, 
                    params={'channel': channel_name},
                    timeout=10, 
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('code') == '00000' and data.get('data'):
                        # 获取影视列表
                        video_list = data.get('data', {}).get('hits', {}).get('hit', {}).get('item', [])
                        
                        if video_list:
                            logger.info(f"成功获取{channel_name} {len(video_list)} 条数据")
                            
                            # 处理数据
                            for item in video_list:
                                result[category_key].append({
                                    'title': item.get('title', ''),
                                    'cover': item.get('src', ''),
                                    'url': '#',
                                    'pv': item.get('hot_score', '0'),
                                    'ranking': item.get('ranking', 0),
                                    'desc': item.get('desc', ''),
                                    'score': item.get('score_avg', ''),
                                    'year': item.get('year', ''),
                                    'area': item.get('area', ''),
                                    'actors': item.get('actors', '')
                                })
                        else:
                            logger.warning(f"{channel_name}数据为空")
                    else:
                        logger.error(f"获取{channel_name}失败: code={data.get('code')}, msg={data.get('msg')}")
                else:
                    logger.error(f"获取{channel_name}失败: HTTP {response.status_code}")
                    
            except Exception as e:
                logger.error(f"获取{channel_name}异常: {e}")
                continue
        
        # 检查是否至少获取到一个分类的数据
        total_count = sum(len(result[key]) for key in result)
        
        if total_count == 0:
            logger.error("所有分类数据获取失败")
            return jsonify({
                'code': 500,
                'message': '获取数据失败'
            }), 500
        
        logger.info(f"夸克数据获取完成 - 电影: {len(result['movie'])}, 电视剧: {len(result['tv'])}, 综艺: {len(result['variety'])}, 动漫: {len(result['anime'])}")
        
        response_data = {
            'code': 200,
            'message': '获取成功',
            'data': result,
            'from_cache': False
        }
        
        # 保存到缓存
        _save_ranking_to_cache(cache_key, 'quark', response_data)
        
        return jsonify(response_data)
            
    except Exception as e:
        logger.error(f"获取夸克排行榜失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'获取失败: {str(e)}'
        }), 500


@video_ranking_bp.route('/360', methods=['GET'])
def get_360_ranking():
    """获取360影视排行榜（支持24小时缓存）"""
    try:
        # 检查是否强制刷新
        refresh = request.args.get('refresh', 'false').lower() == 'true'
        
        # 生成缓存键
        cache_key = _get_cache_key('360')
        
        # 如果不是强制刷新，先尝试从缓存获取
        if not refresh:
            cached_result = _get_cached_ranking(cache_key)
            if cached_result:
                cached_result['from_cache'] = True
                return jsonify(cached_result)
        
        # 定期清理过期缓存（10%概率执行）
        import random
        if random.random() < 0.1:
            _clean_expired_ranking_cache()
        
        # 从API获取数据
        # 360影视API基础URL
        base_url = 'https://api.web.360kan.com/v1/rank'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.360kan.com/',
            'Accept': 'application/json, text/plain, */*'
        }
        
        # 定义分类映射 (cat参数)
        categories = {
            'movie': 2,      # 电影
            'tv': 3,         # 电视剧
            'variety': 4,    # 综艺
            'anime': 5       # 动漫
        }
        
        result = {
            'movie': [],
            'tv': [],
            'variety': [],
            'anime': []
        }
        
        # 分别获取每个分类的数据
        for category_key, cat_id in categories.items():
            try:
                category_name = {'movie': '电影', 'tv': '电视剧', 'variety': '综艺', 'anime': '动漫'}[category_key]
                logger.info(f"正在获取360{category_name}排行榜...")
                
                # 调用360 API，传入cat参数
                response = requests.get(
                    base_url,
                    headers=headers,
                    params={'cat': cat_id},
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('data'):
                        video_list = data.get('data', [])
                        
                        if video_list:
                            logger.info(f"成功获取360{category_name} {len(video_list)} 条数据")
                            
                            # 处理数据
                            for idx, item in enumerate(video_list, 1):
                                # 处理分类标签
                                moviecat = item.get('moviecat', [])
                                category_str = ' '.join(moviecat) if isinstance(moviecat, list) else ''
                                
                                # 处理热度值（去除逗号）
                                pv = item.get('pv', '0').replace(',', '')
                                
                                result[category_key].append({
                                    'title': item.get('title', ''),
                                    'cover': item.get('cover', ''),
                                    'src': item.get('cover', ''),
                                    'url': item.get('url', '#'),
                                    'pv': pv,
                                    'hot_score': pv,
                                    'ranking': idx,
                                    'desc': item.get('description', ''),
                                    'score': item.get('doubanscore', ''),
                                    'score_avg': item.get('doubanscore', ''),
                                    'year': item.get('pubdate', '')[:4] if item.get('pubdate') else '',
                                    'category': category_str,
                                    'actors': '',
                                    'area': '',
                                    'hot_trend': item.get('percent', '0'),
                                    'upinfo': item.get('upinfo', ''),
                                    'vip': item.get('vip', False)
                                })
                        else:
                            logger.warning(f"360{category_name}数据为空")
                    else:
                        logger.error(f"获取360{category_name}失败: 返回数据格式错误")
                else:
                    logger.error(f"获取360{category_name}失败: HTTP {response.status_code}")
                    
            except Exception as e:
                logger.error(f"获取360{category_name}异常: {e}")
                continue
        
        # 检查是否至少获取到一个分类的数据
        total_count = sum(len(result[key]) for key in result)
        
        if total_count == 0:
            logger.error("所有分类数据获取失败")
            return jsonify({
                'code': 500,
                'message': '获取数据失败'
            }), 500
        
        logger.info(f"360数据获取完成 - 电影: {len(result['movie'])}, 电视剧: {len(result['tv'])}, 综艺: {len(result['variety'])}, 动漫: {len(result['anime'])}")
        
        response_data = {
            'code': 200,
            'message': '获取成功',
            'data': result,
            'from_cache': False
        }
        
        # 保存到缓存
        _save_ranking_to_cache(cache_key, '360', response_data)
        
        return jsonify(response_data)
            
    except Exception as e:
        logger.error(f"获取360排行榜失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'获取失败: {str(e)}'
        }), 500


@video_ranking_bp.route('/douban', methods=['GET'])
def get_douban_ranking():
    """获取豆瓣影视排行榜（支持24小时缓存）"""
    try:
        # 检查是否强制刷新
        refresh = request.args.get('refresh', 'false').lower() == 'true'
        
        # 生成缓存键
        cache_key = _get_cache_key('douban')
        
        # 如果不是强制刷新，先尝试从缓存获取
        if not refresh:
            cached_result = _get_cached_ranking(cache_key)
            if cached_result:
                cached_result['from_cache'] = True
                return jsonify(cached_result)
        
        # 定期清理过期缓存（10%概率执行）
        import random
        if random.random() < 0.1:
            _clean_expired_ranking_cache()
        
        # 从API获取数据
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://movie.douban.com/',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
        
        # 获取当前请求的完整URL（包含协议、域名和端口）
        # 优先从 X-Forwarded-Host 获取（Nginx代理会设置），其次使用 request.host
        scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
        host = request.headers.get('X-Forwarded-Host') or request.host
        
        # 构建完整的API基础URL
        api_base = f"{scheme}://{host}"
        
        logger.info(f"构建图片代理URL - scheme: {scheme}, host: {host}, X-Forwarded-Host: {request.headers.get('X-Forwarded-Host')}, request.host: {request.host}, api_base: {api_base}")
        
        result = {
            'movie': [],
            'tv': [],
            'variety': [],
            'anime': []
        }
        
        # 豆瓣电影Top250（电影分类）
        try:
            logger.info("正在获取豆瓣电影排行榜...")
            # 使用豆瓣电影API获取热门电影
            movie_url = 'https://movie.douban.com/j/search_subjects'
            movie_params = {
                'type': 'movie',
                'tag': '热门',
                'page_limit': 20,
                'page_start': 0
            }
            
            response = requests.get(movie_url, headers=headers, params=movie_params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                subjects = data.get('subjects', [])
                
                if subjects:
                    logger.info(f"成功获取豆瓣电影 {len(subjects)} 条数据")
                    
                    for idx, item in enumerate(subjects, 1):
                        # 将豆瓣图片URL转换为代理URL，使用完整的API域名
                        cover_url = item.get('cover', '')
                        if cover_url:
                            # 使用后端代理图片，构建完整URL
                            cover_url = f"{api_base}/api/video_ranking/proxy_image?url={requests.utils.quote(cover_url)}"
                        
                        result['movie'].append({
                            'title': item.get('title', ''),
                            'cover': cover_url,
                            'src': cover_url,
                            'url': item.get('url', '#'),
                            'pv': str(item.get('rate', '0')),
                            'hot_score': str(item.get('rate', '0')),
                            'ranking': idx,
                            'desc': '',
                            'score': item.get('rate', ''),
                            'score_avg': item.get('rate', ''),
                            'year': '',
                            'category': '',
                            'actors': ' '.join(item.get('casts', [])) if item.get('casts') else '',
                            'area': '',
                            'hot_trend': '0'
                        })
                else:
                    logger.warning("豆瓣电影数据为空")
            else:
                logger.error(f"获取豆瓣电影失败: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"获取豆瓣电影异常: {e}")
        
        # 豆瓣电视剧
        try:
            logger.info("正在获取豆瓣电视剧排行榜...")
            tv_url = 'https://movie.douban.com/j/search_subjects'
            tv_params = {
                'type': 'tv',
                'tag': '热门',
                'page_limit': 20,
                'page_start': 0
            }
            
            response = requests.get(tv_url, headers=headers, params=tv_params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                subjects = data.get('subjects', [])
                
                if subjects:
                    logger.info(f"成功获取豆瓣电视剧 {len(subjects)} 条数据")
                    
                    for idx, item in enumerate(subjects, 1):
                        # 将豆瓣图片URL转换为代理URL，使用完整的API域名
                        cover_url = item.get('cover', '')
                        if cover_url:
                            cover_url = f"{api_base}/api/video_ranking/proxy_image?url={requests.utils.quote(cover_url)}"
                        
                        result['tv'].append({
                            'title': item.get('title', ''),
                            'cover': cover_url,
                            'src': cover_url,
                            'url': item.get('url', '#'),
                            'pv': str(item.get('rate', '0')),
                            'hot_score': str(item.get('rate', '0')),
                            'ranking': idx,
                            'desc': '',
                            'score': item.get('rate', ''),
                            'score_avg': item.get('rate', ''),
                            'year': '',
                            'category': '',
                            'actors': ' '.join(item.get('casts', [])) if item.get('casts') else '',
                            'area': '',
                            'hot_trend': '0'
                        })
                else:
                    logger.warning("豆瓣电视剧数据为空")
            else:
                logger.error(f"获取豆瓣电视剧失败: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"获取豆瓣电视剧异常: {e}")
        
        # 豆瓣综艺
        try:
            logger.info("正在获取豆瓣综艺排行榜...")
            variety_url = 'https://movie.douban.com/j/search_subjects'
            variety_params = {
                'type': 'tv',
                'tag': '综艺',
                'page_limit': 20,
                'page_start': 0
            }
            
            response = requests.get(variety_url, headers=headers, params=variety_params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                subjects = data.get('subjects', [])
                
                if subjects:
                    logger.info(f"成功获取豆瓣综艺 {len(subjects)} 条数据")
                    
                    for idx, item in enumerate(subjects, 1):
                        # 将豆瓣图片URL转换为代理URL，使用完整的API域名
                        cover_url = item.get('cover', '')
                        if cover_url:
                            cover_url = f"{api_base}/api/video_ranking/proxy_image?url={requests.utils.quote(cover_url)}"
                        
                        result['variety'].append({
                            'title': item.get('title', ''),
                            'cover': cover_url,
                            'src': cover_url,
                            'url': item.get('url', '#'),
                            'pv': str(item.get('rate', '0')),
                            'hot_score': str(item.get('rate', '0')),
                            'ranking': idx,
                            'desc': '',
                            'score': item.get('rate', ''),
                            'score_avg': item.get('rate', ''),
                            'year': '',
                            'category': '综艺',
                            'actors': ' '.join(item.get('casts', [])) if item.get('casts') else '',
                            'area': '',
                            'hot_trend': '0'
                        })
                else:
                    logger.warning("豆瓣综艺数据为空")
            else:
                logger.error(f"获取豆瓣综艺失败: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"获取豆瓣综艺异常: {e}")
        
        # 豆瓣动漫
        try:
            logger.info("正在获取豆瓣动漫排行榜...")
            anime_url = 'https://movie.douban.com/j/search_subjects'
            anime_params = {
                'type': 'tv',
                'tag': '动画',
                'page_limit': 20,
                'page_start': 0
            }
            
            response = requests.get(anime_url, headers=headers, params=anime_params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                subjects = data.get('subjects', [])
                
                if subjects:
                    logger.info(f"成功获取豆瓣动漫 {len(subjects)} 条数据")
                    
                    for idx, item in enumerate(subjects, 1):
                        # 将豆瓣图片URL转换为代理URL，使用完整的API域名
                        cover_url = item.get('cover', '')
                        if cover_url:
                            cover_url = f"{api_base}/api/video_ranking/proxy_image?url={requests.utils.quote(cover_url)}"
                        
                        result['anime'].append({
                            'title': item.get('title', ''),
                            'cover': cover_url,
                            'src': cover_url,
                            'url': item.get('url', '#'),
                            'pv': str(item.get('rate', '0')),
                            'hot_score': str(item.get('rate', '0')),
                            'ranking': idx,
                            'desc': '',
                            'score': item.get('rate', ''),
                            'score_avg': item.get('rate', ''),
                            'year': '',
                            'category': '动画',
                            'actors': ' '.join(item.get('casts', [])) if item.get('casts') else '',
                            'area': '',
                            'hot_trend': '0'
                        })
                else:
                    logger.warning("豆瓣动漫数据为空")
            else:
                logger.error(f"获取豆瓣动漫失败: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"获取豆瓣动漫异常: {e}")
        
        # 检查是否至少获取到一个分类的数据
        total_count = sum(len(result[key]) for key in result)
        
        if total_count == 0:
            logger.error("所有分类数据获取失败")
            return jsonify({
                'code': 500,
                'message': '获取数据失败'
            }), 500
        
        logger.info(f"豆瓣数据获取完成 - 电影: {len(result['movie'])}, 电视剧: {len(result['tv'])}, 综艺: {len(result['variety'])}, 动漫: {len(result['anime'])}")
        
        response_data = {
            'code': 200,
            'message': '获取成功',
            'data': result,
            'from_cache': False
        }
        
        # 保存到缓存
        _save_ranking_to_cache(cache_key, 'douban', response_data)
        
        return jsonify(response_data)
            
    except Exception as e:
        logger.error(f"获取豆瓣排行榜失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'获取失败: {str(e)}'
        }), 500


@video_ranking_bp.route('/proxy_image', methods=['GET'])
def proxy_image():
    """代理图片请求，解决防盗链问题"""
    try:
        image_url = request.args.get('url')
        
        if not image_url:
            logger.error("代理图片请求缺少URL参数")
            return jsonify({'error': '缺少图片URL参数'}), 400
        
        logger.info(f"代理图片请求 - URL: {image_url}, 来源: {request.referrer}, Host: {request.host}")
        
        # 设置请求头，伪装成豆瓣网站的请求
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://movie.douban.com/',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
        
        # 请求图片
        response = requests.get(image_url, headers=headers, timeout=10, stream=True)
        
        if response.status_code == 200:
            # 获取图片内容类型
            content_type = response.headers.get('Content-Type', 'image/jpeg')
            
            logger.info(f"成功代理图片: {image_url}, Content-Type: {content_type}, Size: {len(response.content)} bytes")
            
            # 返回图片数据
            return Response(
                response.content,
                mimetype=content_type,
                headers={
                    'Cache-Control': 'public, max-age=86400',  # 缓存1天
                    'Access-Control-Allow-Origin': '*'
                }
            )
        else:
            logger.error(f"代理图片失败: HTTP {response.status_code}, URL: {image_url}")
            return jsonify({'error': '获取图片失败', 'status': response.status_code}), response.status_code
            
    except Exception as e:
        logger.error(f"代理图片异常: {e}, URL: {request.args.get('url', 'unknown')}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

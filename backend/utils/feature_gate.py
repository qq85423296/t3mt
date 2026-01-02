# -*- coding: utf-8 -*-
"""
功能限制装饰器
用于API接口的功能权限控制
"""
from functools import wraps
from flask import jsonify
from datetime import datetime, date

from database import get_db
from utils.license_manager import license_manager, LicenseType
from utils.logger import logger


def require_pro(feature_name=None, error_message=None):
    """
    要求付费版功能装饰器
    
    Args:
        feature_name: 功能名称（用于日志）
        error_message: 自定义错误消息
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            license_info = license_manager.get_current_license()
            
            if license_info['type'] != LicenseType.PRO:
                msg = error_message or f'此功能需要付费版，请升级到付费版解锁'
                logger.warning(f"功能限制: {feature_name or f.__name__} - {msg}")
                return jsonify({
                    'code': 403,
                    'message': msg,
                    'data': {
                        'feature': feature_name or f.__name__,
                        'current_license': license_info['type'],
                        'required_license': LicenseType.PRO
                    }
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def check_account_limit():
    """检查账号数量限制"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            license_info = license_manager.get_current_license()
            max_accounts = license_info['features'].get('max_accounts', 1)
            
            # -1表示无限制
            if max_accounts == -1:
                return f(*args, **kwargs)
            
            # 检查当前账号数量
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT COUNT(*) FROM quark_accounts WHERE status = 1')
                    current_count = cursor.fetchone()[0]
                    
                    if current_count >= max_accounts:
                        return jsonify({
                            'code': 403,
                            'message': f'社区版最多只能添加{max_accounts}个账号，请升级到付费版解锁限制',
                            'data': {
                                'current_count': current_count,
                                'max_count': max_accounts,
                                'license_type': license_info['type']
                            }
                        }), 403
            except Exception as e:
                logger.error(f"检查账号限制失败: {e}")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def check_video_task_limit():
    """检查影视任务数量限制"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            license_info = license_manager.get_current_license()
            max_tasks = license_info['features'].get('max_video_tasks', 3)
            
            # -1表示无限制
            if max_tasks == -1:
                return f(*args, **kwargs)
            
            # 检查当前任务数量
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT COUNT(*) FROM video_tasks')
                    current_count = cursor.fetchone()[0]
                    
                    if current_count >= max_tasks:
                        return jsonify({
                            'code': 403,
                            'message': f'社区版最多只能创建{max_tasks}个影视下载任务，请升级到付费版解锁限制',
                            'data': {
                                'current_count': current_count,
                                'max_count': max_tasks,
                                'license_type': license_info['type']
                            }
                        }), 403
            except Exception as e:
                logger.error(f"检查任务限制失败: {e}")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def check_parse_limit():
    """检查每日解析次数限制"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            license_info = license_manager.get_current_license()
            daily_limit = license_info['features'].get('daily_parse_limit', 10)
            
            # -1表示无限制
            if daily_limit == -1:
                return f(*args, **kwargs)
            
            # 检查今日解析次数
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    today = date.today().isoformat()
                    
                    cursor.execute('''
                        SELECT parse_count FROM daily_usage_stats 
                        WHERE stat_date = ? AND usage_type = 'video_parse'
                    ''', (today,))
                    
                    row = cursor.fetchone()
                    current_count = row[0] if row else 0
                    
                    if current_count >= daily_limit:
                        return jsonify({
                            'code': 403,
                            'message': f'今日解析次数已达上限({daily_limit}次)，请明天再试或升级到付费版(200次/天)',
                            'data': {
                                'current_count': current_count,
                                'daily_limit': daily_limit,
                                'license_type': license_info['type']
                            }
                        }), 403
                    
                    # 增加计数
                    if row:
                        cursor.execute('''
                            UPDATE daily_usage_stats 
                            SET parse_count = parse_count + 1, updated_at = datetime('now', 'localtime')
                            WHERE stat_date = ? AND usage_type = 'video_parse'
                        ''', (today,))
                    else:
                        cursor.execute('''
                            INSERT INTO daily_usage_stats (stat_date, usage_type, parse_count)
                            VALUES (?, 'video_parse', 1)
                        ''', (today,))
                    
                    conn.commit()
                    
            except Exception as e:
                logger.error(f"检查解析限制失败: {e}")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def check_quality_limit(requested_quality):
    """
    检查画质限制
    
    Args:
        requested_quality: 请求的画质 (360p/720p/1080p/4k)
    
    Returns:
        (allowed, actual_quality, message)
    """
    license_info = license_manager.get_current_license()
    features = license_info['features']
    
    # 付费版无限制
    if license_info['type'] == LicenseType.PRO:
        return True, requested_quality, None
    
    # 社区版检查
    allowed_quality = features.get('video_quality', '360p')
    trial_count = features.get('video_quality_4k_trial', 3)
    
    # 如果请求4K
    if requested_quality == '4k':
        # 检查体验次数
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                today = date.today().isoformat()
                
                cursor.execute('''
                    SELECT quality_4k_count FROM daily_usage_stats 
                    WHERE stat_date = ? AND usage_type = 'video_parse'
                ''', (today,))
                
                row = cursor.fetchone()
                used_count = row[0] if row else 0
                
                if used_count >= trial_count:
                    return False, '360p', f'4K画质体验次数已用完(每日{trial_count}次)，已自动切换为360P。升级付费版解锁4K画质'
                
                # 增加4K使用计数
                if row:
                    cursor.execute('''
                        UPDATE daily_usage_stats 
                        SET quality_4k_count = quality_4k_count + 1
                        WHERE stat_date = ? AND usage_type = 'video_parse'
                    ''', (today,))
                else:
                    cursor.execute('''
                        INSERT INTO daily_usage_stats (stat_date, usage_type, quality_4k_count)
                        VALUES (?, 'video_parse', 1)
                    ''', (today,))
                
                conn.commit()
                return True, '4k', f'使用4K画质(剩余{trial_count - used_count - 1}次体验机会)'
                
        except Exception as e:
            logger.error(f"检查画质限制失败: {e}")
            return False, '360p', '检查画质限制失败，使用默认360P'
    
    # 其他画质请求，社区版只允许360p
    if requested_quality != '360p':
        return False, '360p', f'社区版仅支持360P画质，请升级付费版解锁{requested_quality}画质'
    
    return True, requested_quality, None


def get_license_info_for_frontend():
    """获取许可证信息供前端显示"""
    license_info = license_manager.get_current_license()
    features = license_info['features']
    
    # 获取今日使用统计
    today_stats = {}
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            today = date.today().isoformat()
            
            cursor.execute('''
                SELECT parse_count, quality_4k_count 
                FROM daily_usage_stats 
                WHERE stat_date = ? AND usage_type = 'video_parse'
            ''', (today,))
            
            row = cursor.fetchone()
            if row:
                today_stats = {
                    'parse_count': row[0] or 0,
                    'quality_4k_count': row[1] or 0
                }
            else:
                today_stats = {
                    'parse_count': 0,
                    'quality_4k_count': 0
                }
    except Exception as e:
        logger.error(f"获取今日统计失败: {e}")
        today_stats = {'parse_count': 0, 'quality_4k_count': 0}
    
    return {
        'license_type': license_info['type'],
        'is_pro': license_info['type'] == LicenseType.PRO,
        'is_trial': license_info.get('is_trial', False),
        'days_remaining': license_info.get('days_remaining', 0),
        'expire_time': license_info.get('expire_time'),
        'features': {
            'max_accounts': features.get('max_accounts', 1),
            'max_video_tasks': features.get('max_video_tasks', 3),
            'custom_parse_api': features.get('custom_parse_api', False),
            'video_quality': features.get('video_quality', '360p'),
            'video_quality_4k_trial': features.get('video_quality_4k_trial', 3),
            'daily_parse_limit': features.get('daily_parse_limit', 10)
        },
        'today_usage': today_stats
    }

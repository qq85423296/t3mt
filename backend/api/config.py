# -*- coding: utf-8 -*-
"""
系统配置API
"""
import json
from flask import Blueprint, request, jsonify
from models.config import ConfigModel
from utils.logger import logger
from utils.feature_gate import require_pro
from utils.config_crypto import config_crypto

config_bp = Blueprint('config', __name__, url_prefix='/api/config')


def _get_default_parse_api():
    """从加密配置获取默认解析接口(隐藏URL)"""
    try:
        default_api = config_crypto.get_config('video_parse.default_parse_api', {})
        if default_api:
            # 返回时隐藏URL,只显示"默认"
            return {
                'api_url': '默认',  # 前端显示"默认"
                'url_path': default_api.get('url_path', 'final_url'),
                'code_path': default_api.get('code_path', 'code'),
                'success_code': default_api.get('success_code', '200'),
                'is_default': True,  # 标记为默认接口
                'readonly': True  # 标记为只读
            }
    except Exception as e:
        logger.error(f"获取默认解析接口失败: {e}")
    return None


@config_bp.route('', methods=['GET'])
def get_config():
    """获取所有配置"""
    try:
        # 获取各类配置
        config_data = {
            'system': {
                'api_base_url': ConfigModel.get_config('system_api_base_url', 'http://127.0.0.1:9710')
            },
            'log': {
                'retention_days': int(ConfigModel.get_config('schedule_log_retention_days', 30))
            },
            'download': {
                'default_dir': ConfigModel.get_config('download_default_dir', 'downloads'),
                'timeout': int(ConfigModel.get_config('download_timeout', 30)),
                # 多线程下载配置
                'enable_multithread': ConfigModel.get_config('download_enable_multithread', 'true') == 'true',
                'threads_per_file': int(ConfigModel.get_config('download_threads_per_file', 4)),
                'multithread_chunk_size': int(ConfigModel.get_config('download_multithread_chunk_size', 10))
            },
            'pansou': {
                'api_url': ConfigModel.get_config('pansou_api_url', 'http://192.168.0.111:8383/'),
                'api_key': ConfigModel.get_config('pansou_api_key', '')
            },
            'video_parse': {
                # 从加密配置获取默认解析接口
                'default_api': _get_default_parse_api(),
                # 用户自定义接口配置
                'apis': ConfigModel.get_config_list('video_parse_apis') or []
            },
            'video_download': {
                'retry_count': int(ConfigModel.get_config('video_download_retry_count', 3)),
                'timeout': int(ConfigModel.get_config('video_download_timeout', 30)),
                'enable_multithread': ConfigModel.get_config('video_download_enable_multithread', 'true') == 'true',
                'threads_count': int(ConfigModel.get_config('video_download_threads_count', 4)),
                'default_dir': ConfigModel.get_config('video_download_default_dir', '/app/backend/downloads/官网下载'),
                'temp_dir': ConfigModel.get_config('video_download_temp_dir', '/app/backend/downloads/temp'),
                'max_threads': int(ConfigModel.get_config('video_download_max_threads', 3))
            },
            'video_expiration': {
                'enabled': ConfigModel.get_config('video_auto_expiration_enabled', '1') == '1',
                'days': int(ConfigModel.get_config('video_auto_expiration_days', '7'))
            },
            'default': {
                'exclude_keywords': ConfigModel.get_config('default_exclude_keywords', '')
            }
        }
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': config_data
        })
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取配置失败: {str(e)}'
        }), 500


@config_bp.route('/video-expiration', methods=['GET'])
def get_video_expiration_config():
    """获取影视任务自动失效配置"""
    try:
        # 获取配置，如果不存在则使用默认值
        enabled_str = ConfigModel.get_config('video_auto_expiration_enabled', '1')
        days_str = ConfigModel.get_config('video_auto_expiration_days', '7')
        
        # 转换为布尔值和整数，添加错误处理
        try:
            enabled = enabled_str == '1'
            days = int(days_str)
            
            # 验证days的合法性
            if days < 1 or days > 365:
                logger.warning(f"配置的超时天数不合法: {days}，使用默认值7天")
                days = 7
                
        except ValueError as e:
            logger.error(f"配置值转换失败: enabled_str={enabled_str}, days_str={days_str}, error={e}")
            # 使用默认值
            enabled = True
            days = 7
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'enabled': enabled,
                'days': days
            }
        })
    except Exception as e:
        logger.error(f"获取影视任务自动失效配置失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'获取配置失败: {str(e)}'
        }), 500


@config_bp.route('/video-expiration', methods=['POST'])
def save_video_expiration_config():
    """保存影视任务自动失效配置"""
    try:
        data = request.get_json()
        
        # 验证请求体是否为空
        if not data:
            return jsonify({
                'code': 400,
                'message': '请求体不能为空'
            }), 400
        
        # 验证必需字段
        if 'enabled' not in data or 'days' not in data:
            return jsonify({
                'code': 400,
                'message': '缺少必需字段：enabled 和 days'
            }), 400
        
        enabled = data['enabled']
        days = data['days']
        
        # 验证enabled字段类型
        if not isinstance(enabled, bool):
            return jsonify({
                'code': 400,
                'message': 'enabled 字段必须是布尔值'
            }), 400
        
        # 验证days字段类型和范围
        if not isinstance(days, int):
            return jsonify({
                'code': 400,
                'message': 'days 字段必须是整数'
            }), 400
        
        if days < 1 or days > 365:
            return jsonify({
                'code': 400,
                'message': '超时天数必须是1-365之间的整数'
            }), 400
        
        # 保存配置
        try:
            enabled_str = '1' if enabled else '0'
            ConfigModel.set_config('video_auto_expiration_enabled', enabled_str, 'video')
            ConfigModel.set_config('video_auto_expiration_days', str(days), 'video')
        except Exception as e:
            logger.error(f"保存配置到数据库失败: enabled={enabled}, days={days}, error={e}", exc_info=True)
            return jsonify({
                'code': 500,
                'message': f'保存配置失败: {str(e)}'
            }), 500
        
        logger.info(f"[AutoExpiration] 配置保存成功: enabled={enabled}, days={days}")
        
        return jsonify({
            'code': 200,
            'message': '配置保存成功'
        })
    except Exception as e:
        logger.error(f"保存影视任务自动失效配置失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'保存配置失败: {str(e)}'
        }), 500


@config_bp.route('', methods=['POST'])
def save_config():
    """保存配置"""
    try:
        data = request.get_json()
        
        # 保存系统配置
        if 'system' in data:
            ConfigModel.set_config('system_api_base_url', data['system']['api_base_url'], 'system')
        
        # 保存日志配置
        if 'log' in data:
            ConfigModel.set_config('schedule_log_retention_days', str(data['log']['retention_days']), 'log')
        
        # 保存下载配置
        if 'download' in data:
            download_config = data['download']
            ConfigModel.set_config('download_default_dir', download_config['default_dir'], 'download')
            ConfigModel.set_config('download_timeout', str(download_config['timeout']), 'download')
            # 多线程下载配置
            ConfigModel.set_config('download_enable_multithread', 'true' if download_config.get('enable_multithread') else 'false', 'download')
            ConfigModel.set_config('download_threads_per_file', str(download_config['threads_per_file']), 'download')
            ConfigModel.set_config('download_multithread_chunk_size', str(download_config['multithread_chunk_size']), 'download')
        
        # 保存盘搜配置
        if 'pansou' in data:
            pansou_config = data['pansou']
            ConfigModel.set_config('pansou_api_url', pansou_config['api_url'], 'pansou')
            ConfigModel.set_config('pansou_api_key', pansou_config.get('api_key', ''), 'pansou')
        
        # 保存影视解析配置
        if 'video_parse' in data:
            video_parse_config = data['video_parse']
            
            # 检查是否尝试修改自定义解析接口（付费版功能）
            if 'apis' in video_parse_config or 'api_url' in video_parse_config:
                from utils.license_manager import license_manager, LicenseType
                license_info = license_manager.get_current_license()
                
                if not license_info['features'].get('custom_parse_api', False):
                    return jsonify({
                        'code': 403,
                        'message': '自定义影视解析接口是付费版功能，请升级到付费版解锁',
                        'data': {
                            'feature': 'custom_parse_api',
                            'license_type': license_info['type']
                        }
                    }), 403
            
            # 保存用户自定义接口配置
            if 'apis' in video_parse_config:
                ConfigModel.set_config_list('video_parse_apis', video_parse_config['apis'], 'video_parse')
        
        # 保存影视下载配置
        if 'video_download' in data:
            video_download_config = data['video_download']
            ConfigModel.set_config('video_download_retry_count', str(video_download_config.get('retry_count', 3)), 'video_download')
            ConfigModel.set_config('video_download_timeout', str(video_download_config.get('timeout', 30)), 'video_download')
            ConfigModel.set_config('video_download_enable_multithread', 'true' if video_download_config.get('enable_multithread') else 'false', 'video_download')
            ConfigModel.set_config('video_download_threads_count', str(video_download_config.get('threads_count', 4)), 'video_download')
            ConfigModel.set_config('video_download_default_dir', video_download_config.get('default_dir', '/app/backend/downloads/官网下载'), 'video_download')
            ConfigModel.set_config('video_download_temp_dir', video_download_config.get('temp_dir', '/app/backend/downloads/temp'), 'video_download')
            ConfigModel.set_config('video_download_max_threads', str(video_download_config.get('max_threads', 3)), 'video_download')
        
        # 保存影视任务自动失效配置
        if 'video_expiration' in data:
            video_expiration_config = data['video_expiration']
            
            # 验证days字段
            days = video_expiration_config.get('days', 7)
            if not isinstance(days, int) or days < 1 or days > 365:
                return jsonify({
                    'code': 400,
                    'message': '超时天数必须是1-365之间的整数'
                }), 400
            
            enabled = video_expiration_config.get('enabled', True)
            enabled_str = '1' if enabled else '0'
            
            ConfigModel.set_config('video_auto_expiration_enabled', enabled_str, 'video')
            ConfigModel.set_config('video_auto_expiration_days', str(days), 'video')
            
            logger.info(f"[AutoExpiration] 配置保存成功: enabled={enabled}, days={days}")
        
        # 保存默认排除关键词配置
        if 'default' in data:
            default_config = data['default']
            if 'exclude_keywords' in default_config:
                exclude_keywords = default_config['exclude_keywords']
                ConfigModel.set_config('default_exclude_keywords', exclude_keywords, 'default')
                logger.info(f"[DefaultConfig] 默认排除关键词保存成功: {exclude_keywords}")
        
        logger.info("系统配置保存成功")
        
        return jsonify({
            'code': 200,
            'message': '配置保存成功'
        })
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'保存配置失败: {str(e)}'
        }), 500

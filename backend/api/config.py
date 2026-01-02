# -*- coding: utf-8 -*-
"""
系统配置API
"""
import json
from flask import Blueprint, request, jsonify
from models.config import ConfigModel
from services.email_service import EmailService
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
                'max_concurrent': int(ConfigModel.get_config('download_max_concurrent', 3)),
                'chunk_size': int(ConfigModel.get_config('download_chunk_size', 2)),
                'retry_count': int(ConfigModel.get_config('download_retry_count', 3)),
                'retry_delay': int(ConfigModel.get_config('download_retry_delay', 5)),
                'timeout': int(ConfigModel.get_config('download_timeout', 30)),
                # 多线程下载配置
                'enable_multithread': ConfigModel.get_config('download_enable_multithread', 'true') == 'true',
                'multithread_threshold': int(ConfigModel.get_config('download_multithread_threshold', 50)),
                'threads_per_file': int(ConfigModel.get_config('download_threads_per_file', 4)),
                'multithread_chunk_size': int(ConfigModel.get_config('download_multithread_chunk_size', 10))
            },
            'email': {
                'smtp_server': ConfigModel.get_config('email_smtp_server', ''),
                'smtp_port': int(ConfigModel.get_config('email_smtp_port', 465)),
                'sender': ConfigModel.get_config('email_sender', ''),
                'password': '******' if ConfigModel.get_config('email_password') else '',
                'receivers': ConfigModel.get_config_list('email_receivers')
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
                'default_dir': ConfigModel.get_config('video_download_default_dir', '/vol2/1000/媒体库/video/官网下载'),
                'temp_dir': ConfigModel.get_config('video_download_temp_dir', '/vol2/1000/媒体库/video/temp'),
                'max_threads': int(ConfigModel.get_config('video_download_max_threads', 3))
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
            ConfigModel.set_config('download_max_concurrent', str(download_config['max_concurrent']), 'download')
            ConfigModel.set_config('download_chunk_size', str(download_config['chunk_size']), 'download')
            ConfigModel.set_config('download_retry_count', str(download_config['retry_count']), 'download')
            ConfigModel.set_config('download_retry_delay', str(download_config['retry_delay']), 'download')
            ConfigModel.set_config('download_timeout', str(download_config['timeout']), 'download')
            # 多线程下载配置
            ConfigModel.set_config('download_enable_multithread', 'true' if download_config.get('enable_multithread') else 'false', 'download')
            ConfigModel.set_config('download_multithread_threshold', str(download_config['multithread_threshold']), 'download')
            ConfigModel.set_config('download_threads_per_file', str(download_config['threads_per_file']), 'download')
            ConfigModel.set_config('download_multithread_chunk_size', str(download_config['multithread_chunk_size']), 'download')
        
        # 保存邮件配置
        if 'email' in data:
            email_config = data['email']
            ConfigModel.set_config('email_smtp_server', email_config['smtp_server'], 'email')
            ConfigModel.set_config('email_smtp_port', str(email_config['smtp_port']), 'email')
            ConfigModel.set_config('email_sender', email_config['sender'], 'email')
            
            # 只有提供了新密码才更新
            if email_config.get('password') and email_config['password'] != '******':
                ConfigModel.set_config('email_password', email_config['password'], 'email')
            
            ConfigModel.set_config_list('email_receivers', email_config.get('receivers', []), 'email')
        
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
            ConfigModel.set_config('video_download_default_dir', video_download_config.get('default_dir', '/vol2/1000/媒体库/video/官网下载'), 'video_download')
            ConfigModel.set_config('video_download_temp_dir', video_download_config.get('temp_dir', '/vol2/1000/媒体库/video/temp'), 'video_download')
            ConfigModel.set_config('video_download_max_threads', str(video_download_config.get('max_threads', 3)), 'video_download')
        
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


@config_bp.route('/email/test', methods=['POST'])
def test_email():
    """测试邮件配置"""
    try:
        data = request.get_json()
        
        # 验证必填字段
        required_fields = ['smtp_server', 'smtp_port', 'sender', 'password', 'receiver']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'code': 400,
                    'message': f'{field}不能为空'
                }), 400
        
        # 构建SMTP配置
        smtp_config = {
            'server': data['smtp_server'],
            'port': data['smtp_port'],
            'sender': data['sender'],
            'password': data['password']
        }
        
        # 发送测试邮件
        EmailService.test_smtp_config(smtp_config, data['receiver'])
        
        return jsonify({
            'code': 200,
            'message': '测试邮件发送成功'
        })
    except Exception as e:
        logger.error(f"测试邮件配置失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'测试失败: {str(e)}'
        }), 500

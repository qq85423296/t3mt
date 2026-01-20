# -*- coding: utf-8 -*-
"""
资源搜索API
"""
from flask import Blueprint, request, jsonify
from services.search_service import SearchService
from services.quark_service import QuarkService
from models.account import Account
from models.config import ConfigModel
from utils.logger import logger

search_bp = Blueprint('search', __name__, url_prefix='/api/search')


@search_bp.route('', methods=['GET'])
def search_resources():
    """搜索资源"""
    try:
        keyword = request.args.get('keyword')
        disk_type = request.args.get('type')
        page = request.args.get('page', default=1, type=int)
        page_size = request.args.get('page_size', default=20, type=int)
        
        # 处理前端传递的字符串"null"
        if disk_type == 'null' or disk_type == '':
            disk_type = None
        
        if not keyword:
            return jsonify({
                'code': 400,
                'message': '搜索关键词不能为空'
            }), 400
        
        # 获取盘搜API配置
        api_url = ConfigModel.get_config('pansou_api_url')
        api_key = ConfigModel.get_config('pansou_api_key')
        
        if not api_url:
            return jsonify({
                'code': 400,
                'message': '请先配置盘搜API地址'
            }), 400
        
        # 执行搜索
        search_service = SearchService(api_url, api_key)
        result = search_service.search(keyword, disk_type, page, page_size)
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': result
        })
    except Exception as e:
        logger.error(f"搜索资源失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'搜索失败: {str(e)}'
        }), 500


@search_bp.route('/check-validity', methods=['POST'])
def check_validity():
    """检测分享链接有效性"""
    try:
        data = request.get_json()
        share_url = data.get('url')
        
        if not share_url:
            return jsonify({
                'code': 400,
                'message': '分享链接不能为空'
            }), 400
        
        # 判断链接类型
        is_tianyi = 'cloud.189.cn' in share_url or 'c.189.cn' in share_url
        
        if is_tianyi:
            # 天翼云盘链接检测
            from services.cloud189_service import Cloud189Service
            from models.cloud_type import CloudType
            
            # 获取天翼云盘主账号
            main_account = Account.get_main_account(CloudType.CLOUD189)
            if not main_account:
                return jsonify({
                    'code': 400,
                    'message': '请先配置天翼云盘账号'
                }), 400
            
            # 创建天翼云盘服务
            cloud189_service = Cloud189Service(
                main_account['cookie'],
                username=main_account.get('username'),
                password=main_account.get('password')
            )
            
            # 解析分享链接
            result = cloud189_service.parse_share_url(share_url)
            
            if result.get('code') == 0:
                return jsonify({
                    'code': 200,
                    'message': 'success',
                    'data': {
                        'valid': True,
                        'title': result.get('data', {}).get('title', ''),
                        'file_count': len(result.get('data', {}).get('files', []))
                    }
                })
            else:
                return jsonify({
                    'code': 200,
                    'message': 'success',
                    'data': {
                        'valid': False,
                        'error': result.get('message', '链接无效')
                    }
                })
        else:
            # 夸克网盘链接检测
            main_account = Account.get_main_account()
            if not main_account:
                return jsonify({
                    'code': 400,
                    'message': '请先配置夸克账号'
                }), 400
            
            # 检测链接有效性
            quark_service = QuarkService(main_account['cookie'])
            result = SearchService.check_quark_share_validity(share_url, quark_service)
            
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': result
            })
    except Exception as e:
        logger.error(f"检测链接有效性失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'检测失败: {str(e)}'
        }), 500

# -*- coding: utf-8 -*-
"""
云盘文件操作API - 支持多云盘类型
"""
from flask import Blueprint, request, jsonify
from services.cloud_service_factory import CloudServiceFactory
from services.account_service import AccountService
from models.cloud_type import CloudType
from utils.logger import logger

quark_bp = Blueprint('quark', __name__, url_prefix='/api/quark')


@quark_bp.route('/files', methods=['GET'])
def get_files():
    """获取文件列表"""
    try:
        account_id = request.args.get('account_id', type=int)
        folder_id = request.args.get('folder_id', default='0')
        page = request.args.get('page', default=1, type=int)
        page_size = request.args.get('page_size', default=50, type=int)
        
        if not account_id:
            return jsonify({
                'code': 400,
                'message': '账号ID不能为空'
            }), 400
        
        # 获取账号信息
        account = AccountService.get_account(account_id)
        if not account:
            return jsonify({
                'code': 404,
                'message': '账号不存在'
            }), 404
        
        cloud_type = account.get('cloud_type', CloudType.QUARK)
        
        # 根据云盘类型创建服务
        service = CloudServiceFactory.create_service(cloud_type, account['cookie'])
        
        # 天翼云盘根目录ID为-11，夸克为0
        if cloud_type == CloudType.CLOUD189 and folder_id == '0':
            folder_id = '-11'
        
        result = service.get_file_list(folder_id, page, page_size)
        
        # 转换数据格式
        if result.get('code') == 0 and result.get('data'):
            file_list = result['data'].get('list', [])
            items = []
            
            for file in file_list:
                # 夸克和天翼云盘字段名不同，统一处理
                if cloud_type == CloudType.QUARK:
                    items.append({
                        'id': file.get('fid'),
                        'name': file.get('file_name'),
                        'isFolder': file.get('dir', False),
                        'size': file.get('size', 0),
                        'modifiedTime': file.get('updated_at'),
                        'mimeType': file.get('mime_type', ''),
                        'category': file.get('category', 0),
                    })
                else:
                    # 天翼云盘格式
                    items.append({
                        'id': file.get('id'),
                        'name': file.get('name'),
                        'isFolder': file.get('isFolder', False),
                        'size': file.get('size', 0),
                        'modifiedTime': file.get('modifiedTime'),
                        'mimeType': file.get('mimeType', ''),
                    })
            
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {
                    'items': items,
                    'total': result['data'].get('metadata', {}).get('_total', len(items)),
                    'cloud_type': cloud_type
                }
            })
        else:
            return jsonify({
                'code': 500,
                'message': result.get('message', '获取文件列表失败')
            }), 500
    except Exception as e:
        logger.error(f"获取文件列表失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'获取文件列表失败: {str(e)}'
        }), 500


@quark_bp.route('/folder', methods=['POST'])
def create_folder():
    """创建文件夹"""
    try:
        data = request.get_json()
        account_id = data.get('account_id')
        parent_id = data.get('parent_id', '0')
        name = data.get('name')
        
        if not account_id or not name:
            return jsonify({
                'code': 400,
                'message': '账号ID和文件夹名称不能为空'
            }), 400
        
        # 获取账号信息
        account = AccountService.get_account(account_id)
        if not account:
            return jsonify({
                'code': 404,
                'message': '账号不存在'
            }), 404
        
        cloud_type = account.get('cloud_type', CloudType.QUARK)
        
        # 天翼云盘根目录ID为-11
        if cloud_type == CloudType.CLOUD189 and parent_id == '0':
            parent_id = '-11'
        
        # 创建文件夹
        service = CloudServiceFactory.create_service(cloud_type, account['cookie'])
        result = service.mkdir(name, parent_id)
        
        logger.info(f"创建文件夹返回: {result}")
        
        if result.get('code') == 0:
            return jsonify({
                'code': 200,
                'message': '文件夹创建成功',
                'data': result.get('data')
            })
        else:
            return jsonify({
                'code': 500,
                'message': result.get('message', '创建文件夹失败')
            }), 500
    except Exception as e:
        logger.error(f"创建文件夹失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'创建文件夹失败: {str(e)}'
        }), 500


@quark_bp.route('/delete', methods=['POST', 'DELETE'])
def delete_files():
    """删除文件/文件夹"""
    try:
        try:
            data = request.get_json(force=True)
        except Exception as json_error:
            logger.error(f"解析JSON失败: {json_error}")
            return jsonify({
                'code': 400,
                'message': f'请求数据格式错误: {str(json_error)}'
            }), 400
        
        if not data:
            return jsonify({
                'code': 400,
                'message': '请求数据不能为空'
            }), 400
        
        account_id = data.get('account_id')
        file_ids = data.get('file_ids', [])
        file_infos = data.get('file_infos')  # 可选，包含name和isFolder
        
        if not account_id or not file_ids:
            return jsonify({
                'code': 400,
                'message': '账号ID和文件ID不能为空'
            }), 400
        
        # 获取账号信息
        account = AccountService.get_account(account_id)
        if not account:
            return jsonify({
                'code': 404,
                'message': '账号不存在'
            }), 404
        
        cloud_type = account.get('cloud_type', CloudType.QUARK)
        
        # 删除文件
        service = CloudServiceFactory.create_service(cloud_type, account['cookie'])
        
        # 天翼云盘需要传递文件信息
        if cloud_type == CloudType.CLOUD189 and file_infos:
            result = service.delete(file_ids, file_infos)
        else:
            result = service.delete(file_ids)
        
        logger.info(f"删除操作返回: {result}")
        
        if result.get('code') == 0:
            return jsonify({
                'code': 200,
                'message': '删除成功',
                'data': result.get('data')
            })
        else:
            return jsonify({
                'code': 500,
                'message': result.get('message', '删除失败')
            }), 500
    except Exception as e:
        logger.error(f"删除文件失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'删除文件失败: {str(e)}'
        }), 500


@quark_bp.route('/share', methods=['POST'])
def share_files():
    """分享文件/文件夹"""
    try:
        data = request.get_json()
        account_id = data.get('account_id')
        file_ids = data.get('file_ids', [])
        expire_days = data.get('expire_days', 7)
        need_password = data.get('need_password', False)
        password = data.get('password')
        
        if not account_id or not file_ids:
            return jsonify({
                'code': 400,
                'message': '账号ID和文件ID不能为空'
            }), 400
        
        # 获取账号信息
        account = AccountService.get_account(account_id)
        if not account:
            return jsonify({
                'code': 404,
                'message': '账号不存在'
            }), 404
        
        cloud_type = account.get('cloud_type', CloudType.QUARK)
        
        # 分享文件
        service = CloudServiceFactory.create_service(cloud_type, account['cookie'])
        result = service.create_share(file_ids, expire_days, need_password, password)
        
        if result.get('code') == 0:
            return jsonify({
                'code': 200,
                'message': '分享成功',
                'data': result.get('data')
            })
        else:
            return jsonify({
                'code': 500,
                'message': result.get('message', '分享失败')
            }), 500
    except Exception as e:
        logger.error(f"分享文件失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'分享文件失败: {str(e)}'
        }), 500


@quark_bp.route('/download', methods=['GET'])
def get_download_url():
    """获取下载链接"""
    try:
        account_id = request.args.get('account_id', type=int)
        file_id = request.args.get('file_id')
        
        if not account_id or not file_id:
            return jsonify({
                'code': 400,
                'message': '账号ID和文件ID不能为空'
            }), 400
        
        # 获取账号信息
        account = AccountService.get_account(account_id)
        if not account:
            return jsonify({
                'code': 404,
                'message': '账号不存在'
            }), 404
        
        cloud_type = account.get('cloud_type', CloudType.QUARK)
        
        # 获取下载链接
        service = CloudServiceFactory.create_service(cloud_type, account['cookie'])
        result, new_cookie = service.get_download_url([file_id])
        
        if result.get('code') == 0 and result.get('data'):
            download_url = result['data'][0].get('download_url', '')
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {
                    'download_url': download_url,
                    'downloadUrl': download_url
                }
            })
        else:
            return jsonify({
                'code': 500,
                'message': result.get('message', '获取下载链接失败')
            }), 500
    except Exception as e:
        logger.error(f"获取下载链接失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'获取下载链接失败: {str(e)}'
        }), 500


@quark_bp.route('/save-share', methods=['POST'])
def save_share():
    """转存分享文件"""
    try:
        data = request.get_json()
        account_id = data.get('account_id')
        share_url = data.get('share_url')
        target_folder_id = data.get('target_folder_id', '0')
        password = data.get('password')
        
        if not account_id or not share_url:
            return jsonify({
                'code': 400,
                'message': '账号ID和分享链接不能为空'
            }), 400
        
        # 获取账号信息
        account = AccountService.get_account(account_id)
        if not account:
            return jsonify({
                'code': 404,
                'message': '账号不存在'
            }), 404
        
        cloud_type = account.get('cloud_type', CloudType.QUARK)
        
        # 天翼云盘根目录ID为-11
        if cloud_type == CloudType.CLOUD189 and target_folder_id == '0':
            target_folder_id = '-11'
        
        # 转存文件
        service = CloudServiceFactory.create_service(cloud_type, account['cookie'])
        result = service.save_share(share_url, target_folder_id, password)
        
        if result.get('success'):
            return jsonify({
                'code': 200,
                'message': '转存成功',
                'data': result
            })
        else:
            return jsonify({
                'code': 500,
                'message': result.get('message', '转存失败')
            }), 500
    except Exception as e:
        logger.error(f"转存文件失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'转存文件失败: {str(e)}'
        }), 500

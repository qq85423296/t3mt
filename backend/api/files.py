# -*- coding: utf-8 -*-
"""
统一文件管理API - 支持多云盘类型
"""
from flask import Blueprint, request, jsonify
from services.file_service import FileService
from utils.logger import logger

files_bp = Blueprint('files', __name__, url_prefix='/api/files')


@files_bp.route('', methods=['GET'])
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
        
        # 获取文件列表
        result = FileService.get_files(account_id, folder_id, page, page_size)
        
        # 转换数据格式
        if result.get('code') == 0 and result.get('data'):
            file_list = result['data'].get('list', [])
            items = []
            
            for file in file_list:
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
                    'total': result['data'].get('metadata', {}).get('_total', len(items))
                }
            })
        else:
            return jsonify({
                'code': 500,
                'message': result.get('message', '获取文件列表失败')
            }), 500
    except Exception as e:
        logger.error(f"获取文件列表失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取文件列表失败: {str(e)}'
        }), 500


@files_bp.route('/folder', methods=['POST'])
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
        
        # 创建文件夹
        result = FileService.create_folder(account_id, name, parent_id)
        
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
        logger.error(f"创建文件夹失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'创建文件夹失败: {str(e)}'
        }), 500


@files_bp.route('', methods=['DELETE'])
def delete_files():
    """删除文件/文件夹"""
    try:
        data = request.get_json(force=True)
        
        if not data:
            return jsonify({
                'code': 400,
                'message': '请求数据不能为空'
            }), 400
        
        account_id = data.get('account_id')
        file_ids = data.get('file_ids', [])
        
        if not account_id or not file_ids:
            return jsonify({
                'code': 400,
                'message': '账号ID和文件ID不能为空'
            }), 400
        
        # 删除文件
        result = FileService.delete_files(account_id, file_ids)
        
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
        logger.error(f"删除文件失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'删除文件失败: {str(e)}'
        }), 500


@files_bp.route('/share', methods=['POST'])
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
        
        # 分享文件
        result = FileService.share_files(account_id, file_ids, expire_days, need_password, password)
        
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
        logger.error(f"分享文件失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'分享文件失败: {str(e)}'
        }), 500


@files_bp.route('/download', methods=['GET'])
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
        
        # 获取下载链接
        result, new_cookie = FileService.get_download_url(account_id, [file_id])
        
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
        logger.error(f"获取下载链接失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取下载链接失败: {str(e)}'
        }), 500

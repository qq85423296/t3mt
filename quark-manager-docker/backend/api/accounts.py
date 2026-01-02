# -*- coding: utf-8 -*-
"""
账号管理API
"""
from flask import Blueprint, request, jsonify
from services.account_service import AccountService
from utils.logger import logger
from utils.feature_gate import check_account_limit

accounts_bp = Blueprint('accounts', __name__, url_prefix='/api/accounts')


@accounts_bp.route('', methods=['GET'])
def get_accounts():
    """获取账号列表"""
    try:
        accounts = AccountService.get_all_accounts()
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': accounts
        })
    except Exception as e:
        logger.error(f"获取账号列表失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取账号列表失败: {str(e)}'
        }), 500


@accounts_bp.route('/<int:account_id>', methods=['GET'])
def get_account(account_id):
    """获取账号详情"""
    try:
        account = AccountService.get_account_by_id(account_id)
        
        if not account:
            return jsonify({
                'code': 404,
                'message': '账号不存在'
            }), 404
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': account
        })
    except Exception as e:
        logger.error(f"获取账号详情失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取账号详情失败: {str(e)}'
        }), 500


@accounts_bp.route('/test', methods=['POST'])
def test_account():
    """测试账号有效性"""
    try:
        data = request.get_json()
        cookie = data.get('cookie')
        
        if not cookie:
            return jsonify({
                'code': 400,
                'message': 'Cookie不能为空'
            }), 400
        
        # 测试账号
        account_info = AccountService.test_account(cookie)
        
        return jsonify({
            'code': 200,
            'message': '账号验证成功',
            'data': account_info
        })
    except Exception as e:
        logger.error(f"测试账号失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'账号验证失败: {str(e)}'
        }), 500


@accounts_bp.route('', methods=['POST'])
@check_account_limit()
def create_account():
    """添加账号"""
    try:
        data = request.get_json()
        
        # 验证必填字段
        if not data.get('remark') or not data.get('cookie'):
            return jsonify({
                'code': 400,
                'message': '账号备注和Cookie不能为空'
            }), 400
        
        # 添加账号
        result = AccountService.add_account(
            remark=data['remark'],
            cookie=data['cookie'],
            is_main=data.get('is_main', 0)
        )
        
        if not result['success']:
            return jsonify({
                'code': 400,
                'message': result['message']
            }), 400
        
        return jsonify({
            'code': 200,
            'message': '账号添加成功',
            'data': {
                'id': result['account_id'],
                'account_info': result['account_info']
            }
        })
    except Exception as e:
        logger.error(f"添加账号失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'添加账号失败: {str(e)}'
        }), 500


@accounts_bp.route('/<int:account_id>', methods=['PUT'])
def update_account(account_id):
    """更新账号"""
    try:
        data = request.get_json()
        
        # 如果更新了Cookie，需要重新测试
        if data.get('cookie'):
            test_result = AccountService.test_account(data['cookie'])
            if not test_result['valid']:
                return jsonify({
                    'code': 400,
                    'message': test_result['message']
                }), 400
            
            data['account_name'] = test_result['account_name']
            data['is_vip'] = test_result['is_vip']
            data['total_size'] = test_result['total_size']
            data['used_size'] = test_result['used_size']
        
        result = AccountService.update_account(account_id, **data)
        
        if not result['success']:
            return jsonify({
                'code': 400,
                'message': result.get('message', '更新失败')
            }), 400
        
        return jsonify({
            'code': 200,
            'message': '账号更新成功'
        })
    except Exception as e:
        logger.error(f"更新账号失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'更新账号失败: {str(e)}'
        }), 500


@accounts_bp.route('/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    """删除账号"""
    try:
        result = AccountService.delete_account(account_id)
        
        if not result['success']:
            return jsonify({
                'code': 400,
                'message': result.get('message', '删除失败')
            }), 400
        
        return jsonify({
            'code': 200,
            'message': '账号删除成功'
        })
    except Exception as e:
        logger.error(f"删除账号失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'删除账号失败: {str(e)}'
        }), 500


@accounts_bp.route('/<int:account_id>/set-main', methods=['PUT'])
def set_main_account(account_id):
    """设为主账号"""
    try:
        result = AccountService.set_main_account(account_id)
        
        if not result['success']:
            return jsonify({
                'code': 400,
                'message': result.get('message', '设置失败')
            }), 400
        
        return jsonify({
            'code': 200,
            'message': '设置主账号成功'
        })
    except Exception as e:
        logger.error(f"设置主账号失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'设置主账号失败: {str(e)}'
        }), 500


@accounts_bp.route('/<int:account_id>/refresh', methods=['POST'])
def refresh_account(account_id):
    """刷新账号信息"""
    try:
        result = AccountService.refresh_account_info(account_id)
        
        if not result['success']:
            return jsonify({
                'code': 400,
                'message': result.get('message', '刷新失败')
            }), 400
        
        return jsonify({
            'code': 200,
            'message': '账号信息刷新成功'
        })
    except Exception as e:
        logger.error(f"刷新账号信息失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'刷新账号信息失败: {str(e)}'
        }), 500

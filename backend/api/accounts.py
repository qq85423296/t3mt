# -*- coding: utf-8 -*-
"""
账号管理API - 支持多云盘类型
"""
from flask import Blueprint, request, jsonify
from services.account_service import AccountService
from services.cloud_service_factory import CloudServiceFactory
from models.cloud_type import CloudType
from utils.logger import logger
from utils.feature_gate import check_account_limit

accounts_bp = Blueprint('accounts', __name__, url_prefix='/api/accounts')


@accounts_bp.route('/test', methods=['POST'])
def test_account():
    """测试账号Cookie有效性（不保存）"""
    try:
        data = request.get_json()
        
        # 安全获取参数，处理None和空字符串情况
        cloud_type = data.get('cloud_type') if data else None
        if not cloud_type:
            cloud_type = CloudType.QUARK
        
        cookie = (data.get('cookie') or '').strip() if data else ''
        username = (data.get('username') or '').strip() if data else ''
        password = (data.get('password') or '').strip() if data else ''
        
        # 记录请求参数（脱敏）
        logger.info(f"测试账号请求: cloud_type={cloud_type}, has_cookie={bool(cookie)}, has_username={bool(username)}, has_password={bool(password)}")
        
        # 验证云盘类型
        if not CloudType.is_valid(cloud_type):
            return jsonify({
                'code': 400,
                'message': f'无效的云盘类型: {cloud_type}'
            }), 400
        
        # 天翼云盘支持账号密码登录
        if cloud_type == CloudType.CLOUD189:
            if username and password:
                # 使用账号密码登录
                try:
                    from services.cloud189_service import Cloud189Service
                    login_result = Cloud189Service.login(username, password)
                    
                    if not login_result.get('success'):
                        return jsonify({
                            'code': 400,
                            'message': login_result.get('message', '登录失败'),
                            'need_captcha': login_result.get('code') == 'NEED_CAPTCHA',
                            'captcha_url': login_result.get('captcha_url', '')
                        }), 400
                    
                    # 登录成功，使用获取的cookie
                    cookie = login_result.get('cookies', '')
                    
                except Exception as e:
                    logger.error(f"天翼云盘登录失败: {e}")
                    return jsonify({
                        'code': 400,
                        'message': f'登录失败: {str(e)}'
                    }), 400
            elif not cookie:
                return jsonify({
                    'code': 400,
                    'message': '请提供Cookie或账号密码'
                }), 400
        else:
            # 其他云盘类型必须提供cookie
            if not cookie:
                return jsonify({
                    'code': 400,
                    'message': 'Cookie不能为空'
                }), 400
        
        # 使用工厂创建对应的云盘服务并测试
        try:
            service = CloudServiceFactory.create_service(cloud_type, cookie)
            account_info = service.get_account_info()
            
            if not account_info:
                return jsonify({
                    'code': 400,
                    'message': 'Cookie无效或已过期'
                }), 400
            
            return jsonify({
                'code': 200,
                'message': '账号验证成功',
                'data': {
                    'nickname': account_info.get('nickname', ''),
                    'is_vip': account_info.get('is_vip', 0),
                    'total_capacity': account_info.get('total_capacity', 0),
                    'use_capacity': account_info.get('use_capacity', 0),
                    'member_type': account_info.get('member_type', ''),
                    'cookie': cookie  # 返回cookie供前端保存
                }
            })
        except Exception as e:
            logger.error(f"测试账号失败: {e}")
            return jsonify({
                'code': 400,
                'message': f'Cookie验证失败: {str(e)}'
            }), 400
            
    except Exception as e:
        logger.error(f"测试账号接口异常: {e}")
        return jsonify({
            'code': 500,
            'message': f'测试账号失败: {str(e)}'
        }), 500


@accounts_bp.route('', methods=['GET'])
def get_accounts():
    """获取账号列表"""
    try:
        # 支持按云盘类型过滤
        cloud_type = request.args.get('cloud_type')
        
        # 验证云盘类型
        if cloud_type and not CloudType.is_valid(cloud_type):
            return jsonify({
                'code': 400,
                'message': f'无效的云盘类型: {cloud_type}'
            }), 400
        
        accounts = AccountService.get_all_accounts(cloud_type)
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
        account = AccountService.get_account(account_id)
        
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


@accounts_bp.route('/verify/<int:account_id>', methods=['POST'])
def verify_account(account_id):
    """验证账号有效性"""
    try:
        result = AccountService.verify_account(account_id)
        
        if result['is_valid']:
            return jsonify({
                'code': 200,
                'message': result['message'],
                'data': result.get('account_info')
            })
        else:
            return jsonify({
                'code': 400,
                'message': result['message']
            }), 400
    except Exception as e:
        logger.error(f"验证账号失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'验证账号失败: {str(e)}'
        }), 500


@accounts_bp.route('', methods=['POST'])
@check_account_limit()
def create_account():
    """添加账号"""
    try:
        data = request.get_json()
        
        # 安全获取云盘类型，处理None和空字符串情况
        cloud_type = data.get('cloud_type') if data else None
        if not cloud_type:
            cloud_type = CloudType.QUARK
        
        # 验证云盘类型
        if not CloudType.is_valid(cloud_type):
            return jsonify({
                'code': 400,
                'message': f'无效的云盘类型: {cloud_type}'
            }), 400
        
        # 验证必填字段
        if not data.get('remark'):
            return jsonify({
                'code': 400,
                'message': '账号备注不能为空'
            }), 400
        
        cookie = (data.get('cookie') or '').strip() if data else ''
        username = (data.get('username') or '').strip() if data else ''
        password = (data.get('password') or '').strip() if data else ''
        
        # 记录请求参数（脱敏）
        logger.info(f"添加账号请求: cloud_type={cloud_type}, has_cookie={bool(cookie)}, has_username={bool(username)}, has_password={bool(password)}")
        
        # 天翼云盘支持账号密码登录
        if cloud_type == CloudType.CLOUD189:
            if username and password:
                # 使用账号密码登录获取cookie
                try:
                    from services.cloud189_service import Cloud189Service
                    login_result = Cloud189Service.login(username, password)
                    
                    if not login_result.get('success'):
                        return jsonify({
                            'code': 400,
                            'message': login_result.get('message', '登录失败'),
                            'need_captcha': login_result.get('code') == 'NEED_CAPTCHA',
                            'captcha_url': login_result.get('captcha_url', '')
                        }), 400
                    
                    # 登录成功，使用获取的cookie
                    cookie = login_result.get('cookies', '')
                    logger.info(f"天翼云盘账号 {username} 登录成功，将保存账号密码用于自动重新登录")
                    
                except Exception as e:
                    logger.error(f"天翼云盘登录失败: {e}")
                    return jsonify({
                        'code': 400,
                        'message': f'登录失败: {str(e)}'
                    }), 400
            elif not cookie:
                return jsonify({
                    'code': 400,
                    'message': '请提供Cookie或账号密码'
                }), 400
        else:
            # 其他云盘类型必须提供cookie
            if not cookie:
                return jsonify({
                    'code': 400,
                    'message': 'Cookie不能为空'
                }), 400
        
        # 创建账号（保存账号密码用于自动重新登录）
        account_id = AccountService.create_account(
            remark=data['remark'],
            cookie=cookie,
            cloud_type=cloud_type,
            username=username if username else None,
            password=password if password else None
        )
        
        return jsonify({
            'code': 200,
            'message': '账号添加成功',
            'data': {
                'id': account_id
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
        
        # 如果更新了云盘类型，需要验证
        if 'cloud_type' in data and not CloudType.is_valid(data['cloud_type']):
            return jsonify({
                'code': 400,
                'message': f'无效的云盘类型: {data["cloud_type"]}'
            }), 400
        
        # 如果更新了Cookie，需要重新验证账号
        if data.get('cookie'):
            # 获取账号的云盘类型
            account = AccountService.get_account(account_id)
            if not account:
                return jsonify({
                    'code': 404,
                    'message': '账号不存在'
                }), 404
            
            cloud_type = data.get('cloud_type', account.get('cloud_type', CloudType.QUARK))
            
            # 验证新Cookie
            from services.cloud_service_factory import CloudServiceFactory
            try:
                service = CloudServiceFactory.create_service(cloud_type, data['cookie'])
                account_info = service.get_account_info()
                
                if not account_info:
                    return jsonify({
                        'code': 400,
                        'message': 'Cookie无效或已过期'
                    }), 400
                
                # 更新账号信息
                data['account_name'] = account_info.get('nickname', '')
                data['is_vip'] = account_info.get('is_vip', 0)
                data['total_size'] = account_info.get('total_capacity', 0)
                data['used_size'] = account_info.get('use_capacity', 0)
                data['member_type'] = account_info.get('member_type', '')
            except Exception as e:
                return jsonify({
                    'code': 400,
                    'message': f'Cookie验证失败: {str(e)}'
                }), 400
        
        success = AccountService.update_account(account_id, **data)
        
        if not success:
            return jsonify({
                'code': 400,
                'message': '更新失败'
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
        success = AccountService.delete_account(account_id)
        
        if not success:
            return jsonify({
                'code': 400,
                'message': '删除失败'
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


@accounts_bp.route('/<int:account_id>/refresh', methods=['POST'])
def refresh_account(account_id):
    """刷新账号信息"""
    try:
        # 获取账号
        account = AccountService.get_account(account_id)
        if not account:
            return jsonify({
                'code': 404,
                'message': '账号不存在'
            }), 404
        
        cloud_type = account.get('cloud_type', CloudType.QUARK)
        cookie = account.get('cookie', '')
        
        if not cookie:
            return jsonify({
                'code': 400,
                'message': '账号Cookie为空'
            }), 400
        
        # 使用工厂创建对应的云盘服务
        try:
            service = CloudServiceFactory.create_service(cloud_type, cookie)
            account_info = service.get_account_info()
            
            if not account_info:
                # 更新账号状态为异常
                AccountService.update_account(account_id, status='异常')
                return jsonify({
                    'code': 400,
                    'message': 'Cookie已过期，请重新登录'
                }), 400
            
            # 更新账号信息
            update_data = {
                'account_name': account_info.get('nickname', ''),
                'is_vip': account_info.get('is_vip', 0),
                'total_size': account_info.get('total_capacity', 0),
                'used_size': account_info.get('use_capacity', 0),
                'member_type': account_info.get('member_type', ''),
                'status': '正常'
            }
            
            AccountService.update_account(account_id, **update_data)
            
            return jsonify({
                'code': 200,
                'message': '刷新成功',
                'data': update_data
            })
            
        except Exception as e:
            logger.error(f"刷新账号失败: {e}")
            return jsonify({
                'code': 400,
                'message': f'刷新失败: {str(e)}'
            }), 400
            
    except Exception as e:
        logger.error(f"刷新账号接口异常: {e}")
        return jsonify({
            'code': 500,
            'message': f'刷新账号失败: {str(e)}'
        }), 500


@accounts_bp.route('/<int:account_id>/set-main', methods=['PUT'])
def set_main_account(account_id):
    """设为主账号"""
    try:
        # 获取账号
        account = AccountService.get_account(account_id)
        if not account:
            return jsonify({
                'code': 404,
                'message': '账号不存在'
            }), 404
        
        cloud_type = account.get('cloud_type', CloudType.QUARK)
        
        # 设为主账号（同类型云盘中只能有一个主账号）
        success = AccountService.set_main_account(account_id, cloud_type)
        
        if not success:
            return jsonify({
                'code': 400,
                'message': '设置失败'
            }), 400
        
        return jsonify({
            'code': 200,
            'message': '设置成功'
        })
    except Exception as e:
        logger.error(f"设置主账号失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'设置主账号失败: {str(e)}'
        }), 500

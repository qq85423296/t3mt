# -*- coding: utf-8 -*-
"""
认证API
"""
from flask import Blueprint, request, jsonify, session
from models.user import User
from utils.logger import logger

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({
                'code': 400,
                'message': '用户名和密码不能为空'
            }), 400
        
        # 验证用户
        user = User.authenticate(username, password)
        
        if user:
            # 设置session
            session.clear()  # 先清空
            session['user_id'] = user['id']
            session['username'] = user['username']
            session.permanent = True  # 设置为永久session
            
            logger.info(f"用户登录成功: {username}, session_id: {session.get('_id', 'N/A')}")
            
            response = jsonify({
                'code': 200,
                'message': '登录成功',
                'data': {
                    'username': user['username']
                }
            })
            
            # 确保响应包含Set-Cookie头
            return response
        else:
            return jsonify({
                'code': 401,
                'message': '用户名或密码错误'
            }), 401
    
    except Exception as e:
        logger.error(f"登录失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'登录失败: {str(e)}'
        }), 500


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """用户登出"""
    try:
        username = session.get('username', 'unknown')
        session.clear()
        
        logger.info(f"用户登出: {username}")
        
        return jsonify({
            'code': 200,
            'message': '登出成功'
        })
    
    except Exception as e:
        logger.error(f"登出失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'登出失败: {str(e)}'
        }), 500


@auth_bp.route('/check', methods=['GET'])
def check():
    """检查登录状态"""
    logger.info(f"检查登录状态, session内容: {dict(session)}, cookies: {request.cookies}")
    
    if 'user_id' in session:
        return jsonify({
            'code': 200,
            'message': '已登录',
            'data': {
                'username': session.get('username')
            }
        })
    else:
        return jsonify({
            'code': 401,
            'message': '未登录'
        }), 401


@auth_bp.route('/change-password', methods=['POST'])
def change_password():
    """修改密码"""
    try:
        # 检查登录状态
        if 'user_id' not in session:
            return jsonify({
                'code': 401,
                'message': '未登录'
            }), 401
        
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({
                'code': 400,
                'message': '当前密码和新密码不能为空'
            }), 400
        
        if len(new_password) < 6:
            return jsonify({
                'code': 400,
                'message': '新密码长度至少6位'
            }), 400
        
        username = session.get('username')
        
        # 验证当前密码
        user = User.authenticate(username, current_password)
        if not user:
            return jsonify({
                'code': 401,
                'message': '当前密码错误'
            }), 401
        
        # 修改密码
        success = User.change_password(username, new_password)
        
        if success:
            logger.info(f"用户修改密码成功: {username}")
            
            # 清除session,要求重新登录
            session.clear()
            
            return jsonify({
                'code': 200,
                'message': '密码修改成功,请重新登录'
            })
        else:
            return jsonify({
                'code': 500,
                'message': '密码修改失败'
            }), 500
    
    except Exception as e:
        logger.error(f"修改密码失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'修改密码失败: {str(e)}'
        }), 500

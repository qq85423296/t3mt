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
            from utils.crypto import CryptoUtil
            
            # 获取天翼云盘账号（优先主账号，如果没有则使用第一个）
            from database import get_db
            with get_db() as conn:
                cursor = conn.cursor()
                # 先尝试获取主账号
                cursor.execute('''
                    SELECT id, remark, cookie, username, password, cloud_type
                    FROM quark_accounts 
                    WHERE cloud_type = ? AND is_main = 1
                ''', (CloudType.CLOUD189,))
                main_account = cursor.fetchone()
                
                # 如果没有主账号，获取第一个天翼云盘账号
                if not main_account:
                    cursor.execute('''
                        SELECT id, remark, cookie, username, password, cloud_type
                        FROM quark_accounts 
                        WHERE cloud_type = ?
                        ORDER BY id ASC
                        LIMIT 1
                    ''', (CloudType.CLOUD189,))
                    main_account = cursor.fetchone()
            
            if not main_account:
                return jsonify({
                    'code': 400,
                    'message': '请先配置天翼云盘账号'
                }), 400
            
            # 使用索引访问（兼容tuple和Row）
            # SELECT id, remark, cookie, username, password, cloud_type
            account_id = main_account[0]
            account_cookie = main_account[2]
            account_username = main_account[3]
            account_password = main_account[4]
            
            # 解密cookie
            decrypted_cookie = CryptoUtil.decrypt(account_cookie) if account_cookie else None
            
            # 解密username和password（如果有）
            username = CryptoUtil.decrypt(account_username) if account_username else None
            password = CryptoUtil.decrypt(account_password) if account_password else None
            
            # 初始化session_key和access_token
            session_key = None
            access_token = None
            
            # 如果没有cookie但有账号密码，先登录获取cookie
            if not decrypted_cookie and username and password:
                logger.info("天翼云盘账号没有Cookie，使用账号密码登录")
                login_result = Cloud189Service.login(username, password)
                if login_result.get('success'):
                    decrypted_cookie = login_result.get('cookie')
                    session_key = login_result.get('session_key')
                    access_token = login_result.get('access_token')
                    
                    # 更新数据库中的cookie
                    encrypted_cookie = CryptoUtil.encrypt(decrypted_cookie)
                    with get_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE quark_accounts 
                            SET cookie = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (encrypted_cookie, account_id))
                        conn.commit()
                    logger.info("天翼云盘Cookie已更新")
                else:
                    return jsonify({
                        'code': 400,
                        'message': f"登录失败: {login_result.get('message', '未知错误')}"
                    }), 400
            
            # 创建天翼云盘服务
            cloud189_service = Cloud189Service(
                cookie=decrypted_cookie,
                username=username,
                password=password,
                session_key=session_key,
                access_token=access_token
            )
            
            # 解析分享链接
            try:
                # parse_share_url返回的是tuple: (share_code, access_code)
                share_code, access_code = cloud189_service.parse_share_url(share_url)
                
                if not share_code:
                    return jsonify({
                        'code': 200,
                        'message': 'success',
                        'data': {
                            'valid': False,
                            'error': '无法解析分享链接'
                        }
                    })
                
                # 获取分享信息
                share_info = cloud189_service.get_share_info(share_code)
                
                if share_info.get('res_code') == 0:
                    # 链接有效
                    share_data = share_info.get('shareInfo', {})
                    return jsonify({
                        'code': 200,
                        'message': 'success',
                        'data': {
                            'valid': True,
                            'title': share_data.get('shareName', ''),
                            'file_count': share_data.get('fileCount', 0)
                        }
                    })
                else:
                    # 链接无效
                    return jsonify({
                        'code': 200,
                        'message': 'success',
                        'data': {
                            'valid': False,
                            'error': share_info.get('res_message', '链接无效')
                        }
                    })
            except Exception as e:
                # 如果是Cookie失效错误，且有账号密码，尝试重新登录
                error_msg = str(e)
                if ('cookie' in error_msg.lower() or '登录' in error_msg or '认证' in error_msg) and username and password:
                    logger.info(f"天翼云盘Cookie可能失效，尝试重新登录: {error_msg}")
                    login_result = Cloud189Service.login(username, password)
                    if login_result.get('success'):
                        new_cookie = login_result.get('cookie')
                        new_session_key = login_result.get('session_key')
                        new_access_token = login_result.get('access_token')
                        
                        # 更新数据库中的cookie
                        encrypted_cookie = CryptoUtil.encrypt(new_cookie)
                        with get_db() as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                UPDATE quark_accounts 
                                SET cookie = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            ''', (encrypted_cookie, account_id))
                            conn.commit()
                        logger.info("天翼云盘Cookie已自动更新，重试检测")
                        
                        # 使用新cookie重试
                        cloud189_service = Cloud189Service(
                            cookie=new_cookie,
                            username=username,
                            password=password,
                            session_key=new_session_key,
                            access_token=new_access_token
                        )
                        # parse_share_url返回的是tuple: (share_code, access_code)
                        share_code, access_code = cloud189_service.parse_share_url(share_url)
                        
                        if share_code:
                            # 获取分享信息
                            share_info = cloud189_service.get_share_info(share_code)
                            
                            if share_info.get('res_code') == 0:
                                share_data = share_info.get('shareInfo', {})
                                return jsonify({
                                    'code': 200,
                                    'message': 'success',
                                    'data': {
                                        'valid': True,
                                        'title': share_data.get('shareName', ''),
                                        'file_count': share_data.get('fileCount', 0)
                                    }
                                })
                            else:
                                return jsonify({
                                    'code': 200,
                                    'message': 'success',
                                    'data': {
                                        'valid': False,
                                        'error': share_info.get('res_message', '链接无效')
                                    }
                                })
                        else:
                            return jsonify({
                                'code': 200,
                                'message': 'success',
                                'data': {
                                    'valid': False,
                                    'error': '无法解析分享链接'
                                }
                            })
                
                # 其他错误直接抛出
                raise
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

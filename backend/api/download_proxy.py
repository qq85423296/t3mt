# -*- coding: utf-8 -*-
"""
下载代理API - 提供永久有效的下载链接，自动302重定向到最新的真实下载地址
类似OpenList的实现方式
"""
from flask import Blueprint, request, redirect, jsonify
from services.account_service import AccountService
from services.cloud_service_factory import CloudServiceFactory
from utils.logger import logger
import hashlib
import time

download_proxy_bp = Blueprint('download_proxy', __name__, url_prefix='/api/download-proxy')


def generate_download_token(account_id: int, file_id: str, timestamp: int) -> str:
    """
    生成下载令牌
    
    Args:
        account_id: 账号ID
        file_id: 文件ID
        timestamp: 时间戳
    
    Returns:
        下载令牌
    """
    # 使用SECRET_KEY作为盐值
    from config import Config
    secret = Config.SECRET_KEY
    
    # 生成签名
    data = f"{account_id}:{file_id}:{timestamp}:{secret}"
    token = hashlib.sha256(data.encode()).hexdigest()
    
    return token


def verify_download_token(account_id: int, file_id: str, timestamp: int, token: str) -> bool:
    """
    验证下载令牌
    
    Args:
        account_id: 账号ID
        file_id: 文件ID
        timestamp: 时间戳
        token: 下载令牌
    
    Returns:
        是否有效
    """
    # 检查时间戳（24小时有效期）
    current_time = int(time.time())
    if current_time - timestamp > 86400:
        return False
    
    # 验证签名
    expected_token = generate_download_token(account_id, file_id, timestamp)
    return token == expected_token


@download_proxy_bp.route('/<int:account_id>/<file_id>', methods=['GET'])
def proxy_download(account_id: int, file_id: str):
    """
    下载代理接口 - 302重定向到最新的真实下载地址
    
    URL格式: /api/download-proxy/{account_id}/{file_id}?token={token}&ts={timestamp}
    
    工作流程:
    1. 验证token和时间戳
    2. 实时获取最新的下载链接
    3. 302重定向到真实下载地址
    
    优势:
    - 代理URL永久有效（24小时内）
    - 每次请求都获取最新链接
    - 支持分段下载、断点续传
    - 自动处理链接过期
    """
    try:
        # 获取参数
        token = request.args.get('token')
        timestamp = request.args.get('ts', type=int)
        
        if not token or not timestamp:
            return jsonify({
                'code': 400,
                'message': '缺少token或时间戳参数'
            }), 400
        
        # 验证token
        if not verify_download_token(account_id, file_id, timestamp, token):
            return jsonify({
                'code': 403,
                'message': '无效的下载令牌或已过期'
            }), 403
        
        # 获取账号信息
        account = AccountService.get_account(account_id)
        if not account:
            return jsonify({
                'code': 404,
                'message': '账号不存在'
            }), 404
        
        cloud_type = account.get('cloud_type', 'quark')
        cookie = account['cookie']
        
        # 创建云盘服务
        service = CloudServiceFactory.create_service(
            cloud_type,
            cookie,
            username=account.get('username'),
            password=account.get('password')
        )
        
        # 实时获取最新的下载链接
        logger.info(f"代理下载请求: account_id={account_id}, file_id={file_id}")
        
        download_result, download_cookie = service.get_download_url([file_id])
        
        if download_result.get('code') != 0:
            return jsonify({
                'code': 500,
                'message': f"获取下载链接失败: {download_result.get('message', '')}"
            }), 500
        
        download_data = download_result.get('data', [])
        if not download_data:
            return jsonify({
                'code': 500,
                'message': '下载链接为空'
            }), 500
        
        download_url = download_data[0].get('download_url') or download_data[0].get('downloadUrl')
        if not download_url:
            return jsonify({
                'code': 500,
                'message': '下载链接无效'
            }), 500
        
        logger.info(f"代理下载重定向: {download_url[:100]}...")
        
        # 302重定向到真实下载地址
        return redirect(download_url, code=302)
        
    except Exception as e:
        logger.error(f"代理下载失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'代理下载失败: {str(e)}'
        }), 500


@download_proxy_bp.route('/generate', methods=['POST'])
def generate_proxy_url():
    """
    生成代理下载URL
    
    请求体:
    {
        "account_id": 1,
        "file_id": "xxx"
    }
    
    返回:
    {
        "code": 200,
        "data": {
            "proxy_url": "http://localhost:8520/api/download-proxy/1/xxx?token=xxx&ts=xxx",
            "expires_at": "2026-01-23 12:00:00"
        }
    }
    """
    try:
        data = request.get_json()
        account_id = data.get('account_id')
        file_id = data.get('file_id')
        
        if not account_id or not file_id:
            return jsonify({
                'code': 400,
                'message': '缺少account_id或file_id参数'
            }), 400
        
        # 生成时间戳和token
        timestamp = int(time.time())
        token = generate_download_token(account_id, file_id, timestamp)
        
        # 构建代理URL
        from config import Config
        base_url = Config.API_BASE_URL
        proxy_url = f"{base_url}/api/download-proxy/{account_id}/{file_id}?token={token}&ts={timestamp}"
        
        # 计算过期时间
        from datetime import datetime, timedelta
        expires_at = datetime.fromtimestamp(timestamp + 86400).strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'code': 200,
            'message': '代理URL生成成功',
            'data': {
                'proxy_url': proxy_url,
                'token': token,
                'timestamp': timestamp,
                'expires_at': expires_at
            }
        })
        
    except Exception as e:
        logger.error(f"生成代理URL失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'生成代理URL失败: {str(e)}'
        }), 500

# -*- coding: utf-8 -*-
"""
许可证管理API
"""
from flask import Blueprint, request, jsonify

from utils.license_manager import license_manager, LicenseType
from utils.machine_id import MachineID
from utils.feature_gate import get_license_info_for_frontend
from utils.logger import logger

license_bp = Blueprint('license', __name__, url_prefix='/api/license')


@license_bp.route('/info', methods=['GET'])
def get_license_info():
    """获取当前许可证信息"""
    try:
        info = get_license_info_for_frontend()
        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': info
        })
    except Exception as e:
        logger.error(f"获取许可证信息失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取失败: {str(e)}'
        }), 500


@license_bp.route('/machine-id', methods=['GET'])
def get_machine_id():
    """获取机器码"""
    try:
        machine_id = MachineID.get_machine_id()
        machine_info = MachineID.get_machine_info()
        
        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': {
                'machine_id': machine_id,
                'machine_info': machine_info
            }
        })
    except Exception as e:
        logger.error(f"获取机器码失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取失败: {str(e)}'
        }), 500


@license_bp.route('/activate', methods=['POST'])
def activate_license():
    """激活许可证"""
    try:
        data = request.get_json()
        license_key = data.get('license_key', '').strip()
        
        if not license_key:
            return jsonify({
                'code': 400,
                'message': '请输入许可证密钥'
            }), 400
        
        # 验证并保存许可证
        success, message = license_manager.save_license(license_key)
        
        if success:
            # 返回最新的许可证信息
            info = get_license_info_for_frontend()
            return jsonify({
                'code': 200,
                'message': message,
                'data': info
            })
        else:
            return jsonify({
                'code': 400,
                'message': message
            }), 400
            
    except Exception as e:
        logger.error(f"激活许可证失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'激活失败: {str(e)}'
        }), 500


@license_bp.route('/generate', methods=['POST'])
def generate_license():
    """
    生成许可证（仅供管理员使用）
    生产环境应该通过独立的许可证服务器生成
    """
    try:
        data = request.get_json()
        license_type = data.get('license_type', LicenseType.COMMUNITY)
        machine_id = data.get('machine_id', '')
        expire_days = data.get('expire_days', 365)
        
        if not machine_id:
            return jsonify({
                'code': 400,
                'message': '请提供机器码'
            }), 400
        
        if license_type not in [LicenseType.COMMUNITY, LicenseType.PRO]:
            return jsonify({
                'code': 400,
                'message': '无效的许可证类型'
            }), 400
        
        # 生成许可证
        license_key = license_manager.generate_license(
            license_type=license_type,
            machine_id=machine_id,
            expire_days=expire_days
        )
        
        return jsonify({
            'code': 200,
            'message': '生成成功',
            'data': {
                'license_key': license_key,
                'license_type': license_type,
                'machine_id': machine_id,
                'expire_days': expire_days
            }
        })
        
    except Exception as e:
        logger.error(f"生成许可证失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'生成失败: {str(e)}'
        }), 500


@license_bp.route('/verify', methods=['POST'])
def verify_license():
    """验证许可证（不保存）"""
    try:
        data = request.get_json()
        license_key = data.get('license_key', '').strip()
        
        if not license_key:
            return jsonify({
                'code': 400,
                'message': '请输入许可证密钥'
            }), 400
        
        is_valid, license_data, error = license_manager.verify_license(license_key)
        
        if is_valid:
            return jsonify({
                'code': 200,
                'message': '许可证有效',
                'data': {
                    'valid': True,
                    'license_type': license_data['type'],
                    'expire_time': license_data['expire_time'],
                    'features': license_data['features']
                }
            })
        else:
            return jsonify({
                'code': 400,
                'message': error,
                'data': {'valid': False}
            }), 400
            
    except Exception as e:
        logger.error(f"验证许可证失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'验证失败: {str(e)}'
        }), 500

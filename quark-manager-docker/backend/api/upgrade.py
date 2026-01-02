# -*- coding: utf-8 -*-
"""
升级管理API
"""
from flask import Blueprint, request, jsonify
from utils.upgrade_manager import upgrade_manager
from utils.machine_id import MachineID
from utils.logger import logger
import threading

upgrade_bp = Blueprint('upgrade', __name__, url_prefix='/api/upgrade')

# 升级状态
upgrade_status = {
    'is_upgrading': False,
    'progress': 0,
    'message': '',
    'error': None
}

@upgrade_bp.route('/check', methods=['GET'])
def check_update():
    """检查更新"""
    try:
        machine_id = MachineID.get_machine_id()
        update_info = upgrade_manager.check_update(machine_id)
        
        return jsonify({
            'code': 200,
            'data': update_info
        })
        
    except Exception as e:
        logger.error(f"检查更新失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'检查更新失败: {str(e)}'
        }), 500

@upgrade_bp.route('/current-version', methods=['GET'])
def get_current_version():
    """获取当前版本"""
    return jsonify({
        'code': 200,
        'data': {
            'version': upgrade_manager.CURRENT_VERSION
        }
    })

@upgrade_bp.route('/backups', methods=['GET'])
def get_backups():
    """获取备份列表"""
    try:
        backups = upgrade_manager.get_backups()
        
        return jsonify({
            'code': 200,
            'data': backups
        })
        
    except Exception as e:
        logger.error(f"获取备份列表失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取备份列表失败: {str(e)}'
        }), 500

@upgrade_bp.route('/backup/<path:backup_path>', methods=['DELETE'])
def delete_backup(backup_path):
    """删除备份"""
    try:
        upgrade_manager.delete_backup(backup_path)
        
        return jsonify({
            'code': 200,
            'message': '备份删除成功'
        })
        
    except Exception as e:
        logger.error(f"删除备份失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'删除备份失败: {str(e)}'
        }), 500

@upgrade_bp.route('/start', methods=['POST'])
def start_upgrade():
    """开始升级"""
    global upgrade_status
    
    if upgrade_status['is_upgrading']:
        return jsonify({
            'code': 400,
            'message': '升级正在进行中'
        }), 400
    
    try:
        data = request.json
        package_url = data.get('package_url')
        package_md5 = data.get('package_md5')
        to_version = data.get('to_version')
        
        if not package_url or not to_version:
            return jsonify({
                'code': 400,
                'message': '缺少必要参数'
            }), 400
        
        # 重置状态
        upgrade_status = {
            'is_upgrading': True,
            'progress': 0,
            'message': '准备升级...',
            'error': None
        }
        
        # 在后台线程执行升级
        thread = threading.Thread(
            target=_do_upgrade,
            args=(package_url, package_md5, to_version)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'code': 200,
            'message': '升级已开始'
        })
        
    except Exception as e:
        logger.error(f"启动升级失败: {e}")
        upgrade_status['is_upgrading'] = False
        return jsonify({
            'code': 500,
            'message': f'启动升级失败: {str(e)}'
        }), 500

@upgrade_bp.route('/status', methods=['GET'])
def get_upgrade_status():
    """获取升级状态"""
    return jsonify({
        'code': 200,
        'data': upgrade_status
    })

@upgrade_bp.route('/rollback', methods=['POST'])
def rollback():
    """回退到备份版本"""
    try:
        data = request.json
        backup_path = data.get('backup_path')
        
        if not backup_path:
            return jsonify({
                'code': 400,
                'message': '缺少备份路径'
            }), 400
        
        logger.info(f"开始回退到: {backup_path}")
        upgrade_manager.rollback(backup_path)
        
        return jsonify({
            'code': 200,
            'message': '回退成功，请重启应用'
        })
        
    except Exception as e:
        logger.error(f"回退失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'回退失败: {str(e)}'
        }), 500

def _do_upgrade(package_url, package_md5, to_version):
    """执行升级(后台线程)"""
    global upgrade_status
    
    machine_id = MachineID.get_machine_id()
    from_version = upgrade_manager.CURRENT_VERSION
    backup_path = None
    
    try:
        # 1. 创建备份
        upgrade_status['progress'] = 10
        upgrade_status['message'] = '正在创建备份...'
        logger.info("创建备份...")
        backup_path = upgrade_manager.create_backup()
        
        # 2. 下载更新包
        upgrade_status['progress'] = 30
        upgrade_status['message'] = '正在下载更新包...'
        logger.info("下载更新包...")
        package_path = upgrade_manager.download_package(package_url, package_md5)
        
        # 3. 应用升级
        upgrade_status['progress'] = 70
        upgrade_status['message'] = '正在应用升级...'
        logger.info("应用升级...")
        upgrade_manager.apply_upgrade(package_path)
        
        # 4. 清理临时文件
        upgrade_status['progress'] = 90
        upgrade_status['message'] = '正在清理临时文件...'
        logger.info("清理临时文件...")
        upgrade_manager.cleanup()
        
        # 5. 完成
        upgrade_status['progress'] = 100
        upgrade_status['message'] = '升级完成，请重启应用'
        upgrade_status['is_upgrading'] = False
        
        logger.info("升级完成")
        
        # 记录升级日志
        upgrade_manager.log_upgrade(machine_id, from_version, to_version, 'success')
        
    except Exception as e:
        logger.error(f"升级失败: {e}")
        
        upgrade_status['is_upgrading'] = False
        upgrade_status['error'] = str(e)
        upgrade_status['message'] = f'升级失败: {str(e)}'
        
        # 记录失败日志
        upgrade_manager.log_upgrade(machine_id, from_version, to_version, 'failed', str(e))
        
        # 如果有备份，提示用户可以回退
        if backup_path:
            upgrade_status['message'] += f'\n备份已保存: {backup_path}'

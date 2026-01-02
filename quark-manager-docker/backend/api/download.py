# -*- coding: utf-8 -*-
"""
下载任务API
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
from services.download_service import DownloadService
from utils.logger import logger

download_bp = Blueprint('download', __name__, url_prefix='/api/download')


@download_bp.route('/tasks', methods=['GET'])
def get_tasks():
    """获取下载任务列表"""
    try:
        tasks = DownloadService.get_all_tasks()
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': tasks
        })
    except Exception as e:
        logger.error(f"获取下载任务列表失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取任务列表失败: {str(e)}'
        }), 500


@download_bp.route('/task', methods=['POST'])
def create_task():
    """创建下载任务"""
    try:
        data = request.get_json()
        
        # 验证必填字段
        required_fields = ['name', 'source_account_id', 'source_path', 'target_path', 'cron_expression']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'code': 400,
                    'message': f'{field}不能为空'
                }), 400
        
        # 创建任务
        task_id = DownloadService.create_task(data)
        
        # TODO: 添加到任务调度器
        
        return jsonify({
            'code': 200,
            'message': '任务创建成功',
            'data': {'id': task_id}
        })
    except Exception as e:
        logger.error(f"创建下载任务失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'创建任务失败: {str(e)}'
        }), 500


@download_bp.route('/task/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """获取下载任务详情"""
    try:
        task = DownloadService.get_task_by_id(task_id)
        if not task:
            return jsonify({
                'code': 404,
                'message': '任务不存在'
            }), 404
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': task
        })
    except Exception as e:
        logger.error(f"获取下载任务详情失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取任务详情失败: {str(e)}'
        }), 500


@download_bp.route('/task/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """更新下载任务"""
    try:
        data = request.get_json()
        
        # 验证任务是否存在
        task = DownloadService.get_task_by_id(task_id)
        if not task:
            return jsonify({
                'code': 404,
                'message': '任务不存在'
            }), 404
        
        # 更新任务
        DownloadService.update_task(task_id, data)
        
        # TODO: 更新任务调度器
        
        return jsonify({
            'code': 200,
            'message': '任务更新成功'
        })
    except Exception as e:
        logger.error(f"更新下载任务失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'更新任务失败: {str(e)}'
        }), 500


@download_bp.route('/task/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除下载任务"""
    try:
        from database import db
        
        # 验证任务是否存在
        task = DownloadService.get_task_by_id(task_id)
        if not task:
            return jsonify({
                'code': 404,
                'message': '任务不存在'
            }), 404
        
        # 删除任务
        DownloadService.delete_task(task_id)
        
        # 删除关联的执行历史记录
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM task_execution_history 
                    WHERE task_id = ? AND task_type = 'download'
                ''', (task_id,))
                deleted_count = cursor.rowcount
                logger.info(f"删除定时下载任务 {task_id} 的 {deleted_count} 条执行历史记录")
        except Exception as e:
            logger.warning(f"删除执行历史记录失败: {str(e)}")
        
        # TODO: 从任务调度器移除
        
        return jsonify({
            'code': 200,
            'message': '任务删除成功'
        })
    except Exception as e:
        logger.error(f"删除下载任务失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'删除任务失败: {str(e)}'
        }), 500


@download_bp.route('/task/<int:task_id>/toggle', methods=['POST'])
def toggle_task(task_id):
    """暂停/启动任务"""
    try:
        # 验证任务是否存在
        task = DownloadService.get_task_by_id(task_id)
        if not task:
            return jsonify({
                'code': 404,
                'message': '任务不存在'
            }), 404
        
        # 切换状态
        new_status = DownloadService.toggle_task_status(task_id)
        
        # TODO: 更新任务调度器
        
        return jsonify({
            'code': 200,
            'message': '操作成功',
            'data': {'status': new_status}
        })
    except Exception as e:
        logger.error(f"切换任务状态失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'操作失败: {str(e)}'
        }), 500


@download_bp.route('/task/<int:task_id>/execute', methods=['POST'])
def execute_task(task_id):
    """立即执行任务（异步）"""
    try:
        from services.task_executor import TaskExecutor
        
        # 验证任务是否存在
        task = DownloadService.get_task_by_id(task_id)
        if not task:
            return jsonify({
                'code': 404,
                'message': '任务不存在'
            }), 404
        
        # 启动异步任务
        if TaskExecutor.start_task(task_id):
            return jsonify({
                'code': 200,
                'message': '任务已启动',
                'data': {
                    'task_id': task_id,
                    'status': 'running'
                }
            })
        else:
            return jsonify({
                'code': 400,
                'message': '任务正在执行中'
            }), 400
            
    except Exception as e:
        logger.error(f"启动任务失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'启动任务失败: {str(e)}'
        }), 500


@download_bp.route('/task/<int:task_id>/progress', methods=['GET'])
def get_progress(task_id):
    """获取下载进度（实时）"""
    try:
        from services.task_executor import TaskExecutor
        
        # 验证任务是否存在
        task = DownloadService.get_task_by_id(task_id)
        if not task:
            return jsonify({
                'code': 404,
                'message': '任务不存在'
            }), 404
        
        # 获取实时任务状态
        task_status = TaskExecutor.get_task_status(task_id)
        
        if task_status:
            # 任务正在执行，返回实时状态
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {
                    'task_id': task_id,
                    'status': task_status['status'],
                    'progress': task_status['progress'],
                    'current_file': task_status['current_file'],
                    'downloaded_files': task_status['downloaded_files'],
                    'total_files': task_status['total_files'],
                    'success_count': task_status['success_count'],
                    'fail_count': task_status['fail_count'],
                    'logs': task_status['logs'],  # 返回所有日志
                    'start_time': task_status['start_time']
                }
            })
        else:
            # 任务未在执行，返回数据库中的状态
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {
                    'task_id': task_id,
                    'status': task['status'],
                    'progress': task['progress'],
                    'current_file': '',
                    'downloaded_files': 0,
                    'total_files': 0,
                    'success_count': 0,
                    'fail_count': 0,
                    'logs': [],
                    'start_time': ''
                }
            })
    except Exception as e:
        logger.error(f"获取下载进度失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取进度失败: {str(e)}'
        }), 500

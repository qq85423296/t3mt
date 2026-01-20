# -*- coding: utf-8 -*-
"""
调度监控API
"""
from flask import Blueprint, request, jsonify
from database import get_db
from utils.logger import logger
from config import Config

monitor_bp = Blueprint('monitor', __name__, url_prefix='/api/monitor')


def parse_logs(logs_data):
    """
    统一的日志解析函数，支持多种格式
    
    Args:
        logs_data: 日志数据（可能是JSON字符串、纯文本字符串或None）
    
    Returns:
        list: 解析后的日志数组
    """
    if not logs_data:
        return []
    
    # 如果已经是列表，直接返回
    if isinstance(logs_data, list):
        return logs_data
    
    # 如果是字符串，尝试解析
    if isinstance(logs_data, str):
        # 尝试解析为JSON格式（定时下载、定时转存使用）
        try:
            import json
            parsed = json.loads(logs_data)
            if isinstance(parsed, list):
                return parsed
        except:
            pass
        
        # 如果不是JSON，按纯文本处理（影视下载使用）
        # 按换行符分割，每行作为一条日志
        lines = logs_data.strip().split('\n')
        result = []
        for line in lines:
            line = line.strip()
            if line:
                # 尝试提取时间戳和消息
                # 格式: [HH:MM:SS] 消息内容
                import re
                match = re.match(r'\[(\d{2}:\d{2}:\d{2})\]\s*(.+)', line)
                if match:
                    timestamp = match.group(1)
                    message = match.group(2)
                    
                    # 判断日志类型
                    log_type = 'info'
                    if '✓' in message or '成功' in message:
                        log_type = 'success'
                    elif '✗' in message or '失败' in message or '异常' in message or '错误' in message:
                        log_type = 'error'
                    elif '⊙' in message or '跳过' in message or '警告' in message:
                        log_type = 'warning'
                    
                    result.append({
                        'timestamp': timestamp,
                        'message': message,
                        'type': log_type
                    })
                else:
                    # 没有时间戳的行，直接作为消息
                    result.append({
                        'message': line,
                        'type': 'info'
                    })
        
        return result if result else []
    
    return []


@monitor_bp.route('/executions', methods=['GET'])
def get_executions():
    """获取任务执行历史列表"""
    try:
        # 获取查询参数
        task_type = request.args.get('task_type')  # transfer 或 download 或 video
        task_id = request.args.get('task_id')  # 任务ID
        task_name = request.args.get('task_name')  # 任务名称模糊搜索
        cloud_type = request.args.get('cloud_type')  # 云盘类型筛选（quark 或 cloud189）
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        status = request.args.get('status')
        schedule_date = request.args.get('schedule_date')  # 账期日期筛选 YYYYMMDD
        show_duplicates = request.args.get('show_duplicates', 'false').lower() == 'true'  # 是否查看重复
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        limit = request.args.get('limit')  # 限制返回数量（用于实时查询）
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 构建查询条件
            conditions = []
            params = []
            
            if task_type:
                conditions.append('task_type = ?')
                params.append(task_type)
            
            if task_id:
                conditions.append('task_id = ?')
                params.append(task_id)
            
            if task_name:
                conditions.append('task_name LIKE ?')
                params.append(f'%{task_name}%')
            
            if cloud_type:
                # 根据cloud_type筛选任务
                # 需要关联对应的任务表获取cloud_type
                conditions.append('cloud_type = ?')
                params.append(cloud_type)
            
            if start_date:
                conditions.append('DATE(start_time) >= ?')
                params.append(start_date)
            
            if end_date:
                conditions.append('DATE(start_time) <= ?')
                params.append(end_date)
            
            if status:
                # 支持多状态筛选（逗号分隔）
                status_list = [s.strip() for s in status.split(',') if s.strip()]
                if len(status_list) == 1:
                    conditions.append('status = ?')
                    params.append(status_list[0])
                elif len(status_list) > 1:
                    placeholders = ','.join(['?' for _ in status_list])
                    conditions.append(f'status IN ({placeholders})')
                    params.extend(status_list)
            
            if schedule_date:
                # 按账期日期筛选（YYYYMMDD）
                conditions.append('schedule_period LIKE ?')
                params.append(f'{schedule_date}%')
            
            where_clause = ' AND '.join(conditions) if conditions else '1=1'
            
            # 如果指定了limit，直接返回最新的N条记录
            if limit:
                if show_duplicates:
                    # 显示重复：返回所有记录
                    cursor.execute(f'''
                        SELECT * FROM task_execution_history
                        WHERE {where_clause}
                        ORDER BY id DESC
                        LIMIT ?
                    ''', params + [int(limit)])
                else:
                    # 不显示重复：每个任务+账期组合只显示最新的一条
                    cursor.execute(f'''
                        SELECT * FROM task_execution_history
                        WHERE id IN (
                            SELECT MAX(id) FROM task_execution_history
                            WHERE {where_clause}
                            GROUP BY task_id, task_type, COALESCE(schedule_period, '')
                        )
                        ORDER BY id DESC
                        LIMIT ?
                    ''', params + [int(limit)])
                
                executions = [dict(row) for row in cursor.fetchall()]
                
                # 解析logs字段
                for execution in executions:
                    execution['logs'] = parse_logs(execution.get('logs'))
                
                return jsonify({
                    'code': 200,
                    'message': 'success',
                    'data': executions
                })
            
            # 根据是否显示重复，使用不同的查询逻辑
            if show_duplicates:
                # 显示重复：查询所有记录
                # 查询总数
                cursor.execute(f'''
                    SELECT COUNT(*) FROM task_execution_history
                    WHERE {where_clause}
                ''', params)
                total = cursor.fetchone()[0]
                
                # 查询列表
                offset = (page - 1) * page_size
                cursor.execute(f'''
                    SELECT * FROM task_execution_history
                    WHERE {where_clause}
                    ORDER BY id DESC
                    LIMIT ? OFFSET ?
                ''', params + [page_size, offset])
                
                executions = [dict(row) for row in cursor.fetchall()]
            else:
                # 不显示重复：每个任务+账期组合只显示最新的一条
                # 查询总数（去重后的数量）
                cursor.execute(f'''
                    SELECT COUNT(*) FROM (
                        SELECT task_id, task_type, COALESCE(schedule_period, '') as sp
                        FROM task_execution_history
                        WHERE {where_clause}
                        GROUP BY task_id, task_type, sp
                    )
                ''', params)
                total = cursor.fetchone()[0]
                
                # 查询列表（每个任务+账期组合取最新的一条）
                offset = (page - 1) * page_size
                cursor.execute(f'''
                    SELECT * FROM task_execution_history
                    WHERE id IN (
                        SELECT MAX(id) FROM task_execution_history
                        WHERE {where_clause}
                        GROUP BY task_id, task_type, COALESCE(schedule_period, '')
                    )
                    ORDER BY id DESC
                    LIMIT ? OFFSET ?
                ''', params + [page_size, offset])
                
                executions = [dict(row) for row in cursor.fetchall()]
            
            # 解析logs字段
            for execution in executions:
                execution['logs'] = parse_logs(execution.get('logs'))
                
                # 获取任务的cloud_type信息
                try:
                    task_type_val = execution.get('task_type')
                    task_id_val = execution.get('task_id')
                    
                    if task_type_val == 'transfer':
                        cursor.execute('SELECT cloud_type FROM transfer_tasks WHERE id = ?', (task_id_val,))
                    elif task_type_val == 'download':
                        cursor.execute('SELECT cloud_type FROM download_tasks WHERE id = ?', (task_id_val,))
                    elif task_type_val == 'video':
                        cursor.execute('SELECT cloud_type, platform FROM video_tasks WHERE id = ?', (task_id_val,))
                    else:
                        continue
                    
                    task_row = cursor.fetchone()
                    if task_row:
                        # 将sqlite3.Row转换为字典
                        task_dict = dict(task_row)
                        execution['cloud_type'] = task_dict.get('cloud_type', 'quark')
                        if task_type_val == 'video':
                            execution['platform'] = task_dict.get('platform', 'mango')
                    else:
                        execution['cloud_type'] = 'quark'  # 默认值
                        if task_type_val == 'video':
                            execution['platform'] = 'mango'
                except Exception as e:
                    logger.warning(f"获取任务cloud_type信息失败: {e}")
                    execution['cloud_type'] = 'quark'
                    if execution.get('task_type') == 'video':
                        execution['platform'] = 'mango'
            
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {
                    'list': executions,
                    'total': total,
                    'page': page,
                    'page_size': page_size
                }
            })
    except Exception as e:
        logger.error(f"获取任务执行历史失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取失败: {str(e)}'
        }), 500


@monitor_bp.route('/execution/<int:execution_id>', methods=['GET'])
def get_execution_detail(execution_id):
    """获取任务执行详情(优先获取实时日志)"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM task_execution_history
                WHERE id = ?
            ''', (execution_id,))
            
            execution = cursor.fetchone()
            
            if not execution:
                return jsonify({
                    'code': 404,
                    'message': '执行记录不存在'
                }), 404
            
            # 转换为字典
            execution_dict = dict(execution)
            
            # 优先从内存获取实时日志(如果任务正在执行)
            task_id = execution_dict.get('task_id')
            task_type = execution_dict.get('task_type')
            
            real_time_logs = None
            if task_type == 'download':
                # 尝试从TaskExecutor获取实时日志
                from services.task_executor import TaskExecutor
                task_status = TaskExecutor.get_task_status(task_id)
                if task_status and task_status.get('execution_id') == execution_id:
                    real_time_logs = task_status.get('logs', [])
                    logger.info(f"从内存获取实时日志: execution_id={execution_id}, 日志数量={len(real_time_logs)}")
            
            # 如果有实时日志,使用实时日志;否则从数据库解析
            if real_time_logs:
                execution_dict['logs'] = real_time_logs
                execution_dict['is_real_time'] = True  # 标记为实时日志
            else:
                execution_dict['logs'] = parse_logs(execution_dict.get('logs'))
                execution_dict['is_real_time'] = False
            
            # 获取任务的cloud_type信息
            try:
                task_type_val = execution_dict.get('task_type')
                task_id_val = execution_dict.get('task_id')
                
                if task_type_val == 'transfer':
                    cursor.execute('SELECT cloud_type FROM transfer_tasks WHERE id = ?', (task_id_val,))
                elif task_type_val == 'download':
                    cursor.execute('SELECT cloud_type FROM download_tasks WHERE id = ?', (task_id_val,))
                elif task_type_val == 'video':
                    cursor.execute('SELECT cloud_type, platform FROM video_tasks WHERE id = ?', (task_id_val,))
                else:
                    execution_dict['cloud_type'] = 'quark'
                    return jsonify({
                        'code': 200,
                        'message': 'success',
                        'data': execution_dict
                    })
                
                task_row = cursor.fetchone()
                if task_row:
                    execution_dict['cloud_type'] = task_row['cloud_type']
                    if task_type_val == 'video':
                        execution_dict['platform'] = task_row.get('platform', 'mango')
                else:
                    execution_dict['cloud_type'] = 'quark'
                    if task_type_val == 'video':
                        execution_dict['platform'] = 'mango'
            except Exception as e:
                logger.warning(f"获取任务cloud_type信息失败: {e}")
                execution_dict['cloud_type'] = 'quark'
                if task_type_val == 'video':
                    execution_dict['platform'] = 'mango'
            
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': execution_dict
            })
    except Exception as e:
        logger.error(f"获取执行详情失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取失败: {str(e)}'
        }), 500


@monitor_bp.route('/execution/<int:execution_id>/stop', methods=['POST'])
def stop_execution(execution_id):
    """终止正在执行的任务"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 获取执行记录
            cursor.execute('''
                SELECT task_id, task_type, task_name, status FROM task_execution_history
                WHERE id = ?
            ''', (execution_id,))
            
            execution = cursor.fetchone()
            
            if not execution:
                return jsonify({
                    'code': 404,
                    'message': '执行记录不存在'
                }), 404
            
            # 只能终止运行中的任务
            if execution['status'] != 'running':
                return jsonify({
                    'code': 400,
                    'message': '只能终止运行中的任务'
                }), 400
            
            task_id = execution['task_id']
            task_type = execution['task_type']
            task_name = execution['task_name']
            
            logger.info(f"尝试终止任务: {task_name} ({task_type}) - execution_id: {execution_id}")
            
            # 根据任务类型终止
            if task_type == 'download':
                # 终止下载任务
                from services.task_executor import TaskExecutor
                from datetime import datetime
                
                # 尝试终止内存中的任务
                stopped_in_memory = TaskExecutor.stop_task(task_id)
                
                # 无论任务是否在内存中,都更新数据库状态
                # (任务可能已完成但数据库状态未更新,或任务确实在运行)
                cursor.execute("""
                    UPDATE task_execution_history 
                    SET status = 'failed', 
                        end_time = ?,
                        error_message = '任务已被手动终止'
                    WHERE id = ?
                """, (datetime.now(), execution_id))
                conn.commit()
                
                if stopped_in_memory:
                    logger.info(f"下载任务已终止(内存+数据库): {task_name}")
                else:
                    logger.info(f"下载任务已终止(仅数据库,任务可能已完成): {task_name}")
                
                return jsonify({
                    'code': 200,
                    'message': '任务已终止'
                })
                    
            elif task_type == 'transfer':
                # 转存任务通过HTTP同步请求执行，无法直接终止
                # 只能标记为已终止，但任务可能仍在后台执行
                from datetime import datetime
                
                # 获取当前日志
                cursor.execute("SELECT logs FROM task_execution_history WHERE id = ?", (execution_id,))
                row = cursor.fetchone()
                logs = row['logs'] if row else '[]'
                
                # 添加终止日志
                import json
                try:
                    log_list = json.loads(logs) if logs else []
                except:
                    log_list = []
                
                log_list.append({
                    'message': '任务已被手动终止（转存任务无法立即停止，可能仍在后台执行）',
                    'type': 'warning',
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                
                cursor.execute("""
                    UPDATE task_execution_history 
                    SET status = 'failed', 
                        end_time = ?,
                        logs = ?,
                        error_message = '任务已被手动终止'
                    WHERE id = ?
                """, (datetime.now(), json.dumps(log_list, ensure_ascii=False), execution_id))
                conn.commit()
                
                logger.info(f"转存任务已标记为终止: {task_name}")
                return jsonify({
                    'code': 200,
                    'message': '任务已标记为终止（转存任务可能仍在后台执行）'
                })
                
            elif task_type == 'video':
                # 影视下载任务通过线程异步执行，无法直接终止
                # 只能标记为已终止
                from datetime import datetime
                
                # 获取当前日志
                cursor.execute("SELECT logs FROM task_execution_history WHERE id = ?", (execution_id,))
                row = cursor.fetchone()
                current_logs = row['logs'] if row else ''
                
                # 添加终止日志
                if current_logs:
                    new_logs = current_logs + f"\n[{datetime.now().strftime('%H:%M:%S')}] ⊙ 任务已被手动终止"
                else:
                    new_logs = f"[{datetime.now().strftime('%H:%M:%S')}] ⊙ 任务已被手动终止"
                
                cursor.execute("""
                    UPDATE task_execution_history 
                    SET status = 'failed', 
                        end_time = ?,
                        logs = ?,
                        error_message = '任务已被手动终止'
                    WHERE id = ?
                """, (datetime.now(), new_logs, execution_id))
                conn.commit()
                
                # 更新任务状态
                from models.video_task import VideoTask
                VideoTask.update(task_id, status='idle')
                
                logger.info(f"影视下载任务已标记为终止: {task_name}")
                return jsonify({
                    'code': 200,
                    'message': '任务已标记为终止'
                })
            else:
                return jsonify({
                    'code': 400,
                    'message': f'未知的任务类型: {task_type}'
                }), 400
            
    except Exception as e:
        logger.error(f"终止任务失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'终止失败: {str(e)}'
        }), 500


@monitor_bp.route('/execution/<int:execution_id>/retry', methods=['POST'])
def retry_execution(execution_id):
    """重新执行任务"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 获取执行记录
            cursor.execute('''
                SELECT task_id, task_type, task_name, schedule_period FROM task_execution_history
                WHERE id = ?
            ''', (execution_id,))
            
            execution = cursor.fetchone()
            
            if not execution:
                return jsonify({
                    'code': 404,
                    'message': '执行记录不存在'
                }), 404
            
            task_id = execution['task_id']
            task_type = execution['task_type']
            task_name = execution['task_name']
            schedule_period = execution['schedule_period']
            
            logger.info(f"准备重做任务: {task_name} ({task_type})")
            
            # 删除该任务的所有执行记录（避免唯一约束冲突）
            cursor.execute("""
                DELETE FROM task_execution_history 
                WHERE task_id = ? AND task_type = ?
            """, (task_id, task_type))
            conn.commit()
            
            logger.info(f"已删除任务 {task_name} 的历史记录")
            
            # 根据任务类型立即执行
            if task_type == 'transfer':
                # 调用转存任务执行
                from services.transfer_service import TransferService
                task = TransferService.get_task_by_id(task_id)
                if not task:
                    return jsonify({
                        'code': 404,
                        'message': '转存任务不存在'
                    }), 404
                
                import requests
                response = requests.post(
                    f'{Config.API_BASE_URL}/api/transfer/task/{task_id}/execute',
                    timeout=300
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('code') == 200:
                        return jsonify({
                            'code': 200,
                            'message': '转存任务已重新启动'
                        })
                    else:
                        return jsonify({
                            'code': 400,
                            'message': result.get('message', '转存任务启动失败')
                        }), 400
                else:
                    return jsonify({
                        'code': 400,
                        'message': '转存任务启动失败'
                    }), 400
                    
            elif task_type == 'download':
                # 调用下载任务执行
                # 先强制清除任务状态
                from services.task_executor import TaskExecutor
                TaskExecutor.force_clear_task(task_id)
                logger.info(f"已清除下载任务 {task_id} 的状态")
                
                # 下载任务会自己创建执行记录
                import requests
                response = requests.post(
                    f'{Config.API_BASE_URL}/api/download/task/{task_id}/execute',
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('code') == 200:
                        return jsonify({
                            'code': 200,
                            'message': '下载任务已重新启动'
                        })
                    else:
                        return jsonify({
                            'code': 400,
                            'message': result.get('message', '下载任务启动失败')
                        }), 400
                else:
                    return jsonify({
                        'code': 400,
                        'message': '下载任务启动失败'
                    }), 400
                    
            elif task_type == 'video':
                # 调用影视下载任务执行
                # 影视任务会自己创建执行记录
                import requests
                response = requests.post(
                    f'{Config.API_BASE_URL}/api/video/task/{task_id}/execute',
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('code') == 200:
                        return jsonify({
                            'code': 200,
                            'message': '影视下载任务已重新启动'
                        })
                    else:
                        return jsonify({
                            'code': 400,
                            'message': result.get('message', '影视下载任务启动失败')
                        }), 400
                else:
                    return jsonify({
                        'code': 400,
                        'message': '影视下载任务启动失败'
                    }), 400
            else:
                return jsonify({
                    'code': 400,
                    'message': f'未知的任务类型: {task_type}'
                }), 400
            
    except Exception as e:
        logger.error(f"重新执行任务失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'执行失败: {str(e)}'
        }), 500


@monitor_bp.route('/execution/<int:execution_id>/force-execute', methods=['POST'])
def force_execute(execution_id):
    """强制执行待执行任务"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 获取执行记录
            cursor.execute('''
                SELECT task_id, task_type, task_name, status FROM task_execution_history
                WHERE id = ?
            ''', (execution_id,))
            
            execution = cursor.fetchone()
            
            if not execution:
                return jsonify({
                    'code': 404,
                    'message': '执行记录不存在'
                }), 404
            
            # 只允许强制执行待执行状态的任务
            if execution['status'] != 'pending':
                return jsonify({
                    'code': 400,
                    'message': f'只能强制执行待执行状态的任务，当前状态: {execution["status"]}'
                }), 400
            
            task_id = execution['task_id']
            task_type = execution['task_type']
            task_name = execution['task_name']
            
            logger.info(f"强制执行待执行任务: {task_name} ({task_type}), 执行ID: {execution_id}")
            
            # 导入调度服务
            from services.scheduler_service import SchedulerService
            
            # 根据任务类型调用对应的执行方法
            if task_type == 'video':
                # 使用线程异步执行，避免阻塞
                import threading
                thread = threading.Thread(
                    target=SchedulerService._execute_video_task,
                    args=(execution_id, task_id),
                    daemon=True
                )
                thread.start()
                
                return jsonify({
                    'code': 200,
                    'message': '影视下载任务已开始执行'
                })
                
            elif task_type == 'transfer':
                # 使用线程异步执行
                import threading
                thread = threading.Thread(
                    target=SchedulerService._execute_transfer_task,
                    args=(execution_id, task_id),
                    daemon=True
                )
                thread.start()
                
                return jsonify({
                    'code': 200,
                    'message': '转存任务已开始执行'
                })
                
            elif task_type == 'download':
                # 使用线程异步执行
                import threading
                thread = threading.Thread(
                    target=SchedulerService._execute_download_task,
                    args=(execution_id, task_id),
                    daemon=True
                )
                thread.start()
                
                return jsonify({
                    'code': 200,
                    'message': '下载任务已开始执行'
                })
            else:
                return jsonify({
                    'code': 400,
                    'message': f'未知的任务类型: {task_type}'
                }), 400
            
    except Exception as e:
        logger.error(f"强制执行任务失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'执行失败: {str(e)}'
        }), 500


@monitor_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """获取任务执行统计信息"""
    try:
        # 获取查询参数
        task_type = request.args.get('task_type')  # transfer 或 download 或 video
        cloud_type = request.args.get('cloud_type')  # quark 或 cloud189
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 构建查询条件
            conditions = []
            params = []
            
            if task_type:
                conditions.append('teh.task_type = ?')
                params.append(task_type)
            
            if start_date:
                conditions.append('DATE(teh.start_time) >= ?')
                params.append(start_date)
            
            if end_date:
                conditions.append('DATE(teh.start_time) <= ?')
                params.append(end_date)
            
            where_clause = ' AND '.join(conditions) if conditions else '1=1'
            
            # 根据任务类型构建JOIN子句
            join_clause = ''
            cloud_type_field = 'NULL'
            
            if task_type == 'transfer':
                join_clause = 'LEFT JOIN transfer_tasks tt ON teh.task_id = tt.id'
                cloud_type_field = 'tt.cloud_type'
            elif task_type == 'download':
                join_clause = 'LEFT JOIN download_tasks dt ON teh.task_id = dt.id'
                cloud_type_field = 'dt.cloud_type'
            elif task_type == 'video':
                join_clause = 'LEFT JOIN video_tasks vt ON teh.task_id = vt.id'
                cloud_type_field = 'vt.cloud_type'
            
            # 如果指定了cloud_type，添加过滤条件
            if cloud_type and join_clause:
                where_clause += f' AND {cloud_type_field} = ?'
                params.append(cloud_type)
            
            # 查询总体统计
            if join_clause:
                cursor.execute(f'''
                    SELECT 
                        COUNT(*) as total_count,
                        SUM(CASE WHEN teh.status = 'success' THEN 1 ELSE 0 END) as success_count,
                        SUM(CASE WHEN teh.status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                        SUM(CASE WHEN teh.status = 'running' THEN 1 ELSE 0 END) as running_count,
                        SUM(CASE WHEN teh.status = 'pending' THEN 1 ELSE 0 END) as pending_count
                    FROM task_execution_history teh
                    {join_clause}
                    WHERE {where_clause}
                ''', params)
            else:
                cursor.execute(f'''
                    SELECT 
                        COUNT(*) as total_count,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                        SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running_count,
                        SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count
                    FROM task_execution_history
                    WHERE {where_clause}
                ''', params)
            
            overall = dict(cursor.fetchone())
            
            # 计算成功率
            total = overall['total_count'] or 0
            success = overall['success_count'] or 0
            overall['success_rate'] = round(success / total * 100, 2) if total > 0 else 0
            
            # 按云盘类型分组统计（如果有JOIN）
            by_cloud_type = []
            if join_clause and not cloud_type:  # 只有在未指定cloud_type时才分组统计
                cursor.execute(f'''
                    SELECT 
                        {cloud_type_field} as cloud_type,
                        COUNT(*) as total_count,
                        SUM(CASE WHEN teh.status = 'success' THEN 1 ELSE 0 END) as success_count,
                        SUM(CASE WHEN teh.status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                        SUM(CASE WHEN teh.status = 'running' THEN 1 ELSE 0 END) as running_count,
                        SUM(CASE WHEN teh.status = 'pending' THEN 1 ELSE 0 END) as pending_count
                    FROM task_execution_history teh
                    {join_clause}
                    WHERE {where_clause}
                    GROUP BY {cloud_type_field}
                ''', params)
                
                for row in cursor.fetchall():
                    row_dict = dict(row)
                    total = row_dict['total_count'] or 0
                    success = row_dict['success_count'] or 0
                    row_dict['success_rate'] = round(success / total * 100, 2) if total > 0 else 0
                    by_cloud_type.append(row_dict)
            
            # 按任务类型分组统计（如果未指定task_type）
            by_task_type = []
            if not task_type:
                cursor.execute(f'''
                    SELECT 
                        task_type,
                        COUNT(*) as total_count,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                        SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running_count,
                        SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count
                    FROM task_execution_history
                    WHERE {where_clause}
                    GROUP BY task_type
                ''', params)
                
                for row in cursor.fetchall():
                    row_dict = dict(row)
                    total = row_dict['total_count'] or 0
                    success = row_dict['success_count'] or 0
                    row_dict['success_rate'] = round(success / total * 100, 2) if total > 0 else 0
                    by_task_type.append(row_dict)
            
            # 最近失败的任务（用于告警）
            recent_failures = []
            if join_clause:
                cursor.execute(f'''
                    SELECT 
                        teh.id,
                        teh.task_id,
                        teh.task_type,
                        teh.task_name,
                        {cloud_type_field} as cloud_type,
                        teh.start_time,
                        teh.end_time,
                        teh.error_message
                    FROM task_execution_history teh
                    {join_clause}
                    WHERE {where_clause} AND teh.status = 'failed'
                    ORDER BY teh.start_time DESC
                    LIMIT 10
                ''', params)
            else:
                cursor.execute(f'''
                    SELECT 
                        id,
                        task_id,
                        task_type,
                        task_name,
                        start_time,
                        end_time,
                        error_message
                    FROM task_execution_history
                    WHERE {where_clause} AND status = 'failed'
                    ORDER BY start_time DESC
                    LIMIT 10
                ''', params)
            
            recent_failures = [dict(row) for row in cursor.fetchall()]
            
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {
                    'overall': overall,
                    'by_cloud_type': by_cloud_type,
                    'by_task_type': by_task_type,
                    'recent_failures': recent_failures
                }
            })
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取统计信息失败: {str(e)}'
        }), 500

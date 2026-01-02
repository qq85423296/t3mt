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
                
                # 如果是影视下载任务，获取平台信息
                if execution.get('task_type') == 'video':
                    try:
                        cursor.execute('''
                            SELECT platform FROM video_tasks WHERE id = ?
                        ''', (execution['task_id'],))
                        video_task = cursor.fetchone()
                        if video_task:
                            execution['platform'] = video_task['platform']
                        else:
                            execution['platform'] = 'mango'  # 默认值
                    except Exception as e:
                        logger.warning(f"获取影视任务平台信息失败: {e}")
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
    """获取任务执行详情"""
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
            
            # 解析logs字段（支持JSON和纯文本格式）
            execution_dict['logs'] = parse_logs(execution_dict.get('logs'))
            
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
                if TaskExecutor.stop_task(task_id):
                    # 更新执行记录状态为已终止
                    from datetime import datetime
                    cursor.execute("""
                        UPDATE task_execution_history 
                        SET status = 'failed', 
                            end_time = ?,
                            error_message = '任务已被手动终止'
                        WHERE id = ?
                    """, (datetime.now(), execution_id))
                    conn.commit()
                    
                    logger.info(f"下载任务已终止: {task_name}")
                    return jsonify({
                        'code': 200,
                        'message': '任务已终止'
                    })
                else:
                    return jsonify({
                        'code': 400,
                        'message': '任务未在运行中'
                    }), 400
                    
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

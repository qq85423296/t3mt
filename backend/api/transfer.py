# -*- coding: utf-8 -*-
"""
转存任务API
"""
import json
from flask import Blueprint, request, jsonify
from datetime import datetime
from services.transfer_service import TransferService
from database import get_db
from utils.logger import logger

transfer_bp = Blueprint('transfer', __name__, url_prefix='/api/transfer')


def create_path_recursive(quark, full_path, add_log=None, idx=1, total=1):
    """
    递归创建目录路径
    
    Args:
        quark: QuarkService实例
        full_path: 完整路径，如 /夸克自动转存测试/20260111
        add_log: 日志函数
        idx: 当前索引
        total: 总数
    
    Returns:
        str: 最终目录的FID，失败返回"0"
    """
    if not full_path or full_path == '/':
        return "0"
    
    # 分割路径
    parts = [p for p in full_path.split('/') if p]
    if not parts:
        return "0"
    
    current_fid = "0"  # 从根目录开始
    current_path = ""
    
    for part in parts:
        current_path = f"{current_path}/{part}"
        
        # 先查询该路径是否存在
        fid_infos = quark.get_fids_by_paths([current_path])
        
        if fid_infos and len(fid_infos) > 0:
            fid_info = fid_infos[0]
            if isinstance(fid_info, dict) and 'fid' in fid_info:
                current_fid = fid_info['fid']
                continue
        
        # 路径不存在，创建目录（只传文件夹名称和父目录FID）
        mkdir_result = quark.mkdir(part, current_fid)
        logger.info(f"创建目录 {part} (父目录FID: {current_fid}) 结果: {mkdir_result}")
        
        if mkdir_result.get('code') == 0:
            current_fid = mkdir_result['data']['fid']
            if add_log:
                add_log(f"[{idx}/{total}] 创建子目录成功: {part}", 'info')
        else:
            error_msg = mkdir_result.get('message', '未知错误')
            logger.error(f"创建目录失败: {part}, 错误: {error_msg}")
            if add_log:
                add_log(f"[{idx}/{total}] 创建子目录失败: {part}, 错误: {error_msg}", 'error')
            return "0"
    
    return current_fid


@transfer_bp.route('/tasks', methods=['GET'])
def get_tasks():
    """获取转存任务列表"""
    try:
        # 获取cloud_type筛选参数
        cloud_type = request.args.get('cloud_type')
        
        # 获取任务列表，支持按cloud_type筛选
        tasks = TransferService.get_all_tasks(cloud_type=cloud_type)
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': tasks
        })
    except Exception as e:
        logger.error(f"获取转存任务列表失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取任务列表失败: {str(e)}'
        }), 500


@transfer_bp.route('/task', methods=['POST'])
def create_task():
    """创建转存任务"""
    try:
        data = request.get_json()
        
        # 验证必填字段
        required_fields = ['name', 'share_urls', 'target_account_id', 'target_path', 'cron_expression']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'code': 400,
                    'message': f'{field}不能为空'
                }), 400
        
        # 创建任务
        task_id = TransferService.create_task(data)
        
        # TODO: 添加到任务调度器
        
        return jsonify({
            'code': 200,
            'message': '任务创建成功',
            'data': {'id': task_id}
        })
    except Exception as e:
        logger.error(f"创建转存任务失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'创建任务失败: {str(e)}'
        }), 500


@transfer_bp.route('/task/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """获取转存任务详情"""
    try:
        task = TransferService.get_task_by_id(task_id)
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
        logger.error(f"获取转存任务详情失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取任务详情失败: {str(e)}'
        }), 500


@transfer_bp.route('/task/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """更新转存任务"""
    try:
        data = request.get_json()
        
        # 验证任务是否存在
        task = TransferService.get_task_by_id(task_id)
        if not task:
            return jsonify({
                'code': 404,
                'message': '任务不存在'
            }), 404
        
        # 更新任务
        TransferService.update_task(task_id, data)
        
        # TODO: 更新任务调度器
        
        return jsonify({
            'code': 200,
            'message': '任务更新成功'
        })
    except Exception as e:
        logger.error(f"更新转存任务失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'更新任务失败: {str(e)}'
        }), 500


@transfer_bp.route('/task/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除转存任务"""
    try:
        from database import db
        from tasks.scheduler import task_scheduler
        
        # 验证任务是否存在
        task = TransferService.get_task_by_id(task_id)
        if not task:
            return jsonify({
                'code': 404,
                'message': '任务不存在'
            }), 404
        
        # 从调度器中移除任务
        try:
            task_scheduler.remove_task(task_id, 'transfer')
            logger.info(f"从调度器移除转存任务: {task_id}")
        except Exception as e:
            logger.warning(f"从调度器移除任务失败: {str(e)}")
        
        # 删除任务
        TransferService.delete_task(task_id)
        
        # 删除关联的执行历史记录
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM task_execution_history 
                    WHERE task_id = ? AND task_type = 'transfer'
                ''', (task_id,))
                deleted_count = cursor.rowcount
                logger.info(f"删除转存任务 {task_id} 的 {deleted_count} 条执行历史记录")
        except Exception as e:
            logger.warning(f"删除执行历史记录失败: {str(e)}")
        
        return jsonify({
            'code': 200,
            'message': '任务删除成功'
        })
    except Exception as e:
        logger.error(f"删除转存任务失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'删除任务失败: {str(e)}'
        }), 500


@transfer_bp.route('/task/<int:task_id>/toggle', methods=['POST'])
def toggle_task(task_id):
    """发布/下线任务"""
    try:
        # 验证任务是否存在
        task = TransferService.get_task_by_id(task_id)
        if not task:
            return jsonify({
                'code': 404,
                'message': '任务不存在'
            }), 404
        
        # 切换状态
        new_status = TransferService.toggle_task_status(task_id)
        
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


@transfer_bp.route('/task/<int:task_id>/execute', methods=['POST'])
def execute_task(task_id):
    """立即执行任务"""
    print(f"[DEBUG] execute_task被调用: task_id={task_id}")
    logger.info(f"[execute_task] 开始执行任务: task_id={task_id}")
    execution_id = None
    schedule_period = None
    
    try:
        # 验证任务是否存在
        task = TransferService.get_task_by_id(task_id)
        if not task:
            return jsonify({
                'code': 404,
                'message': '任务不存在'
            }), 404
        
        # 手动执行：删除该任务之前的所有执行记录，确保每个任务只保留最新一次执行记录
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM task_execution_history 
                WHERE task_id = ? AND task_type = 'transfer'
            ''', (task_id,))
        
        # 生成账期（当前时间）
        schedule_period = datetime.now().strftime('%Y%m%d%H')
        
        # 创建执行历史记录
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO task_execution_history (
                    task_id, task_type, task_name, schedule_period,
                    status, start_time, logs
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (task_id, 'transfer', task['name'], schedule_period,
                  'running', datetime.now(), '[]'))
            conn.commit()
            execution_id = cursor.lastrowid
        
        # 执行日志列表
        logs = []
        
        def add_log(message, log_type='info'):
            """添加日志"""
            logs.append({
                'message': message,
                'type': log_type,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            logger.info(f"[任务{task_id}] {message}")
        
        try:
            add_log(f"开始执行任务: {task['name']}", 'info')
            
            # 获取目标账号
            from models.account import Account
            
            account = Account.get_by_id(task['target_account_id'])
            if not account:
                add_log('目标账号不存在', 'error')
                return jsonify({
                    'code': 400,
                    'message': '目标账号不存在',
                    'data': {'logs': logs}
                })
            
            add_log(f"使用账号: {account['remark']}", 'info')
            add_log(f"目标路径: {task['target_path']}", 'info')
            
            # 根据账号云盘类型选择服务
            cloud_type = account.get('cloud_type', 'quark')
            add_log(f"云盘类型: {cloud_type}", 'info')
            
            if cloud_type == 'cloud189':
                # 天翼云盘
                from services.cloud189_service import Cloud189Service
                # 传入 username 和 password 以支持 Cookie 自动更新
                cloud_service = Cloud189Service(
                    cookie=account['cookie'],
                    username=account.get('username'),
                    password=account.get('password')
                )
                
                # 解析分享链接
                share_urls = task['share_urls']
                add_log(f"共有 {len(share_urls)} 个分享链接待处理", 'info')
                
                success_count = 0
                fail_count = 0
                total_files = 0
                
                for idx, share_url_obj in enumerate(share_urls, 1):
                    try:
                        # 提取URL
                        if isinstance(share_url_obj, dict):
                            share_url = share_url_obj['url']
                            url_status = share_url_obj.get('status', '未检查')
                        else:
                            share_url = share_url_obj
                            url_status = '未检查'
                        
                        add_log(f"[{idx}/{len(share_urls)}] 正在处理: {share_url[:60]}...", 'info')
                        
                        # 显示链接状态
                        if url_status != '未检查' and url_status != '正常':
                            add_log(f"[{idx}/{len(share_urls)}] 跳过异常链接", 'warning')
                            fail_count += 1
                            continue
                        
                        # 解析分享链接
                        add_log(f"[{idx}/{len(share_urls)}] 解析分享链接...", 'info')
                        share_code, access_code = Cloud189Service.parse_share_url(share_url)
                        add_log(f"[{idx}/{len(share_urls)}] 解析结果: share_code={share_code}, access_code={access_code}", 'info')
                        
                        if not share_code:
                            add_log(f"[{idx}/{len(share_urls)}] 解析失败：无效的分享链接", 'error')
                            fail_count += 1
                            continue
                        
                        # 执行转存
                        add_log(f"[{idx}/{len(share_urls)}] 开始转存...", 'info')
                        
                        # 获取目标文件夹ID（优先使用保存的ID）
                        target_folder_id = task.get('target_folder_id')  # 新增：优先使用保存的文件夹ID
                        final_target_path = task['target_path']
                        
                        # 处理保存模式
                        if task.get('save_mode') == 'subfolder' and task.get('target_folder_name'):
                            final_target_path = f"{task['target_path'].rstrip('/')}/{task['target_folder_name']}"
                        
                        # 如果没有保存的folder_id，则通过路径获取或创建
                        if not target_folder_id:
                            if cloud_type == 'cloud189':
                                target_folder_id = '-11'  # 天翼云盘根目录
                            else:
                                target_folder_id = '0'  # 夸克网盘根目录
                            
                            # 如果目标路径不是根目录，需要创建或查找目标文件夹
                            if final_target_path and final_target_path != '/':
                                add_log(f"[{idx}/{len(share_urls)}] 目标路径: {final_target_path}", 'info')
                                # 获取或创建目标文件夹
                                if cloud_type == 'cloud189':
                                    target_folder_id = cloud_service.get_or_create_folder_by_path(final_target_path)
                                else:
                                    # 夸克网盘也需要类似的方法
                                    target_folder_id = final_target_path  # 夸克直接使用路径作为ID
                                logger.info(f"{cloud_type}云盘目标文件夹ID: {target_folder_id}")
                        else:
                            add_log(f"[{idx}/{len(share_urls)}] 使用保存的文件夹ID: {target_folder_id}", 'info')
                        
                        # 调用转存方法
                        # 获取重存模式参数
                        overwrite_mode = task.get('overwrite_mode', 0) == 1
                        logger.info(f"调用save_share: url={share_url}, target_folder_id={target_folder_id}, access_code={access_code}, overwrite_mode={overwrite_mode}")
                        result = cloud_service.save_share(share_url, target_folder_id, access_code, overwrite_mode)
                        logger.info(f"save_share返回: {result}")
                        
                        if result.get('success'):
                            # 检查是否有跳过的文件
                            if result.get('skipped'):
                                skipped_count = result.get('skipped_count', 0)
                                add_log(f"[{idx}/{len(share_urls)}] 转存完成（跳过{skipped_count}个已存在文件）", 'success')
                            else:
                                add_log(f"[{idx}/{len(share_urls)}] 转存成功", 'success')
                            success_count += 1
                            # 统计实际转存的文件数
                            total_files += result.get('total_count', 1)
                            
                            # ========== 新增：排除关键词过滤 ==========
                            exclude_keywords = task.get('exclude_keywords')
                            if exclude_keywords:
                                try:
                                    # 解析排除关键词
                                    exclude_keyword_list = [kw.strip() for kw in exclude_keywords.split('|') if kw.strip()]
                                    if exclude_keyword_list:
                                        add_log(f"[{idx}/{len(share_urls)}] 开始清理包含排除关键词的文件...", 'info')
                                        add_log(f"[{idx}/{len(share_urls)}] 排除关键词: {', '.join(exclude_keyword_list)}", 'info')
                                        
                                        # 等待文件系统同步（天翼云盘需要时间）
                                        import time
                                        time.sleep(2)
                                        add_log(f"[{idx}/{len(share_urls)}] 等待文件系统同步...", 'info')
                                        
                                        # 获取目标文件夹的文件列表
                                        if cloud_type == 'cloud189':
                                            # 天翼云盘返回列表
                                            files_list = cloud_service.list_files(target_folder_id)
                                        else:
                                            # 夸克网盘返回列表
                                            files_list = cloud_service.list_files(target_folder_id)
                                        
                                        if files_list:
                                            files_to_delete = []
                                            for file_item in files_list:
                                                # 天翼云盘和夸克网盘的字段名不同
                                                file_name = file_item.get('name') or file_item.get('file_name', '')
                                                # 检查文件名是否包含排除关键词
                                                for keyword in exclude_keyword_list:
                                                    if keyword in file_name:
                                                        files_to_delete.append(file_item)
                                                        add_log(f"[{idx}/{len(share_urls)}] 发现需要删除的文件: {file_name} (包含关键词'{keyword}')", 'info')
                                                        break
                                            
                                            # 批量删除文件
                                            if files_to_delete:
                                                deleted_count = 0
                                                
                                                if cloud_type == 'cloud189':
                                                    # 天翼云盘需要传递文件ID列表和文件信息列表
                                                    file_ids = []
                                                    file_infos = []
                                                    for file_item in files_to_delete:
                                                        file_id = file_item.get('id')
                                                        file_name = file_item.get('name', '')
                                                        is_folder = file_item.get('isFolder', False)
                                                        
                                                        file_ids.append(file_id)
                                                        file_infos.append({
                                                            'name': file_name,
                                                            'isFolder': is_folder
                                                        })
                                                    
                                                    delete_result = cloud_service.delete(file_ids, file_infos)
                                                    
                                                    if delete_result.get('code') == 0:
                                                        deleted_count = len(files_to_delete)
                                                        for f in files_to_delete:
                                                            add_log(f"[{idx}/{len(share_urls)}] 已删除: {f.get('name', '')}", 'info')
                                                    else:
                                                        add_log(f"[{idx}/{len(share_urls)}] 删除失败: {delete_result.get('message', '未知错误')}", 'warning')
                                                else:
                                                    # 夸克网盘
                                                    for file_item in files_to_delete:
                                                        try:
                                                            file_id = file_item.get('fid')
                                                            file_name = file_item.get('file_name', '')
                                                            
                                                            delete_result = cloud_service.delete([file_id])
                                                            
                                                            if delete_result.get('status') == 200:
                                                                deleted_count += 1
                                                                add_log(f"[{idx}/{len(share_urls)}] 已删除: {file_name}", 'info')
                                                            else:
                                                                add_log(f"[{idx}/{len(share_urls)}] 删除失败: {file_name}", 'warning')
                                                        except Exception as del_e:
                                                            logger.error(f"删除文件失败: {del_e}")
                                                            add_log(f"[{idx}/{len(share_urls)}] 删除文件异常: {str(del_e)}", 'warning')
                                                
                                                add_log(f"[{idx}/{len(share_urls)}] 清理完成，共删除 {deleted_count} 个文件", 'success')
                                                # 更新实际文件数（减去被删除的文件）
                                                total_files -= deleted_count
                                            else:
                                                add_log(f"[{idx}/{len(share_urls)}] 未发现需要清理的文件", 'info')
                                        else:
                                            add_log(f"[{idx}/{len(share_urls)}] 无法获取文件列表，跳过清理", 'warning')
                                except Exception as filter_e:
                                    logger.error(f"排除关键词过滤失败: {filter_e}", exc_info=True)
                                    add_log(f"[{idx}/{len(share_urls)}] 排除关键词过滤失败: {str(filter_e)}", 'warning')
                            # ========== 排除关键词过滤结束 ==========
                        else:
                            add_log(f"[{idx}/{len(share_urls)}] 转存失败: {result.get('message', '未知错误')}", 'error')
                            fail_count += 1
                    
                    except Exception as e:
                        logger.error(f"处理分享链接失败: {e}", exc_info=True)
                        add_log(f"[{idx}/{len(share_urls)}] 处理失败: {str(e)}", 'error')
                        fail_count += 1
                
                add_log(f"任务执行完成！成功: {success_count}, 失败: {fail_count}, 文件数: {total_files}", 'success')
                
                # 根据失败数量判断最终状态
                final_status = 'success' if fail_count == 0 else ('partial' if success_count > 0 else 'failed')
                
                # 更新执行历史
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE task_execution_history 
                        SET status = ?, end_time = ?, logs = ?,
                            success_count = ?, failed_count = ?, total_count = ?
                        WHERE id = ?
                    """, (final_status, datetime.now(), json.dumps(logs, ensure_ascii=False),
                          success_count, fail_count, total_files, execution_id))
                    conn.commit()
                
                # 如果有新内容转存成功，更新last_content_update_time
                if success_count > 0:
                    try:
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        with get_db() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE transfer_tasks 
                                SET last_content_update_time = ?, updated_at = ?
                                WHERE id = ?
                            """, (current_time, current_time, task_id))
                            conn.commit()
                        logger.info(f"[AutoExpiration] 转存任务有新内容，已重置计时器: task_id={task_id}, last_content_update_time={current_time}")
                    except Exception as e:
                        logger.error(f"[AutoExpiration] 更新last_content_update_time失败: {e}")
                
                # 执行关联的插件
                try:
                    from services.plugin_executor import PluginExecutor
                    
                    # 从执行历史中获取真实的开始时间和结束时间
                    with get_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT start_time, end_time, duration
                            FROM task_execution_history
                            WHERE id = ?
                        """, (execution_id,))
                        history_row = cursor.fetchone()
                    
                    if history_row:
                        start_time_str = history_row[0]
                        end_time_str = history_row[1]
                        duration = history_row[2] or 0
                    else:
                        start_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        end_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        duration = 0
                    
                    # 构建来源路径（分享链接列表）
                    share_urls_list = task.get('share_urls', [])
                    if share_urls_list:
                        # 提取所有分享链接
                        source_urls = []
                        for url_obj in share_urls_list:
                            if isinstance(url_obj, dict):
                                source_urls.append(url_obj.get('url', ''))
                            else:
                                source_urls.append(url_obj)
                        source_path = '\n'.join(source_urls[:3])  # 最多显示3个链接
                        if len(source_urls) > 3:
                            source_path += f'\n... 等共 {len(source_urls)} 个链接'
                    else:
                        source_path = '无'
                    
                    # 构建目标路径（包含子目录）
                    target_path = task.get('target_path', '')
                    if task.get('save_mode') == 'subfolder' and task.get('target_folder_name'):
                        target_path = f"{target_path.rstrip('/')}/{task.get('target_folder_name')}"
                    
                    # 构建任务上下文
                    task_context = {
                        'task_id': task_id,
                        'task_name': task.get('name', ''),
                        'task_type': 'transfer',
                        'status': 'success' if fail_count == 0 else 'partial',
                        'start_time': start_time_str,
                        'end_time': end_time_str,
                        'duration': duration,
                        'total_count': total_files,
                        'success_count': success_count,
                        'failed_count': fail_count,
                        'total_size': 0,  # 转存任务暂不统计大小
                        'source_path': source_path,
                        'target_path': target_path,
                    }
                    
                    add_log('开始执行关联插件...', 'info')
                    plugin_result = PluginExecutor.execute_plugins(
                        task_id=task_id,
                        task_type='transfer',
                        execution_id=execution_id,
                        task_context=task_context
                    )
                    
                    if plugin_result['total'] > 0:
                        add_log(
                            f"插件执行完成: 总计 {plugin_result['total']} 个，"
                            f"成功 {plugin_result['success']} 个，"
                            f"失败 {plugin_result['failed']} 个，"
                            f"跳过 {plugin_result['skipped']} 个", 
                            'info')
                        
                        # 更新日志到数据库
                        with get_db() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE task_execution_history 
                                SET logs = ?
                                WHERE id = ?
                            """, (json.dumps(logs, ensure_ascii=False), execution_id))
                            conn.commit()
                    else:
                        add_log('没有关联的插件需要执行', 'info')
                        
                except Exception as plugin_error:
                    add_log(f"插件执行异常: {str(plugin_error)}", 'warning')
                    logger.error(f"执行插件异常: {plugin_error}", exc_info=True)
                    
                    # 更新日志到数据库
                    with get_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE task_execution_history 
                            SET logs = ?
                            WHERE id = ?
                        """, (json.dumps(logs, ensure_ascii=False), execution_id))
                        conn.commit()
                
                return jsonify({
                    'code': 200,
                    'message': '执行完成',
                    'data': {
                        'logs': logs,
                        'success_count': success_count,
                        'fail_count': fail_count,
                        'total_files': total_files
                    }
                })
            
            # 夸克网盘（默认）
            from services.quark_service import QuarkService
            quark = QuarkService(account['cookie'])
            
            # 解析分享链接
            share_urls = task['share_urls']
            add_log(f"共有 {len(share_urls)} 个分享链接待处理", 'info')
            
            success_count = 0
            fail_count = 0
            total_files = 0
            
            for idx, share_url_obj in enumerate(share_urls, 1):
                try:
                    # 提取URL和源路径（兼容字符串和对象格式）
                    if isinstance(share_url_obj, dict):
                        share_url = share_url_obj['url']
                        source_path = share_url_obj.get('source_path', '/')
                        url_status = share_url_obj.get('status', '未检查')
                    else:
                        share_url = share_url_obj
                        source_path = '/'
                        url_status = '未检查'
                    
                    add_log(f"[{idx}/{len(share_urls)}] 正在处理: {share_url[:60]}...", 'info')
                    if source_path != '/':
                        add_log(f"[{idx}/{len(share_urls)}] 源路径: {source_path}", 'info')
                    
                    # 显示链接状态
                    if url_status != '未检查':
                        add_log(f"[{idx}/{len(share_urls)}] 链接状态: {url_status}", 'info')
                        if url_status != '正常':
                            add_log(f"[{idx}/{len(share_urls)}] 跳过异常链接", 'warning')
                            fail_count += 1
                            continue
                    
                    # 解析分享链接
                    add_log(f"[{idx}/{len(share_urls)}] 解析分享链接...", 'info')
                    pwd_id, passcode, folder_id = QuarkService.parse_share_url(share_url)
                    
                    # 调试日志
                    logger.info(f"解析结果 - pwd_id: {pwd_id}, passcode: {passcode}, folder_id: {folder_id}")
                    add_log(f"[{idx}/{len(share_urls)}] 解析结果: pwd_id={pwd_id}, folder_id={folder_id}", 'info')
                    
                    if not pwd_id:
                        add_log(f"[{idx}/{len(share_urls)}] 解析失败：无效的分享链接", 'error')
                        fail_count += 1
                        continue
                    
                    # 获取分享令牌
                    add_log(f"[{idx}/{len(share_urls)}] 获取分享令牌...", 'info')
                    token_response = quark.get_stoken(pwd_id, passcode)
                    
                    if token_response.get('code') != 0:
                        add_log(f"[{idx}/{len(share_urls)}] 获取令牌失败: {token_response.get('message', '未知错误')}", 'error')
                        fail_count += 1
                        continue
                    
                    stoken = token_response['data']['stoken']
                    
                    # 初始化为根目录
                    pdir_fid = '0'
                    
                    # 如果URL中包含文件夹ID，直接使用
                    if folder_id:
                        pdir_fid = folder_id
                        add_log(f"[{idx}/{len(share_urls)}] 使用URL中的文件夹ID: {folder_id}", 'info')
                    # 如果指定了源路径，需要先找到对应的目录ID
                    elif source_path and source_path != '/':
                        add_log(f"[{idx}/{len(share_urls)}] 定位源目录: {source_path}", 'info')
                        # 简单实现：只支持一级目录
                        source_dir_name = source_path.strip('/').split('/')[-1]
                        root_response = quark.get_share_detail(pwd_id, stoken, '0')
                        if root_response.get('code') == 0:
                            for f in root_response['data']['list']:
                                if f.get('dir') and f['file_name'] == source_dir_name:
                                    pdir_fid = f['fid']
                                    add_log(f"[{idx}/{len(share_urls)}] 找到源目录", 'info')
                                    break
                            
                            if pdir_fid == '0':
                                add_log(f"[{idx}/{len(share_urls)}] 未找到源目录，使用根目录", 'warning')
                    else:
                        add_log(f"[{idx}/{len(share_urls)}] 使用根目录", 'info')
                    
                    # 获取分享文件列表（递归获取，保留目录结构）
                    add_log(f"[{idx}/{len(share_urls)}] 获取文件列表...", 'info')
                    
                    # 递归获取所有文件和文件夹的函数（保留层级关系）
                    def get_all_items_recursive(pwd_id, stoken, parent_fid, parent_path="", depth=0, max_depth=10):
                        """递归获取文件夹中的所有文件和文件夹，保留层级关系"""
                        if depth > max_depth:
                            add_log(f"[{idx}/{len(share_urls)}] 达到最大递归深度 {max_depth}，停止递归", 'warning')
                            return [], []
                        
                        detail_response = quark.get_share_detail(pwd_id, stoken, parent_fid)
                        
                        if detail_response.get('code') != 0:
                            add_log(f"[{idx}/{len(share_urls)}] 获取文件列表失败: {detail_response.get('message', '未知错误')}", 'error')
                            return [], []
                        
                        items = detail_response['data']['list']
                        all_files = []
                        all_folders = []
                        
                        for item in items:
                            item_path = f"{parent_path}/{item.get('file_name', '')}" if parent_path else item.get('file_name', '')
                            
                            if item.get('dir'):
                                # 这是一个文件夹
                                folder_info = {
                                    'item': item,
                                    'path': item_path,
                                    'parent_fid': parent_fid
                                }
                                all_folders.append(folder_info)
                                
                                folder_name = item.get('file_name', '未知文件夹')
                                folder_fid = item.get('fid')
                                add_log(f"[{idx}/{len(share_urls)}] 正在扫描文件夹: {item_path}", 'info')
                                
                                # 递归获取子文件夹
                                sub_files, sub_folders = get_all_items_recursive(pwd_id, stoken, folder_fid, item_path, depth + 1, max_depth)
                                all_files.extend(sub_files)
                                all_folders.extend(sub_folders)
                            else:
                                # 这是一个文件
                                file_info = {
                                    'item': item,
                                    'path': item_path,
                                    'parent_fid': parent_fid,
                                    'parent_path': parent_path
                                }
                                all_files.append(file_info)
                        
                        return all_files, all_folders
                    
                    # 递归获取所有文件和文件夹
                    all_files, all_folders = get_all_items_recursive(pwd_id, stoken, pdir_fid)
                    
                    if not all_files:
                        add_log(f"[{idx}/{len(share_urls)}] 未找到文件", 'warning')
                        continue
                    
                    add_log(f"[{idx}/{len(share_urls)}] 递归扫描完成，共找到 {len(all_files)} 个文件，{len(all_folders)} 个文件夹", 'info')
                    
                    # 应用过滤规则
                    filtered_files = all_files
                    
                    # 1. 按文件扩展名过滤（排除）
                    if task.get('filter_extensions'):
                        exts = [e.strip() for e in task['filter_extensions'].split(',')]
                        # 确保扩展名以点开头
                        exts = [ext if ext.startswith('.') else f'.{ext}' for ext in exts]
                        filtered_files = [f for f in filtered_files if not any(f['item']['file_name'].endswith(ext) for ext in exts)]
                        add_log(f"[{idx}/{len(share_urls)}] 排除扩展名 {', '.join(exts)} 后剩余 {len(filtered_files)} 个文件", 'info')
                    
                    # 2. 按文件扩展名筛选（仅包含）
                    if task.get('include_extensions'):
                        exts = [e.strip() for e in task['include_extensions'].split(',')]
                        # 确保扩展名以点开头
                        exts = [ext if ext.startswith('.') else f'.{ext}' for ext in exts]
                        filtered_files = [f for f in filtered_files if any(f['item']['file_name'].endswith(ext) for ext in exts)]
                        add_log(f"[{idx}/{len(share_urls)}] 仅保留扩展名 {', '.join(exts)} 后剩余 {len(filtered_files)} 个文件", 'info')
                    
                    # 3. 按文件创建日期过滤
                    if task.get('file_start_date'):
                        try:
                            from datetime import datetime as dt
                            start_date = dt.strptime(task['file_start_date'], '%Y-%m-%d')
                            start_timestamp = int(start_date.timestamp())
                            
                            original_count = len(filtered_files)
                            filtered_files = [
                                f for f in filtered_files 
                                if f['item'].get('created_at', 0) > start_timestamp
                            ]
                            add_log(f"[{idx}/{len(share_urls)}] 按起始日期过滤：{original_count} -> {len(filtered_files)} 个文件", 'info')
                        except Exception as e:
                            add_log(f"[{idx}/{len(share_urls)}] 日期过滤失败: {str(e)}", 'warning')
                    
                    # 4. 按目录名称过滤
                    if task.get('update_dirs'):
                        dir_filters = [d.strip() for d in task['update_dirs'].split('|') if d.strip()]
                        if dir_filters:
                            original_count = len(filtered_files)
                            # 只保留文件名包含指定目录关键词的文件
                            filtered_files = [
                                f for f in filtered_files 
                                if any(dir_filter in f['item'].get('file_name', '') for dir_filter in dir_filters)
                            ]
                            add_log(f"[{idx}/{len(share_urls)}] 按目录过滤 ({', '.join(dir_filters)})：{original_count} -> {len(filtered_files)} 个文件", 'info')
                    
                    if not filtered_files:
                        add_log(f"[{idx}/{len(share_urls)}] 过滤后无文件需要转存", 'warning')
                        continue
                    
                    # 按父文件夹分组，保留目录结构
                    add_log(f"[{idx}/{len(share_urls)}] 分析目录结构...", 'info')
                    folders_with_files = {}  # {parent_fid: [file_info, ...]}
                    
                    for file_info in filtered_files:
                        parent_fid = file_info['parent_fid']
                        if parent_fid not in folders_with_files:
                            folders_with_files[parent_fid] = []
                        folders_with_files[parent_fid].append(file_info)
                    
                    add_log(f"[{idx}/{len(share_urls)}] 需要转存 {len(folders_with_files)} 个文件夹中的文件", 'info')
                    
                    # 获取目标文件夹ID
                    add_log(f"[{idx}/{len(share_urls)}] 查找目标文件夹...", 'info')
                    
                    # 获取目标文件夹ID（优先使用保存的ID）
                    target_fid = task.get('target_folder_id')  # 新增：优先使用保存的文件夹ID
                    final_target_path = task['target_path']
                    
                    # 处理保存模式
                    if task.get('save_mode') == 'subfolder' and task.get('target_folder_name'):
                        # 子文件夹模式：目标路径 + 自定义文件夹名
                        # 去除子文件夹名的前导和尾随斜杠，避免路径拼接错误
                        subfolder_name = task['target_folder_name'].strip('/')
                        final_target_path = f"{task['target_path'].rstrip('/')}/{subfolder_name}"
                        # 规范化路径：将多个连续斜杠替换为单个斜杠
                        import re
                        final_target_path = re.sub(r'/+', '/', final_target_path)
                        add_log(f"[{idx}/{len(share_urls)}] 使用子文件夹模式: {final_target_path}", 'info')
                    else:
                        add_log(f"[{idx}/{len(share_urls)}] 使用当前文件夹模式: {final_target_path}", 'info')
                    
                    # 如果没有保存的folder_id，则通过路径获取或创建
                    if not target_fid:
                        target_fid = "0"  # 默认根目录
                        
                        if final_target_path and final_target_path != '/':
                            # 使用get_fids_by_paths获取目标文件夹ID
                            add_log(f"[{idx}/{len(share_urls)}] 正在查询路径: {final_target_path}", 'info')
                            fid_infos = quark.get_fids_by_paths([final_target_path])
                            
                            # 记录查询结果用于调试
                            logger.info(f"查询路径结果: {fid_infos}")
                            
                            if fid_infos and len(fid_infos) > 0:
                                fid_info = fid_infos[0]
                                # 检查返回的数据结构
                                if isinstance(fid_info, dict) and 'fid' in fid_info:
                                    target_fid = fid_info['fid']
                                    add_log(f"[{idx}/{len(share_urls)}] 找到目标文件夹 FID: {target_fid}", 'info')
                                else:
                                    add_log(f"[{idx}/{len(share_urls)}] 路径查询返回数据格式异常: {fid_info}", 'warning')
                                    # 尝试逐级创建目录
                                    add_log(f"[{idx}/{len(share_urls)}] 尝试创建目录...", 'info')
                                    target_fid = create_path_recursive(quark, final_target_path, add_log, idx, len(share_urls))
                                    if target_fid:
                                        add_log(f"[{idx}/{len(share_urls)}] 创建目录成功，FID: {target_fid}", 'success')
                                    else:
                                        add_log(f"[{idx}/{len(share_urls)}] 创建目录失败，使用根目录", 'warning')
                            else:
                                # 目标路径不存在，尝试逐级创建
                                add_log(f"[{idx}/{len(share_urls)}] 目标路径不存在，尝试创建...", 'info')
                                target_fid = create_path_recursive(quark, final_target_path, add_log, idx, len(share_urls))
                                if target_fid:
                                    add_log(f"[{idx}/{len(share_urls)}] 创建目录成功，FID: {target_fid}", 'success')
                                else:
                                    add_log(f"[{idx}/{len(share_urls)}] 创建目录失败，使用根目录", 'warning')
                        else:
                            add_log(f"[{idx}/{len(share_urls)}] 使用根目录", 'info')
                    
                    # 按文件夹分组转存，保留目录结构
                    add_log(f"[{idx}/{len(share_urls)}] 开始转存 {len(filtered_files)} 个文件（保留目录结构）...", 'info')
                    
                    # 为每个文件夹创建对应的目标子文件夹
                    folder_mapping = {}  # {parent_path: target_fid}
                    folder_mapping[''] = target_fid  # 根目录映射
                    
                    # 按文件夹分组
                    files_by_folder = {}  # {parent_path: [file_info, ...]}
                    for file_info in filtered_files:
                        parent_path = file_info['parent_path']
                        if parent_path not in files_by_folder:
                            files_by_folder[parent_path] = []
                        files_by_folder[parent_path].append(file_info)
                    
                    # 为每个文件夹创建目标子文件夹
                    for parent_path in sorted(files_by_folder.keys()):
                        if parent_path == '':
                            # 根目录文件，直接使用目标根目录
                            continue
                        
                        # 逐级创建文件夹
                        path_parts = parent_path.split('/')
                        current_path = final_target_path.rstrip('/')
                        current_fid = target_fid
                        
                        for part in path_parts:
                            if not part:
                                continue
                            
                            current_path = f"{current_path}/{part}"
                            
                            # 尝试获取文件夹
                            fid_infos = quark.get_fids_by_paths([current_path])
                            if fid_infos and len(fid_infos) > 0 and isinstance(fid_infos[0], dict) and 'fid' in fid_infos[0]:
                                current_fid = fid_infos[0]['fid']
                            else:
                                # 创建文件夹(使用文件夹名称,不是完整路径)
                                mkdir_result = quark.mkdir(part, current_fid)
                                if mkdir_result.get('code') == 0:
                                    current_fid = mkdir_result['data']['fid']
                                    add_log(f"[{idx}/{len(share_urls)}] 创建文件夹成功: {part}", 'success')
                                else:
                                    add_log(f"[{idx}/{len(share_urls)}] 创建文件夹失败: {part}, 错误: {mkdir_result.get('message', '未知错误')}", 'warning')
                                    # 创建失败,使用父目录
                                    break
                        
                        folder_mapping[parent_path] = current_fid
                    
                    # 按文件夹分别转存文件
                    total_transferred = 0
                    for parent_path, files_in_folder in files_by_folder.items():
                        folder_target_fid = folder_mapping.get(parent_path, target_fid)
                        folder_display = parent_path if parent_path else '根目录'
                        
                        add_log(f"[{idx}/{len(share_urls)}] 转存文件夹 [{folder_display}] 中的 {len(files_in_folder)} 个文件", 'info')
                        
                        # 处理重存/增量模式
                        files_to_transfer = files_in_folder
                        
                        if task.get('overwrite_mode') == 1:
                            # 重存模式：删除目标目录中已存在的同名文件
                            try:
                                target_files_response = quark.get_file_list(folder_id=folder_target_fid, page=1, size=500)
                                if target_files_response.get('code') == 0:
                                    target_files = target_files_response['data']['list']
                                    target_file_names = {f['file_name'] for f in target_files}
                                    
                                    files_to_delete = [
                                        f for f in target_files 
                                        if f['file_name'] in {tf['item']['file_name'] for tf in files_in_folder}
                                    ]
                                    
                                    if files_to_delete:
                                        delete_fids = [f['fid'] for f in files_to_delete]
                                        add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 删除 {len(files_to_delete)} 个已存在文件", 'info')
                                        delete_result = quark.delete(delete_fids)
                                        if delete_result.get('status') != 200:
                                            add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 删除失败: {delete_result.get('message', '未知错误')}", 'warning')
                            except Exception as e:
                                add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 检查已存在文件失败: {str(e)}", 'warning')
                        else:
                            # 增量模式：只转存新文件
                            try:
                                target_files_response = quark.get_file_list(folder_id=folder_target_fid, page=1, size=500)
                                if target_files_response.get('code') == 0:
                                    target_files = target_files_response['data']['list']
                                    target_file_names = {f['file_name'] for f in target_files}
                                    
                                    original_count = len(files_to_transfer)
                                    
                                    # 根据check_mode决定使用哪个文件名进行检查
                                    check_mode = task.get('check_mode', 'replaced')
                                    regex_pattern = task.get('regex_pattern')
                                    
                                    if check_mode == 'replaced' and regex_pattern:
                                        # 使用替换后的文件名检查
                                        from utils.filename_replacer import FilenameReplacer
                                        replacer = FilenameReplacer()
                                        
                                        filtered_files = []
                                        for f in files_to_transfer:
                                            original_name = f['item']['file_name']
                                            # 应用正则替换 (返回: success, new_filename, message)
                                            matched, new_name, _ = replacer.apply_regex_replacement(
                                                original_name,
                                                regex_pattern,
                                                task.get('replacement_pattern', '')
                                            )
                                            # 使用替换后的文件名检查是否存在
                                            check_name = new_name if matched else original_name
                                            if check_name not in target_file_names:
                                                filtered_files.append(f)
                                        
                                        files_to_transfer = filtered_files
                                        add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 使用替换后文件名检查重复", 'info')
                                    else:
                                        # 使用原文件名检查
                                        files_to_transfer = [
                                            f for f in files_to_transfer 
                                            if f['item']['file_name'] not in target_file_names
                                        ]
                                    
                                    if original_count > len(files_to_transfer):
                                        add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 跳过 {original_count - len(files_to_transfer)} 个已存在文件", 'info')
                                    
                                    if not files_to_transfer:
                                        add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 所有文件已存在，跳过", 'info')
                                        continue
                            except Exception as e:
                                add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 检查已存在文件失败: {str(e)}，将转存所有文件", 'warning')
                        
                        if not files_to_transfer:
                            continue
                        
                        # 准备文件ID和token列表
                        fid_list = [f['item']['fid'] for f in files_to_transfer]
                        fid_token_list = [f['item']['share_fid_token'] for f in files_to_transfer]
                        
                        add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 实际转存 {len(files_to_transfer)} 个文件", 'info')
                        
                        # 批量转存文件到对应的目标文件夹
                        save_response = quark.save_share_file(
                            fid_list,
                            fid_token_list,
                            folder_target_fid,
                            pwd_id,
                            stoken
                        )
                        
                        add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 转存响应状态: {save_response.get('status', save_response.get('code'))}", 'info')
                        
                        if save_response.get('code') == 0:
                            task_id = save_response['data']['task_id']
                            add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 转存任务ID: {task_id}", 'info')
                            
                            # 等待转存完成
                            add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 等待转存完成...", 'info')
                            task_result = quark.query_task(task_id)
                            
                            # 检查任务状态 (status在data里面)
                            task_status = task_result.get('data', {}).get('status')
                            if task_status == 2:
                                add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 转存成功", 'success')
                                total_transferred += len(files_to_transfer)
                                
                                # 应用正则替换重命名文件
                                if task.get('regex_pattern'):
                                    add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 开始应用正则替换...", 'info')
                                    try:
                                        from utils.filename_replacer import FilenameReplacer
                                        replacer = FilenameReplacer()
                                        
                                        # 获取目标文件夹中的文件列表
                                        target_files_response = quark.get_file_list(folder_id=folder_target_fid, page=1, size=500)
                                        if target_files_response.get('code') == 0:
                                            target_files = target_files_response['data']['list']
                                            
                                            # 只处理刚转存的文件
                                            transferred_filenames = {f['item']['file_name'] for f in files_to_transfer}
                                            files_to_rename = [f for f in target_files if f['file_name'] in transferred_filenames]
                                            
                                            renamed_count = 0
                                            for file_obj in files_to_rename:
                                                original_name = file_obj['file_name']
                                                
                                                # 应用正则替换 (返回: success, new_filename, message)
                                                matched, new_name, _ = replacer.apply_regex_replacement(
                                                    original_name,
                                                    task['regex_pattern'],
                                                    task.get('replacement_pattern', '')
                                                )
                                                
                                                if matched and new_name != original_name:
                                                    # 检查目标文件名是否已存在
                                                    if any(f['file_name'] == new_name for f in target_files if f['fid'] != file_obj['fid']):
                                                        # 生成唯一文件名
                                                        new_name = replacer.generate_unique_filename(
                                                            new_name,
                                                            [f['file_name'] for f in target_files if f['fid'] != file_obj['fid']]
                                                        )
                                                        add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 文件名冲突，使用唯一名称: {new_name}", 'warning')
                                                    
                                                    # 执行重命名
                                                    rename_result = quark.rename(file_obj['fid'], new_name)
                                                    if rename_result.get('status') == 200:
                                                        add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 重命名: {original_name} -> {new_name}", 'success')
                                                        renamed_count += 1
                                                    else:
                                                        add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 重命名失败: {original_name}, 错误: {rename_result.get('message', '未知错误')}", 'error')
                                                elif matched:
                                                    add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 文件名未改变: {original_name}", 'info')
                                            
                                            if renamed_count > 0:
                                                add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 成功重命名 {renamed_count} 个文件", 'success')
                                        else:
                                            add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 获取文件列表失败，跳过重命名", 'warning')
                                    except Exception as rename_error:
                                        logger.error(f"应用正则替换失败: {rename_error}", exc_info=True)
                                        add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 正则替换失败: {str(rename_error)}", 'error')
                                
                                # ========== 新增：排除关键词过滤（夸克网盘） ==========
                                exclude_keywords = task.get('exclude_keywords')
                                if exclude_keywords:
                                    try:
                                        # 解析排除关键词
                                        exclude_keyword_list = [kw.strip() for kw in exclude_keywords.split('|') if kw.strip()]
                                        if exclude_keyword_list:
                                            add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 开始清理包含排除关键词的文件...", 'info')
                                            add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 排除关键词: {', '.join(exclude_keyword_list)}", 'info')
                                            
                                            # 获取目标文件夹的文件列表
                                            files_list = quark.list_files(folder_target_fid)
                                            
                                            if files_list:
                                                files_to_delete = []
                                                for file_item in files_list:
                                                    file_name = file_item.get('file_name', '')
                                                    # 检查文件名是否包含排除关键词
                                                    for keyword in exclude_keyword_list:
                                                        if keyword in file_name:
                                                            files_to_delete.append(file_item)
                                                            add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 发现需要删除的文件: {file_name} (包含关键词'{keyword}')", 'info')
                                                            break
                                                
                                                # 批量删除文件
                                                if files_to_delete:
                                                    deleted_count = 0
                                                    delete_fids = [f.get('fid') for f in files_to_delete]
                                                    delete_result = quark.delete(delete_fids)
                                                    
                                                    if delete_result.get('status') == 200:
                                                        deleted_count = len(files_to_delete)
                                                        for f in files_to_delete:
                                                            add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 已删除: {f.get('file_name', '')}", 'info')
                                                        add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 清理完成，共删除 {deleted_count} 个文件", 'success')
                                                        # 更新实际文件数（减去被删除的文件）
                                                        total_transferred -= deleted_count
                                                    else:
                                                        add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 批量删除失败: {delete_result.get('message', '未知错误')}", 'warning')
                                                else:
                                                    add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 未发现需要清理的文件", 'info')
                                            else:
                                                add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 无法获取文件列表，跳过清理", 'warning')
                                    except Exception as filter_e:
                                        logger.error(f"排除关键词过滤失败: {filter_e}", exc_info=True)
                                        add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 排除关键词过滤失败: {str(filter_e)}", 'warning')
                                # ========== 排除关键词过滤结束 ==========
                            else:
                                error_msg = task_result.get('data', {}).get('message') or task_result.get('message', '未知错误')
                                add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 转存失败: {error_msg}", 'error')
                                fail_count += 1
                        else:
                            add_log(f"[{idx}/{len(share_urls)}] [{folder_display}] 转存失败: {save_response.get('message', '未知错误')}", 'error')
                            fail_count += 1
                    
                    if total_transferred > 0:
                        add_log(f"[{idx}/{len(share_urls)}] 共转存 {total_transferred} 个文件", 'success')
                        success_count += 1
                    else:
                        add_log(f"[{idx}/{len(share_urls)}] 未转存任何文件", 'warning')
                
                except Exception as e:
                    logger.error(f"处理分享链接失败: {e}")
                    add_log(f"[{idx}/{len(share_urls)}] 处理失败: {str(e)}", 'error')
                    fail_count += 1
            
            # 更新任务最后执行时间
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE transfer_tasks 
                    SET last_execute_time = ?, updated_at = ?
                    WHERE id = ?
                """, (datetime.now(), datetime.now(), task_id))
                conn.commit()
            
            # 记录执行日志到数据库
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO log_records (
                        task_type, task_id, task_name, log_level,
                        log_content, file_count, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    'transfer',
                    task_id,
                    task['name'],
                    'success' if fail_count == 0 else 'warning' if success_count > 0 else 'error',
                    f"成功: {success_count}, 失败: {fail_count}, 文件数: {total_files}",
                    total_files,
                    datetime.now()
                ))
                conn.commit()
            
            # 更新执行历史记录
            if execution_id:
                with get_db() as conn:
                    cursor = conn.cursor()
                    logs_json = json.dumps(logs, ensure_ascii=False)
                    cursor.execute("""
                        UPDATE task_execution_history 
                        SET status = ?, end_time = ?, logs = ?,
                            success_count = ?, failed_count = ?
                        WHERE id = ?
                    """, ('success', datetime.now(), logs_json, success_count, fail_count, execution_id))
                    conn.commit()
                
                # 如果有新内容转存成功，更新last_content_update_time
                if success_count > 0:
                    try:
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        with get_db() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE transfer_tasks 
                                SET last_content_update_time = ?, updated_at = ?
                                WHERE id = ?
                            """, (current_time, current_time, task_id))
                            conn.commit()
                        logger.info(f"[AutoExpiration] 转存任务有新内容，已重置计时器: task_id={task_id}, last_content_update_time={current_time}")
                    except Exception as e:
                        logger.error(f"[AutoExpiration] 更新last_content_update_time失败: {e}")
                
                # 执行关联的插件
                try:
                    from services.plugin_executor import PluginExecutor
                    
                    # 从执行历史中获取真实的开始时间和结束时间
                    with get_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT start_time, end_time, duration
                            FROM task_execution_history
                            WHERE id = ?
                        """, (execution_id,))
                        history_row = cursor.fetchone()
                    
                    if history_row:
                        start_time_str = history_row[0]
                        end_time_str = history_row[1]
                        duration = history_row[2] or 0
                    else:
                        start_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        end_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        duration = 0
                    
                    # 构建来源路径（分享链接列表）
                    share_urls_list = task.get('share_urls', [])
                    if share_urls_list:
                        # 提取所有分享链接
                        source_urls = []
                        for url_obj in share_urls_list:
                            if isinstance(url_obj, dict):
                                source_urls.append(url_obj.get('url', ''))
                            else:
                                source_urls.append(url_obj)
                        source_path = '\n'.join(source_urls[:3])  # 最多显示3个链接
                        if len(source_urls) > 3:
                            source_path += f'\n... 等共 {len(source_urls)} 个链接'
                    else:
                        source_path = '无'
                    
                    # 构建目标路径（包含子目录）
                    target_path = task.get('target_path', '')
                    if task.get('save_mode') == 'subfolder' and task.get('target_folder_name'):
                        target_path = f"{target_path.rstrip('/')}/{task.get('target_folder_name')}"
                    
                    # 构建任务上下文
                    task_context = {
                        'task_id': task_id,
                        'task_name': task.get('name', ''),
                        'task_type': 'transfer',
                        'status': 'success' if fail_count == 0 else 'partial',
                        'start_time': start_time_str,
                        'end_time': end_time_str,
                        'duration': duration,
                        'total_count': total_files,
                        'success_count': success_count,
                        'failed_count': fail_count,
                        'total_size': 0,  # 转存任务暂不统计大小
                        'source_path': source_path,
                        'target_path': target_path,
                    }
                    
                    add_log('开始执行关联插件...', 'info')
                    plugin_result = PluginExecutor.execute_plugins(
                        task_id=task_id,
                        task_type='transfer',
                        execution_id=execution_id,
                        task_context=task_context
                    )
                    
                    if plugin_result['total'] > 0:
                        add_log(
                            f"插件执行完成: 总计 {plugin_result['total']} 个，"
                            f"成功 {plugin_result['success']} 个，"
                            f"失败 {plugin_result['failed']} 个，"
                            f"跳过 {plugin_result['skipped']} 个", 
                            'info')
                        
                        # 更新日志到数据库
                        with get_db() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE task_execution_history 
                                SET logs = ?
                                WHERE id = ?
                            """, (json.dumps(logs, ensure_ascii=False), execution_id))
                            conn.commit()
                    else:
                        add_log('没有关联的插件需要执行', 'info')
                        
                except Exception as plugin_error:
                    add_log(f"插件执行异常: {str(plugin_error)}", 'warning')
                    logger.error(f"执行插件异常: {plugin_error}", exc_info=True)
                    
                    # 更新日志到数据库
                    with get_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE task_execution_history 
                            SET logs = ?
                            WHERE id = ?
                        """, (json.dumps(logs, ensure_ascii=False), execution_id))
                        conn.commit()
            
            add_log(f"任务执行完成！成功: {success_count}, 失败: {fail_count}, 文件数: {total_files}", 'success')
            
            return jsonify({
                'code': 200,
                'message': '任务执行完成',
                'data': {
                    'logs': logs,
                    'success_count': success_count,
                    'fail_count': fail_count,
                    'total_files': total_files
                }
            })
            
        except Exception as e:
            add_log(f"执行异常: {str(e)}", 'error')
            logger.error(f"执行任务异常: {e}", exc_info=True)
            
            # 更新执行历史记录为失败
            if execution_id:
                with get_db() as conn:
                    cursor = conn.cursor()
                    logs_json = json.dumps(logs, ensure_ascii=False)
                    cursor.execute("""
                        UPDATE task_execution_history 
                        SET status = ?, end_time = ?, logs = ?, error_message = ?
                        WHERE id = ?
                    """, ('failed', datetime.now(), logs_json, str(e), execution_id))
                    conn.commit()
            
            return jsonify({
                'code': 500,
                'message': f'执行失败: {str(e)}',
                'data': {'logs': logs}
            })
        
    except Exception as e:
        logger.error(f"执行任务失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'执行任务失败: {str(e)}'
        }), 500


@transfer_bp.route('/task/<int:task_id>/check-shares', methods=['POST'])
def check_share_status(task_id):
    """检查任务的分享链接状态"""
    try:
        # 验证任务是否存在
        task = TransferService.get_task_by_id(task_id)
        if not task:
            return jsonify({
                'code': 404,
                'message': '任务不存在'
            }), 404
        
        # 获取目标账号
        from models.account import Account
        account = Account.get_by_id(task['target_account_id'])
        if not account:
            return jsonify({
                'code': 400,
                'message': '目标账号不存在'
            })
        
        # 获取云盘类型
        cloud_type = account.get('cloud_type', 'quark')
        
        # 根据云盘类型初始化服务
        if cloud_type == 'cloud189':
            from services.cloud189_service import Cloud189Service
            # 传入 username 和 password 以支持 Cookie 自动更新
            cloud_service = Cloud189Service(
                cookie=account['cookie'],
                username=account.get('username'),
                password=account.get('password')
            )
        else:
            from services.quark_service import QuarkService
            cloud_service = QuarkService(account['cookie'])
        
        # 检查每个分享链接
        share_urls = task['share_urls']
        updated_urls = []
        
        for url_obj in share_urls:
            url = url_obj['url'] if isinstance(url_obj, dict) else url_obj
            
            try:
                if cloud_type == 'cloud189':
                    # 天翼云盘链接检查
                    share_code, access_code = Cloud189Service.parse_share_url(url)
                    
                    if not share_code:
                        status = '链接格式错误'
                    else:
                        # 获取分享信息
                        share_info = cloud_service.get_share_info(share_code)
                        logger.info(f"天翼云盘分享信息: {share_info}")
                        
                        if share_info.get('res_code') == 0:
                            # 尝试直接列出分享内容来判断是否真的需要访问码
                            share_id = share_info.get('shareId')
                            file_id = share_info.get('fileId')
                            share_mode = share_info.get('shareMode')
                            
                            logger.info(f"提取的字段: share_id={share_id}, file_id={file_id}, share_mode={share_mode}")
                            
                            if share_id and file_id and share_mode:
                                # 尝试不带访问码访问
                                list_result = cloud_service.list_share_dir(
                                    share_id=share_id,
                                    file_id=file_id,
                                    share_mode=share_mode,
                                    access_code='',
                                    share_code=share_code,
                                    root_file_id=file_id
                                )
                                
                                if list_result.get('res_code') == 0:
                                    # 可以直接访问,不需要访问码
                                    status = '正常'
                                elif list_result.get('res_code') == 4031:
                                    # 需要访问码
                                    if access_code:
                                        # 尝试带访问码访问
                                        list_result2 = cloud_service.list_share_dir(
                                            share_id=share_id,
                                            file_id=file_id,
                                            share_mode=share_mode,
                                            access_code=access_code,
                                            share_code=share_code,
                                            root_file_id=file_id
                                        )
                                        if list_result2.get('res_code') == 0:
                                            status = '正常'
                                        else:
                                            status = '访问码错误'
                                    else:
                                        status = '需要访问码'
                                else:
                                    status = f"异常({list_result.get('res_code')})"
                            else:
                                # 缺少必要信息
                                status = '分享信息不完整'
                        elif share_info.get('res_code') == 4031:
                            status = '分享已失效'
                        elif share_info.get('res_code') == 4032:
                            status = '分享违规'
                        else:
                            status = f"异常({share_info.get('res_code')})"
                else:
                    # 夸克云盘链接检查 - 使用统一的check_share_link方法
                    check_result = cloud_service.check_share_link(url)
                    logger.info(f"夸克链接检查结果: {check_result}")
                    status = check_result.get('status', '检查失败')
                    logger.info(f"提取的status字段: {status}")
                
            except Exception as e:
                status = f'检查失败: {str(e)}'
            
            # 更新状态
            if isinstance(url_obj, dict):
                url_obj['status'] = status
                url_obj['last_check_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                updated_urls.append(url_obj)
            else:
                updated_urls.append({
                    'url': url,
                    'source_path': '/',
                    'is_primary': False,
                    'status': status,
                    'last_check_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
        
        # 更新任务
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE transfer_tasks 
                SET share_urls = ?, updated_at = ?
                WHERE id = ?
            """, (json.dumps(updated_urls), datetime.now(), task_id))
            conn.commit()
        
        logger.info(f"链接检查完成,返回数据: {updated_urls}")
        
        return jsonify({
            'code': 200,
            'message': '检查完成',
            'data': updated_urls
        })
        
    except Exception as e:
        logger.error(f"检查分享链接状态失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'检查失败: {str(e)}'
        }), 500


@transfer_bp.route('/parse-share', methods=['POST'])
def parse_share():
    """解析分享链接"""
    try:
        data = request.get_json()
        share_url = data.get('url')
        
        if not share_url:
            return jsonify({
                'code': 400,
                'message': '分享链接不能为空'
            }), 400
        
        # TODO: 解析分享链接，获取标题、文件数量等信息
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'title': '示例标题',
                'file_count': 10,
                'total_size': 1024000000,
                'suggested_path': '/示例路径'
            }
        })
    except Exception as e:
        logger.error(f"解析分享链接失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'解析失败: {str(e)}'
        }), 500


@transfer_bp.route('/browse-share', methods=['POST'])
def browse_share():
    """浏览分享文件"""
    try:
        data = request.get_json()
        share_url = data.get('url')
        pdir_fid = data.get('pdir_fid', '0')  # 父目录ID，默认根目录
        account_id = data.get('account_id')
        
        logger.info(f"浏览分享文件请求: url={share_url}, pdir_fid={pdir_fid}, account_id={account_id}")
        
        if not share_url:
            return jsonify({
                'code': 400,
                'message': '分享链接不能为空'
            }), 400
        
        if not account_id:
            return jsonify({
                'code': 400,
                'message': '请选择账号'
            }), 400
        
        # 获取账号
        from models.account import Account
        account = Account.get_by_id(account_id)
        if not account:
            return jsonify({
                'code': 404,
                'message': '账号不存在'
            }), 404
        
        # 根据云盘类型选择服务
        cloud_type = account.get('cloud_type', 'quark')
        logger.info(f"账号云盘类型: {cloud_type}")
        
        if cloud_type == 'cloud189':
            # 天翼云盘
            from services.cloud189_service import Cloud189Service
            # 传入 username 和 password 以支持 Cookie 自动更新
            cloud_service = Cloud189Service(
                cookie=account['cookie'],
                username=account.get('username'),
                password=account.get('password')
            )
            
            # 解析分享链接
            share_code, access_code = Cloud189Service.parse_share_url(share_url)
            logger.info(f"解析结果: share_code={share_code}, access_code={access_code}")
            
            if not share_code:
                return jsonify({
                    'code': 400,
                    'message': '无效的分享链接'
                }), 400
            
            # 获取分享信息
            logger.info(f"获取分享信息: share_code={share_code}")
            share_info = cloud_service.get_share_info(share_code)
            logger.info(f"分享信息响应: {share_info}")
            
            if share_info.get('res_code') != 0:
                return jsonify({
                    'code': 400,
                    'message': f"获取分享信息失败: {share_info.get('res_message', '未知错误')}"
                }), 400
            
            share_id = share_info.get('shareId')
            share_mode = share_info.get('shareMode')
            root_file_id = share_info.get('fileId')  # 分享根目录的fileId
            is_folder = share_info.get('isFolder', True)
            logger.info(f"分享ID: {share_id}, 分享模式: {share_mode}, 根文件ID: {root_file_id}, 是否文件夹: {is_folder}")
            
            # 验证访问码（如果需要）
            if access_code:
                logger.info(f"验证访问码: {access_code}")
                check_result = cloud_service.check_access_code(share_code, access_code)
                logger.info(f"访问码验证结果: {check_result}")
                if check_result.get('res_code') != 0:
                    return jsonify({
                        'code': 400,
                        'message': '访问码错误'
                    }), 400
                
                # 关键修复：如果get_share_info没有返回shareId，从check_access_code结果中获取
                if not share_id and check_result.get('shareId'):
                    share_id = check_result.get('shareId')
                    logger.info(f"从访问码验证结果中获取到shareId: {share_id}")
            
            # 验证必需参数
            if not share_id:
                return jsonify({
                    'code': 400,
                    'message': '无法获取分享ID，请检查分享链接是否有效'
                }), 400
            
            # 获取分享文件列表
            # 如果pdir_fid是0或空，使用分享根目录的fileId
            file_id = pdir_fid if pdir_fid != '0' and pdir_fid else ''
            logger.info(f"获取分享文件列表: share_id={share_id}, file_id={file_id}, share_mode={share_mode}, root_file_id={root_file_id}")
            
            file_list_result = cloud_service.list_share_dir(
                share_id, file_id, share_mode, access_code, 
                is_folder=is_folder, share_code=share_code, root_file_id=str(root_file_id)
            )
            
            logger.info(f"分享文件列表响应: {file_list_result}")
            
            if file_list_result.get('res_code') != 0:
                return jsonify({
                    'code': 400,
                    'message': f"获取文件列表失败: {file_list_result.get('res_message', '未知错误')}"
                }), 400
            
            # 解析文件列表
            file_list_ao = file_list_result.get('fileListAO', {})
            folder_list = file_list_ao.get('folderList', [])
            file_list = file_list_ao.get('fileList', [])
            
            # 格式化文件列表
            formatted_files = []
            
            # 先添加文件夹
            for folder in folder_list:
                formatted_files.append({
                    'fid': str(folder.get('id')),
                    'file_name': folder.get('name'),
                    'size': 0,
                    'file_type': 0,
                    'dir': True,
                    'updated_at': folder.get('lastOpTime', ''),
                    'share_fid_token': ''
                })
            
            # 再添加文件
            for file in file_list:
                formatted_files.append({
                    'fid': str(file.get('id')),
                    'file_name': file.get('name'),
                    'size': file.get('size', 0),
                    'file_type': file.get('mediaType', 0),
                    'dir': False,
                    'updated_at': file.get('lastOpTime', ''),
                    'share_fid_token': ''
                })
            
            # 格式化标准链接：只有当原始链接不是标准格式时才返回
            # 判断原始链接是否需要格式化
            needs_normalization = False
            normalized_url = None
            
            # 检查是否包含括号形式的密码或其他非标准格式
            if access_code:
                # 检查原始URL是否已经是标准格式 ?code=xxx&pwd=xxx
                import re
                if not re.search(r'[?&]pwd=' + re.escape(access_code), share_url):
                    # 原始链接不是标准格式，需要格式化
                    needs_normalization = True
                    normalized_url = f"https://cloud.189.cn/web/share?code={share_code}&pwd={access_code}"
                    logger.info(f"链接需要格式化: {share_url} -> {normalized_url}")
            
            # 构建返回数据
            response_data = {
                'files': formatted_files,
                'share_id': share_id,
                'share_code': share_code,
                'share_name': share_info.get('fileName', '')  # 分享标题
            }
            
            # 只有需要格式化时才返回 normalized_url
            if needs_normalization and normalized_url:
                response_data['normalized_url'] = normalized_url
            
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': response_data
            })
        
        else:
            # 夸克网盘（默认）
            from services.quark_service import QuarkService
            quark = QuarkService(account['cookie'])
            
            # 解析分享链接
            pwd_id, passcode, folder_id = QuarkService.parse_share_url(share_url)
            
            if not pwd_id:
                return jsonify({
                    'code': 400,
                    'message': '无效的分享链接'
                }), 400
            
            # 获取分享令牌
            token_response = quark.get_stoken(pwd_id, passcode)
            
            if token_response.get('code') != 0:
                return jsonify({
                    'code': 400,
                    'message': f"获取令牌失败: {token_response.get('message', '未知错误')}"
                }), 400
            
            stoken = token_response['data']['stoken']
            
            # 获取文件列表
            detail_response = quark.get_share_detail(pwd_id, stoken, pdir_fid)
            
            if detail_response.get('code') != 0:
                return jsonify({
                    'code': 400,
                    'message': f"获取文件列表失败: {detail_response.get('message', '未知错误')}"
                }), 400
            
            files = detail_response['data']['list']
            
            # 格式化文件列表
            file_list = []
            for f in files:
                file_list.append({
                    'fid': f['fid'],
                    'file_name': f['file_name'],
                    'size': f.get('size', 0),
                    'file_type': f.get('file_type', 0),
                    'dir': f.get('dir', False),
                    'updated_at': f.get('updated_at', ''),
                    'share_fid_token': f.get('share_fid_token', '')
                })
            
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {
                    'files': file_list,
                    'pwd_id': pwd_id,
                    'stoken': stoken
                }
            })
        
    except Exception as e:
        logger.error(f"浏览分享文件失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'浏览失败: {str(e)}'
        }), 500

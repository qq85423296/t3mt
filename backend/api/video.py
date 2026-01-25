# -*- coding: utf-8 -*-
"""
影视下载API
"""
from flask import Blueprint, request, jsonify
from services.mango_service import mango_service
from models.video_task import VideoTask
from utils.logger import logger
from utils.feature_gate import check_video_task_limit, check_parse_limit, check_quality_limit

video_bp = Blueprint('video', __name__, url_prefix='/api/video')


@video_bp.route('/read-website', methods=['POST'])
@check_parse_limit()
def read_website():
    """读取官网信息"""
    try:
        from services.video_parse_service import video_parse_service
        
        data = request.get_json()
        url = data.get('url', '').strip()
        platform = data.get('platform', '').strip()  # 可选的平台参数
        
        if not url:
            return jsonify({'code': 400, 'message': '请输入官网地址'})
        
        # 使用video_parse_service统一处理，支持自动识别平台
        result = video_parse_service.read_website(url, platform if platform else None)
        
        if result.get('success'):
            return jsonify({
                'code': 200,
                'message': '读取成功',
                'data': {
                    'video_info': result['video_info'],
                    'episodes': result['episodes'],
                    'total_episodes': result['total_episodes'],
                    'platform': result.get('platform', 'mango'),  # 返回识别的平台
                    'video_type': result.get('video_type', '其他')  # 返回识别的视频类型
                }
            })
        else:
            return jsonify({
                'code': 500,
                'message': result.get('error', '读取失败')
            })
            
    except Exception as e:
        return jsonify({'code': 500, 'message': f'读取失败: {str(e)}'})


@video_bp.route('/task', methods=['POST'])
@check_video_task_limit()
def create_task():
    """创建影视下载任务"""
    try:
        data = request.get_json()
        
        # 验证必填字段
        required_fields = ['name', 'website_url', 'save_directory', 'cron_expression']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'code': 400, 'message': f'缺少必填字段: {field}'})
        
        # 获取平台参数，如果没有则自动识别
        platform = data.get('platform', '')
        if not platform:
            from services.video_parse_service import video_parse_service
            platform = video_parse_service.detect_platform(data['website_url'])
        
        # 验证平台是否支持
        supported_platforms = ['mango', 'tencent', 'iqiyi', 'youku']
        if platform not in supported_platforms:
            return jsonify({
                'code': 400, 
                'message': '目前仅支持腾讯、爱奇艺、优酷、芒果平台'
            })
        
        # 获取文件大小限制配置
        enable_file_size_check = data.get('enable_file_size_check', 0)
        min_file_size = data.get('min_file_size', 100)
        
        # 验证文件大小限制配置
        if enable_file_size_check:
            if not isinstance(min_file_size, int) or min_file_size <= 0:
                return jsonify({'code': 400, 'message': '最小文件大小必须为正整数'})
        
        # 获取失败重试配置
        enable_retry = data.get('enable_retry', 0)
        max_retry_count = data.get('max_retry_count', 3)
        retry_interval = data.get('retry_interval', 5)
        
        # 验证失败重试配置
        if enable_retry:
            if not isinstance(max_retry_count, int) or max_retry_count < 1 or max_retry_count > 10:
                return jsonify({'code': 400, 'message': '最大重试次数必须为1-10之间的整数'})
            
            if not isinstance(retry_interval, int) or retry_interval < 1:
                return jsonify({'code': 400, 'message': '重试间隔必须为不小于1的整数'})
        
        # 创建任务
        task_id = VideoTask.create(
            name=data['name'],
            website_url=data['website_url'],
            video_id=data.get('video_id', ''),
            clip_id=data.get('clip_id', ''),
            save_directory=data['save_directory'],
            cron_expression=data['cron_expression'],
            episodes=data.get('episodes', []),
            video_info=data.get('video_info', {}),
            create_subfolder=data.get('create_subfolder', 0),
            selected_episodes=data.get('selected_episodes', []),
            platform=platform,
            video_type=data.get('video_type', '电视剧'),
            enable_file_size_check=enable_file_size_check,
            min_file_size=min_file_size,
            enable_retry=enable_retry,
            max_retry_count=max_retry_count,
            retry_interval=retry_interval,
            regex_pattern=data.get('regex_pattern'),
            replacement_pattern=data.get('replacement_pattern'),
            exclude_keywords=data.get('exclude_keywords')
        )
        
        return jsonify({
            'code': 200,
            'message': '任务创建成功',
            'data': {'id': task_id}
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': f'创建任务失败: {str(e)}'})


@video_bp.route('/task', methods=['GET'])
def get_task_list():
    """获取任务列表"""
    try:
        tasks = VideoTask.get_all()
        
        task_list = []
        for task in tasks:
            task_dict = task.to_dict()
            task_dict['total_episodes'] = len(task.episodes) if task.episodes else 0
            task_list.append(task_dict)
        
        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': task_list
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': f'获取任务列表失败: {str(e)}'})


@video_bp.route('/task/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """获取任务详情"""
    try:
        task = VideoTask.get_by_id(task_id)
        if not task:
            return jsonify({'code': 404, 'message': '任务不存在'})
        
        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': task.to_dict()
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': f'获取任务详情失败: {str(e)}'})


@video_bp.route('/task/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """更新任务"""
    try:
        task = VideoTask.get_by_id(task_id)
        if not task:
            return jsonify({'code': 404, 'message': '任务不存在'})
        
        data = request.get_json()
        
        # 更新字段
        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name']
        if 'website_url' in data:
            update_data['website_url'] = data['website_url']
        if 'save_directory' in data:
            update_data['save_directory'] = data['save_directory']
        if 'cron_expression' in data:
            update_data['cron_expression'] = data['cron_expression']
        if 'episodes' in data:
            update_data['episodes'] = data['episodes']
        if 'video_info' in data:
            update_data['video_info'] = data['video_info']
        if 'create_subfolder' in data:
            update_data['create_subfolder'] = data['create_subfolder']
        if 'selected_episodes' in data:
            update_data['selected_episodes'] = data['selected_episodes']
        if 'platform' in data:
            update_data['platform'] = data['platform']
        if 'video_type' in data:
            update_data['video_type'] = data['video_type']
        
        # 处理文件大小限制配置
        if 'enable_file_size_check' in data:
            enable_file_size_check = data['enable_file_size_check']
            update_data['enable_file_size_check'] = enable_file_size_check
            
        if 'min_file_size' in data:
            min_file_size = data['min_file_size']
            # 验证最小文件大小
            if not isinstance(min_file_size, int) or min_file_size <= 0:
                return jsonify({'code': 400, 'message': '最小文件大小必须为正整数'})
            update_data['min_file_size'] = min_file_size
        
        # 处理失败重试配置
        if 'enable_retry' in data:
            enable_retry = data['enable_retry']
            update_data['enable_retry'] = enable_retry
            
        if 'max_retry_count' in data:
            max_retry_count = data['max_retry_count']
            # 验证最大重试次数
            if not isinstance(max_retry_count, int) or max_retry_count < 1 or max_retry_count > 10:
                return jsonify({'code': 400, 'message': '最大重试次数必须为1-10之间的整数'})
            update_data['max_retry_count'] = max_retry_count
            
        if 'retry_interval' in data:
            retry_interval = data['retry_interval']
            # 验证重试间隔
            if not isinstance(retry_interval, int) or retry_interval < 1:
                return jsonify({'code': 400, 'message': '重试间隔必须为不小于1的整数'})
            update_data['retry_interval'] = retry_interval
        
        # 处理正则替换配置
        if 'regex_pattern' in data:
            update_data['regex_pattern'] = data['regex_pattern']
        if 'replacement_pattern' in data:
            update_data['replacement_pattern'] = data['replacement_pattern']
        
        # 处理排除关键词配置
        if 'exclude_keywords' in data:
            update_data['exclude_keywords'] = data['exclude_keywords']
        
        VideoTask.update(task_id, **update_data)
        
        return jsonify({
            'code': 200,
            'message': '更新成功'
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': f'更新任务失败: {str(e)}'})


@video_bp.route('/task/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除任务"""
    try:
        from database import db
        from tasks.scheduler import task_scheduler
        
        task = VideoTask.get_by_id(task_id)
        if not task:
            return jsonify({'code': 404, 'message': '任务不存在'})
        
        # 从调度器中移除任务
        try:
            task_scheduler.remove_task(task_id, 'video')
            logger.info(f"从调度器移除影视下载任务: {task_id}")
        except Exception as e:
            logger.warning(f"从调度器移除任务失败: {str(e)}")
        
        # 删除任务记录
        VideoTask.delete(task_id)
        
        # 删除关联的执行历史记录
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM task_execution_history 
                    WHERE task_id = ? AND task_type = 'video'
                ''', (task_id,))
                deleted_count = cursor.rowcount
                logger.info(f"删除影视下载任务 {task_id} 的 {deleted_count} 条执行历史记录")
        except Exception as e:
            logger.warning(f"删除执行历史记录失败: {str(e)}")
        
        # 删除任务的失败记录
        try:
            from services.retry_manager import RetryManager
            RetryManager.clear_task_failures(task_id)
            logger.info(f"清除影视下载任务 {task_id} 的失败记录")
        except Exception as e:
            logger.warning(f"清除失败记录失败: {str(e)}")
        
        return jsonify({
            'code': 200,
            'message': '删除成功'
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': f'删除任务失败: {str(e)}'})


@video_bp.route('/task/<int:task_id>/execute', methods=['POST'])
def execute_task(task_id):
    """执行任务（立即下载）"""
    try:
        from services.video_download_service import video_download_service
        from services.mango_service import mango_service
        from database import db
        from datetime import datetime
        import os
        
        task = VideoTask.get_by_id(task_id)
        if not task:
            return jsonify({'code': 404, 'message': '任务不存在'})
        
        # 检查是否有剧集
        if not task.episodes or len(task.episodes) == 0:
            return jsonify({'code': 400, 'message': '任务没有可下载的剧集'})
        
        # 检查是否从调度服务传入了execution_id（通过请求体）
        data = request.get_json() if request.is_json else {}
        execution_id = data.get('execution_id')
        
        if execution_id:
            # 使用调度服务传入的execution_id，更新状态为running
            history_id = execution_id
            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE task_execution_history 
                    SET status = 'running', start_time = ?, total_count = ?
                    WHERE id = ?
                ''', (start_time, len(task.episodes), history_id))
        else:
            # 手动执行：不删除历史记录，直接创建新的执行记录
            # 创建新的执行历史记录
            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            schedule_period = datetime.now().strftime('%Y%m%d')  # 设置账期为当天，确保能被筛选到
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO task_execution_history 
                    (task_id, task_type, task_name, start_time, status, total_count, schedule_period)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (task_id, 'video', task.name, start_time, 'running', len(task.episodes), schedule_period))
                history_id = cursor.lastrowid
                conn.commit()  # 立即提交，确保记录可见
        
        # 执行任务时不修改任务状态，只重置进度
        # 任务状态只能通过"发布"和"下线"按钮修改
        VideoTask.update(task_id, progress=0)
        
        # 异步执行下载（避免阻塞请求）
        import threading
        import json
        
        def download_thread():
            from utils.task_logger import TaskLogger
            
            error_message = None
            
            # 创建日志记录器
            task_logger = TaskLogger()
            
            # 实时更新日志到数据库的函数
            def update_logs_to_db():
                try:
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE task_execution_history 
                            SET logs = ?
                            WHERE id = ?
                        ''', (json.dumps(task_logger.get_logs(), ensure_ascii=False), history_id))
                except Exception as e:
                    logger.error(f"更新日志到数据库失败: {str(e)}")
            
            # 设置日志更新回调
            task_logger.update_callback = update_logs_to_db
            
            try:
                task_logger.info("开始执行影视下载任务")
                task_logger.info(f"任务名称: {task.name}")
                
                # 提前构建任务配置，避免在异常处理中使用未定义的变量
                task_config = {
                    'task_id': task_id,
                    'enable_file_size_check': task.enable_file_size_check,
                    'min_file_size': task.min_file_size,
                    'enable_retry': task.enable_retry,
                    'max_retry_count': task.max_retry_count,
                    'retry_interval': task.retry_interval
                }
                
                # 增量更新：重新读取官网获取最新剧集
                task_logger.info("正在检查更新...")
                
                try:
                    from services.video_parse_service import video_parse_service
                    
                    # 获取任务的平台信息
                    platform = task.platform if hasattr(task, 'platform') and task.platform else 'mango'
                    
                    result = video_parse_service.read_website(task.website_url, platform)
                    if result.get('success'):
                        latest_episodes = result['episodes']
                        task_logger.info(f"官网最新剧集数: {len(latest_episodes)}")
                        
                        # 获取用户选择的剧集索引
                        selected_indices = []
                        if hasattr(task, 'selected_episodes') and task.selected_episodes:
                            try:
                                selected_indices = task.selected_episodes if isinstance(task.selected_episodes, list) else []
                                if selected_indices:
                                    task_logger.info(f"用户选择了 {len(selected_indices)} 集进行下载")
                            except Exception as e:
                                logger.error(f"解析selected_episodes失败: {str(e)}")
                        
                        # 根据用户选择筛选剧集
                        if selected_indices:
                            # 用户指定了要下载的剧集，检查哪些已下载
                            actual_save_directory = task.save_directory
                            if task.create_subfolder:
                                actual_save_directory = os.path.join(task.save_directory, task.name)
                            
                            # 检查哪些剧集已经下载
                            downloaded_episode_names = set()
                            if os.path.exists(actual_save_directory):
                                for file in os.listdir(actual_save_directory):
                                    if file.endswith('.mp4'):
                                        # 去掉.mp4后缀
                                        episode_name = file[:-4]
                                        downloaded_episode_names.add(episode_name)
                            
                            task_logger.info(f"已下载剧集数: {len(downloaded_episode_names)}")
                            
                            # 筛选出需要下载的剧集
                            episodes_to_download = []
                            for index in selected_indices:
                                if 0 <= index < len(latest_episodes):
                                    ep = latest_episodes[index]
                                    
                                    # 构建完整的文件名（与下载时一致）
                                    episode_name = ep.get('name', '')
                                    episode_title = ep.get('title', '')
                                    if episode_title:
                                        full_name = f"{episode_name} - {episode_title}"
                                    else:
                                        full_name = episode_name
                                    
                                    # 清理文件名中的非法字符
                                    illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
                                    safe_name = full_name
                                    for char in illegal_chars:
                                        safe_name = safe_name.replace(char, '_')
                                    safe_name = safe_name.strip()
                                    
                                    # 应用正则替换（如果配置了）
                                    final_safe_name = safe_name
                                    if task.regex_pattern:
                                        try:
                                            from utils.filename_replacer import FilenameReplacer
                                            success, new_name, msg = FilenameReplacer.apply_regex_replacement(
                                                safe_name, task.regex_pattern, task.replacement_pattern or ''
                                            )
                                            if success and new_name != safe_name:
                                                # 再次清理替换后的文件名
                                                for char in illegal_chars:
                                                    new_name = new_name.replace(char, '_')
                                                final_safe_name = new_name.strip()
                                        except Exception as e:
                                            logger.warning(f"正则替换失败: {str(e)}, 使用原文件名")
                                    
                                    # 只添加未下载的剧集
                                    if final_safe_name not in downloaded_episode_names:
                                        episodes_to_download.append(ep)
                            
                            task_logger.info(f"根据用户选择，需要下载 {len(episodes_to_download)} 集（已跳过 {len(selected_indices) - len(episodes_to_download)} 集）")
                        else:
                            # 用户没有指定，使用增量更新逻辑（只下载未下载的）
                            actual_save_directory = task.save_directory
                            if task.create_subfolder:
                                actual_save_directory = os.path.join(task.save_directory, task.name)
                            
                            # 检查哪些剧集已经下载
                            downloaded_episode_names = set()
                            if os.path.exists(actual_save_directory):
                                for file in os.listdir(actual_save_directory):
                                    if file.endswith('.mp4'):
                                        # 去掉.mp4后缀
                                        episode_name = file[:-4]
                                        downloaded_episode_names.add(episode_name)
                            
                            task_logger.info(f"已下载剧集数: {len(downloaded_episode_names)}")
                            
                            # 筛选出需要下载的新剧集
                            episodes_to_download = []
                            for ep in latest_episodes:
                                # 构建完整的文件名（与下载时一致）
                                episode_name = ep.get('name', '')
                                episode_title = ep.get('title', '')
                                if episode_title:
                                    full_name = f"{episode_name} - {episode_title}"
                                else:
                                    full_name = episode_name
                                
                                # 清理文件名中的非法字符（与video_download_service._sanitize_filename逻辑一致）
                                illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
                                safe_name = full_name
                                for char in illegal_chars:
                                    safe_name = safe_name.replace(char, '_')
                                safe_name = safe_name.strip()
                                
                                # 应用正则替换（如果配置了）
                                final_safe_name = safe_name
                                if task.regex_pattern:
                                    try:
                                        from utils.filename_replacer import FilenameReplacer
                                        success, new_name, msg = FilenameReplacer.apply_regex_replacement(
                                            safe_name, task.regex_pattern, task.replacement_pattern or ''
                                        )
                                        if success and new_name != safe_name:
                                            # 再次清理替换后的文件名
                                            for char in illegal_chars:
                                                new_name = new_name.replace(char, '_')
                                            final_safe_name = new_name.strip()
                                    except Exception as e:
                                        logger.warning(f"正则替换失败: {str(e)}, 使用原文件名")
                                
                                if final_safe_name not in downloaded_episode_names:
                                    episodes_to_download.append(ep)
                        
                        if len(episodes_to_download) == 0:
                            task_logger.info("所有剧集均已下载完成，无需下载")
                            task_logger.info("任务执行完成")
                            
                            # 手动执行完成，恢复为active状态（如果原来是active）
                            # 或保持原状态不变
                            # 只更新进度，不修改状态
                            VideoTask.update(task_id, progress=100)
                            
                            # 计算执行时长
                            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                            end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                            duration = int((end_dt - start_dt).total_seconds())
                            
                            # 更新执行历史为成功状态
                            with db.get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute('''
                                    UPDATE task_execution_history 
                                    SET end_time = ?, duration = ?, status = ?, logs = ?,
                                        success_count = ?, failed_count = ?
                                    WHERE id = ?
                                ''', (end_time, duration, 'success', json.dumps(task_logger.get_logs(), ensure_ascii=False), 
                                      len(latest_episodes), 0, history_id))
                            
                            logger.info(f"影视下载任务 {task_id} 完成：所有剧集均已下载")
                            return
                        
                        task_logger.info(f"发现 {len(episodes_to_download)} 集新内容")
                        task_logger.info("开始下载新增剧集...")
                        
                        # 更新任务的剧集列表（保存最新的完整列表）
                        VideoTask.update(task_id, episodes=latest_episodes, video_info=result['video_info'])
                        
                        # 使用新剧集列表进行下载
                        task.episodes = episodes_to_download
                        
                    else:
                        task_logger.info("无法获取最新剧集，使用已保存的剧集列表")
                except Exception as e:
                    task_logger.info(f"检查更新失败: {str(e)}，使用已保存的剧集列表")
                    
                    # 使用已保存的剧集列表时，也需要检查是否已全部下载
                    actual_save_directory = task.save_directory
                    if task.create_subfolder:
                        actual_save_directory = os.path.join(task.save_directory, task.name)
                    
                    # 检查哪些剧集已经下载
                    downloaded_episode_names = set()
                    if os.path.exists(actual_save_directory):
                        for file in os.listdir(actual_save_directory):
                            if file.endswith('.mp4'):
                                # 去掉.mp4后缀
                                episode_name = file[:-4]
                                downloaded_episode_names.add(episode_name)
                    
                    task_logger.info(f"已下载剧集数: {len(downloaded_episode_names)}")
                    
                    # 筛选出需要下载的剧集
                    episodes_to_download = []
                    for ep in task.episodes:
                        # 构建完整的文件名（与下载时一致）
                        episode_name = ep.get('name', '')
                        episode_title = ep.get('title', '')
                        if episode_title:
                            full_name = f"{episode_name} - {episode_title}"
                        else:
                            full_name = episode_name
                        
                        # 清理文件名中的非法字符
                        illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
                        safe_name = full_name
                        for char in illegal_chars:
                            safe_name = safe_name.replace(char, '_')
                        safe_name = safe_name.strip()
                        
                        # 应用正则替换（如果配置了）
                        final_safe_name = safe_name
                        if task.regex_pattern:
                            try:
                                from utils.filename_replacer import FilenameReplacer
                                success, new_name, msg = FilenameReplacer.apply_regex_replacement(
                                    safe_name, task.regex_pattern, task.replacement_pattern or ''
                                )
                                if success and new_name != safe_name:
                                    # 再次清理替换后的文件名
                                    for char in illegal_chars:
                                        new_name = new_name.replace(char, '_')
                                    final_safe_name = new_name.strip()
                            except Exception as e:
                                logger.warning(f"正则替换失败: {str(e)}, 使用原文件名")
                        
                        if final_safe_name not in downloaded_episode_names:
                            episodes_to_download.append(ep)
                    
                    # 如果所有剧集都已下载，直接返回成功
                    if len(episodes_to_download) == 0:
                        task_logger.info("所有剧集均已下载完成，无需下载")
                        task_logger.info("任务执行完成")
                        
                        # 手动执行完成，恢复为active状态（如果原来是active）
                        # 或保持原状态不变
                        # 只更新进度，不修改状态
                        VideoTask.update(task_id, progress=100)
                        
                        # 计算执行时长
                        end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                        end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                        duration = int((end_dt - start_dt).total_seconds())
                        
                        # 更新执行历史为成功状态
                        with db.get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                UPDATE task_execution_history 
                                SET end_time = ?, duration = ?, status = ?, logs = ?,
                                    success_count = ?, failed_count = ?
                                WHERE id = ?
                            ''', (end_time, duration, 'success', json.dumps(task_logger.get_logs(), ensure_ascii=False), 
                                  len(task.episodes), 0, history_id))
                        
                        logger.info(f"影视下载任务 {task_id} 完成：所有剧集均已下载")
                        return
                    
                    # 更新任务的剧集列表为需要下载的剧集
                    task.episodes = episodes_to_download
                
                task_logger.info(f"剧集总数: {len(task.episodes)}")
                
                # 根据create_subfolder决定实际保存路径
                actual_save_directory = task.save_directory
                if task.create_subfolder:
                    actual_save_directory = os.path.join(task.save_directory, task.name)
                    task_logger.info("按名称分类已启用")
                    task_logger.info(f"保存目录: {actual_save_directory}")
                else:
                    task_logger.info(f"保存目录: {actual_save_directory}")
                
                update_logs_to_db()  # 立即更新到数据库
                
                # 进度回调
                def progress_callback(current, total, episode_name, status, 
                                    downloaded=0, total_size=0, percentage=0):
                    # 更新任务进度
                    task_progress = int((current / total) * 100)
                    VideoTask.update(
                        task_id, 
                        progress=task_progress,
                        downloaded_episodes=current - 1 if status in ['success', 'skipped'] else current - 1
                    )
                    
                    # 记录日志
                    if status == 'checking':
                        task_logger.info(f"检查文件: {episode_name}")
                    elif status == 'downloading':
                        if percentage > 0:
                            task_logger.info(f"正在下载: {episode_name} ({percentage:.1f}%)")
                            # 下载进度日志不需要每次都更新到数据库，避免频繁写入
                    elif status == 'success':
                        task_logger.success(f"下载成功: {episode_name}")
                    elif status == 'skipped':
                        task_logger.warning(f"文件已存在，跳过: {episode_name}")
                    elif status == 'failed':
                        task_logger.error(f"下载失败: {episode_name}")
                
                # 执行下载
                result = video_download_service.download_task_episodes(
                    task_id,
                    task.episodes,
                    actual_save_directory,
                    task.name,  # 传入任务名称
                    task_config,  # 传入任务配置
                    progress_callback,
                    lambda msg: task_logger.info(msg),
                    task.regex_pattern,  # 传入正则表达式
                    task.replacement_pattern,  # 传入替换表达式
                    task.exclude_keywords  # 传入排除关键词
                )
                
                # 更新最终状态
                end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                duration = int((end_dt - start_dt).total_seconds())
                
                # 根据下载结果判断最终状态
                success_count = result['success_count'] + result.get('skipped_count', 0)
                failed_count = result['failed_count']
                
                if failed_count == 0:
                    final_status = 'success'
                elif success_count == 0:
                    final_status = 'failed'
                else:
                    final_status = 'partial'  # 部分成功
                
                if result['success']:
                    # 手动执行完成，保持原状态不变
                    # 只更新进度和下载数
                    VideoTask.update(
                        task_id,
                        progress=100,
                        downloaded_episodes=success_count
                    )
                    
                    task_logger.info("任务执行完成")
                    task_logger.info(f"新下载: {result['success_count']}, 跳过: {result.get('skipped_count', 0)}, 过滤: {result.get('filtered_count', 0)}, 失败: {result['failed_count']}, 总计: {result['total']}")
                    
                    # 更新执行历史
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE task_execution_history 
                            SET end_time = ?, duration = ?, status = ?, 
                                success_count = ?, failed_count = ?, logs = ?
                            WHERE id = ?
                        ''', (end_time, duration, final_status, success_count, 
                              failed_count, json.dumps(task_logger.get_logs(), ensure_ascii=False), history_id))
                    
                    # 执行关联的插件
                    try:
                        from services.plugin_executor import PluginExecutor
                        
                        task_logger.info('开始执行关联插件...')
                        
                        # 构建任务上下文
                        task_context = {
                            'task_id': task_id,
                            'task_name': task.name,
                            'task_type': 'video',
                            'status': 'success',
                            'start_time': start_time,
                            'end_time': end_time,
                            'duration': duration,
                            'total_count': result['total'],
                            'success_count': result['success_count'] + result.get('skipped_count', 0),
                            'failed_count': result['failed_count'],
                            'total_size': 0,  # 影视下载不统计总大小
                            'source_path': task.website_url,
                            'target_path': actual_save_directory,
                            'error_message': '',
                            # 影视下载特有字段
                            'video_name': task.name,
                            'platform': task.platform if hasattr(task, 'platform') else 'mango',
                            'video_type': task.video_type if hasattr(task, 'video_type') else '电视剧',
                        }
                        
                        plugin_result = PluginExecutor.execute_plugins(
                            task_id=task_id,
                            task_type='video',
                            execution_id=history_id,
                            task_context=task_context
                        )
                        
                        if plugin_result['total'] > 0:
                            msg = (f"插件执行完成: 总计 {plugin_result['total']} 个，"
                                   f"成功 {plugin_result['success']} 个，"
                                   f"失败 {plugin_result['failed']} 个，"
                                   f"跳过 {plugin_result['skipped']} 个")
                            task_logger.info(msg)
                            
                            # 更新日志到数据库
                            update_logs_to_db()
                    except Exception as e:
                        error_msg = f"插件执行异常: {str(e)}"
                        task_logger.warning(error_msg)
                        logger.error(error_msg, exc_info=True)
                        
                        # 更新日志到数据库
                        update_logs_to_db()
                else:
                    # 下载失败的情况
                    success_count = result['success_count']
                    failed_count = result['failed_count']
                    
                    # 根据成功/失败数量判断最终状态
                    if failed_count == 0:
                        final_status = 'success'
                    elif success_count == 0:
                        final_status = 'failed'
                    else:
                        final_status = 'partial'  # 部分成功
                    
                    VideoTask.update(
                        task_id,
                        status=final_status,
                        downloaded_episodes=success_count
                    )
                    
                    error_message = f"部分下载失败: 成功 {success_count}/{result['total']}"
                    task_logger.info(f"{error_message}")
                    
                    # 更新执行历史
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE task_execution_history 
                            SET end_time = ?, duration = ?, status = ?, 
                                success_count = ?, failed_count = ?, logs = ?, error_message = ?
                            WHERE id = ?
                        ''', (end_time, duration, final_status, success_count, 
                              failed_count, json.dumps(task_logger.get_logs(), ensure_ascii=False), error_message, history_id))
                    
                    # 执行关联的插件（即使任务失败也执行）
                    try:
                        from services.plugin_executor import PluginExecutor
                        
                        task_logger.info('开始执行关联插件...')
                        
                        # 构建任务上下文
                        task_context = {
                            'task_id': task_id,
                            'task_name': task.name,
                            'task_type': 'video',
                            'status': final_status,
                            'start_time': start_time,
                            'end_time': end_time,
                            'duration': duration,
                            'total_count': result['total'],
                            'success_count': success_count,
                            'failed_count': failed_count,
                            'total_size': 0,  # 影视下载不统计总大小
                            'source_path': task.website_url,
                            'target_path': actual_save_directory,
                            'error_message': error_message,
                            # 影视下载特有字段
                            'video_name': task.name,
                            'platform': task.platform if hasattr(task, 'platform') else 'mango',
                            'video_type': task.video_type if hasattr(task, 'video_type') else '电视剧',
                        }
                        
                        plugin_result = PluginExecutor.execute_plugins(
                            task_id=task_id,
                            task_type='video',
                            execution_id=history_id,
                            task_context=task_context
                        )
                        
                        if plugin_result['total'] > 0:
                            msg = (f"插件执行完成: 总计 {plugin_result['total']} 个，"
                                   f"成功 {plugin_result['success']} 个，"
                                   f"失败 {plugin_result['failed']} 个，"
                                   f"跳过 {plugin_result['skipped']} 个")
                            task_logger.info(msg)
                            
                            # 更新日志到数据库
                            update_logs_to_db()
                    except Exception as e:
                        error_msg = f"插件执行异常: {str(e)}"
                        task_logger.warning(error_msg)
                        logger.error(error_msg, exc_info=True)
                        
                        # 更新日志到数据库
                        update_logs_to_db()
                    
            except Exception as e:
                logger.error(f"下载任务 {task_id} 失败: {str(e)}", exc_info=True)
                # 手动执行失败，保持原状态不变
                # 不修改任务状态
                
                error_message = str(e)
                task_logger.info(f"执行异常: {error_message}")
                
                # 更新执行历史
                end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                duration = int((end_dt - start_dt).total_seconds())
                
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE task_execution_history 
                        SET end_time = ?, duration = ?, status = ?, logs = ?, error_message = ?
                        WHERE id = ?
                    ''', (end_time, duration, 'failed', json.dumps(task_logger.get_logs(), ensure_ascii=False), error_message, history_id))
                
                # 执行关联的插件（即使任务异常也执行）
                try:
                    from services.plugin_executor import PluginExecutor
                    
                    task_logger.info('开始执行关联插件...')
                    
                    # 构建任务上下文
                    task_context = {
                        'task_id': task_id,
                        'task_name': task.name,
                        'task_type': 'video',
                        'status': 'failed',
                        'start_time': start_time,
                        'end_time': end_time,
                        'duration': duration,
                        'total_count': 0,
                        'success_count': 0,
                        'failed_count': 0,
                        'total_size': 0,
                        'source_path': task.website_url,
                        'target_path': actual_save_directory,
                        'error_message': error_message,
                        # 影视下载特有字段
                        'video_name': task.name,
                        'platform': task.platform if hasattr(task, 'platform') else 'mango',
                        'video_type': task.video_type if hasattr(task, 'video_type') else '电视剧',
                    }
                    
                    plugin_result = PluginExecutor.execute_plugins(
                        task_id=task_id,
                        task_type='video',
                        execution_id=history_id,
                        task_context=task_context
                    )
                    
                    if plugin_result['total'] > 0:
                        msg = (f"插件执行完成: 总计 {plugin_result['total']} 个，"
                               f"成功 {plugin_result['success']} 个，"
                               f"失败 {plugin_result['failed']} 个，"
                               f"跳过 {plugin_result['skipped']} 个")
                        task_logger.info(msg)
                        
                        # 更新日志到数据库
                        update_logs_to_db()
                except Exception as plugin_error:
                    error_msg = f"插件执行异常: {str(plugin_error)}"
                    task_logger.warning(error_msg)
                    logger.error(error_msg, exc_info=True)
                    
                    # 更新日志到数据库
                    update_logs_to_db()
        
        # 启动下载线程
        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()
        
        return jsonify({
            'code': 200,
            'message': '任务已开始执行',
            'data': {
                'execution_id': history_id,  # 返回执行记录ID，前端可以直接跳转
                'task_id': task_id
            }
        })
        
    except Exception as e:
        logger.error(f"执行任务失败: {str(e)}", exc_info=True)
        return jsonify({'code': 500, 'message': f'执行任务失败: {str(e)}'})


@video_bp.route('/parse-test', methods=['POST'])
def parse_test():
    """测试解析接口"""
    try:
        from services.video_parse_service import video_parse_service
        
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'code': 400, 'message': '请输入测试地址'})
        
        # 调用解析服务
        result = video_parse_service.parse_video_url(url)
        
        if result.get('success'):
            return jsonify({
                'code': 200,
                'message': '解析成功',
                'data': result
            })
        else:
            return jsonify({
                'code': 500,
                'message': result.get('message', '解析失败'),
                'data': result
            })
            
    except Exception as e:
        return jsonify({'code': 500, 'message': f'测试失败: {str(e)}'})


@video_bp.route('/task/<int:task_id>/toggle', methods=['POST'])
def toggle_task(task_id):
    """发布/下线任务"""
    try:
        task = VideoTask.get_by_id(task_id)
        if not task:
            return jsonify({'code': 404, 'message': '任务不存在'})
        
        # 状态转换逻辑：
        # draft(新建) -> active(生效)
        # inactive(失效) -> active(生效)
        # active(生效) -> inactive(失效)
        # 兼容旧状态：waiting/idle -> active, disabled -> inactive
        current_status = task.status
        
        if current_status in ['draft', 'inactive', 'waiting', 'idle', 'disabled']:
            new_status = 'active'
        elif current_status == 'active':
            new_status = 'inactive'
        else:
            # 其他状态（running, completed等）默认转为active
            new_status = 'active'
        
        VideoTask.update(task_id, status=new_status)
        
        return jsonify({
            'code': 200,
            'message': '状态更新成功',
            'data': {'status': new_status}
        })
        
    except Exception as e:
        return jsonify({'code': 500, 'message': f'更新状态失败: {str(e)}'})


@video_bp.route('/task/<int:task_id>/clear-failures', methods=['POST'])
def clear_task_failures(task_id):
    """清除任务的失败记录"""
    try:
        from services.retry_manager import retry_manager
        
        task = VideoTask.get_by_id(task_id)
        if not task:
            return jsonify({'code': 404, 'message': '任务不存在'})
        
        # 清除失败记录
        retry_manager.clear_task_failures(task_id)
        
        return jsonify({
            'code': 200,
            'message': '失败记录已清除'
        })
        
    except Exception as e:
        logger.error(f"清除失败记录失败: {str(e)}", exc_info=True)
        return jsonify({'code': 500, 'message': f'清除失败记录失败: {str(e)}'})

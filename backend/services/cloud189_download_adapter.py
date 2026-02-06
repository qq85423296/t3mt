# -*- coding: utf-8 -*-
"""
天翼云盘Aria2下载适配模块
负责将天翼云盘下载任务适配到Aria2（串行下载模式）
"""
import os
import time
import threading
from services.aria2_service import Aria2Service
from services.cloud189_service import Cloud189Service
from utils.logger import logger


class Cloud189DownloadAdapter:
    """天翼云盘Aria2下载适配器（串行下载）"""
    
    def __init__(self, aria2_rpc_url='http://127.0.0.1:6800/jsonrpc', log_callback=None, execution_id=None):
        """
        初始化适配器
        
        Args:
            aria2_rpc_url: Aria2 RPC地址
            log_callback: 日志回调函数，签名为 log_callback(message, log_type='info')
            execution_id: 执行历史记录ID（用于直接写入数据库日志）
        """
        self.aria2 = Aria2Service(aria2_rpc_url)
        self.current_gid = None  # 当前下载任务的GID
        self.current_file_info = None  # 当前文件信息（用于重试）
        self.pending_files = []  # 待下载文件队列
        self.failed_files = []  # 失败文件列表
        self.completed_count = 0  # 已完成文件数
        self.monitor_thread = None
        self.monitor_running = False
        self.log_callback = log_callback
        self.task_id = None
        self.execution_id = execution_id
        self.cloud189_service = None
        self.task_info = None
        self.logs = []  # 本地日志缓存
        self.max_retries = 3  # 最大重试次数（获取链接失败时的重试）
        
        # 卡住检测相关字段
        self.last_completed_length = 0  # 上次已下载大小
        self.last_progress_time = time.time()  # 上次进度更新时间
        self.stall_timeout = self._get_config('aria2_stall_timeout', 60)  # 卡住超时时间（秒）
        self.stall_retry_count = 0  # 卡住重试次数
        self.max_stall_retries = self._get_config('aria2_max_stall_retries', 5)  # 最大卡住重试次数
    
    def _get_config(self, key: str, default):
        """获取配置值"""
        try:
            from models.config import ConfigModel
            value = ConfigModel.get_config(key, str(default))
            # 转换为正确的类型
            if isinstance(default, int):
                return int(value)
            elif isinstance(default, float):
                return float(value)
            else:
                return value
        except Exception as e:
            logger.warning(f"获取配置 {key} 失败: {e}，使用默认值: {default}")
            return default
    
    def download_files(self, task, files, cloud189_service, execution_id=None):
        """
        使用Aria2下载天翼云盘文件（串行模式，支持断点续传）
        
        Args:
            task: 下载任务信息（dict）
            files: 文件列表
            cloud189_service: Cloud189Service实例
            execution_id: 执行历史记录ID
        
        Returns:
            dict: 下载结果
        """
        try:
            self.task_id = task['id']
            self.execution_id = execution_id
            self.cloud189_service = cloud189_service
            self.task_info = task
            target_path = task['target_path']
            keep_structure = task.get('keep_structure', 1)
            
            logger.info(f"开始Aria2串行下载任务: task_id={self.task_id}, execution_id={self.execution_id}, 文件数={len(files)}")
            
            # 构建待下载文件队列
            self.pending_files = []
            skipped_count = 0  # 跳过的文件数量
            
            for file in files:
                if file.get('isFolder', False):
                    continue
                
                # 确定下载目录
                if keep_structure:
                    file_path = file.get('path', '')  # 文件所在的文件夹路径（相对路径）
                    # 直接使用 file_path 作为子目录，不要用 dirname（dirname 会截断最后一级目录）
                    download_dir = os.path.join(target_path, file_path) if file_path else target_path
                else:
                    download_dir = target_path
                
                # 应用正则替换
                final_file_name = self._apply_regex_replacement(
                    file['name'],
                    task.get('regex_pattern'),
                    task.get('replacement_pattern')
                )
                
                # 检查文件是否已下载（断点续传）
                final_file_path = os.path.join(download_dir, final_file_name)
                logger.info(f"[断点续传] 检查文件: {final_file_path}")
                if os.path.exists(final_file_path):
                    # 对比文件大小
                    actual_size = os.path.getsize(final_file_path)
                    expected_size = file.get('size', 0)
                    logger.info(f"[断点续传] 文件存在: {final_file_name}, 实际大小={actual_size}, 期望大小={expected_size}")
                    
                    if actual_size == expected_size:
                        # 文件已完整下载，跳过
                        skipped_count += 1
                        logger.info(f"[断点续传] 跳过已下载文件: {final_file_name} ({actual_size} bytes)")
                        continue
                    else:
                        # 文件不完整，删除后重新下载
                        logger.warning(f"[断点续传] 文件大小不匹配，删除后重新下载: {final_file_name} (期望:{expected_size}, 实际:{actual_size})")
                        try:
                            os.remove(final_file_path)
                            logger.info(f"[断点续传] 已删除不完整文件: {final_file_path}")
                        except Exception as e:
                            logger.error(f"[断点续传] 删除不完整文件失败: {final_file_path}, {e}")
                else:
                    logger.info(f"[断点续传] 文件不存在，需要下载: {final_file_path}")
                
                self.pending_files.append({
                    'file_id': file['id'],
                    'file_name': file['name'],
                    'final_file_name': final_file_name,
                    'file_size': file.get('size', 0),
                    'download_dir': download_dir,
                    'retry_count': 0  # 添加重试计数
                })
            
            total_files = len(files) - sum(1 for f in files if f.get('isFolder', False))  # 总文件数（不含文件夹）
            files_to_download = len(self.pending_files)  # 需要下载的文件数
            
            if skipped_count > 0:
                self._add_log_to_db(f'检测到 {skipped_count} 个已下载文件，跳过（断点续传）', 'info')
                logger.info(f"断点续传：跳过 {skipped_count} 个已下载文件")
            
            if files_to_download == 0:
                self._add_log_to_db(f'所有文件均已下载完成，无需下载', 'success')
                # 所有文件都已存在，设置completed_count为跳过的文件数
                self.completed_count = skipped_count
                # 更新执行状态为完成
                if self.execution_id:
                    self._update_execution_status_with_plugin()
                return {'success': True, 'total': total_files, 'submitted': 0, 'failed': 0}
            
            # 通知前台：串行下载模式已启动
            self._add_log_to_db(f'Aria2串行下载模式已启动，共 {files_to_download} 个文件待下载（已跳过 {skipped_count} 个）', 'info')
            
            # 启动监控线程（会自动提交第一个文件）
            self._start_monitor()
            
            return {
                'success': True,
                'total': total_files,
                'submitted': files_to_download,  # 标记为已提交（实际是排队中）
                'failed': 0,
                'serial_mode': True  # 标记为串行模式
            }
            
        except Exception as e:
            logger.error(f"Aria2下载任务失败: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def _apply_regex_replacement(self, filename, regex_pattern, replacement_pattern):
        """应用正则替换规则"""
        if not regex_pattern or not replacement_pattern:
            return filename
        try:
            import re
            return re.sub(regex_pattern, replacement_pattern, filename)
        except Exception as e:
            logger.warning(f"正则替换失败: {e}")
            return filename
    
    def _add_log_to_db(self, message, log_type='info'):
        """直接将日志写入数据库"""
        from datetime import datetime
        
        # 添加到本地缓存
        log_entry = {
            'message': message,
            'type': log_type,
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }
        self.logs.append(log_entry)
        
        # 调用回调（如果存在）
        if self.log_callback:
            self.log_callback(message, log_type)
        
        # 写入数据库
        if self.execution_id:
            try:
                from database import get_db
                import json
                
                logs_json = json.dumps(self.logs, ensure_ascii=False)
                
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE task_execution_history 
                        SET logs = ?
                        WHERE id = ?
                    """, (logs_json, self.execution_id))
                    conn.commit()
            except Exception as e:
                logger.error(f"写入日志到数据库失败: {e}")
    
    def _start_monitor(self):
        """启动监控线程"""
        if self.monitor_running:
            return
        
        self.monitor_running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_and_submit,
            daemon=True
        )
        self.monitor_thread.start()
        logger.info(f"启动Aria2串行下载监控线程: task_id={self.task_id}")
    
    def _monitor_and_submit(self):
        """监控下载并串行提交文件"""
        try:
            # 提交第一个文件
            if self.pending_files:
                self._submit_next_file()
            
            # 监控循环
            while self.monitor_running and (self.current_gid or self.pending_files):
                if self.current_gid:
                    # 查询当前任务状态
                    status = self.aria2.get_status(self.current_gid)
                    
                    if status:
                        if status['status'] == 'complete':
                            # 文件下载完成
                            self.completed_count += 1
                            self._add_log_to_db(f"文件下载完成 ({self.completed_count}/{self.completed_count + len(self.pending_files) + len(self.failed_files)})", 'success')
                            self.current_gid = None
                            self.current_file_info = None
                            
                            # 提交下一个文件
                            if self.pending_files:
                                time.sleep(1)  # 短暂延迟
                                self._submit_next_file()
                        
                        elif status['status'] == 'error':
                            # 下载失败
                            error_msg = status.get('errorMessage', '未知错误')
                            logger.error(f"Aria2下载失败: {error_msg}")
                            
                            # 检查是否需要重试
                            if self.current_file_info and self.current_file_info['retry_count'] < self.max_retries:
                                self.current_file_info['retry_count'] += 1
                                retry_count = self.current_file_info['retry_count']
                                self._add_log_to_db(f"下载失败，正在重试 ({retry_count}/{self.max_retries}): {self.current_file_info['file_name']}", 'warning')
                                
                                # 重新提交当前文件
                                self.current_gid = None
                                time.sleep(2)  # 等待2秒后重试
                                self._submit_file(self.current_file_info)
                            else:
                                # 达到最大重试次数，记录失败
                                file_name = self.current_file_info['file_name'] if self.current_file_info else '未知文件'
                                self._add_log_to_db(f"文件下载失败（已重试{self.max_retries}次）: {file_name} - {error_msg}", 'error')
                                self.failed_files.append({'file_name': file_name, 'error': error_msg})
                                self.current_gid = None
                                self.current_file_info = None
                                
                                # 提交下一个文件
                                if self.pending_files:
                                    time.sleep(1)
                                    self._submit_next_file()
                        
                        elif status['status'] == 'active':
                            # 正在下载，检测进度是否真的在增加
                            total = status['totalLength']
                            completed = status['completedLength']
                            speed = status['downloadSpeed']
                            current_time = time.time()
                            
                            # 检查进度是否有变化
                            if completed > self.last_completed_length:
                                # 进度有变化，更新记录
                                self.last_completed_length = completed
                                self.last_progress_time = current_time
                                self.stall_retry_count = 0  # 重置卡住重试计数
                                
                                # 显示进度
                                if total > 0:
                                    progress = int((completed / total) * 100)
                                    speed_mb = speed / 1024 / 1024
                                    self._add_log_to_db(f"下载进度: {progress}% | 速度: {speed_mb:.2f}MB/s", 'info')
                            else:
                                # 进度没有变化，检查是否超时
                                if current_time - self.last_progress_time > self.stall_timeout:
                                    # 检测到卡住
                                    logger.warning(f"检测到下载卡住: gid={self.current_gid}, 已{self.stall_timeout}秒无进度")
                                    self._handle_stall()
                
                # 等待5秒后再次查询
                time.sleep(5)
            
            # 所有文件处理完成
            logger.info(f"所有下载任务已完成: task_id={self.task_id}, 成功={self.completed_count}, 失败={len(self.failed_files)}")
            
            # 更新最终状态并调用插件
            if self.execution_id:
                self._update_execution_status_with_plugin()
            
            if self.failed_files:
                self._add_log_to_db(f"下载完成！成功: {self.completed_count} 个，失败: {len(self.failed_files)} 个", 'warning')
            else:
                self._add_log_to_db(f"下载完成！共成功下载 {self.completed_count} 个文件", 'success')
            
        except Exception as e:
            logger.error(f"监控线程异常: {e}", exc_info=True)
        finally:
            self.monitor_running = False
            
            # 从TaskExecutor的适配器字典中移除（任务完成或异常时清理）
            try:
                from services.task_executor import TaskExecutor
                with TaskExecutor._adapter_lock:
                    if self.task_id in TaskExecutor._aria2_adapters:
                        TaskExecutor._aria2_adapters.pop(self.task_id, None)
                        logger.info(f"已从适配器字典中清理: task_id={self.task_id}")
                
                # 触发队列处理（检查是否有等待的任务）
                TaskExecutor._ensure_queue_processor_running()
                
            except Exception as cleanup_err:
                logger.warning(f"清理适配器字典失败: {cleanup_err}")
    
    def _submit_next_file(self):
        """从队列中取出下一个文件并提交"""
        if not self.pending_files:
            return
        
        file_info = self.pending_files.pop(0)
        self._submit_file(file_info)
    
    def _submit_file(self, file_info):
        """提交指定文件到Aria2（支持重试）"""
        file_name = file_info['file_name']
        
        try:
            # 保存当前文件信息（用于重试）
            self.current_file_info = file_info
            
            # 获取下载链接
            logger.info(f"获取文件下载链接: {file_name}")
            result, _ = self.cloud189_service.get_download_url([file_info['file_id']])
            
            if result.get('code') != 0 or not result.get('data'):
                raise Exception(result.get('message', '获取下载链接失败'))
            
            download_url = result['data'][0].get('download_url') or result['data'][0].get('downloadUrl')
            if not download_url:
                raise Exception('下载URL为空')
            
            # 获取302重定向后的真实地址
            logger.info(f"获取302重定向后的真实下载地址: {file_name}")
            import requests
            response = requests.get(
                download_url,
                allow_redirects=True,
                stream=True,
                timeout=10,
                headers={
                    'User-Agent': self.cloud189_service.session.headers.get('User-Agent', 'Mozilla/5.0'),
                    'Cookie': self.cloud189_service.cookie
                }
            )
            real_download_url = response.url
            response.close()
            logger.info(f"真实下载地址: {real_download_url[:100]}...")
            
            # 确保目录存在（使用 exist_ok=True 避免并发创建时报错）
            download_dir = file_info['download_dir']
            if not os.path.exists(download_dir):
                os.makedirs(download_dir, exist_ok=True)
                logger.info(f"创建下载目录: {download_dir}")
            
            # 提交到Aria2
            aria2_options = {
                'dir': download_dir,
                'out': file_info['final_file_name']
            }
            
            gid = self.aria2.add_download(real_download_url, aria2_options)
            
            if gid:
                self.current_gid = gid
                # 重置卡住检测状态
                self.last_completed_length = 0
                self.last_progress_time = time.time()
                self.stall_retry_count = 0
                
                logger.info(f"文件已提交到Aria2: {file_name}, gid={gid}")
                retry_info = f" (重试 {file_info['retry_count']}/{self.max_retries})" if file_info['retry_count'] > 0 else ""
                self._add_log_to_db(f"开始下载: {file_name}{retry_info}", 'info')
            else:
                raise Exception('提交到Aria2失败')
        
        except Exception as e:
            logger.error(f"提交文件失败: {file_name}, error={e}")
            
            # 检查是否需要重试
            if file_info['retry_count'] < self.max_retries:
                file_info['retry_count'] += 1
                retry_count = file_info['retry_count']
                self._add_log_to_db(f"获取下载链接失败，正在重试 ({retry_count}/{self.max_retries}): {file_name}", 'warning')
                
                # 重要：清除current_gid
                self.current_gid = None
                
                # 等待后重试
                time.sleep(2)
                self._submit_file(file_info)
            else:
                # 达到最大重试次数，记录失败
                self.failed_files.append({'file_name': file_name, 'error': str(e)})
                self._add_log_to_db(f"文件提交失败（已重试{self.max_retries}次）: {file_name} - {str(e)}", 'error')
                
                # 重要：清除current_gid和current_file_info
                self.current_gid = None
                self.current_file_info = None
                
                # 继续提交下一个
                if self.pending_files:
                    time.sleep(1)
                    self._submit_next_file()
    
    def _handle_stall(self):
        """处理下载卡住"""
        if self.stall_retry_count < self.max_stall_retries:
            self.stall_retry_count += 1
            self._add_log_to_db(
                f"检测到下载卡住（{self.stall_timeout}秒无进度），正在自动重试 ({self.stall_retry_count}/{self.max_stall_retries})",
                'warning'
            )
            
            # 强制删除当前aria2任务
            if self.current_gid:
                try:
                    self.aria2.remove_task(self.current_gid, force=True)
                    logger.info(f"已强制删除卡住的aria2任务: gid={self.current_gid}")
                except Exception as e:
                    logger.warning(f"删除卡住的aria2任务失败: {e}")
            
            # 重置状态
            self.current_gid = None
            self.last_completed_length = 0
            self.last_progress_time = time.time()
            
            # 重新提交当前文件
            time.sleep(2)  # 等待2秒后重试
            self._submit_file(self.current_file_info)
        else:
            # 达到最大重试次数
            file_name = self.current_file_info['file_name'] if self.current_file_info else '未知文件'
            self._add_log_to_db(
                f"文件下载失败（卡住后已重试{self.max_stall_retries}次）: {file_name}",
                'error'
            )
            self.failed_files.append({
                'file_name': file_name,
                'error': f'下载卡住，已重试{self.max_stall_retries}次仍失败'
            })
            self.current_gid = None
            self.current_file_info = None
            self.stall_retry_count = 0  # 重置计数器
            
            # 提交下一个文件
            if self.pending_files:
                time.sleep(1)
                self._submit_next_file()
    
    def _update_execution_status(self):
        """更新执行历史记录的最终状态（不调用插件，由_update_execution_status_with_plugin调用）"""
        try:
            from database import get_db
            from datetime import datetime
            
            if len(self.failed_files) == 0:
                status = 'completed'
                error_message = None  # 成功时error_message为空
            else:
                status = 'completed_with_errors'
                # 将失败信息记录到error_message
                failed_list = [f"{f['file_name']}: {f['error']}" for f in self.failed_files[:5]]  # 只记录前5个
                error_message = f"失败 {len(self.failed_files)} 个文件: " + "; ".join(failed_list)
                if len(self.failed_files) > 5:
                    error_message += f" ... 还有 {len(self.failed_files) - 5} 个文件失败"
            
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            logger.info(f"[状态更新] 准备更新执行历史: execution_id={self.execution_id}, status={status}, success={self.completed_count}, failed={len(self.failed_files)}")
            
            # 使用重试机制确保状态更新成功
            max_retries = 3
            for retry in range(max_retries):
                try:
                    with get_db() as conn:
                        cursor = conn.cursor()
                        
                        # 先查询当前状态
                        cursor.execute("SELECT status FROM task_execution_history WHERE id = ?", (self.execution_id,))
                        row = cursor.fetchone()
                        if not row:
                            logger.error(f"[状态更新] 执行记录不存在: execution_id={self.execution_id}")
                            return
                        
                        old_status = row['status']
                        logger.info(f"[状态更新] 当前状态: {old_status}, 目标状态: {status}")
                        
                        # 更新状态
                        cursor.execute("""
                            UPDATE task_execution_history 
                            SET status = ?, 
                                end_time = ?,
                                error_message = ?,
                                success_count = ?,
                                failed_count = ?
                            WHERE id = ?
                        """, (status, end_time, error_message, 
                              self.completed_count, len(self.failed_files), self.execution_id))
                        
                        affected_rows = cursor.rowcount
                        conn.commit()
                        
                        if affected_rows == 0:
                            logger.warning(f"[状态更新] 更新失败，affected_rows=0，重试 {retry + 1}/{max_retries}")
                            continue
                        
                        # 验证更新是否成功
                        cursor.execute("SELECT status, end_time, success_count, failed_count FROM task_execution_history WHERE id = ?", (self.execution_id,))
                        row = cursor.fetchone()
                        if row:
                            actual_status = row['status']
                            if actual_status == status:
                                logger.info(f"[状态更新] ✓ 更新成功: status={actual_status}, end_time={row['end_time']}, success={row['success_count']}, failed={row['failed_count']}")
                                return  # 成功，退出重试循环
                            else:
                                logger.error(f"[状态更新] ✗ 状态不一致: 期望={status}, 实际={actual_status}，重试 {retry + 1}/{max_retries}")
                        else:
                            logger.error(f"[状态更新] ✗ 验证失败: 未找到execution_id={self.execution_id}的记录")
                        
                except Exception as retry_err:
                    logger.error(f"[状态更新] 重试 {retry + 1}/{max_retries} 失败: {retry_err}")
                    if retry < max_retries - 1:
                        import time
                        time.sleep(1)  # 等待1秒后重试
                    else:
                        raise
            
            # 所有重试都失败
            logger.error(f"[状态更新] ✗ 所有重试都失败，状态更新失败: execution_id={self.execution_id}")
            
        except Exception as e:
            logger.error(f"[状态更新] 更新执行历史状态异常: {e}", exc_info=True)
    
    def _update_execution_status_with_plugin(self):
        """更新执行历史记录的最终状态并调用插件"""
        try:
            # 先更新数据库状态
            self._update_execution_status()
            
            # 调用插件
            if self.execution_id and self.task_id:
                logger.info(f"开始调用插件: task_id={self.task_id}, execution_id={self.execution_id}")
                
                try:
                    from services.plugin_executor import PluginExecutor
                    
                    # 构建任务上下文
                    task_context = {
                        'task_name': self.task_info.get('task_name', '天翼云盘下载任务'),
                        'target_path': self.task_info.get('target_path', ''),
                        'total_files': self.completed_count + len(self.failed_files),
                        'success_count': self.completed_count,
                        'failed_count': len(self.failed_files),
                        'failed_files': self.failed_files,
                        'status': 'completed' if len(self.failed_files) == 0 else 'completed_with_errors',
                        'logs': self.logs
                    }
                    
                    # 调用插件
                    plugin_result = PluginExecutor.execute_plugins(
                        task_id=self.task_id,
                        task_type='download',
                        execution_id=self.execution_id,
                        task_context=task_context
                    )
                    
                    # 检查返回结果
                    if plugin_result:
                        total = plugin_result.get('total', 0)
                        success = plugin_result.get('success', 0)
                        failed = plugin_result.get('failed', 0)
                        skipped = plugin_result.get('skipped', 0)
                        
                        if total == 0:
                            logger.info(f"没有配置插件，跳过")
                            self._add_log_to_db(f"没有配置插件", 'info')
                        elif failed > 0:
                            logger.warning(f"插件执行完成: 总计{total}个，成功{success}个，失败{failed}个，跳过{skipped}个")
                            self._add_log_to_db(f"插件执行完成: 成功{success}个，失败{failed}个", 'warning')
                        else:
                            logger.info(f"插件执行成功: 总计{total}个，成功{success}个")
                            self._add_log_to_db(f"插件执行成功: {success}个插件已执行", 'success')
                    else:
                        logger.warning(f"插件调用返回空结果")
                        self._add_log_to_db(f"插件执行异常: 返回空结果", 'error')
                        
                except Exception as plugin_err:
                    logger.error(f"调用插件异常: {plugin_err}", exc_info=True)
                    self._add_log_to_db(f"插件执行异常: {str(plugin_err)}", 'error')
            
        except Exception as e:
            logger.error(f"更新执行历史状态并调用插件失败: {e}", exc_info=True)
    
    def stop_monitor(self):
        """停止进度监控并强制终止Aria2任务"""
        logger.info(f"停止Aria2监控: task_id={self.task_id}")
        
        # 1. 停止监控线程
        self.monitor_running = False
        
        # 2. 强制删除正在下载的Aria2任务
        if self.current_gid:
            try:
                self.aria2.remove_task(self.current_gid, force=True)
                logger.info(f"已强制删除Aria2任务: gid={self.current_gid}")
            except Exception as e:
                logger.warning(f"删除Aria2任务失败: {e}")
        
        # 3. 等待监控线程结束
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=10)
            logger.info(f"监控线程已结束: task_id={self.task_id}")

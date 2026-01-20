# -*- coding: utf-8 -*-
"""
任务执行器 - 异步执行下载任务（支持多线程分块下载）
"""
import os
import threading
import requests
import time
from datetime import datetime
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from services.quark_service import QuarkService
from services.download_service import DownloadService
from models.account import Account
from models.config import ConfigModel
from utils.logger import logger


class TaskExecutor:
    """任务执行器"""
    
    # 存储正在执行的任务状态
    _running_tasks: Dict[int, Dict] = {}
    _lock = threading.Lock()
    _download_url_lock = threading.Lock()  # 新增：下载链接获取锁
    
    @classmethod
    def _get_config(cls, key: str, default):
        """获取配置值"""
        try:
            value = ConfigModel.get_config(key, str(default))
            # 转换为正确的类型
            if isinstance(default, bool):
                # 布尔值判断：支持多种格式
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on')
                return bool(value)
            elif isinstance(default, int):
                return int(value)
            else:
                return value
        except Exception as e:
            logger.warning(f"获取配置 {key} 失败: {e}，使用默认值: {default}")
            return default
    
    @classmethod
    def stop_task(cls, task_id: int) -> bool:
        """
        停止任务执行
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功停止
        """
        with cls._lock:
            if task_id not in cls._running_tasks:
                return False
            
            # 标记任务为已停止
            cls._running_tasks[task_id]['status'] = 'stopped'
            cls._add_log(task_id, '任务已被手动终止', 'warning')
            
            logger.info(f"任务 {task_id} 已标记为停止")
            return True
    
    @classmethod
    def start_task(cls, task_id: int, execution_id: int = None, schedule_period: str = None) -> bool:
        """
        启动任务执行
        
        Args:
            task_id: 任务ID
            execution_id: 执行记录ID（可选，用于调度任务）
            schedule_period: 账期（可选）
            
        Returns:
            是否成功启动
        """
        logger.info(f"[TaskExecutor] start_task 被调用: task_id={task_id}, execution_id={execution_id}, schedule_period={schedule_period}")
        
        with cls._lock:
            # 检查任务是否已在执行
            if task_id in cls._running_tasks:
                logger.warning(f"[TaskExecutor] 任务 {task_id} 已在执行中")
                return False
            
            # 初始化任务状态
            cls._running_tasks[task_id] = {
                'status': 'running',
                'logs': [],
                'progress': 0,
                'current_file': '',
                'downloaded_files': 0,
                'total_files': 0,
                'success_count': 0,
                'fail_count': 0,
                'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'execution_id': execution_id,
                'schedule_period': schedule_period
            }
            logger.info(f"[TaskExecutor] 任务 {task_id} 状态已初始化到 _running_tasks")
        
        # 在新线程中执行任务
        thread = threading.Thread(target=cls._execute_task, args=(task_id,), daemon=True)
        thread.start()
        logger.info(f"[TaskExecutor] 任务 {task_id} 执行线程已启动")
        
        return True
    
    @classmethod
    def get_task_status(cls, task_id: int) -> Dict:
        """获取任务状态"""
        with cls._lock:
            status = cls._running_tasks.get(task_id, None)
            if status:
                logger.debug(f"[TaskExecutor] get_task_status({task_id}): 找到状态, logs数量={len(status.get('logs', []))}")
            else:
                logger.debug(f"[TaskExecutor] get_task_status({task_id}): 未找到状态")
            return status
    
    @classmethod
    def _add_log(cls, task_id: int, message: str, log_type: str = 'info'):
        """添加日志(优化版:减少数据库写入频率)"""
        with cls._lock:
            if task_id in cls._running_tasks:
                cls._running_tasks[task_id]['logs'].append({
                    'message': message,
                    'type': log_type,
                    'timestamp': datetime.now().strftime('%H:%M:%S')
                })
                logger.info(f"[下载任务{task_id}] {message}")
                
                # 优化: 不再每次都写数据库,而是标记需要更新
                # 数据库更新由定期任务或任务完成时统一处理
                cls._running_tasks[task_id]['logs_dirty'] = True
            else:
                # 任务不在运行列表中，只记录到应用日志
                logger.info(f"[下载任务{task_id}] {message}")
    
    @classmethod
    def _flush_logs_to_db(cls, task_id: int):
        """将日志刷新到数据库(批量更新)"""
        with cls._lock:
            if task_id not in cls._running_tasks:
                return
            
            # 检查是否需要更新
            if not cls._running_tasks[task_id].get('logs_dirty', False):
                return
            
            execution_id = cls._running_tasks[task_id].get('execution_id')
            if not execution_id:
                return
            
            try:
                from database import get_db
                import json
                
                # 将日志转换为JSON格式保存
                logs_json = json.dumps(cls._running_tasks[task_id]['logs'], ensure_ascii=False)
                
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE task_execution_history 
                        SET logs = ?
                        WHERE id = ?
                    ''', (logs_json, execution_id))
                    conn.commit()
                
                # 清除脏标记
                cls._running_tasks[task_id]['logs_dirty'] = False
            except Exception as e:
                logger.error(f"批量更新执行历史日志失败: {e}")
    
    @classmethod
    def _update_progress(cls, task_id: int, **kwargs):
        """更新任务进度"""
        with cls._lock:
            if task_id in cls._running_tasks:
                cls._running_tasks[task_id].update(kwargs)
    
    @classmethod
    def _format_size(cls, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    @classmethod
    def _check_range_support(cls, download_url: str, headers: dict) -> bool:
        """
        检测下载链接是否支持Range请求（分段下载）
        
        Args:
            download_url: 下载链接
            headers: 请求头
        
        Returns:
            bool: 是否支持Range请求
        """
        try:
            # 发送HEAD请求检查Accept-Ranges头
            test_headers = headers.copy()
            response = requests.head(download_url, headers=test_headers, timeout=10, verify=False, allow_redirects=True)
            
            # 检查Accept-Ranges头
            accept_ranges = response.headers.get('Accept-Ranges', '').lower()
            if accept_ranges == 'bytes':
                logger.info(f"检测到Accept-Ranges: bytes，支持分段下载")
                return True
            
            # 如果HEAD请求没有Accept-Ranges，尝试发送Range请求测试
            test_headers['Range'] = 'bytes=0-1023'  # 请求前1KB
            response = requests.get(download_url, headers=test_headers, timeout=10, verify=False, stream=True)
            
            # 206状态码表示支持Range请求
            if response.status_code == 206:
                logger.info(f"Range请求返回206状态码，支持分段下载")
                response.close()
                return True
            
            # 200状态码但返回了部分内容也算支持
            if response.status_code == 200:
                content_range = response.headers.get('Content-Range', '')
                if content_range:
                    logger.info(f"检测到Content-Range头，支持分段下载")
                    response.close()
                    return True
            
            logger.warning(f"不支持Range请求，状态码: {response.status_code}")
            response.close()
            return False
            
        except Exception as e:
            logger.error(f"检测Range支持失败: {e}")
            # 检测失败时保守处理，返回False使用单线程
            return False
    
    @classmethod
    def _download_chunk(cls, task_id: int, cloud_service, file_fid: str, headers: dict, start: int, end: int, 
                       chunk_file: Path, chunk_index: int, total_chunks: int, retry: int = 0) -> Dict:
        """
        下载文件的一个分块（每个线程独立获取下载链接）
        
        Args:
            task_id: 任务ID
            cloud_service: 云盘服务实例（用于获取下载链接）
            file_fid: 文件ID
            headers: 请求头
            start: 起始字节
            end: 结束字节
            chunk_file: 分块文件保存路径
            chunk_index: 分块索引
            total_chunks: 总分块数
            retry: 当前重试次数
        """
        try:
            # 每个线程独立获取下载链接
            cls._add_log(task_id, f"      线程 {chunk_index + 1}/{total_chunks} 获取下载链接...", 'info')
            download_result, download_cookie = cloud_service.get_download_url([file_fid])
            
            if download_result.get('code') != 0:
                raise Exception(f"获取下载链接失败: {download_result.get('message', '')}")
            
            download_data = download_result.get('data', [])
            if not download_data:
                raise Exception("下载链接为空")
            
            download_url = download_data[0].get('download_url') or download_data[0].get('downloadUrl')
            if not download_url:
                raise Exception("下载链接无效")
            
            # 设置Range请求头
            chunk_headers = headers.copy()
            chunk_headers['Range'] = f'bytes={start}-{end}'
            
            # 更新Cookie（使用最新的）
            if download_cookie:
                chunk_headers['Cookie'] = download_cookie
            
            timeout = cls._get_config('download_timeout', 60)
            
            cls._add_log(task_id, f"      线程 {chunk_index + 1}/{total_chunks} 开始下载 ({cls._format_size(start)}-{cls._format_size(end)})", 'info')
            
            response = requests.get(
                download_url,
                headers=chunk_headers,
                stream=True,
                timeout=timeout,
                verify=False
            )
            
            if response.status_code not in [200, 206]:
                raise Exception(f"状态码: {response.status_code}")
            
            # 写入分块文件
            downloaded = 0
            chunk_size_bytes = end - start + 1
            with open(chunk_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    # 检查任务是否被停止
                    with cls._lock:
                        if task_id in cls._running_tasks and cls._running_tasks[task_id].get('status') == 'stopped':
                            cls._add_log(task_id, f"      线程 {chunk_index + 1}/{total_chunks} 已停止", 'warning')
                            response.close()
                            if chunk_file.exists():
                                chunk_file.unlink()
                            return {'success': False, 'message': '任务已停止'}
                    
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            
            cls._add_log(task_id, f"      线程 {chunk_index + 1}/{total_chunks} 完成 ({cls._format_size(chunk_file.stat().st_size)})", 'success')
            
            return {'success': True, 'size': chunk_file.stat().st_size}
            
        except Exception as e:
            retry_times = cls._get_config('download_retry_count', 3)
            retry_delay = cls._get_config('download_retry_delay', 5)
            
            if retry < retry_times:
                cls._add_log(task_id, f"      线程 {chunk_index + 1}/{total_chunks} 失败，重试 {retry + 1}/{retry_times}", 'warning')
                time.sleep(retry_delay)
                return cls._download_chunk(task_id, cloud_service, file_fid, headers, start, end, chunk_file, chunk_index, total_chunks, retry + 1)
            else:
                cls._add_log(task_id, f"      线程 {chunk_index + 1}/{total_chunks} 失败: {str(e)}", 'error')
                return {'success': False, 'message': str(e)}
    
    @classmethod
    def _merge_chunks(cls, target_file: Path, chunk_files: List[Path]) -> bool:
        """合并文件分块"""
        try:
            with open(target_file, 'wb') as target:
                for chunk_file in chunk_files:
                    if not chunk_file.exists():
                        raise Exception(f"分块文件不存在: {chunk_file}")
                    
                    with open(chunk_file, 'rb') as chunk:
                        target.write(chunk.read())
                    
                    chunk_file.unlink()
            
            return True
        except Exception as e:
            logger.error(f"合并文件分块失败: {e}")
            return False
    
    @classmethod
    def _download_file_multithread(cls, task_id: int, file_info: dict, cloud_service, file_fid: str,
                                   headers: dict, local_file_path: str) -> bool:
        """
        多线程分块下载单个文件（批次下载：每批获取一次链接，5个线程共用）
        
        Args:
            task_id: 任务ID
            file_info: 文件信息
            cloud_service: 云盘服务实例
            file_fid: 文件ID
            headers: 请求头
            local_file_path: 本地文件路径
        """
        file_name = file_info['file_name']
        file_size = file_info['size']
        
        target_file = Path(local_file_path)
        
        # 从配置读取参数
        threads_per_file = cls._get_config('download_threads_per_file', 4)
        multithread_chunk_size = cls._get_config('download_multithread_chunk_size', 10) * 1024 * 1024
        batch_size = 5  # 每批5个线程共用一个下载链接
        
        cls._add_log(task_id, f"🚀 使用多线程下载: {file_name} ({cls._format_size(file_size)})", 'info')
        cls._add_log(task_id, f"   配置: {threads_per_file} 个线程，每块 {cls._format_size(multithread_chunk_size)}", 'info')
        cls._add_log(task_id, f"   批次下载: 每批 {batch_size} 个线程共用一个下载链接", 'info')
        
        try:
            # 计算分块
            num_chunks = (file_size + multithread_chunk_size - 1) // multithread_chunk_size
            chunks = []
            
            for i in range(num_chunks):
                start = i * multithread_chunk_size
                end = min(start + multithread_chunk_size - 1, file_size - 1)
                chunk_file = target_file.with_suffix(f'.part{i}')
                chunks.append({
                    'start': start,
                    'end': end,
                    'file': chunk_file,
                    'index': i
                })
            
            cls._add_log(task_id, f"   分块数量: {num_chunks}，分为 {(num_chunks + batch_size - 1) // batch_size} 批", 'info')
            
            # 按批次下载
            start_time = time.time()
            failed_chunks = []
            chunk_results = {}
            
            # 将分块分成多个批次
            for batch_idx in range(0, num_chunks, batch_size):
                batch_chunks = chunks[batch_idx:batch_idx + batch_size]
                batch_num = batch_idx // batch_size + 1
                total_batches = (num_chunks + batch_size - 1) // batch_size
                
                cls._add_log(task_id, f"   批次 {batch_num}/{total_batches}: 处理分块 {batch_idx + 1}-{min(batch_idx + batch_size, num_chunks)}", 'info')
                
                # 为这一批获取下载链接
                try:
                    download_result, download_cookie = cloud_service.get_download_url([file_fid])
                    
                    if download_result.get('code') != 0:
                        raise Exception(f"获取下载链接失败: {download_result.get('message', '')}")
                    
                    download_data = download_result.get('data', [])
                    if not download_data:
                        raise Exception("下载链接为空")
                    
                    download_url = download_data[0].get('download_url') or download_data[0].get('downloadUrl')
                    if not download_url:
                        raise Exception("下载链接无效")
                    
                    # 更新Cookie
                    download_headers = headers.copy()
                    if download_cookie:
                        download_headers['Cookie'] = download_cookie
                    
                except Exception as e:
                    cls._add_log(task_id, f"   批次 {batch_num} 获取下载链接失败: {str(e)}", 'error')
                    # 标记这批所有分块为失败
                    for chunk in batch_chunks:
                        failed_chunks.append({
                            'index': chunk['index'],
                            'reason': f'获取下载链接失败: {str(e)}',
                            'range': f"{cls._format_size(chunk['start'])}-{cls._format_size(chunk['end'])}"
                        })
                    continue
                
                # 使用这个下载链接并行下载这一批的分块
                with ThreadPoolExecutor(max_workers=min(threads_per_file, len(batch_chunks))) as executor:
                    future_to_chunk = {
                        executor.submit(
                            cls._download_chunk_with_shared_url,
                            task_id,
                            download_url,
                            download_headers,
                            chunk['start'],
                            chunk['end'],
                            chunk['file'],
                            chunk['index'],
                            num_chunks
                        ): chunk
                        for chunk in batch_chunks
                    }
                    
                    for future in as_completed(future_to_chunk):
                        chunk = future_to_chunk[future]
                        try:
                            result = future.result()
                            chunk_results[chunk['index']] = result
                            if not result['success']:
                                failed_chunks.append({
                                    'index': chunk['index'],
                                    'reason': result.get('message', '未知错误'),
                                    'range': f"{cls._format_size(chunk['start'])}-{cls._format_size(chunk['end'])}"
                                })
                        except Exception as e:
                            error_msg = f"{type(e).__name__}: {str(e)}"
                            failed_chunks.append({
                                'index': chunk['index'],
                                'reason': error_msg,
                                'range': f"{cls._format_size(chunk['start'])}-{cls._format_size(chunk['end'])}"
                            })
                            logger.error(f"分块 {chunk['index']} 异常: {e}")
            
            # 检查是否有失败的分块
            if failed_chunks:
                cls._add_log(task_id, f"   ❌ {len(failed_chunks)} 个分块下载失败:", 'error')
                # 只显示前10个失败的分块
                for failed in failed_chunks[:10]:
                    cls._add_log(task_id, 
                        f"      分块 {failed['index'] + 1}/{num_chunks} ({failed['range']}): {failed['reason']}", 
                        'error')
                if len(failed_chunks) > 10:
                    cls._add_log(task_id, f"      ... 还有 {len(failed_chunks) - 10} 个分块失败", 'error')
                
                # 清理所有分块文件
                for chunk in chunks:
                    if chunk['file'].exists():
                        try:
                            chunk['file'].unlink()
                        except Exception as e:
                            logger.error(f"清理分块文件失败: {chunk['file']}, {e}")
                
                return False
            
            # 验证所有分块文件都存在且大小正确
            cls._add_log(task_id, f"   验证 {num_chunks} 个分块完整性...", 'info')
            missing_chunks = []
            invalid_chunks = []
            
            for chunk in chunks:
                if not chunk['file'].exists():
                    missing_chunks.append(chunk['index'])
                else:
                    actual_size = chunk['file'].stat().st_size
                    expected_size = chunk['end'] - chunk['start'] + 1
                    if actual_size != expected_size:
                        invalid_chunks.append({
                            'index': chunk['index'],
                            'expected': expected_size,
                            'actual': actual_size
                        })
            
            # 如果有缺失或无效的分块,清理并返回失败
            if missing_chunks or invalid_chunks:
                if missing_chunks:
                    cls._add_log(task_id, f"   ❌ 缺失分块: {[i+1 for i in missing_chunks[:10]]}", 'error')
                    if len(missing_chunks) > 10:
                        cls._add_log(task_id, f"      ... 还有 {len(missing_chunks) - 10} 个分块缺失", 'error')
                if invalid_chunks:
                    cls._add_log(task_id, f"   ❌ 分块大小不匹配:", 'error')
                    for invalid in invalid_chunks[:10]:
                        cls._add_log(task_id, 
                            f"      分块 {invalid['index'] + 1}: 期望 {cls._format_size(invalid['expected'])}, "
                            f"实际 {cls._format_size(invalid['actual'])}", 
                            'error')
                    if len(invalid_chunks) > 10:
                        cls._add_log(task_id, f"      ... 还有 {len(invalid_chunks) - 10} 个分块大小不匹配", 'error')
                
                # 清理所有分块文件
                for chunk in chunks:
                    if chunk['file'].exists():
                        try:
                            chunk['file'].unlink()
                        except Exception as e:
                            logger.error(f"清理分块文件失败: {chunk['file']}, {e}")
                
                return False
            
            cls._add_log(task_id, f"   ✅ 所有分块验证通过", 'success')
            
            # 合并分块
            cls._add_log(task_id, f"   合并 {num_chunks} 个分块...", 'info')
            chunk_files = [chunk['file'] for chunk in chunks]
            
            if not cls._merge_chunks(target_file, chunk_files):
                return False
            
            # 验证文件大小
            actual_size = target_file.stat().st_size
            if actual_size != file_size:
                target_file.unlink()
                cls._add_log(task_id, f"   文件大小不匹配: {actual_size}/{file_size}", 'error')
                return False
            
            elapsed_time = time.time() - start_time
            speed = file_size / elapsed_time if elapsed_time > 0 else 0
            
            cls._add_log(task_id, f"✅ 多线程下载完成: {file_name}", 'success')
            cls._add_log(task_id, f"   耗时: {elapsed_time:.1f}秒，平均速度: {cls._format_size(speed)}/s", 'info')
            return True
            
        except Exception as e:
            # 清理分块文件
            for chunk in chunks:
                if chunk['file'].exists():
                    chunk['file'].unlink()
            cls._add_log(task_id, f"多线程下载失败: {file_name} - {str(e)}", 'error')
            return False
    
    @classmethod
    def _download_chunk_with_shared_url(cls, task_id: int, download_url: str, headers: dict, start: int, end: int, 
                                        chunk_file: Path, chunk_index: int, total_chunks: int, retry: int = 0) -> Dict:
        """
        下载文件的一个分块（使用共享的下载链接）
        
        Args:
            task_id: 任务ID
            download_url: 下载链接（共享）
            headers: 请求头
            start: 起始字节
            end: 结束字节
            chunk_file: 分块文件保存路径
            chunk_index: 分块索引
            total_chunks: 总分块数
            retry: 当前重试次数
        """
        try:
            # 设置Range请求头
            chunk_headers = headers.copy()
            chunk_headers['Range'] = f'bytes={start}-{end}'
            
            timeout = cls._get_config('download_timeout', 60)
            
            cls._add_log(task_id, f"      线程 {chunk_index + 1}/{total_chunks} 开始下载 ({cls._format_size(start)}-{cls._format_size(end)})", 'info')
            
            response = requests.get(
                download_url,
                headers=chunk_headers,
                stream=True,
                timeout=timeout,
                verify=False
            )
            
            if response.status_code not in [200, 206]:
                raise Exception(f"状态码: {response.status_code}")
            
            # 写入分块文件
            downloaded = 0
            with open(chunk_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    # 检查任务是否被停止
                    with cls._lock:
                        if task_id in cls._running_tasks and cls._running_tasks[task_id].get('status') == 'stopped':
                            cls._add_log(task_id, f"      线程 {chunk_index + 1}/{total_chunks} 已停止", 'warning')
                            response.close()
                            if chunk_file.exists():
                                chunk_file.unlink()
                            return {'success': False, 'message': '任务已停止'}
                    
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            
            cls._add_log(task_id, f"      线程 {chunk_index + 1}/{total_chunks} 完成 ({cls._format_size(chunk_file.stat().st_size)})", 'success')
            
            return {'success': True, 'size': chunk_file.stat().st_size}
            
        except Exception as e:
            retry_times = cls._get_config('download_retry_count', 3)
            retry_delay = cls._get_config('download_retry_delay', 5)
            
            if retry < retry_times:
                cls._add_log(task_id, f"      线程 {chunk_index + 1}/{total_chunks} 失败，重试 {retry + 1}/{retry_times}: {type(e).__name__}", 'warning')
                time.sleep(retry_delay)
                return cls._download_chunk_with_shared_url(task_id, download_url, headers, start, end, chunk_file, chunk_index, total_chunks, retry + 1)
            else:
                cls._add_log(task_id, f"      线程 {chunk_index + 1}/{total_chunks} 失败: {type(e).__name__}: {str(e)}", 'error')
                return {'success': False, 'message': str(e)}
    
    @classmethod
    def _download_file_single(cls, task_id: int, file_info: dict, cloud_service, file_fid: str,
                             headers: dict, local_file_path: str, retry: int = 0) -> bool:
        """
        单线程下载文件(支持失败重试,每次重试重新获取下载地址)
        
        Args:
            task_id: 任务ID
            file_info: 文件信息
            cloud_service: 云盘服务实例(用于重新获取下载链接)
            file_fid: 文件ID
            headers: 请求头
            local_file_path: 本地文件路径
            retry: 当前重试次数
        """
        file_name = file_info['file_name']
        file_size = file_info['size']
        
        try:
            # 获取下载链接(每次重试都重新获取)
            cls._add_log(task_id, f"   获取下载链接...", 'info')
            download_result, download_cookie = cloud_service.get_download_url([file_fid])
            
            if download_result.get('code') != 0:
                raise Exception(f"获取下载链接失败: {download_result.get('message', '')}")
            
            download_data = download_result.get('data', [])
            if not download_data:
                raise Exception("下载链接为空")
            
            download_url = download_data[0].get('download_url') or download_data[0].get('downloadUrl')
            if not download_url:
                raise Exception("下载链接无效")
            
            # 更新Cookie
            if download_cookie:
                headers = headers.copy()
                headers['Cookie'] = download_cookie
            
            temp_file_path = local_file_path + '.tmp'
            
            # 对于大文件,使用更长的超时时间(或None表示无超时)
            # 注意: timeout只影响连接建立和每次读取chunk的超时,不是总下载时间
            timeout = cls._get_config('download_timeout', 60)  # 增加到60秒
            chunk_size = cls._get_config('download_chunk_size', 2) * 1024 * 1024
            
            cls._add_log(task_id, f"   开始请求下载链接...", 'info')
            
            # 使用verify=False避免SSL证书问题
            response = requests.get(download_url, headers=headers, stream=True, timeout=timeout, verify=False)
            
            if response.status_code != 200:
                cls._add_log(task_id, f"   下载失败，状态码: {response.status_code}", 'error')
                cls._add_log(task_id, f"   响应内容: {response.text[:200]}", 'error')
                return False
            
            cls._add_log(task_id, f"   连接成功，开始下载...", 'info')
            
            # 分块写入文件，并显示进度
            downloaded_size = 0
            last_log_time = time.time()
            last_flush_time = time.time()
            start_time = time.time()
            
            with open(temp_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    # 检查任务是否被停止
                    with cls._lock:
                        if task_id in cls._running_tasks and cls._running_tasks[task_id].get('status') == 'stopped':
                            cls._add_log(task_id, f"   下载已停止，清理临时文件", 'warning')
                            response.close()
                            f.close()
                            # 删除临时文件
                            if os.path.exists(temp_file_path):
                                try:
                                    os.remove(temp_file_path)
                                except:
                                    pass
                            return False
                    
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        current_time = time.time()
                        
                        # 每5秒强制刷新到磁盘(避免缓冲导致文件大小为0)
                        if current_time - last_flush_time >= 5:
                            f.flush()
                            os.fsync(f.fileno())
                            last_flush_time = current_time
                        
                        # 每10秒或每100MB输出一次进度
                        if current_time - last_log_time >= 10 or downloaded_size % (100 * 1024 * 1024) < chunk_size:
                            progress_pct = (downloaded_size / file_size * 100) if file_size > 0 else 0
                            elapsed = current_time - start_time
                            speed = downloaded_size / elapsed if elapsed > 0 else 0
                            
                            cls._add_log(task_id, 
                                f"   进度: {cls._format_size(downloaded_size)}/{cls._format_size(file_size)} "
                                f"({progress_pct:.1f}%), 速度: {cls._format_size(speed)}/s", 
                                'info')
                            last_log_time = current_time
                
                # 最后再刷新一次
                f.flush()
                os.fsync(f.fileno())
            
            cls._add_log(task_id, f"   下载完成，验证文件大小...", 'info')
            
            # 验证文件大小
            if file_size > 0 and downloaded_size != file_size:
                os.remove(temp_file_path)
                cls._add_log(task_id, f"   文件大小不匹配: {downloaded_size}/{file_size}", 'error')
                return False
            
            # 重命名临时文件
            if os.path.exists(local_file_path):
                os.remove(local_file_path)
            os.rename(temp_file_path, local_file_path)
            
            total_time = time.time() - start_time
            avg_speed = file_size / total_time if total_time > 0 else 0
            
            cls._add_log(task_id, f"✅ 单线程下载完成: {file_name}", 'success')
            cls._add_log(task_id, f"   总耗时: {total_time:.1f}秒, 平均速度: {cls._format_size(avg_speed)}/s", 'info')
            return True
            
        except requests.exceptions.Timeout as e:
            retry_times = cls._get_config('download_retry_count', 3)
            retry_delay = cls._get_config('download_retry_delay', 5)
            
            temp_file_path = local_file_path + '.tmp'
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass
            
            if retry < retry_times:
                cls._add_log(task_id, f"   下载超时，重试 {retry + 1}/{retry_times}", 'warning')
                time.sleep(retry_delay)
                return cls._download_file_single(task_id, file_info, cloud_service, file_fid, headers, local_file_path, retry + 1)
            else:
                cls._add_log(task_id, f"   下载超时: {str(e)}", 'error')
                cls._add_log(task_id, f"   已下载: {cls._format_size(downloaded_size) if 'downloaded_size' in locals() else '0'}", 'error')
                return False
                
        except Exception as e:
            retry_times = cls._get_config('download_retry_count', 3)
            retry_delay = cls._get_config('download_retry_delay', 5)
            
            temp_file_path = local_file_path + '.tmp'
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass
            
            if retry < retry_times:
                cls._add_log(task_id, f"   下载失败，重试 {retry + 1}/{retry_times}: {str(e)}", 'warning')
                time.sleep(retry_delay)
                return cls._download_file_single(task_id, file_info, cloud_service, file_fid, headers, local_file_path, retry + 1)
            else:
                cls._add_log(task_id, f"   下载异常: {type(e).__name__}: {str(e)}", 'error')
                cls._add_log(task_id, f"   已下载: {cls._format_size(downloaded_size) if 'downloaded_size' in locals() else '0'}", 'error')
                return False
    
    @classmethod
    def _execute_task(cls, task_id: int):
        """执行下载任务（在后台线程中运行）"""
        execution_id = None
        schedule_period = None
        
        logger.info(f"[TaskExecutor] _execute_task 线程开始执行: task_id={task_id}")
        
        try:
            # 获取任务状态中的execution_id和schedule_period
            with cls._lock:
                if task_id in cls._running_tasks:
                    execution_id = cls._running_tasks[task_id].get('execution_id')
                    schedule_period = cls._running_tasks[task_id].get('schedule_period')
                    logger.info(f"[TaskExecutor] 从_running_tasks获取: execution_id={execution_id}, schedule_period={schedule_period}")
                else:
                    logger.error(f"[TaskExecutor] 任务 {task_id} 不在 _running_tasks 中！")
            
            # 获取任务信息
            logger.info(f"[TaskExecutor] 开始获取任务信息: task_id={task_id}")
            task = DownloadService.get_task_by_id(task_id)
            if not task:
                logger.error(f"[TaskExecutor] 任务 {task_id} 不存在")
                cls._add_log(task_id, '任务不存在', 'error')
                cls._update_progress(task_id, status='failed')
                return
            
            logger.info(f"[TaskExecutor] 任务信息获取成功: {task['name']}")
            
            # 如果没有传入execution_id，先创建执行历史记录
            if not execution_id:
                logger.info(f"[TaskExecutor] 开始创建执行历史记录")
                from database import get_db
                with get_db() as conn:
                    cursor = conn.cursor()
                    
                    # 如果没有账期，说明是手动执行，使用精确到秒的时间戳避免唯一约束冲突
                    if not schedule_period:
                        schedule_period = datetime.now().strftime('%Y%m%d%H%M%S')
                    
                    cursor.execute("""
                        INSERT INTO task_execution_history (
                            task_id, task_type, task_name, schedule_period,
                            status, start_time, logs
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (task_id, 'download', task['name'], schedule_period, 
                          'running', datetime.now(), '[]'))
                    conn.commit()
                    execution_id = cursor.lastrowid
                    
                    logger.info(f"[TaskExecutor] 执行历史记录创建成功: execution_id={execution_id}")
                    
                    # 更新任务状态中的execution_id
                    with cls._lock:
                        if task_id in cls._running_tasks:
                            cls._running_tasks[task_id]['execution_id'] = execution_id
                            logger.info(f"[TaskExecutor] execution_id已更新到_running_tasks")
            
            # 开始记录日志
            logger.info(f"[TaskExecutor] 开始记录日志")
            cls._add_log(task_id, '任务已启动，正在初始化...', 'info')
            cls._add_log(task_id, f'执行历史记录ID: {execution_id}', 'info')
            cls._add_log(task_id, f"开始执行任务: {task['name']}", 'info')
            
            # 获取源账号
            account = Account.get_by_id(task['source_account_id'])
            if not account:
                cls._add_log(task_id, '源账号不存在', 'error')
                cls._update_progress(task_id, status='failed')
                return
            
            cls._add_log(task_id, f"使用账号: {account['remark']}", 'info')
            cls._add_log(task_id, f"网盘目录: {task['source_path']}", 'info')
            cls._add_log(task_id, f"本地目录: {task['target_path']}", 'info')
            
            # 根据账号类型初始化对应的云盘服务
            from services.cloud_service_factory import CloudServiceFactory
            from models.cloud_type import CloudType
            
            cloud_type = account.get('cloud_type', CloudType.QUARK)
            cls._add_log(task_id, f"云盘类型: {cloud_type}", 'info')
            
            try:
                cloud_service = CloudServiceFactory.create_service(
                    cloud_type, 
                    account['cookie'],
                    username=account.get('username'),
                    password=account.get('password')
                )
            except Exception as e:
                cls._add_log(task_id, f"初始化云盘服务失败: {str(e)}", 'error')
                cls._update_progress(task_id, status='failed')
                return
            
            # 获取文件列表
            cls._add_log(task_id, '正在获取文件列表...', 'info')
            
            source_path = task['source_path']
            source_folder_id = task.get('source_folder_id')  # 新增：优先使用文件夹ID
            folder_id = '0' if cloud_type == CloudType.QUARK else '-11'  # 夸克用'0',天翼用'-11'
            
            # 优先使用 folder_id，如果没有则使用路径查找
            if source_folder_id:
                cls._add_log(task_id, f"使用文件夹ID: {source_folder_id}", 'info')
                current_fid = source_folder_id
            elif source_path and source_path != '/':
                cls._add_log(task_id, f"使用路径查找: {source_path}", 'info')
                path_parts = [p for p in source_path.strip('/').split('/') if p]
                cls._add_log(task_id, f"解析路径: {' -> '.join(path_parts)}", 'info')
                
                current_fid = folder_id
                for part in path_parts:
                    # 使用统一的接口获取文件列表
                    files = cloud_service.list_files(current_fid)
                    if files is None:
                        cls._add_log(task_id, f"获取目录失败", 'error')
                        cls._update_progress(task_id, status='failed')
                        return
                    
                    # 调试：记录当前目录下的所有文件夹
                    folder_names = []
                    for f in files:
                        is_folder = f.get('dir') or f.get('isFolder')
                        if is_folder:
                            file_name = f.get('file_name') or f.get('name')
                            folder_names.append(file_name)
                    
                    if folder_names:
                        cls._add_log(task_id, f"当前目录下的文件夹: {', '.join(folder_names[:10])}", 'info')
                        if len(folder_names) > 10:
                            cls._add_log(task_id, f"... 等共 {len(folder_names)} 个文件夹", 'info')
                    
                    found = False
                    for f in files:
                        # 统一处理不同云盘的字段名
                        is_folder = f.get('dir') or f.get('isFolder')
                        file_name = f.get('file_name') or f.get('name')
                        file_id = f.get('fid') or f.get('id')
                        
                        # 去除首尾空格后进行匹配
                        if is_folder and file_name and file_name.strip() == part.strip():
                            current_fid = str(file_id)
                            found = True
                            cls._add_log(task_id, f"找到目录: {part} (ID: {current_fid})", 'info')
                            break
                    
                    if not found:
                        cls._add_log(task_id, f"未找到目录: {part}", 'error')
                        cls._add_log(task_id, f"期望目录名: '{part}' (长度: {len(part)})", 'error')
                        cls._update_progress(task_id, status='failed')
                        
                        # 更新执行历史记录
                        if execution_id:
                            import json
                            from database import get_db
                            with get_db() as conn:
                                cursor = conn.cursor()
                                logs_json = json.dumps(cls._running_tasks[task_id]['logs'], ensure_ascii=False)
                                cursor.execute("""
                                    UPDATE task_execution_history 
                                    SET status = ?, end_time = ?, logs = ?,
                                        success_count = ?, failed_count = ?, error_message = ?
                                    WHERE id = ?
                                """, ('failed', datetime.now(), logs_json, 0, 0, f'未找到目录: {part}', execution_id))
                                conn.commit()
                        
                        # 清理任务状态
                        with cls._lock:
                            if task_id in cls._running_tasks:
                                del cls._running_tasks[task_id]
                        
                        return
            else:
                # 使用根目录
                cls._add_log(task_id, f"使用根目录", 'info')
                current_fid = folder_id
            
            # 递归获取所有文件和文件夹的函数
            def get_all_files_recursive(folder_id, parent_path="", depth=0, max_depth=10):
                """递归获取文件夹中的所有文件，保留层级关系"""
                if depth > max_depth:
                    cls._add_log(task_id, f"达到最大递归深度 {max_depth}，停止递归", 'warning')
                    return []
                
                # 使用统一的接口获取文件列表
                files = cloud_service.list_files(folder_id)
                
                if files is None:
                    cls._add_log(task_id, f"获取文件列表失败", 'error')
                    return []
                
                all_files = []
                
                for item in files:
                    # 统一处理不同云盘的字段名
                    is_folder = item.get('dir') or item.get('isFolder')
                    item_name = item.get('file_name') or item.get('name')
                    item_id = item.get('fid') or item.get('id')
                    
                    item_path = f"{parent_path}/{item_name}" if parent_path else item_name
                    
                    if is_folder:
                        # 这是一个文件夹
                        cls._add_log(task_id, f"正在扫描文件夹: {item_path}", 'info')
                        
                        # 递归获取子文件夹
                        sub_files = get_all_files_recursive(str(item_id), item_path, depth + 1, max_depth)
                        all_files.extend(sub_files)
                    else:
                        # 这是一个文件
                        file_info = {
                            'file': item,
                            'relative_path': parent_path  # 相对于根目录的路径
                        }
                        all_files.append(file_info)
                
                return all_files
            
            # 递归获取所有文件
            cls._add_log(task_id, '开始递归扫描文件...', 'info')
            all_files = get_all_files_recursive(current_fid)
            
            if not all_files:
                cls._add_log(task_id, '未找到任何文件', 'warning')
                cls._update_progress(task_id, status='success', total_files=0)
                
                # 更新执行历史记录
                if execution_id:
                    import json
                    from database import get_db
                    with get_db() as conn:
                        cursor = conn.cursor()
                        logs_json = json.dumps(cls._running_tasks[task_id]['logs'], ensure_ascii=False)
                        cursor.execute("""
                            UPDATE task_execution_history 
                            SET status = ?, end_time = ?, logs = ?,
                                success_count = ?, failed_count = ?, error_message = ?
                            WHERE id = ?
                        """, ('success', datetime.now(), logs_json, 0, 0, '未找到任何文件', execution_id))
                        conn.commit()
                
                # 清理任务状态
                with cls._lock:
                    if task_id in cls._running_tasks:
                        del cls._running_tasks[task_id]
                
                return
            
            cls._add_log(task_id, f"递归扫描完成，共找到 {len(all_files)} 个文件", 'info')
            
            # 应用过滤规则
            filtered_files = all_files
            
            # 获取文件名的统一方法
            def get_file_name(file_info):
                return file_info['file'].get('file_name') or file_info['file'].get('name', '')
            
            # 过滤扩展名（排除）
            if task.get('filter_extensions'):
                exts = [e.strip() for e in task['filter_extensions'].split(',')]
                # 确保扩展名以点开头
                exts = [ext if ext.startswith('.') else f'.{ext}' for ext in exts]
                filtered_files = [f for f in filtered_files if not any(get_file_name(f).endswith(ext) for ext in exts)]
                cls._add_log(task_id, f"排除扩展名 {', '.join(exts)} 后剩余 {len(filtered_files)} 个文件", 'info')
            
            # 过滤扩展名（包含）
            if task.get('include_extensions'):
                exts = [e.strip() for e in task['include_extensions'].split(',')]
                # 确保扩展名以点开头
                exts = [ext if ext.startswith('.') else f'.{ext}' for ext in exts]
                filtered_files = [f for f in filtered_files if any(get_file_name(f).endswith(ext) for ext in exts)]
                cls._add_log(task_id, f"仅保留扩展名 {', '.join(exts)} 后剩余 {len(filtered_files)} 个文件", 'info')
            
            if not filtered_files:
                cls._add_log(task_id, '没有需要下载的文件', 'warning')
                cls._update_progress(task_id, status='success', total_files=0)
                return
            
            cls._update_progress(task_id, total_files=len(filtered_files))
            cls._add_log(task_id, f"准备下载 {len(filtered_files)} 个文件", 'info')
            
            # 确保本地目录存在
            target_path = task['target_path']
            if not os.path.exists(target_path):
                try:
                    os.makedirs(target_path, exist_ok=True)
                    cls._add_log(task_id, f"创建本地目录: {target_path}", 'info')
                except Exception as e:
                    cls._add_log(task_id, f"创建本地目录失败: {str(e)}", 'error')
                    cls._update_progress(task_id, status='failed')
                    return
            
            # 开始下载文件
            success_count = 0
            fail_count = 0
            last_log_flush_time = time.time()  # 记录上次刷新日志的时间
            
            for idx, file_info in enumerate(filtered_files, 1):
                # 检查任务是否被停止
                with cls._lock:
                    if task_id in cls._running_tasks and cls._running_tasks[task_id].get('status') == 'stopped':
                        cls._add_log(task_id, '任务已终止，停止下载', 'warning')
                        
                        # 刷新日志到数据库
                        cls._flush_logs_to_db(task_id)
                        
                        # 更新执行历史记录为已终止
                        if execution_id:
                            import json
                            from database import get_db
                            with get_db() as conn:
                                cursor = conn.cursor()
                                logs_json = json.dumps(cls._running_tasks[task_id]['logs'], ensure_ascii=False)
                                cursor.execute("""
                                    UPDATE task_execution_history 
                                    SET status = ?, end_time = ?, logs = ?,
                                        success_count = ?, failed_count = ?, error_message = ?
                                    WHERE id = ?
                                """, ('failed', datetime.now(), logs_json, success_count, fail_count, '任务已被手动终止', execution_id))
                                conn.commit()
                        
                        # 清理任务状态
                        with cls._lock:
                            if task_id in cls._running_tasks:
                                del cls._running_tasks[task_id]
                                logger.info(f"[TaskExecutor] 任务 {task_id} 已终止，已清除状态")
                        
                        return
                
                # 定期刷新日志到数据库(每10秒或每10个文件)
                current_time = time.time()
                if current_time - last_log_flush_time > 10 or idx % 10 == 0:
                    cls._flush_logs_to_db(task_id)
                    last_log_flush_time = current_time
                
                # 额外: 每5个文件也刷新一次,确保监控页面能看到进度
                if idx % 5 == 0:
                    cls._flush_logs_to_db(task_id)
                
                file = file_info['file']
                relative_path = file_info['relative_path']
                
                # 统一获取文件名和ID(兼容不同云盘)
                file_name = file.get('file_name') or file.get('name')
                file_fid = str(file.get('fid') or file.get('id'))
                file_size = file.get('size', 0)
                size_mb = file_size / (1024 * 1024)
                
                # 显示文件的完整路径
                display_path = f"{relative_path}/{file_name}" if relative_path else file_name
                
                progress = int((idx - 1) / len(filtered_files) * 100)
                cls._update_progress(
                    task_id,
                    current_file=display_path,
                    downloaded_files=idx - 1,
                    progress=progress
                )
                
                cls._add_log(task_id, f"[{idx}/{len(filtered_files)}] 正在下载: {display_path} ({size_mb:.2f} MB)", 'info')
                
                try:
                    # 构建本地文件路径（保持目录结构）
                    if relative_path:
                        local_dir = os.path.join(target_path, relative_path)
                        # 确保子目录存在
                        if not os.path.exists(local_dir):
                            os.makedirs(local_dir, exist_ok=True)
                            cls._add_log(task_id, f"   创建子目录: {relative_path}", 'info')
                        local_file_path = os.path.join(local_dir, file_name)
                    else:
                        local_file_path = os.path.join(target_path, file_name)
                    
                    # 检查文件是否已存在
                    if os.path.exists(local_file_path):
                        local_size = os.path.getsize(local_file_path)
                        if local_size == file_size:
                            cls._add_log(task_id, f"[{idx}/{len(filtered_files)}] 文件已存在，跳过", 'info')
                            success_count += 1
                            continue
                        else:
                            cls._add_log(task_id, f"[{idx}/{len(filtered_files)}] 文件大小不匹配，重新下载", 'warning')
                    
                    # 判断是否使用多线程下载
                    file_info = {'file_name': file_name, 'size': file_size}
                    
                    enable_multithread = cls._get_config('download_enable_multithread', True)
                    multithread_threshold = cls._get_config('download_multithread_threshold', 50) * 1024 * 1024
                    
                    # 准备请求头(根据云盘类型设置)
                    download_headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Cookie': account['cookie']
                    }
                    
                    # 根据云盘类型设置Referer
                    if cloud_type == CloudType.QUARK:
                        from config import Config
                        if Config.QUARK_BASE_URL:
                            quark_referer = Config.QUARK_BASE_URL.replace('drive-pc', 'pan')
                            download_headers['Referer'] = quark_referer
                    elif cloud_type == CloudType.CLOUD189:
                        download_headers['Referer'] = 'https://cloud.189.cn'
                    
                    # 判断是否使用多线程下载
                    if enable_multithread and file_size >= multithread_threshold:
                        cls._add_log(task_id, f"[{idx}/{len(filtered_files)}] 文件大小 {size_mb:.2f}MB >= {multithread_threshold/(1024*1024):.0f}MB，使用多线程下载", 'info')
                        # 大文件使用多线程下载（每个线程独立获取下载链接）
                        download_success = cls._download_file_multithread(
                            task_id, file_info, cloud_service, file_fid, download_headers, local_file_path
                        )
                    else:
                        if not enable_multithread:
                            cls._add_log(task_id, f"[{idx}/{len(filtered_files)}] 多线程下载已禁用，使用单线程下载", 'info')
                        else:
                            cls._add_log(task_id, f"[{idx}/{len(filtered_files)}] 文件大小 {size_mb:.2f}MB < {multithread_threshold/(1024*1024):.0f}MB，使用单线程下载", 'info')
                        
                        # 小文件使用单线程下载(传递cloud_service和file_fid以支持重试时重新获取下载地址)
                        download_success = cls._download_file_single(
                            task_id, file_info, cloud_service, file_fid, download_headers, local_file_path
                        )
                    
                    if download_success:
                        success_count += 1
                        
                        # 应用正则替换重命名文件
                        if task.get('regex_pattern'):
                            try:
                                from utils.filename_replacer import FilenameReplacer
                                matched, new_name, msg = FilenameReplacer.apply_regex_replacement(
                                    file_name,
                                    task['regex_pattern'],
                                    task.get('replacement_pattern', '')
                                )
                                
                                if matched and new_name != file_name:
                                    # 构建新的文件路径
                                    if relative_path:
                                        new_file_path = os.path.join(target_path, relative_path, new_name)
                                    else:
                                        new_file_path = os.path.join(target_path, new_name)
                                    
                                    # 检查目标文件是否已存在
                                    if os.path.exists(new_file_path):
                                        # 生成唯一文件名
                                        base, ext = os.path.splitext(new_name)
                                        counter = 1
                                        while os.path.exists(new_file_path):
                                            new_name = f"{base}_{counter}{ext}"
                                            if relative_path:
                                                new_file_path = os.path.join(target_path, relative_path, new_name)
                                            else:
                                                new_file_path = os.path.join(target_path, new_name)
                                            counter += 1
                                        cls._add_log(task_id, f"   文件名冲突，使用: {new_name}", 'warning')
                                    
                                    # 执行重命名
                                    os.rename(local_file_path, new_file_path)
                                    cls._add_log(task_id, f"   重命名: {file_name} -> {new_name}", 'success')
                            except Exception as rename_error:
                                cls._add_log(task_id, f"   正则替换失败: {str(rename_error)}", 'error')
                    else:
                        fail_count += 1
                    
                    # 更新数据库进度
                    DownloadService.update_progress(task_id, progress)
                    
                except Exception as e:
                    cls._add_log(task_id, f"[{idx}/{len(filtered_files)}] 下载异常: {str(e)}", 'error')
                    fail_count += 1
            
            # 最后刷新一次日志到数据库
            cls._flush_logs_to_db(task_id)
            
            # 更新任务执行时间和进度
            DownloadService.update_execute_time(task_id, last_time=datetime.now())
            DownloadService.update_progress(task_id, 100)
            
            # 判断最终状态
            if fail_count == 0:
                final_status = 'success'
            elif success_count == 0:
                final_status = 'failed'
            else:
                final_status = 'partial'  # 部分成功
            
            # 更新执行历史记录
            if execution_id:
                import json
                from database import get_db
                with get_db() as conn:
                    cursor = conn.cursor()
                    logs_json = json.dumps(cls._running_tasks[task_id]['logs'], ensure_ascii=False)
                    cursor.execute("""
                        UPDATE task_execution_history 
                        SET status = ?, end_time = ?, logs = ?,
                            success_count = ?, failed_count = ?
                        WHERE id = ?
                    """, (final_status, datetime.now(), logs_json, success_count, fail_count, execution_id))
                    conn.commit()
            
            # 执行关联的插件
            if execution_id:
                try:
                    from services.plugin_executor import PluginExecutor
                    
                    # 构建任务上下文
                    task_context = {
                        'task_id': task_id,
                        'task_name': task.get('name', ''),
                        'task_type': 'download',
                        'status': final_status,
                        'start_time': cls._running_tasks[task_id].get('start_time'),
                        'end_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'duration': 0,  # 下载任务暂不统计耗时
                        'total_count': len(filtered_files),
                        'success_count': success_count,
                        'failed_count': fail_count,
                        'total_size': 0,  # 下载任务暂不统计大小
                        'source_path': task.get('source_path', ''),
                        'target_path': task.get('target_path', ''),
                    }
                    
                    cls._add_log(task_id, '开始执行关联插件...', 'info')
                    plugin_result = PluginExecutor.execute_plugins(
                        task_id=task_id,
                        task_type='download',
                        execution_id=execution_id,
                        task_context=task_context
                    )
                    
                    if plugin_result['total'] > 0:
                        cls._add_log(task_id, 
                            f"插件执行完成: 总计 {plugin_result['total']} 个，"
                            f"成功 {plugin_result['success']} 个，"
                            f"失败 {plugin_result['failed']} 个，"
                            f"跳过 {plugin_result['skipped']} 个", 
                            'info')
                    else:
                        cls._add_log(task_id, '没有关联的插件需要执行', 'info')
                        
                except Exception as plugin_error:
                    cls._add_log(task_id, f"插件执行异常: {str(plugin_error)}", 'warning')
                    logger.error(f"执行插件异常: {plugin_error}", exc_info=True)
            
            # 更新最终状态
            cls._update_progress(
                task_id,
                status='success',
                progress=100,
                downloaded_files=len(filtered_files),
                success_count=success_count,
                fail_count=fail_count,
                current_file=''
            )
            
            cls._add_log(task_id, f"\n任务执行完成！", 'success')
            cls._add_log(task_id, f"成功: {success_count} 个，失败: {fail_count} 个", 'info')
            
            # 清理任务状态
            with cls._lock:
                if task_id in cls._running_tasks:
                    del cls._running_tasks[task_id]
                    logger.info(f"[TaskExecutor] 任务 {task_id} 执行完成，已清除状态")
            
        except Exception as e:
            cls._add_log(task_id, f"执行异常: {str(e)}", 'error')
            cls._update_progress(task_id, status='failed')
            
            # 刷新日志到数据库
            cls._flush_logs_to_db(task_id)
            
            # 更新执行历史记录为失败
            if execution_id:
                import json
                from database import get_db
                with get_db() as conn:
                    cursor = conn.cursor()
                    logs_json = json.dumps(cls._running_tasks.get(task_id, {}).get('logs', []), ensure_ascii=False)
                    cursor.execute("""
                        UPDATE task_execution_history 
                        SET status = ?, end_time = ?, logs = ?, error_message = ?
                        WHERE id = ?
                    """, ('failed', datetime.now(), logs_json, str(e), execution_id))
                    conn.commit()
            
            logger.error(f"执行下载任务异常: {e}", exc_info=True)
            
            # 清理任务状态
            with cls._lock:
                if task_id in cls._running_tasks:
                    del cls._running_tasks[task_id]
                    logger.info(f"[TaskExecutor] 任务 {task_id} 执行异常，已清除状态")
    
    @classmethod
    def clear_task(cls, task_id: int):
        """清除任务状态"""
        with cls._lock:
            if task_id in cls._running_tasks:
                del cls._running_tasks[task_id]
                logger.info(f"[TaskExecutor] 已清除任务 {task_id} 的状态")
    
    @classmethod
    def force_clear_task(cls, task_id: int) -> bool:
        """
        强制清除任务状态(用于处理异常状态)
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功清除
        """
        try:
            # 1. 清除内存中的任务状态
            with cls._lock:
                if task_id in cls._running_tasks:
                    del cls._running_tasks[task_id]
                    logger.info(f"[TaskExecutor] 强制清除任务 {task_id} 的内存状态")
            
            # 2. 更新数据库中未完成的执行记录
            from database import get_db
            with get_db() as conn:
                cursor = conn.cursor()
                
                # 查找该任务所有状态为running的执行记录
                cursor.execute("""
                    SELECT id FROM task_execution_history 
                    WHERE task_id = ? AND task_type = 'download' AND status = 'running'
                """, (task_id,))
                
                running_executions = cursor.fetchall()
                
                if running_executions:
                    # 将所有running状态改为interrupted
                    cursor.execute("""
                        UPDATE task_execution_history 
                        SET status = 'interrupted', 
                            end_time = ?,
                            error_message = '任务被强制中断'
                        WHERE task_id = ? AND task_type = 'download' AND status = 'running'
                    """, (datetime.now(), task_id))
                    
                    conn.commit()
                    logger.info(f"[TaskExecutor] 已将任务 {task_id} 的 {len(running_executions)} 条执行记录标记为interrupted")
            
            return True
            
        except Exception as e:
            logger.error(f"[TaskExecutor] 强制清除任务 {task_id} 失败: {e}")
            return False

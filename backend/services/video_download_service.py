# -*- coding: utf-8 -*-
"""
影视下载服务
用于下载解析后的影视文件
"""
import os
import re
import requests
from typing import Dict, Optional, Callable
from urllib.parse import urljoin, urlparse
from config import Config
from utils.logger import logger
from services.video_parse_service import video_parse_service


class VideoDownloadService:
    """影视下载服务类"""
    
    def __init__(self):
        self.chunk_size = Config.CHUNK_SIZE
        self.retry_times = Config.RETRY_TIMES
        self.retry_delay = Config.RETRY_DELAY
        self.timeout = Config.TIMEOUT
    
    def _is_m3u8_url(self, url: str) -> bool:
        """判断是否为m3u8地址"""
        return url.lower().endswith('.m3u8') or 'm3u8' in url.lower()
    
    def _parse_m3u8(self, m3u8_content: str, base_url: str) -> tuple:
        """
        解析m3u8文件，获取初始化片段和所有ts片段URL
        
        Args:
            m3u8_content: m3u8文件内容
            base_url: 基础URL，用于拼接相对路径
            
        Returns:
            (init_url, ts_urls) 元组：初始化片段URL和ts片段URL列表
        """
        init_url = None
        ts_urls = []
        lines = m3u8_content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # 检查是否是初始化片段（EXT-X-MAP）
            if line.startswith('#EXT-X-MAP'):
                # 提取URI
                import re
                match = re.search(r'URI="([^"]+)"', line)
                if match:
                    uri = match.group(1)
                    if uri.startswith('http://') or uri.startswith('https://'):
                        init_url = uri
                    else:
                        init_url = urljoin(base_url, uri)
                    logger.info(f"找到初始化片段: {init_url}")
                continue
            
            # 跳过注释和空行
            if not line or line.startswith('#'):
                continue
            
            # 处理媒体片段URL
            if line.startswith('http://') or line.startswith('https://'):
                ts_urls.append(line)
            else:
                # 相对路径，需要拼接
                ts_urls.append(urljoin(base_url, line))
        
        return init_url, ts_urls
    
    def _download_m3u8_video(self, m3u8_url: str, save_path: str, 
                            file_name: str = '',
                            progress_callback: Optional[Callable] = None,
                            log_callback: Optional[Callable] = None) -> Dict:
        """
        下载m3u8格式的视频
        
        Args:
            m3u8_url: m3u8地址
            save_path: 保存路径
            file_name: 文件名
            progress_callback: 进度回调
            log_callback: 日志回调 callback(message)
            
        Returns:
            下载结果
        """
        try:
            logger.info(f"开始下载m3u8视频: {file_name}")
            if log_callback:
                log_callback(f"开始下载m3u8视频: {file_name}")
            
            # 1. 下载m3u8文件
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.mgtv.com/'
            }
            
            response = requests.get(m3u8_url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            m3u8_content = response.text
            
            logger.info(f"m3u8文件下载成功，开始解析")
            if log_callback:
                log_callback(f"m3u8播放列表下载成功，开始解析")
            
            # 2. 解析m3u8，获取初始化片段和ts片段列表
            base_url = m3u8_url.rsplit('/', 1)[0] + '/'
            init_url, ts_urls = self._parse_m3u8(m3u8_content, base_url)
            
            if not ts_urls:
                return {
                    'success': False,
                    'message': 'm3u8文件中未找到视频片段'
                }
            
            logger.info(f"解析到 {len(ts_urls)} 个视频片段")
            if init_url:
                logger.info(f"找到初始化片段")
                if log_callback:
                    log_callback(f"解析到初始化片段和 {len(ts_urls)} 个视频片段")
            else:
                if log_callback:
                    log_callback(f"解析到 {len(ts_urls)} 个视频片段，开始下载...")
            
            # 3. 创建临时目录存放ts片段
            temp_dir = save_path + '_temp'
            os.makedirs(temp_dir, exist_ok=True)
            
            # 4. 下载初始化片段（如果存在）
            downloaded_files = []
            if init_url:
                init_file = os.path.join(temp_dir, 'init.mp4')
                try:
                    logger.info(f"下载初始化片段: {init_url}")
                    if log_callback:
                        log_callback(f"下载初始化片段...")
                    
                    init_response = requests.get(init_url, headers=headers, timeout=self.timeout)
                    init_response.raise_for_status()
                    
                    logger.info(f"初始化片段响应成功，大小: {len(init_response.content)} 字节")
                    
                    with open(init_file, 'wb') as f:
                        f.write(init_response.content)
                    
                    downloaded_files.append(init_file)
                    logger.info(f"初始化片段下载成功")
                    if log_callback:
                        log_callback(f"初始化片段下载成功")
                except requests.exceptions.Timeout:
                    logger.error(f"初始化片段下载超时（{self.timeout}秒）")
                    if log_callback:
                        log_callback(f"初始化片段下载超时，跳过")
                except requests.exceptions.RequestException as e:
                    logger.error(f"初始化片段下载失败（网络错误）: {str(e)}")
                    if log_callback:
                        log_callback(f"初始化片段下载失败: {str(e)}")
                except Exception as e:
                    logger.error(f"初始化片段下载失败（未知错误）: {str(e)}", exc_info=True)
                    if log_callback:
                        log_callback(f"初始化片段下载失败，可能影响播放")
            
            # 5. 下载所有ts片段（支持多线程）
            failed_count = 0
            
            # 先扫描已下载的片段，实现断点续传
            existing_files = []
            skip_count = 0
            for index in range(1, len(ts_urls) + 1):
                ts_file = os.path.join(temp_dir, f'segment_{index:04d}.ts')
                if os.path.exists(ts_file) and os.path.getsize(ts_file) > 0:
                    existing_files.append(ts_file)
                    skip_count += 1
                else:
                    break  # 找到第一个未下载的片段就停止
            
            if skip_count > 0:
                logger.info(f"检测到 {skip_count} 个已下载片段，从片段 {skip_count + 1} 继续下载")
                if log_callback:
                    log_callback(f"检测到 {skip_count} 个已下载片段，从片段 {skip_count + 1} 继续下载")
            
            logger.info(f"开始下载 {len(ts_urls) - skip_count} 个视频片段（共 {len(ts_urls)} 个）")
            if log_callback:
                log_callback(f"开始下载 {len(ts_urls) - skip_count} 个视频片段")
            
            # 如果有断点续传的文件，添加到downloaded_files（但要保持init.mp4在最前面）
            if existing_files:
                downloaded_files.extend(existing_files)
            
            # 获取多线程配置
            from models.config import ConfigModel
            max_workers = 3  # 默认3个线程
            try:
                max_workers = int(ConfigModel.get_config('video_download_max_threads', '3'))
                logger.info(f"使用配置的线程数: {max_workers}")
            except Exception as e:
                logger.warning(f"获取线程配置失败，使用默认值: {str(e)}")
            
            # 使用线程池下载片段
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import threading
            
            # 线程安全的计数器和锁
            download_lock = threading.Lock()
            completed_count = [skip_count]  # 使用列表以便在闭包中修改
            
            def download_segment(index, ts_url):
                """下载单个片段"""
                try:
                    # 添加线程启动日志
                    logger.info(f"[线程-{index}] 线程已启动，准备下载片段 {index}/{len(ts_urls)}")
                    if log_callback:
                        log_callback(f"  [线程-{index}] 开始下载片段 {index}/{len(ts_urls)}")
                    
                    ts_file = os.path.join(temp_dir, f'segment_{index:04d}.ts')
                    
                    # 下载ts片段（带重试）
                    retry_count = 0
                    success = False
                    
                    while retry_count < self.retry_times and not success:
                        try:
                            logger.info(f"[线程-{index}] 发起HTTP请求: {ts_url[:100]}...")
                            ts_response = requests.get(ts_url, headers=headers, timeout=self.timeout)
                            ts_response.raise_for_status()
                            
                            logger.info(f"[线程-{index}] HTTP响应成功，开始写入文件")
                            with open(ts_file, 'wb') as f:
                                f.write(ts_response.content)
                            
                            success = True
                            
                            # 线程安全地更新进度
                            with download_lock:
                                completed_count[0] += 1
                                current = completed_count[0]
                            
                            # 更新进度
                            if progress_callback:
                                percentage = (current / len(ts_urls)) * 100
                                progress_callback(current * self.chunk_size, len(ts_urls) * self.chunk_size, percentage)
                            
                            # 每个片段都输出日志，与芒果TV保持一致
                            logger.info(f"片段 {current}/{len(ts_urls)} 下载成功 ({(current/len(ts_urls)*100):.1f}%)")
                            if log_callback:
                                log_callback(f"  ✓ 片段 {current}/{len(ts_urls)} 下载成功 ({(current/len(ts_urls)*100):.1f}%)")
                            
                            return {'success': True, 'index': index, 'file': ts_file}
                            
                        except requests.exceptions.Timeout:
                            retry_count += 1
                            logger.warning(f"[线程-{index}] 片段 {index} 下载超时（重试 {retry_count}/{self.retry_times}）")
                            if retry_count >= self.retry_times:
                                logger.error(f"[线程-{index}] 片段 {index} 下载失败，已达最大重试次数")
                                if log_callback:
                                    log_callback(f"  ✗ 片段 {index} 下载失败（超时）")
                                return {'success': False, 'index': index}
                        except Exception as e:
                            retry_count += 1
                            logger.warning(f"[线程-{index}] 片段 {index} 下载失败（重试 {retry_count}/{self.retry_times}）: {str(e)}")
                            
                            if retry_count >= self.retry_times:
                                logger.error(f"[线程-{index}] 片段 {index} 下载失败，已达最大重试次数: {str(e)}")
                                if log_callback:
                                    log_callback(f"  ✗ 片段 {index} 下载失败: {str(e)}")
                                return {'success': False, 'index': index}
                    
                    return {'success': False, 'index': index}
                    
                except Exception as e:
                    logger.error(f"[线程-{index}] 线程执行异常: {str(e)}", exc_info=True)
                    if log_callback:
                        log_callback(f"  ✗ 片段 {index} 线程异常: {str(e)}")
                    return {'success': False, 'index': index}
            
            # 准备下载任务（跳过已下载的）
            download_tasks = [(index, ts_url) for index, ts_url in enumerate(ts_urls, 1) if index > skip_count]
            
            # 使用线程池并发下载
            segment_results = {}
            # 单个片段最大下载时间：10分钟
            SEGMENT_TIMEOUT = 600
            
            try:
                # 添加开始下载的明确日志
                logger.info(f"启动 {max_workers} 个线程开始并发下载...")
                if log_callback:
                    log_callback(f"启动 {max_workers} 个线程开始并发下载...")
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # 提交所有下载任务
                    future_to_index = {
                        executor.submit(download_segment, index, ts_url): index 
                        for index, ts_url in download_tasks
                    }
                    
                    logger.info(f"已提交 {len(download_tasks)} 个下载任务到线程池")
                    if log_callback:
                        log_callback(f"已提交 {len(download_tasks)} 个下载任务，开始执行...")
                    
                    # 等待所有任务完成，每个任务最多等待10分钟
                    for future in as_completed(future_to_index, timeout=None):
                        try:
                            # 为每个future设置超时
                            result = future.result(timeout=SEGMENT_TIMEOUT)
                            segment_results[result['index']] = result
                            if not result['success']:
                                failed_count += 1
                        except TimeoutError:
                            # 片段下载超时（超过10分钟）
                            index = future_to_index[future]
                            logger.error(f"片段 {index} 下载超时（超过{SEGMENT_TIMEOUT}秒），强制取消")
                            if log_callback:
                                log_callback(f"  ✗ 片段 {index} 下载超时（超过{SEGMENT_TIMEOUT//60}分钟）")
                            segment_results[index] = {'success': False, 'index': index}
                            failed_count += 1
                            future.cancel()  # 尝试取消任务
                        except Exception as e:
                            index = future_to_index[future]
                            logger.error(f"片段 {index} 下载异常: {str(e)}")
                            if log_callback:
                                log_callback(f"  ✗ 片段 {index} 下载异常: {str(e)}")
                            segment_results[index] = {'success': False, 'index': index}
                            failed_count += 1
                
                logger.info(f"所有下载任务已完成")
                if log_callback:
                    log_callback(f"所有下载任务已完成")
                    
            except RuntimeError as e:
                if 'cannot schedule new futures after interpreter shutdown' in str(e):
                    logger.error("线程池已关闭，无法继续下载")
                    if log_callback:
                        log_callback("下载被中断（程序正在关闭）")
                    return {
                        'success': False,
                        'message': '下载失败: 程序正在关闭，请稍后重试'
                    }
                else:
                    raise
            except Exception as e:
                logger.error(f"线程池执行失败: {str(e)}")
                return {
                    'success': False,
                    'message': f'下载失败: {str(e)}'
                }
            
            # 按顺序添加下载成功的片段到列表
            for index in range(skip_count + 1, len(ts_urls) + 1):
                if index in segment_results and segment_results[index]['success']:
                    downloaded_files.append(segment_results[index]['file'])
            
            if failed_count > 0:
                logger.warning(f"有 {failed_count} 个片段下载失败")
                if log_callback:
                    log_callback(f"警告: 有 {failed_count} 个片段下载失败")
            
            # 检查是否所有片段都下载成功
            if len(downloaded_files) < len(ts_urls) + (1 if init_url else 0):
                logger.error(f"片段下载不完整: 期望 {len(ts_urls) + (1 if init_url else 0)} 个，实际 {len(downloaded_files)} 个")
                if log_callback:
                    log_callback(f"片段下载不完整，请稍后重试任务继续下载")
                
                return {
                    'success': False,
                    'message': f'有 {failed_count} 个片段下载失败，请稍后重试任务继续下载'
                }
            
            if not downloaded_files:
                return {
                    'success': False,
                    'message': '所有视频片段下载失败'
                }
            
            # 6. 合并fMP4片段
            logger.info(f"开始合并 {len(downloaded_files)} 个视频片段")
            if log_callback:
                log_callback(f"开始合并 {len(downloaded_files)} 个视频片段...")
            
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 检查片段格式
            is_fmp4 = False
            check_file = downloaded_files[1] if len(downloaded_files) > 1 else downloaded_files[0]
            
            if downloaded_files:
                try:
                    with open(check_file, 'rb') as f:
                        header = f.read(20)
                        if b'ftyp' in header or b'styp' in header or b'moof' in header or b'mdat' in header:
                            is_fmp4 = True
                            logger.info("检测到fMP4格式片段")
                            if log_callback:
                                log_callback(f"检测到fMP4格式片段")
                except Exception as e:
                    logger.warning(f"检测片段格式失败: {str(e)}")
            
            merge_success = False
            merge_error = None
            
            # fMP4格式：直接二进制合并（init + 所有片段）
            if is_fmp4:
                logger.info("使用二进制合并方式处理fMP4片段")
                if log_callback:
                    log_callback(f"使用二进制合并方式...")
                
                try:
                    # 验证所有文件都存在
                    missing_files = []
                    for segment_file in downloaded_files:
                        if not os.path.exists(segment_file) or os.path.getsize(segment_file) == 0:
                            missing_files.append(segment_file)
                    
                    if missing_files:
                        logger.error(f"有 {len(missing_files)} 个片段文件缺失或为空")
                        for f in missing_files[:5]:  # 只显示前5个
                            logger.error(f"  缺失文件: {f}")
                        merge_error = f"有 {len(missing_files)} 个片段文件缺失，无法合并"
                        raise Exception(merge_error)
                    
                    with open(save_path, 'wb') as output_file:
                        for i, segment_file in enumerate(downloaded_files):
                            try:
                                with open(segment_file, 'rb') as input_file:
                                    data = input_file.read()
                                    output_file.write(data)
                                    logger.info(f"合并片段 {i+1}/{len(downloaded_files)}: {len(data)} bytes")
                            except Exception as e:
                                logger.error(f"读取片段失败: {segment_file}, 错误: {str(e)}")
                                raise
                    
                    # 检查文件大小
                    if os.path.exists(save_path):
                        file_size = os.path.getsize(save_path)
                        if file_size > 1024 * 1024:  # 至少1MB
                            merge_success = True
                            logger.info(f"fMP4二进制合并成功: {file_size} bytes")
                            if log_callback:
                                log_callback(f"视频合并完成")
                        else:
                            logger.error(f"合并文件过小: {file_size} bytes")
                            merge_error = f"合并文件过小: {file_size} bytes"
                    
                except Exception as e:
                    logger.error(f"fMP4二进制合并失败: {str(e)}")
                    merge_error = str(e)
            
            # 非fMP4格式：尝试FFmpeg合并
            else:
                strategies = [
                    {
                        'name': 'TS-copy',
                        'desc': '直接复制流',
                        'cmd': [
                            'ffmpeg', '-f', 'concat', '-safe', '0',
                            '-i', '{list_file}',
                            '-c', 'copy',
                            '-y', '{output}'
                        ]
                    },
                    {
                        'name': 'TS-recode',
                        'desc': '重新编码',
                        'cmd': [
                            'ffmpeg', '-f', 'concat', '-safe', '0',
                            '-i', '{list_file}',
                            '-c:v', 'libx264', '-c:a', 'aac',
                            '-y', '{output}'
                        ]
                    }
                ]
                
                for strategy in strategies:
                    try:
                        import subprocess
                        
                        abs_save_path = os.path.abspath(save_path)
                        
                        # 创建文件列表（只包含实际存在的文件）
                        list_file = os.path.join(temp_dir, 'filelist.txt')
                        valid_files = []
                        for ts_file in downloaded_files:
                            if os.path.exists(ts_file) and os.path.getsize(ts_file) > 0:
                                valid_files.append(ts_file)
                            else:
                                logger.warning(f"片段文件不存在或为空: {ts_file}")
                        
                        if len(valid_files) != len(downloaded_files):
                            logger.error(f"文件列表不完整: 期望 {len(downloaded_files)} 个，实际 {len(valid_files)} 个")
                            merge_error = f"文件列表不完整: 缺少 {len(downloaded_files) - len(valid_files)} 个片段"
                            break
                        
                        with open(list_file, 'w', encoding='utf-8') as f:
                            for ts_file in valid_files:
                                abs_path = os.path.abspath(ts_file).replace('\\', '/')
                                f.write(f"file '{abs_path}'\n")
                        
                        abs_list_file = os.path.abspath(list_file)
                        
                        # 构建命令
                        cmd = [part.replace('{list_file}', abs_list_file).replace('{output}', abs_save_path) 
                               for part in strategy['cmd']]
                        
                        logger.info(f"尝试合并策略: {strategy['name']} - {strategy['desc']}")
                        if log_callback:
                            log_callback(f"尝试合并方法: {strategy['desc']}")
                        
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            errors='ignore',
                            timeout=3600
                        )
                        
                        if result.returncode == 0 and os.path.exists(abs_save_path):
                            file_size = os.path.getsize(abs_save_path)
                            if file_size > 1024:
                                merge_success = True
                                logger.info(f"合并成功: {strategy['name']}, 文件大小: {file_size} bytes")
                                if log_callback:
                                    log_callback(f"视频合并完成")
                                break
                            else:
                                logger.warning(f"合并文件过小: {file_size} bytes")
                                os.remove(abs_save_path)
                        else:
                            error_output = result.stderr if result.stderr else result.stdout
                            merge_error = error_output[-500:] if error_output else "未知错误"
                            logger.warning(f"策略 {strategy['name']} 失败")
                            
                    except subprocess.TimeoutExpired:
                        logger.warning(f"策略 {strategy['name']} 超时")
                        merge_error = "处理超时"
                        continue
                    except Exception as e:
                        logger.warning(f"策略 {strategy['name']} 异常: {str(e)}")
                        merge_error = str(e)
                        continue
            
            # 合并失败
            if not merge_success:
                # 不删除临时文件，保留以便下次重试断点续传
                logger.warning(f"临时文件保留在: {temp_dir}，下次执行将继续下载")
                if log_callback:
                    log_callback(f"临时文件已保留，下次执行将继续下载")
                
                error_msg = f'视频合并失败'
                if merge_error:
                    error_msg += f': {merge_error[:200]}'
                
                logger.error(error_msg)
                if log_callback:
                    log_callback(f"合并失败: {error_msg}")
                
                return {
                    'success': False,
                    'message': error_msg
                }
            
            # 清理临时文件
            try:
                import shutil
                shutil.rmtree(temp_dir)
                logger.info("临时文件清理完成")
                if log_callback:
                    log_callback(f"临时文件清理完成")
            except Exception as e:
                logger.warning(f"清理临时文件失败: {str(e)}")
            
            # 检查文件大小
            if not os.path.exists(save_path):
                return {
                    'success': False,
                    'message': '视频文件未生成'
                }
            
            file_size = os.path.getsize(save_path)
            logger.info(f"视频下载完成: {file_name}, 大小: {file_size} bytes")
            if log_callback:
                log_callback(f"视频合并完成，文件大小: {file_size / (1024*1024):.2f} MB")
            
            if file_size < 1024 * 1024:  # 小于1MB可能有问题
                logger.warning(f"下载的文件大小异常: {file_size} bytes")
            
            return {
                'success': True,
                'message': '下载成功',
                'file_path': save_path,
                'file_size': file_size,
                'content_type': 'video/mp4',
                'segments_count': len(downloaded_files),
                'failed_segments': failed_count,
                'merge_method': 'ffmpeg'
            }
            
        except Exception as e:
            logger.error(f"下载m3u8视频失败: {file_name}, 错误: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'下载失败: {str(e)}'
            }
    
    def download_episode(self, episode_url: str, save_path: str, 
                        episode_name: str = '', 
                        progress_callback: Optional[Callable] = None,
                        log_callback: Optional[Callable] = None) -> Dict:
        """
        下载单集
        
        Args:
            episode_url: 剧集官网地址
            save_path: 保存路径（完整文件路径）
            episode_name: 集数名称
            progress_callback: 进度回调函数 callback(downloaded, total, percentage)
            
        Returns:
            下载结果
            {
                'success': True/False,
                'message': '消息',
                'file_path': '文件路径',
                'file_size': 文件大小,
                'skipped': True/False  # 是否跳过（文件已存在）
            }
        """
        try:
            # 0. 检查文件是否已存在
            if os.path.exists(save_path):
                file_size = os.path.getsize(save_path)
                
                # 检查文件大小是否合理（大于1MB认为是有效文件）
                if file_size > 1024 * 1024:
                    logger.info(f"文件已存在，跳过下载: {episode_name} ({file_size} bytes)")
                    return {
                        'success': True,
                        'message': '文件已存在，跳过下载',
                        'file_path': save_path,
                        'file_size': file_size,
                        'skipped': True,
                        'url': episode_url
                    }
                else:
                    # 文件太小，可能是损坏的，删除后重新下载
                    logger.warning(f"文件大小异常({file_size} bytes)，删除后重新下载: {episode_name}")
                    try:
                        os.remove(save_path)
                    except:
                        pass
            
            # 1. 解析获取真实下载地址
            logger.info(f"开始解析剧集: {episode_name}, URL: {episode_url}")
            parse_result = video_parse_service.parse_episode(episode_url, episode_name)
            
            if not parse_result.get('success'):
                error_msg = parse_result.get('message', '未知错误')
                return {
                    'success': False,
                    'message': f"解析失败: {error_msg}",
                    'skipped': False,
                    'url': episode_url
                }
            
            download_url = parse_result.get('download_url')
            if not download_url:
                return {
                    'success': False,
                    'message': '解析结果中未找到下载地址',
                    'skipped': False,
                    'url': episode_url
                }
            
            logger.info(f"解析成功，开始下载: {episode_name} -> {download_url}")
            
            # 2. 下载文件
            result = self._download_file(
                download_url, 
                save_path, 
                episode_name,
                progress_callback,
                log_callback
            )
            
            # 添加skipped标记和URL
            if 'skipped' not in result:
                result['skipped'] = False
            result['url'] = episode_url
            result['download_url'] = download_url
            
            return result
            
        except Exception as e:
            logger.error(f"下载剧集失败: {episode_name}, URL: {episode_url}, 错误: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'下载异常: {str(e)}',
                'skipped': False,
                'url': episode_url
            }
    
    def _download_file(self, url: str, save_path: str, 
                      file_name: str = '',
                      progress_callback: Optional[Callable] = None,
                      log_callback: Optional[Callable] = None) -> Dict:
        """
        下载文件（支持重试）
        自动识别m3u8格式并使用对应的下载方法
        
        Args:
            url: 下载地址
            save_path: 保存路径
            file_name: 文件名（用于日志）
            progress_callback: 进度回调
            log_callback: 日志回调
            
        Returns:
            下载结果
        """
        # 判断是否为m3u8格式
        if self._is_m3u8_url(url):
            logger.info(f"检测到m3u8格式，使用HLS下载器: {file_name}")
            if log_callback:
                log_callback(f"检测到m3u8格式视频流")
            return self._download_m3u8_video(url, save_path, file_name, progress_callback, log_callback)
        
        # 普通文件下载
        retry_count = 0
        last_error = None
        
        while retry_count < self.retry_times:
            try:
                # 确保目录存在
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                
                # 发送请求
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://www.mgtv.com/'
                }
                
                response = requests.get(
                    url, 
                    headers=headers,
                    stream=True,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                # 获取文件大小
                total_size = int(response.headers.get('content-length', 0))
                
                # 检查实际内容类型
                content_type = response.headers.get('content-type', '')
                logger.info(f"Content-Type: {content_type}, 文件大小: {total_size} bytes")
                
                # 下载文件
                downloaded_size = 0
                
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=self.chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # 调用进度回调
                            if progress_callback and total_size > 0:
                                percentage = (downloaded_size / total_size) * 100
                                progress_callback(downloaded_size, total_size, percentage)
                
                logger.info(f"下载完成: {file_name}, 大小: {downloaded_size} bytes")
                
                return {
                    'success': True,
                    'message': '下载成功',
                    'file_path': save_path,
                    'file_size': downloaded_size,
                    'content_type': content_type
                }
                
            except requests.Timeout:
                last_error = '下载超时'
                logger.warning(f"下载超时: {file_name}, 重试 {retry_count + 1}/{self.retry_times}")
                
            except requests.RequestException as e:
                last_error = f'请求失败: {str(e)}'
                logger.warning(f"下载失败: {file_name}, 错误: {str(e)}, 重试 {retry_count + 1}/{self.retry_times}")
                
            except Exception as e:
                last_error = f'下载异常: {str(e)}'
                logger.error(f"下载异常: {file_name}, 错误: {str(e)}", exc_info=True)
                break  # 其他异常不重试
            
            retry_count += 1
            
            # 删除不完整的文件
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except:
                    pass
        
        # 所有重试都失败
        return {
            'success': False,
            'message': f'下载失败（已重试{retry_count}次）: {last_error}'
        }
    
    def download_task_episodes(self, task_id: int, episodes: list, 
                               save_directory: str,
                               task_name: str = '',
                               progress_callback: Optional[Callable] = None,
                               log_callback: Optional[Callable] = None) -> Dict:
        """
        下载任务的所有剧集
        
        Args:
            task_id: 任务ID
            episodes: 剧集列表
            save_directory: 最终保存目录
            task_name: 任务名称（用于创建临时目录）
            progress_callback: 进度回调 callback(current, total, episode_name, status)
            log_callback: 日志回调
            
        Returns:
            下载结果
        """
        total = len(episodes)
        success_count = 0
        failed_count = 0
        skipped_count = 0
        results = []
        
        logger.info(f"开始下载任务 {task_id} 的剧集，共 {total} 集")
        
        # 获取临时目录配置
        from models.config import ConfigModel
        temp_base_dir = ConfigModel.get_config('video_download_temp_dir', '/vol2/1000/媒体库/video/temp')
        
        # 为当前任务创建临时目录：temp_dir/任务名称/
        safe_task_name = self._sanitize_filename(task_name or f'task_{task_id}')
        temp_task_dir = os.path.join(temp_base_dir, safe_task_name)
        
        # 确保临时目录存在
        os.makedirs(temp_task_dir, exist_ok=True)
        logger.info(f"使用临时目录: {temp_task_dir}")
        if log_callback:
            log_callback(f"临时下载目录: {temp_task_dir}")
        
        for index, episode in enumerate(episodes, 1):
            episode_name = episode.get('name', f'第{index}集')
            episode_title = episode.get('title', '')
            episode_url = episode.get('url', '')
            
            # 构建完整的显示名称（与前端显示一致）
            if episode_title:
                full_name = f"{episode_name} - {episode_title}"
            else:
                full_name = episode_name
            
            if not episode_url:
                failed_count += 1
                results.append({
                    'name': full_name,
                    'success': False,
                    'message': '缺少URL',
                    'skipped': False
                })
                continue
            
            # 构建文件名（去除非法字符）
            safe_name = self._sanitize_filename(full_name)
            
            # 最终文件路径（正式目录）
            final_file_path = os.path.join(save_directory, f"{safe_name}.mp4")
            
            # 临时文件路径（临时目录/任务名称/剧集名称.mp4）
            temp_file_path = os.path.join(temp_task_dir, f"{safe_name}.mp4")
            
            # 回调：开始检查/下载
            if progress_callback:
                progress_callback(index, total, full_name, 'checking')
            
            # 检查最终目录是否已存在（跳过已下载的）
            if os.path.exists(final_file_path):
                file_size = os.path.getsize(final_file_path)
                if file_size > 1024 * 1024:  # 大于1MB认为是有效文件
                    skipped_count += 1
                    results.append({
                        'name': full_name,
                        'success': True,
                        'message': '文件已存在，跳过下载',
                        'skipped': True
                    })
                    if progress_callback:
                        progress_callback(index, total, full_name, 'skipped')
                    continue
            
            # 下载剧集到临时目录
            def episode_progress(downloaded, total_size, percentage):
                if progress_callback:
                    progress_callback(
                        index, total, full_name, 'downloading',
                        downloaded, total_size, percentage
                    )
            
            result = self.download_episode(
                episode_url, 
                temp_file_path,  # 下载到临时目录
                full_name,
                episode_progress,
                log_callback
            )
            
            result['name'] = full_name
            results.append(result)
            
            if result.get('success'):
                if result.get('skipped'):
                    skipped_count += 1
                    if progress_callback:
                        progress_callback(index, total, full_name, 'skipped')
                else:
                    # 下载成功，移动到正式目录
                    try:
                        # 确保正式目录存在
                        os.makedirs(save_directory, exist_ok=True)
                        
                        # 移动文件
                        import shutil
                        shutil.move(temp_file_path, final_file_path)
                        logger.info(f"文件已移动到正式目录: {final_file_path}")
                        
                        success_count += 1
                        if progress_callback:
                            progress_callback(index, total, full_name, 'success')
                    except Exception as e:
                        logger.error(f"移动文件失败: {temp_file_path} -> {final_file_path}, 错误: {str(e)}")
                        failed_count += 1
                        result['success'] = False
                        result['message'] = f'移动文件失败: {str(e)}'
                        if progress_callback:
                            progress_callback(index, total, full_name, 'failed')
            else:
                failed_count += 1
                # 记录详细的失败原因（包含URL）
                error_msg = result.get('message', '未知错误')
                logger.error(f"下载失败: {full_name}, URL: {episode_url}, 原因: {error_msg}")
                if log_callback:
                    log_callback(f"失败原因: {error_msg}")
                    log_callback(f"错误URL: {episode_url}")
                if progress_callback:
                    progress_callback(index, total, full_name, 'failed')
        
        # 清理临时目录
        try:
            if os.path.exists(temp_task_dir):
                # 检查临时目录是否为空或只有失败的文件
                remaining_files = os.listdir(temp_task_dir)
                if len(remaining_files) == 0:
                    os.rmdir(temp_task_dir)
                    logger.info(f"临时目录已清理: {temp_task_dir}")
                    if log_callback:
                        log_callback(f"临时目录已清理")
                else:
                    logger.warning(f"临时目录中还有 {len(remaining_files)} 个文件未处理: {temp_task_dir}")
                    if log_callback:
                        log_callback(f"警告: 临时目录中还有 {len(remaining_files)} 个未完成的文件")
        except Exception as e:
            logger.error(f"清理临时目录失败: {str(e)}")
        
        logger.info(f"任务 {task_id} 下载完成: 成功 {success_count}/{total}, 跳过 {skipped_count}, 失败 {failed_count}")
        
        # 判断任务是否成功：只有当没有失败的剧集时才算成功
        # 如果有部分成功、部分失败，应该标记为失败
        is_success = failed_count == 0 and (success_count + skipped_count) > 0
        
        return {
            'success': is_success,
            'total': total,
            'success_count': success_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
            'results': results
        }
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除非法字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            清理后的文件名
        """
        # Windows非法字符
        illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        
        return filename.strip()


# 创建全局实例
video_download_service = VideoDownloadService()

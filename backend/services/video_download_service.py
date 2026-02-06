# -*- coding: utf-8 -*-
"""
影视下载服务
用于下载解析后的影视文件
"""
import os
import re
import requests
from typing import Dict, Optional, Callable, List, Tuple
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
        # m3u8 缓存字典 {url: content}
        self.m3u8_cache = {}
    
    def _is_m3u8_url(self, url: str) -> bool:
        """判断是否为m3u8地址"""
        return url.lower().endswith('.m3u8') or 'm3u8' in url.lower()
    
    def _validate_file_size(self, file_path: str, min_size_mb: int) -> tuple:
        """
        验证文件大小是否满足最小要求
        
        Args:
            file_path: 文件路径
            min_size_mb: 最小文件大小(MB)
            
        Returns:
            (is_valid, actual_size_mb, message) 元组
            - is_valid: 是否验证通过
            - actual_size_mb: 实际文件大小(MB)
            - message: 验证消息
        """
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return False, 0, "文件不存在"
        
        # 获取文件大小（字节）
        file_size_bytes = os.path.getsize(file_path)
        # 转换为MB
        file_size_mb = file_size_bytes / (1024 * 1024)
        
        # 验证文件大小
        if file_size_mb < min_size_mb:
            return False, int(file_size_mb), f"文件大小不足: {file_size_mb:.2f}MB < {min_size_mb}MB"
        
        return True, int(file_size_mb), f"文件大小验证通过: {file_size_mb:.2f}MB"
    
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
    
    def _detect_m3u8_type(self, m3u8_content: str) -> str:
        """
        检测 m3u8 文件类型
        
        Args:
            m3u8_content: m3u8 文件内容
            
        Returns:
            'master' - Master Playlist (包含多个码率)
            'media' - Media Playlist (包含 ts 片段)
        """
        # Master Playlist 包含 #EXT-X-STREAM-INF 标签
        if '#EXT-X-STREAM-INF' in m3u8_content:
            return 'master'
        # Media Playlist 包含 #EXTINF 标签
        elif '#EXTINF' in m3u8_content:
            return 'media'
        else:
            # 默认当作 Media Playlist
            return 'media'
    
    def _extract_stream_info(self, m3u8_content: str, base_url: str) -> List[Dict]:
        """
        从 Master Playlist 中提取所有码率信息
        
        Args:
            m3u8_content: m3u8 文件内容
            base_url: 基础 URL
            
        Returns:
            码率信息列表，按 bandwidth 从高到低排序
            [
                {
                    'bandwidth': 2000000,
                    'resolution': '1080x608',
                    'url': 'https://...'
                },
                ...
            ]
        """
        streams = []
        lines = m3u8_content.strip().split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('#EXT-X-STREAM-INF'):
                # 解析码率信息
                bandwidth = None
                resolution = None
                
                # 提取 BANDWIDTH
                bandwidth_match = re.search(r'BANDWIDTH=(\d+)', line)
                if bandwidth_match:
                    bandwidth = int(bandwidth_match.group(1))
                
                # 提取 RESOLUTION
                resolution_match = re.search(r'RESOLUTION=([\dx]+)', line)
                if resolution_match:
                    resolution = resolution_match.group(1)
                
                # 下一行是 m3u8 URL
                if i + 1 < len(lines):
                    url_line = lines[i + 1].strip()
                    if url_line and not url_line.startswith('#'):
                        # 拼接完整 URL
                        if url_line.startswith('http://') or url_line.startswith('https://'):
                            full_url = url_line
                        else:
                            full_url = urljoin(base_url, url_line)
                        
                        streams.append({
                            'bandwidth': bandwidth or 0,
                            'resolution': resolution or 'unknown',
                            'url': full_url
                        })
                
                i += 2  # 跳过下一行
            else:
                i += 1
        
        # 按 bandwidth 从高到低排序
        streams.sort(key=lambda x: x['bandwidth'], reverse=True)
        
        return streams
    
    def _download_m3u8_content(self, url: str, session: requests.Session) -> str:
        """
        下载 m3u8 文件内容（带缓存）
        
        Args:
            url: m3u8 URL
            session: requests.Session 对象（用于复用连接）
            
        Returns:
            m3u8 文件内容
        """
        # 检查缓存
        if url in self.m3u8_cache:
            logger.info(f"使用缓存的 m3u8: {url}")
            return self.m3u8_cache[url]
        
        # 下载（使用 Session）
        response = session.get(url, timeout=self.timeout)
        response.raise_for_status()
        content = response.text
        
        # 缓存
        self.m3u8_cache[url] = content
        
        return content
    
    def _parse_encryption_info(self, m3u8_content: str, base_url: str) -> Optional[Dict]:
        """
        解析 m3u8 中的加密信息
        
        Args:
            m3u8_content: m3u8 文件内容
            base_url: 基础 URL
            
        Returns:
            加密信息字典，如果没有加密则返回 None
            {
                'method': 'AES-128',
                'uri': 'https://...',
                'iv': '0x...'
            }
        """
        lines = m3u8_content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('#EXT-X-KEY'):
                # 提取加密方法
                method_match = re.search(r'METHOD=([^,\s]+)', line)
                if not method_match:
                    continue
                
                method = method_match.group(1)
                
                # 如果是 NONE，表示没有加密
                if method == 'NONE':
                    return None
                
                # 提取密钥 URI
                uri_match = re.search(r'URI="([^"]+)"', line)
                if not uri_match:
                    continue
                
                uri = uri_match.group(1)
                
                # 拼接完整 URL
                if not uri.startswith('http://') and not uri.startswith('https://'):
                    uri = urljoin(base_url, uri)
                
                # 提取 IV（可选）
                iv = None
                iv_match = re.search(r'IV=0x([0-9A-Fa-f]+)', line)
                if iv_match:
                    iv = iv_match.group(1)
                
                return {
                    'method': method,
                    'uri': uri,
                    'iv': iv
                }
        
        return None
    
    def _download_and_decrypt_segment(self, ts_url: str, session: requests.Session, 
                                     encryption_info: Optional[Dict]) -> bytes:
        """
        下载并解密单个 ts 片段
        
        Args:
            ts_url: ts 片段 URL
            session: requests.Session 对象（用于复用连接）
            encryption_info: 加密信息
            
        Returns:
            解密后的数据
        """
        # 下载 ts 片段（使用 Session）
        response = session.get(ts_url, timeout=self.timeout)
        response.raise_for_status()
        data = response.content
        
        # 验证下载数据不为空
        if not data or len(data) == 0:
            raise Exception(f"下载的数据为空，URL: {ts_url[:100]}...")
        
        # 如果没有加密，直接返回
        if not encryption_info:
            return data
        
        # 解密
        method = encryption_info['method']
        
        if method == 'AES-128':
            # 验证数据长度（AES-128 CBC模式要求数据长度必须是16的倍数）
            if len(data) % 16 != 0:
                raise Exception(
                    f"数据不完整：长度 {len(data)} bytes 不是16的倍数，"
                    f"可能是网络传输中断导致。URL: {ts_url[:100]}..."
                )
            
            # 下载密钥（使用 Session）
            key_response = session.get(encryption_info['uri'], timeout=self.timeout)
            key_response.raise_for_status()
            key = key_response.content
            
            # 验证密钥长度
            if len(key) != 16:
                raise Exception(f"密钥长度错误：期望16 bytes，实际 {len(key)} bytes")
            
            # 准备 IV
            if encryption_info['iv']:
                iv = bytes.fromhex(encryption_info['iv'])
            else:
                # 如果没有指定 IV，使用序列号作为 IV（HLS 规范）
                iv = b'\x00' * 16
            
            # 解密
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            try:
                decrypted_data = decryptor.update(data) + decryptor.finalize()
            except Exception as e:
                raise Exception(
                    f"解密失败：{str(e)}，数据长度: {len(data)} bytes，"
                    f"URL: {ts_url[:100]}..."
                )
            
            # 移除 PKCS7 填充
            padding_length = decrypted_data[-1]
            if isinstance(padding_length, int) and 1 <= padding_length <= 16:
                decrypted_data = decrypted_data[:-padding_length]
            
            return decrypted_data
        else:
            raise Exception(f"不支持的加密方式: {method}")
    
    def _validate_segment(self, segment_file: str, encryption_info: Optional[Dict]) -> Tuple[bool, str]:
        """
        验证片段完整性
        
        Args:
            segment_file: 片段文件路径
            encryption_info: 加密信息（用于验证解密）
            
        Returns:
            (is_valid, error_message) 元组
        """
        # 1. 检查文件是否存在
        if not os.path.exists(segment_file):
            return False, "文件不存在"
        
        # 2. 大小验证
        file_size = os.path.getsize(segment_file)
        if file_size == 0:
            return False, "文件大小为 0"
        
        if file_size < 1024:  # 小于 1KB 认为异常
            return False, f"文件过小: {file_size} bytes"
        
        # 3. 不进行解密验证
        # 注意：片段文件中存储的是解密后的数据，已经移除了 PKCS7 填充
        # 解密后的数据长度不一定是 16 的倍数，这是正常的
        # 因此不需要验证数据长度
        
        return True, "验证通过"
    
    def _parse_m3u8_recursive(self, m3u8_url: str, session: requests.Session, 
                              depth: int = 0, max_depth: int = 10,
                              log_callback: Optional[Callable] = None) -> Tuple[Optional[str], List[str], Optional[Dict]]:
        """
        递归解析多级 m3u8
        
        Args:
            m3u8_url: m3u8 URL
            session: requests.Session 对象（用于复用连接）
            depth: 当前递归深度
            max_depth: 最大递归深度
            log_callback: 日志回调
            
        Returns:
            (init_url, ts_urls, encryption_info) 元组
        """
        # 检查递归深度
        if depth >= max_depth:
            raise Exception(f"m3u8嵌套层级过深（超过{max_depth}层），可能存在循环引用")
        
        # 下载 m3u8 内容（使用 Session）
        m3u8_content = self._download_m3u8_content(m3u8_url, session)
        
        # 检测类型
        m3u8_type = self._detect_m3u8_type(m3u8_content)
        
        base_url = m3u8_url.rsplit('/', 1)[0] + '/'
        
        if m3u8_type == 'master':
            # Master Playlist - 提取所有码率
            logger.info(f"检测到多级m3u8（Master Playlist），开始解析码率信息")
            if log_callback:
                log_callback(f"检测到多级m3u8，开始解析")
            
            streams = self._extract_stream_info(m3u8_content, base_url)
            
            if not streams:
                raise Exception("Master Playlist 中未找到任何码率信息")
            
            logger.info(f"解析到 {len(streams)} 个可用码率")
            
            # 尝试从最高码率开始下载
            for i, stream in enumerate(streams):
                bandwidth_kb = stream['bandwidth'] // 1000
                logger.info(f"尝试码率 {bandwidth_kb}k ({stream['resolution']})")
                if log_callback:
                    log_callback(f"选择码率: {bandwidth_kb}k")
                
                try:
                    # 递归解析下一层（传递 Session）
                    return self._parse_m3u8_recursive(
                        stream['url'], 
                        session,  # 传递 Session 而不是 headers
                        depth + 1, 
                        max_depth,
                        log_callback
                    )
                except Exception as e:
                    logger.warning(f"码率 {bandwidth_kb}k 解析失败: {str(e)}")
                    
                    # 如果不是最后一个码率，尝试降级
                    if i < len(streams) - 1:
                        next_bandwidth_kb = streams[i + 1]['bandwidth'] // 1000
                        logger.info(f"降级到次高码率: {next_bandwidth_kb}k")
                        if log_callback:
                            log_callback(f"降级到码率: {next_bandwidth_kb}k")
                        continue
                    else:
                        # 所有码率都失败了
                        raise Exception(f"所有码率下载失败，最后错误: {str(e)}")
        
        else:
            # Media Playlist - 解析 ts 片段
            logger.info(f"检测到 Media Playlist，开始解析视频片段")
            
            # 解析加密信息
            encryption_info = self._parse_encryption_info(m3u8_content, base_url)
            if encryption_info:
                logger.info(f"检测到加密视频: {encryption_info['method']}")
                if log_callback:
                    log_callback(f"检测到加密视频，开始下载密钥")
            
            # 解析 ts 片段
            init_url, ts_urls = self._parse_m3u8(m3u8_content, base_url)
            
            return init_url, ts_urls, encryption_info
    
    def _download_m3u8_video(self, m3u8_url: str, save_path: str, 
                            file_name: str = '',
                            headers: Optional[Dict] = None,
                            progress_callback: Optional[Callable] = None,
                            log_callback: Optional[Callable] = None) -> Dict:
        """
        下载m3u8格式的视频
        
        Args:
            m3u8_url: m3u8地址
            save_path: 保存路径
            file_name: 文件名
            headers: 请求头（可选），如果不传则使用默认请求头
            progress_callback: 进度回调
            log_callback: 日志回调 callback(message)
            
        Returns:
            下载结果
        """
        # 创建 Session（关键优化：复用连接）
        session = requests.Session()
        
        try:
            logger.info(f"开始下载m3u8视频: {file_name}")
            if log_callback:
                log_callback(f"开始下载m3u8视频: {file_name}")
            
            # 1. 准备请求头（合并传入的和默认的）
            default_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            # 如果传入了 headers，则合并（传入的优先级更高）
            if headers:
                default_headers.update(headers)
            
            # 设置到 Session
            session.headers.update(default_headers)
            
            # 2. 递归解析 m3u8（支持多级）
            logger.info(f"开始解析m3u8: {m3u8_url}")
            if log_callback:
                log_callback(f"开始解析m3u8播放列表")
            
            init_url, ts_urls, encryption_info = self._parse_m3u8_recursive(
                m3u8_url, 
                session,  # 传入 Session
                log_callback=log_callback
            )
            
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
                    
                    # 使用 Session 下载
                    init_response = session.get(init_url, timeout=self.timeout)
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
            
            # 先扫描已下载的片段，实现断点续传（修复 bug：扫描所有片段）
            existing_segments = set()  # 使用 set 记录已下载片段的索引
            existing_files = []
            skip_count = 0
            
            for index in range(1, len(ts_urls) + 1):
                ts_file = os.path.join(temp_dir, f'segment_{index:04d}.ts')
                if os.path.exists(ts_file) and os.path.getsize(ts_file) > 0:
                    # 验证片段完整性
                    is_valid, error_msg = self._validate_segment(ts_file, encryption_info)
                    if is_valid:
                        existing_segments.add(index)
                        existing_files.append(ts_file)
                        skip_count += 1
                    else:
                        # 验证失败，删除损坏的片段
                        logger.warning(f"片段 {index} 验证失败（{error_msg}），将重新下载")
                        try:
                            os.remove(ts_file)
                        except:
                            pass
            
            if skip_count > 0:
                logger.info(f"检测到 {skip_count} 个已下载片段（已验证完整性），跳过下载")
                if log_callback:
                    log_callback(f"检测到 {skip_count} 个已下载片段，跳过下载")
            
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
            retry_stats = {}  # 记录每个片段的重试次数
            
            def download_segment(index, ts_url):
                """下载单个片段"""
                try:
                    # 添加线程启动日志
                    logger.info(f"[线程-{index}] 开始下载片段 {index}/{len(ts_urls)}")
                    if log_callback:
                        log_callback(f"  [线程-{index}] 开始下载片段 {index}/{len(ts_urls)}")
                    
                    ts_file = os.path.join(temp_dir, f'segment_{index:04d}.ts')
                    
                    # 下载ts片段（带重试、解密和验证）
                    retry_count = 0
                    max_retries = 20  # 增加最大重试次数到 20 次
                    success = False
                    last_error = None
                    
                    # 递增延迟策略：2, 5, 8, 10, 15, 20, 30, 40, 50, 60 秒，之后都是 60 秒
                    retry_delays = [2, 5, 8, 10, 15, 20, 30, 40, 50, 60]
                    
                    while retry_count < max_retries and not success:
                        try:
                            # 记录重试信息
                            if retry_count > 0:
                                delay = retry_delays[retry_count - 1] if retry_count <= len(retry_delays) else 60
                                logger.info(f"[线程-{index}] 第 {retry_count} 次重试，延迟 {delay} 秒后重试")
                                if log_callback:
                                    log_callback(f"  [线程-{index}] 第 {retry_count} 次重试（延迟 {delay}s）")
                                import time
                                time.sleep(delay)
                            
                            # 下载并解密（使用 Session）
                            data = self._download_and_decrypt_segment(ts_url, session, encryption_info)
                            
                            # 写入文件
                            with open(ts_file, 'wb') as f:
                                f.write(data)
                            
                            # 验证完整性
                            is_valid, error_msg = self._validate_segment(ts_file, encryption_info)
                            if not is_valid:
                                logger.warning(f"[线程-{index}] 完整性验证失败: {error_msg}")
                                if log_callback:
                                    log_callback(f"  [线程-{index}] 验证失败: {error_msg}")
                                raise Exception(f"完整性验证失败: {error_msg}")
                            
                            # 成功
                            success = True
                            
                            # 记录重试统计
                            if retry_count > 0:
                                with download_lock:
                                    retry_stats[index] = retry_count
                            
                            # 线程安全地更新进度
                            with download_lock:
                                completed_count[0] += 1
                                current = completed_count[0]
                            
                            # 更新进度
                            if progress_callback:
                                percentage = (current / len(ts_urls)) * 100
                                progress_callback(current * self.chunk_size, len(ts_urls) * self.chunk_size, percentage)
                            
                            # 输出成功日志
                            if retry_count > 0:
                                logger.info(f"[成功] 片段 {current}/{len(ts_urls)} 下载成功（重试 {retry_count} 次后成功，{(current/len(ts_urls)*100):.1f}%）")
                                if log_callback:
                                    log_callback(f"  [成功] 片段 {current}/{len(ts_urls)} 成功（重试 {retry_count} 次，{(current/len(ts_urls)*100):.1f}%）")
                            else:
                                logger.info(f"[成功] 片段 {current}/{len(ts_urls)} 下载成功 ({(current/len(ts_urls)*100):.1f}%)")
                                if log_callback:
                                    log_callback(f"  [成功] 片段 {current}/{len(ts_urls)} 下载成功 ({(current/len(ts_urls)*100):.1f}%)")
                            
                            return {'success': True, 'index': index, 'file': ts_file, 'retry_count': retry_count}
                            
                        except requests.exceptions.Timeout as e:
                            retry_count += 1
                            last_error = f"超时: {str(e)}"
                            
                            if retry_count >= max_retries:
                                logger.error(f"[线程-{index}] 片段 {index} 下载失败，已达最大重试次数（{max_retries}次）: {last_error}")
                                logger.error(f"[线程-{index}] 失败 URL: {ts_url[:100]}...")
                                if log_callback:
                                    log_callback(f"  [失败] 片段 {index} 下载失败（超时，已重试 {max_retries} 次）")
                                return {'success': False, 'index': index, 'error': last_error, 'url': ts_url, 'retry_count': retry_count}
                            
                            logger.warning(f"[线程-{index}] 片段 {index} 下载超时（重试 {retry_count}/{max_retries}）: {last_error}")
                            
                        except Exception as e:
                            retry_count += 1
                            last_error = str(e)
                            
                            if retry_count >= max_retries:
                                logger.error(f"[线程-{index}] 片段 {index} 下载失败，已达最大重试次数（{max_retries}次）: {last_error}")
                                logger.error(f"[线程-{index}] 失败 URL: {ts_url[:100]}...")
                                if log_callback:
                                    log_callback(f"  [失败] 片段 {index} 下载失败: {last_error[:50]}")
                                return {'success': False, 'index': index, 'error': last_error, 'url': ts_url, 'retry_count': retry_count}
                            
                            logger.warning(f"[线程-{index}] 片段 {index} 下载失败（重试 {retry_count}/{max_retries}）: {last_error}")
                    
                    # 所有重试都失败
                    logger.error(f"[线程-{index}] 片段 {index} 下载失败，已达最大重试次数")
                    return {'success': False, 'index': index, 'error': last_error or '未知错误', 'url': ts_url, 'retry_count': retry_count}
                    
                except Exception as e:
                    logger.error(f"[线程-{index}] 线程执行异常: {str(e)}", exc_info=True)
                    if log_callback:
                        log_callback(f"  [异常] 片段 {index} 线程异常: {str(e)}")
                    return {'success': False, 'index': index, 'error': str(e), 'url': ts_url, 'retry_count': 0}
            
            # 准备下载任务（只下载未下载的片段）
            download_tasks = [(index, ts_url) for index, ts_url in enumerate(ts_urls, 1) 
                            if index not in existing_segments]
            
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
                                log_callback(f"  [超时] 片段 {index} 下载超时（超过{SEGMENT_TIMEOUT//60}分钟）")
                            segment_results[index] = {'success': False, 'index': index}
                            failed_count += 1
                            future.cancel()  # 尝试取消任务
                        except Exception as e:
                            index = future_to_index[future]
                            logger.error(f"片段 {index} 下载异常: {str(e)}")
                            if log_callback:
                                log_callback(f"  [异常] 片段 {index} 下载异常: {str(e)}")
                            segment_results[index] = {'success': False, 'index': index}
                            failed_count += 1
                
                logger.info(f"所有下载任务已完成")
                if log_callback:
                    log_callback(f"所有下载任务已完成")
                
                # 输出重试统计
                if retry_stats:
                    logger.info(f"重试统计: 共 {len(retry_stats)} 个片段需要重试")
                    retry_summary = []
                    for seg_index in sorted(retry_stats.keys()):
                        retry_count = retry_stats[seg_index]
                        retry_summary.append(f"片段 {seg_index} 重试 {retry_count} 次")
                    
                    # 输出前 10 个重试片段的详情
                    for summary in retry_summary[:10]:
                        logger.info(f"  {summary}")
                    
                    if len(retry_summary) > 10:
                        logger.info(f"  ... 还有 {len(retry_summary) - 10} 个片段")
                    
                    if log_callback:
                        log_callback(f"重试统计: {len(retry_stats)} 个片段需要重试")
                else:
                    logger.info(f"所有片段一次下载成功，无需重试")
                    if log_callback:
                        log_callback(f"所有片段一次下载成功")
                    
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
        finally:
            # 关闭 Session（关键：释放资源）
            try:
                session.close()
            except:
                pass
    
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
            if log_callback:
                log_callback(f"正在解析: {episode_name}")
            
            parse_result = video_parse_service.parse_episode(episode_url, episode_name)
            
            if not parse_result.get('success'):
                error_msg = parse_result.get('message', '未知错误')
                logger.error(f"解析失败: {episode_name}, 错误: {error_msg}")
                if log_callback:
                    log_callback(f"✗ 解析失败: {episode_name} - {error_msg}")
                return {
                    'success': False,
                    'message': f"解析失败: {error_msg}",
                    'skipped': False,
                    'url': episode_url
                }
            
            download_url = parse_result.get('download_url')
            if not download_url:
                error_msg = '解析结果中未找到下载地址'
                logger.error(f"{error_msg}: {episode_name}")
                if log_callback:
                    log_callback(f"✗ {error_msg}: {episode_name}")
                return {
                    'success': False,
                    'message': error_msg,
                    'skipped': False,
                    'url': episode_url
                }
            
            logger.info(f"解析成功，开始下载: {episode_name}")
            if log_callback:
                log_callback(f"✓ 解析成功: {episode_name}")
            
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
    
    def download_episode_with_validation(self, episode_url: str, save_path: str,
                                        episode_name: str,
                                        task_config: Dict,
                                        retry_manager,
                                        progress_callback: Optional[Callable] = None,
                                        log_callback: Optional[Callable] = None) -> Dict:
        """
        下载单集并进行文件大小验证和重试管理
        
        Args:
            episode_url: 剧集官网地址
            save_path: 保存路径（完整文件路径）
            episode_name: 集数名称
            task_config: 任务配置，包含:
                - task_id: 任务ID
                - enable_file_size_check: 是否启用文件大小检查
                - min_file_size: 最小文件大小(MB)
                - enable_retry: 是否启用重试
                - max_retry_count: 最大重试次数
                - retry_interval: 重试间隔(分钟)
            retry_manager: 重试管理器实例
            progress_callback: 进度回调函数
            log_callback: 日志回调函数
        
        Returns:
            下载结果字典
        """
        try:
            # 1. 检查是否需要重试
            if task_config.get('enable_retry'):
                should_retry, current_count, reason = retry_manager.should_retry(
                    task_config['task_id'],
                    episode_url,
                    task_config['max_retry_count'],
                    task_config['retry_interval']
                )
                
                if not should_retry:
                    logger.info(f"跳过剧集 {episode_name}: {reason}")
                    if log_callback:
                        log_callback(f"跳过: {reason}")
                    
                    return {
                        'success': False,
                        'message': reason,
                        'skipped': True,
                        'retry_exhausted': True,
                        'url': episode_url
                    }
                
                # 如果有失败记录，记录重试信息
                if current_count > 0:
                    remaining = task_config['max_retry_count'] - current_count
                    logger.info(f"开始第 {current_count + 1} 次重试: {episode_name} (剩余 {remaining} 次)")
                    if log_callback:
                        log_callback(f"开始第 {current_count + 1} 次重试 (剩余 {remaining} 次)")
            
            # 2. 执行下载
            result = self.download_episode(
                episode_url, 
                save_path, 
                episode_name,
                progress_callback,
                log_callback
            )
            
            # 如果下载失败，记录失败并返回
            if not result['success']:
                if task_config.get('enable_retry'):
                    failure_count = retry_manager.record_failure(
                        task_config['task_id'],
                        episode_url,
                        episode_name,
                        result['message']
                    )
                    result['failure_count'] = failure_count
                    
                    remaining = task_config['max_retry_count'] - failure_count
                    if remaining > 0:
                        logger.info(f"下载失败，已记录失败次数: {failure_count}/{task_config['max_retry_count']}")
                        if log_callback:
                            log_callback(f"下载失败，失败次数: {failure_count}/{task_config['max_retry_count']}")
                    else:
                        logger.warning(f"下载失败，已达最大重试次数: {failure_count}/{task_config['max_retry_count']}")
                        if log_callback:
                            log_callback(f"已达最大重试次数，停止重试")
                
                return result
            
            # 如果文件已存在被跳过，清除失败记录
            if result.get('skipped'):
                if task_config.get('enable_retry'):
                    retry_manager.record_success(task_config['task_id'], episode_url)
                return result
            
            # 3. 文件大小验证
            if task_config.get('enable_file_size_check'):
                is_valid, actual_size, message = self._validate_file_size(
                    save_path,
                    task_config['min_file_size']
                )
                
                logger.info(f"文件大小验证: {episode_name}, {message}")
                if log_callback:
                    log_callback(message)
                
                if not is_valid:
                    # 删除不合格的文件
                    try:
                        if os.path.exists(save_path):
                            os.remove(save_path)
                            logger.info(f"已删除不完整文件: {episode_name}")
                            if log_callback:
                                log_callback(f"已删除不完整文件: {episode_name}")
                    except Exception as e:
                        logger.error(f"删除文件失败: {str(e)}")
                    
                    # 记录失败
                    failure_count = None
                    if task_config.get('enable_retry'):
                        failure_count = retry_manager.record_failure(
                            task_config['task_id'],
                            episode_url,
                            episode_name,
                            message
                        )
                        
                        remaining = task_config['max_retry_count'] - failure_count
                        if remaining > 0:
                            logger.info(f"文件大小验证失败，已记录失败次数: {failure_count}/{task_config['max_retry_count']}")
                            if log_callback:
                                log_callback(f"失败次数: {failure_count}/{task_config['max_retry_count']}, 剩余重试: {remaining}")
                        else:
                            logger.warning(f"文件大小验证失败，已达最大重试次数")
                            if log_callback:
                                log_callback(f"已达最大重试次数，停止重试")
                    
                    result_dict = {
                        'success': False,
                        'message': message,
                        'file_size_validation_failed': True,
                        'actual_size_mb': actual_size,
                        'skipped': False,
                        'url': episode_url
                    }
                    
                    if failure_count is not None:
                        result_dict['failure_count'] = failure_count
                    
                    return result_dict
            
            # 4. 下载成功，清除失败记录
            if task_config.get('enable_retry'):
                retry_manager.record_success(task_config['task_id'], episode_url)
                logger.info(f"下载成功，已清除失败记录: {episode_name}")
            
            return result
            
        except Exception as e:
            logger.error(f"下载验证失败: {episode_name}, 错误: {str(e)}", exc_info=True)
            
            # 记录异常失败
            if task_config.get('enable_retry'):
                failure_count = retry_manager.record_failure(
                    task_config['task_id'],
                    episode_url,
                    episode_name,
                    f'下载异常: {str(e)}'
                )
                
                return {
                    'success': False,
                    'message': f'下载异常: {str(e)}',
                    'failure_count': failure_count,
                    'skipped': False,
                    'url': episode_url
                }
            
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
            return self._download_m3u8_video(
                m3u8_url=url, 
                save_path=save_path, 
                file_name=file_name,
                headers=None,  # 使用默认请求头
                progress_callback=progress_callback, 
                log_callback=log_callback
            )
        
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
                               task_config: Optional[Dict] = None,
                               progress_callback: Optional[Callable] = None,
                               log_callback: Optional[Callable] = None,
                               regex_pattern: str = None,
                               replacement_pattern: str = None,
                               exclude_keywords: str = None) -> Dict:
        """
        下载任务的所有剧集
        
        Args:
            task_id: 任务ID
            episodes: 剧集列表
            save_directory: 最终保存目录
            task_name: 任务名称（用于创建临时目录）
            task_config: 任务配置（可选），包含:
                - enable_file_size_check: 是否启用文件大小检查
                - min_file_size: 最小文件大小(MB)
                - enable_retry: 是否启用重试
                - max_retry_count: 最大重试次数
                - retry_interval: 重试间隔(分钟)
            progress_callback: 进度回调 callback(current, total, episode_name, status)
            log_callback: 日志回调
            regex_pattern: 正则表达式（可选）
            replacement_pattern: 替换表达式（可选）
            exclude_keywords: 排除关键词（可选，用|分割）
            
        Returns:
            下载结果
        """
        total = len(episodes)
        success_count = 0
        failed_count = 0
        skipped_count = 0
        filtered_count = 0  # 被过滤的剧集数
        retry_exhausted_count = 0  # 重试耗尽的剧集数
        results = []
        
        logger.info(f"开始下载任务 {task_id} 的剧集，共 {total} 集")
        
        # 解析排除关键词
        exclude_keyword_list = []
        if exclude_keywords:
            exclude_keyword_list = [kw.strip() for kw in exclude_keywords.split('|') if kw.strip()]
            if exclude_keyword_list:
                logger.info(f"排除关键词已配置: {exclude_keyword_list}")
                if log_callback:
                    log_callback(f"排除关键词: {', '.join(exclude_keyword_list)}")
        
        # 如果提供了任务配置，记录配置信息
        if task_config:
            if task_config.get('enable_file_size_check'):
                logger.info(f"文件大小限制已启用: 最小 {task_config.get('min_file_size')}MB")
                if log_callback:
                    log_callback(f"文件大小限制: 最小 {task_config.get('min_file_size')}MB")
            
            if task_config.get('enable_retry'):
                logger.info(f"失败重试已启用: 最大 {task_config.get('max_retry_count')} 次, 间隔 {task_config.get('retry_interval')} 分钟")
                if log_callback:
                    log_callback(f"失败重试: 最大 {task_config.get('max_retry_count')} 次, 间隔 {task_config.get('retry_interval')} 分钟")
        
        # 获取临时目录配置
        from models.config import ConfigModel
        temp_base_dir = ConfigModel.get_config('video_download_temp_dir', '/app/backend/downloads/temp')
        
        # 为当前任务创建临时目录：temp_dir/任务名称/
        safe_task_name = self._sanitize_filename(task_name or f'task_{task_id}')
        temp_task_dir = os.path.join(temp_base_dir, safe_task_name)
        
        # 确保临时目录存在
        os.makedirs(temp_task_dir, exist_ok=True)
        logger.info(f"使用临时目录: {temp_task_dir}")
        if log_callback:
            log_callback(f"临时下载目录: {temp_task_dir}")
        
        # 初始化重试管理器（如果启用了重试）
        retry_mgr = None
        if task_config and task_config.get('enable_retry'):
            from services.retry_manager import retry_manager
            retry_mgr = retry_manager
        
        for index, episode in enumerate(episodes, 1):
            episode_name = episode.get('name', f'第{index}集')
            episode_title = episode.get('title', '')
            episode_url = episode.get('url', '')
            
            # 构建完整的显示名称（与前端显示一致）
            if episode_title:
                full_name = f"{episode_name} - {episode_title}"
            else:
                full_name = episode_name
            
            # 检查是否包含排除关键词
            if exclude_keyword_list:
                should_skip = False
                matched_keyword = None
                for keyword in exclude_keyword_list:
                    if keyword in full_name:
                        should_skip = True
                        matched_keyword = keyword
                        break
                
                if should_skip:
                    filtered_count += 1
                    logger.info(f"剧集被过滤（包含关键词'{matched_keyword}'）: {full_name}")
                    if log_callback:
                        log_callback(f"跳过: {full_name} (包含关键词'{matched_keyword}')")
                    
                    results.append({
                        'name': full_name,
                        'success': True,
                        'message': f'已过滤（包含关键词: {matched_keyword}）',
                        'skipped': True,
                        'filtered': True
                    })
                    
                    if progress_callback:
                        progress_callback(index, total, full_name, 'filtered')
                    
                    continue
            
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
                # 如果启用了文件大小检查，使用配置的阈值；否则使用默认的1MB
                min_size_bytes = 1024 * 1024  # 默认1MB
                if task_config and task_config.get('enable_file_size_check'):
                    min_size_bytes = task_config.get('min_file_size', 100) * 1024 * 1024
                
                if file_size > min_size_bytes:
                    skipped_count += 1
                    results.append({
                        'name': full_name,
                        'success': True,
                        'message': '文件已存在，跳过下载',
                        'skipped': True
                    })
                    if progress_callback:
                        progress_callback(index, total, full_name, 'skipped')
                    
                    # 清除失败记录（如果有）
                    if retry_mgr:
                        retry_mgr.record_success(task_id, episode_url)
                    
                    continue
            
            # 下载剧集到临时目录
            def episode_progress(downloaded, total_size, percentage):
                if progress_callback:
                    progress_callback(
                        index, total, full_name, 'downloading',
                        downloaded, total_size, percentage
                    )
            
            # 根据是否有任务配置选择下载方法
            if task_config and (task_config.get('enable_file_size_check') or task_config.get('enable_retry')):
                # 使用带验证的下载方法
                config_with_id = task_config.copy()
                config_with_id['task_id'] = task_id
                
                result = self.download_episode_with_validation(
                    episode_url,
                    temp_file_path,
                    full_name,
                    config_with_id,
                    retry_mgr,
                    episode_progress,
                    log_callback
                )
            else:
                # 使用原有的下载方法
                result = self.download_episode(
                    episode_url, 
                    temp_file_path,
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
                        
                        # 应用正则替换（如果配置了）
                        final_safe_name = safe_name
                        if regex_pattern:
                            try:
                                from utils.filename_replacer import FilenameReplacer
                                # 对文件名（不含扩展名）应用正则替换
                                success, new_name, msg = FilenameReplacer.apply_regex_replacement(
                                    safe_name, regex_pattern, replacement_pattern or ''
                                )
                                if success and new_name != safe_name:
                                    final_safe_name = self._sanitize_filename(new_name)
                                    logger.info(f"正则替换: {safe_name} -> {final_safe_name}")
                                    if log_callback:
                                        log_callback(f"文件名替换: {safe_name} -> {final_safe_name}")
                            except Exception as e:
                                logger.warning(f"正则替换失败: {str(e)}, 使用原文件名")
                        
                        # 最终文件路径
                        final_file_path = os.path.join(save_directory, f"{final_safe_name}.mp4")
                        
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
                # 检查是否是重试耗尽
                if result.get('retry_exhausted'):
                    retry_exhausted_count += 1
                    logger.warning(f"剧集已达最大重试次数，跳过: {full_name}")
                    if log_callback:
                        log_callback(f"跳过: {full_name} (已达最大重试次数)")
                else:
                    failed_count += 1
                    # 记录详细的失败原因（包含URL）
                    error_msg = result.get('message', '未知错误')
                    logger.error(f"下载失败: {full_name}, URL: {episode_url}, 原因: {error_msg}")
                    
                    # 如果是文件大小验证失败，记录详细信息
                    if result.get('file_size_validation_failed'):
                        actual_size = result.get('actual_size_mb', 0)
                        logger.warning(f"文件大小不足: {full_name}, 实际: {actual_size}MB")
                        if log_callback:
                            log_callback(f"文件大小不足: 实际 {actual_size}MB")
                    
                    # 如果有失败次数信息，记录
                    if 'failure_count' in result and task_config and task_config.get('enable_retry'):
                        failure_count = result['failure_count']
                        max_count = task_config.get('max_retry_count', 3)
                        remaining = max_count - failure_count
                        logger.info(f"失败次数: {failure_count}/{max_count}, 剩余重试: {remaining}")
                        if log_callback:
                            log_callback(f"失败次数: {failure_count}/{max_count}, 剩余: {remaining}")
                    
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
        
        # 输出统计信息
        logger.info(f"任务 {task_id} 下载完成: 成功 {success_count}/{total}, 跳过 {skipped_count}, 过滤 {filtered_count}, 失败 {failed_count}, 重试耗尽 {retry_exhausted_count}")
        
        if log_callback:
            log_callback(f"下载完成: 成功 {success_count}, 跳过 {skipped_count}, 过滤 {filtered_count}, 失败 {failed_count}")
            if retry_exhausted_count > 0:
                log_callback(f"重试耗尽: {retry_exhausted_count} 个剧集已达最大重试次数")
        
        # 判断任务是否成功：只有当没有失败的剧集时才算成功
        # 重试耗尽的剧集不计入失败（它们会在下次执行时继续被跳过）
        is_success = failed_count == 0 and (success_count + skipped_count + filtered_count) > 0
        
        return {
            'success': is_success,
            'total': total,
            'success_count': success_count,
            'skipped_count': skipped_count,
            'filtered_count': filtered_count,
            'failed_count': failed_count,
            'retry_exhausted_count': retry_exhausted_count,
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

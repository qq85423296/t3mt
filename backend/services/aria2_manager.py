# -*- coding: utf-8 -*-
"""
Aria2进程管理模块
负责Aria2进程的启动、停止和健康检查
"""
import os
import sys
import platform
import subprocess
import time
import atexit
from utils.logger import logger


class Aria2Manager:
    """Aria2进程管理器"""
    
    def __init__(self):
        self.process = None
        self.rpc_url = 'http://127.0.0.1:6800/jsonrpc'
        self.rpc_port = 6800
        self.download_dir = None
        self.aria2_config = {}
        
    def _get_aria2_executable(self):
        """获取Aria2可执行文件路径"""
        system = platform.system()
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 优先尝试使用系统安装的aria2c（支持多架构）
        try:
            result = subprocess.run(['which', 'aria2c'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                system_aria2 = result.stdout.strip()
                logger.info(f"找到系统安装的Aria2: {system_aria2}")
                return system_aria2
        except Exception as e:
            logger.debug(f"未找到系统安装的Aria2: {e}")
        
        # 如果系统没有安装，使用内置的aria2c
        if system == 'Windows':
            aria2_path = os.path.join(base_dir, 'bin', 'aria2', 'windows', 'aria2c.exe')
        elif system == 'Linux':
            aria2_path = os.path.join(base_dir, 'bin', 'aria2', 'linux', 'aria2c')
        else:
            # macOS或其他系统
            aria2_path = 'aria2c'
        
        logger.info(f"尝试使用内置Aria2: {aria2_path}")
        
        # 检查文件是否存在
        if os.path.exists(aria2_path):
            logger.info(f"内置Aria2文件存在: {aria2_path}")
            
            # Linux下检查并设置执行权限
            if system == 'Linux':
                # 检查当前权限
                import stat
                file_stat = os.stat(aria2_path)
                current_mode = oct(file_stat.st_mode)
                logger.info(f"内置Aria2文件当前权限: {current_mode}")
                
                # 检查是否有执行权限
                if not os.access(aria2_path, os.X_OK):
                    logger.warning(f"内置Aria2文件没有执行权限，尝试设置...")
                    try:
                        os.chmod(aria2_path, 0o755)
                        logger.info(f"已设置内置Aria2执行权限: 0o755")
                    except Exception as chmod_err:
                        logger.error(f"设置执行权限失败: {chmod_err}")
                else:
                    logger.info(f"内置Aria2文件已有执行权限")
                
                # 尝试执行测试（检查架构兼容性）
                try:
                    test_result = subprocess.run([aria2_path, '--version'], 
                                               capture_output=True, 
                                               timeout=5)
                    if test_result.returncode == 0:
                        logger.info(f"内置Aria2可执行，架构兼容")
                        return aria2_path
                    else:
                        logger.warning(f"内置Aria2执行失败，可能架构不兼容")
                except Exception as test_err:
                    logger.warning(f"内置Aria2测试失败: {test_err}，可能架构不兼容")
            else:
                return aria2_path
        
        # 最后尝试从PATH查找
        logger.warning(f"内置Aria2不可用，尝试使用系统PATH中的aria2c")
        return 'aria2c'
    
    def _load_config(self):
        """从数据库加载Aria2配置（只使用云盘下载配置）"""
        try:
            from database import get_db
            
            with get_db() as conn:
                cursor = conn.cursor()
                
                # 只读取云盘下载配置（每文件线程数、每线程分块大小）
                cursor.execute("""
                    SELECT config_key, config_value 
                    FROM system_config 
                    WHERE config_key IN ('download_threads_per_file', 'download_multithread_chunk_size')
                """)
                cloud_configs = cursor.fetchall()
                
                # 映射云盘配置到Aria2配置
                for config in cloud_configs:
                    if config['config_key'] == 'download_threads_per_file':
                        # 每文件线程数 -> split
                        threads = int(config['config_value'])
                        self.aria2_config['split'] = str(threads)
                        logger.info(f"从云盘配置读取线程数: {threads}")
                    elif config['config_key'] == 'download_multithread_chunk_size':
                        # 每线程分块大小 -> min_split_size
                        chunk_size = int(config['config_value'])
                        self.aria2_config['min_split_size'] = f"{chunk_size}M"
                        logger.info(f"从云盘配置读取分块大小: {chunk_size}M")
                
                # 设置默认值（如果没有配置）
                self.aria2_config.setdefault('split', '16')
                self.aria2_config.setdefault('min_split_size', '1M')
                self.aria2_config.setdefault('max_concurrent_downloads', '1')  # 串行下载
                self.aria2_config.setdefault('max_connection_per_server', '16')
                
                logger.info(f"已加载Aria2配置: {self.aria2_config}")
                
        except Exception as e:
            logger.warning(f"加载Aria2配置失败，使用默认配置: {e}")
            # 使用默认配置
            self.aria2_config = {
                'max_concurrent_downloads': '1',  # 串行下载
                'split': '16',
                'min_split_size': '1M',
                'max_connection_per_server': '16'
            }
    
    def _get_download_dir(self):
        """获取下载目录"""
        try:
            from config import Config
            download_dir = Config.DOWNLOAD_DIR
            
            # 确保目录存在
            if not os.path.exists(download_dir):
                os.makedirs(download_dir)
            
            return download_dir
        except Exception as e:
            logger.error(f"获取下载目录失败: {e}")
            # 使用默认目录
            default_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'downloads')
            if not os.path.exists(default_dir):
                os.makedirs(default_dir)
            return default_dir
    
    def _kill_existing_aria2(self):
        """杀掉已存在的Aria2进程（避免端口冲突）"""
        try:
            system = platform.system()
            
            if system == 'Windows':
                # Windows下使用taskkill
                subprocess.run(['taskkill', '/F', '/IM', 'aria2c.exe'], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE,
                             timeout=5)
                logger.info("已清理残留的Aria2进程（Windows）")
            else:
                # Linux下使用pkill
                subprocess.run(['pkill', '-9', 'aria2c'], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE,
                             timeout=5)
                logger.info("已清理残留的Aria2进程（Linux）")
            
            # 等待端口释放
            time.sleep(1)
            
        except Exception as e:
            logger.debug(f"清理Aria2进程: {e}")
    
    def start(self):
        """启动Aria2进程"""
        if self.is_running():
            logger.info("Aria2进程已在运行")
            return True
        
        try:
            # 先清理可能残留的Aria2进程
            self._kill_existing_aria2()
            
            # 加载配置
            self._load_config()
            
            # 获取下载目录
            self.download_dir = self._get_download_dir()
            logger.info(f"Aria2下载目录: {self.download_dir}")
            
            # 获取可执行文件路径（会自动检查和设置权限）
            aria2_exe = self._get_aria2_executable()
            
            # 检查可执行文件是否可用
            if aria2_exe != 'aria2c' and not os.path.exists(aria2_exe):
                logger.error(f"Aria2可执行文件不存在: {aria2_exe}")
                return False
            
            # 构建启动参数
            args = [
                aria2_exe,
                '--enable-rpc',
                f'--rpc-listen-port={self.rpc_port}',
                f'--dir={self.download_dir}',
                '--continue=true',  # 支持断点续传
                f'--max-concurrent-downloads={self.aria2_config.get("max_concurrent_downloads", "3")}',
                f'--split={self.aria2_config.get("split", "16")}',
                f'--min-split-size={self.aria2_config.get("min_split_size", "10M")}',
                f'--max-connection-per-server={self.aria2_config.get("max_connection_per_server", "16")}',
                '--auto-file-renaming=false',  # 禁用自动重命名
                '--allow-overwrite=false',  # 禁止覆盖已存在文件
            ]
            
            logger.info(f"启动Aria2进程，命令: {' '.join(args)}")
            
            # 启动进程
            if platform.system() == 'Windows':
                # Windows下不捕获输出，让Aria2正常运行
                self.process = subprocess.Popen(
                    args,
                    creationflags=subprocess.CREATE_NO_WINDOW  # 不创建新窗口
                )
            else:
                # Linux下捕获stderr用于诊断
                self.process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            
            logger.info(f"Aria2进程已启动，PID: {self.process.pid}，等待2秒...")
            
            # 等待进程启动
            time.sleep(2)
            
            # 检查进程是否正常运行
            poll_result = self.process.poll()
            if poll_result is not None:
                # 进程已退出，读取错误信息
                logger.error(f"Aria2进程启动后立即退出，退出码: {poll_result}")
                try:
                    stdout, stderr = self.process.communicate(timeout=1)
                    if stdout:
                        stdout_msg = stdout.decode('utf-8', errors='ignore')
                        logger.error(f"Aria2 stdout: {stdout_msg}")
                    if stderr:
                        stderr_msg = stderr.decode('utf-8', errors='ignore')
                        logger.error(f"Aria2 stderr: {stderr_msg}")
                except Exception as comm_err:
                    logger.error(f"读取Aria2输出失败: {comm_err}")
                return False
            
            # 注册退出时的清理函数
            atexit.register(self.stop)
            
            logger.info(f"Aria2进程启动成功，PID: {self.process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"启动Aria2进程失败: {e}", exc_info=True)
            return False
    
    def stop(self):
        """停止Aria2进程"""
        if self.process is None:
            return
        
        try:
            logger.info("正在停止Aria2进程...")
            
            # 尝试优雅关闭
            self.process.terminate()
            
            # 等待最多5秒
            try:
                self.process.wait(timeout=5)
                logger.info("Aria2进程已正常关闭")
            except subprocess.TimeoutExpired:
                # 强制关闭
                logger.warning("Aria2进程未响应，强制关闭")
                self.process.kill()
                self.process.wait()
                logger.info("Aria2进程已强制关闭")
            
            self.process = None
            
        except Exception as e:
            logger.error(f"停止Aria2进程失败: {e}", exc_info=True)
    
    def is_running(self):
        """检查Aria2进程是否在运行"""
        if self.process is None:
            return False
        
        # 检查进程是否还在运行
        return self.process.poll() is None
    
    def restart(self):
        """重启Aria2进程"""
        logger.info("重启Aria2进程...")
        self.stop()
        time.sleep(1)
        return self.start()
    
    def get_rpc_url(self):
        """获取RPC URL"""
        return self.rpc_url


# 全局Aria2管理器实例
aria2_manager = Aria2Manager()

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
        
        if system == 'Windows':
            aria2_path = os.path.join(base_dir, 'bin', 'aria2', 'windows', 'aria2c.exe')
        elif system == 'Linux':
            aria2_path = os.path.join(base_dir, 'bin', 'aria2', 'linux', 'aria2c')
        else:
            # macOS或其他系统，尝试从PATH查找
            aria2_path = 'aria2c'
        
        # 检查文件是否存在
        if os.path.exists(aria2_path):
            # Linux下确保有执行权限
            if system == 'Linux':
                os.chmod(aria2_path, 0o755)
            return aria2_path
        else:
            logger.warning(f"Aria2可执行文件不存在: {aria2_path}，尝试使用系统PATH")
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
            
            # 获取可执行文件路径
            aria2_exe = self._get_aria2_executable()
            
            # 构建启动参数（简化版，移除可能导致RPC超时的参数）
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
            
            logger.info(f"启动Aria2进程: {' '.join(args)}")
            
            # 启动进程
            if platform.system() == 'Windows':
                # Windows下不捕获输出，让Aria2正常运行
                self.process = subprocess.Popen(
                    args,
                    creationflags=subprocess.CREATE_NO_WINDOW  # 不创建新窗口
                )
            else:
                # Linux下正常启动
                self.process = subprocess.Popen(
                    args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            # 等待进程启动
            time.sleep(2)
            
            # 检查进程是否正常运行
            if self.process.poll() is not None:
                # 进程已退出
                logger.error(f"Aria2进程启动后立即退出")
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

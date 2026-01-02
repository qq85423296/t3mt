# -*- coding: utf-8 -*-
"""
配置文件
"""
import os

class Config:
    """应用配置"""
    
    # 应用配置
    # 使用固定的SECRET_KEY,避免重启后Session失效
    SECRET_KEY = 'quark_manager_secret_key_2024_fixed'
    DEBUG = True
    
    # Session配置
    SESSION_COOKIE_SAMESITE = None  # 允许跨域携带Cookie
    SESSION_COOKIE_SECURE = False  # 开发环境不使用HTTPS
    SESSION_COOKIE_HTTPONLY = False  # 允许JavaScript访问（开发环境）
    SESSION_COOKIE_DOMAIN = None  # 不限制域名
    SESSION_COOKIE_PATH = '/'  # Cookie路径
    PERMANENT_SESSION_LIFETIME = 86400  # Session有效期24小时（秒）
    
    # 数据库配置
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'quark_manager.db')
    
    # 服务器配置
    HOST = '0.0.0.0'  # 监听所有网络接口，允许外部访问
    PORT = 8520  # 用户端端口
    
    # API基础URL（用于内部服务间调用）
    # 在服务器上部署时，使用实际的服务器地址
    API_BASE_URL = 'http://127.0.0.1:8520'  # 本地回环地址，用于后端内部调用
    
    # 日志配置
    LOG_LEVEL = 'INFO'
    LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
    
    # 下载配置
    DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), 'downloads')
    MAX_CONCURRENT_DOWNLOADS = 3  # 最大并发下载任务数
    CHUNK_SIZE = 2 * 1024 * 1024  # 2MB 每次下载块大小
    RETRY_TIMES = 3  # 下载失败重试次数
    RETRY_DELAY = 5  # 重试延迟（秒）
    TIMEOUT = 30  # 请求超时（秒）
    
    # 多线程下载配置
    ENABLE_MULTITHREAD_DOWNLOAD = True  # 启用单文件多线程下载
    MULTITHREAD_THRESHOLD = 50 * 1024 * 1024  # 50MB，超过此大小启用多线程下载
    THREADS_PER_FILE = 4  # 每个文件的下载线程数（建议 4-8）
    MULTITHREAD_CHUNK_SIZE = 10 * 1024 * 1024  # 10MB，每个线程下载的块大小
    
    # 夸克API配置 - 从加密配置中读取
    _quark_config_cache = None
    
    @classmethod
    def _load_quark_config(cls):
        """从加密配置中加载夸克API配置"""
        if cls._quark_config_cache is not None:
            return cls._quark_config_cache
        
        from utils.config_crypto import config_crypto
        from utils.logger import logger
        
        quark_config = config_crypto.get_config('quark_api', {})
        
        if not quark_config:
            error_msg = "夸克API配置未加载,请联系管理员获取配置"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 验证必需的配置项
        required_keys = ['base_url', 'base_url_app', 'user_agent']
        missing_keys = [key for key in required_keys if key not in quark_config]
        if missing_keys:
            error_msg = f"夸克API配置缺少必需项: {', '.join(missing_keys)},请联系管理员"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        cls._quark_config_cache = quark_config
        logger.info("夸克API配置加载成功")
        return quark_config

# 动态设置夸克API配置属性
try:
    _quark_cfg = Config._load_quark_config()
    Config.QUARK_BASE_URL = _quark_cfg['base_url']
    Config.QUARK_BASE_URL_APP = _quark_cfg['base_url_app']
    Config.QUARK_USER_AGENT = _quark_cfg['user_agent']
except Exception as e:
    # 配置加载失败时,设置为None,让服务在使用时报错
    Config.QUARK_BASE_URL = None
    Config.QUARK_BASE_URL_APP = None
    Config.QUARK_USER_AGENT = None
    print(f"警告: 夸克API配置加载失败: {e}")


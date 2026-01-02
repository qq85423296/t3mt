# -*- coding: utf-8 -*-
"""
日志工具
"""
import logging
import os
from datetime import datetime
from config import Config


class Logger:
    """日志管理类"""
    
    _loggers = {}
    
    @staticmethod
    def get_logger(name='app'):
        """获取日志记录器"""
        if name in Logger._loggers:
            return Logger._loggers[name]
        
        # 创建日志目录
        if not os.path.exists(Config.LOG_DIR):
            os.makedirs(Config.LOG_DIR)
        
        # 创建logger
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, Config.LOG_LEVEL))
        
        # 避免重复添加handler
        if logger.handlers:
            return logger
        
        # 创建文件handler
        log_file = os.path.join(
            Config.LOG_DIR, 
            f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 创建控制台handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 创建formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加handler
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        Logger._loggers[name] = logger
        return logger


# 创建默认logger
logger = Logger.get_logger()

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
    def get_logger(name='app', cloud_type=None):
        """
        获取日志记录器
        
        Args:
            name: 日志记录器名称
            cloud_type: 云盘类型（可选），用于区分不同云盘的日志
        
        Returns:
            logger: 日志记录器实例
        """
        # 如果指定了cloud_type，将其添加到logger名称中
        if cloud_type:
            logger_name = f"{name}_{cloud_type}"
        else:
            logger_name = name
            
        if logger_name in Logger._loggers:
            return Logger._loggers[logger_name]
        
        # 创建日志目录
        if not os.path.exists(Config.LOG_DIR):
            os.makedirs(Config.LOG_DIR)
        
        # 创建logger
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, Config.LOG_LEVEL))
        
        # 避免重复添加handler
        if logger.handlers:
            return logger
        
        # 创建文件handler
        log_file = os.path.join(
            Config.LOG_DIR, 
            f"{logger_name}_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 创建控制台handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 创建formatter - 包含cloud_type信息
        if cloud_type:
            formatter = logging.Formatter(
                f'%(asctime)s - %(name)s - [{cloud_type}] - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加handler
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        Logger._loggers[logger_name] = logger
        return logger


# 创建默认logger
logger = Logger.get_logger()

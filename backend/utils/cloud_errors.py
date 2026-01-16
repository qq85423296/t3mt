# -*- coding: utf-8 -*-
"""
云盘服务统一错误处理
定义云盘服务相关的异常类
"""


class CloudServiceError(Exception):
    """云盘服务基础异常类"""
    
    def __init__(self, message, cloud_type=None, error_code=None):
        """
        初始化异常
        
        Args:
            message: 错误消息
            cloud_type: 云盘类型
            error_code: 错误码
        """
        self.message = message
        self.cloud_type = cloud_type
        self.error_code = error_code
        super().__init__(self.message)
    
    def __str__(self):
        if self.cloud_type:
            return f"[{self.cloud_type}] {self.message}"
        return self.message


class AuthenticationError(CloudServiceError):
    """认证失败异常"""
    pass


class InvalidCookieError(AuthenticationError):
    """Cookie无效或过期异常"""
    pass


class PermissionDeniedError(CloudServiceError):
    """权限不足异常"""
    pass


class ResourceNotFoundError(CloudServiceError):
    """资源不存在异常"""
    pass


class QuotaExceededError(CloudServiceError):
    """配额超限异常"""
    pass


class NetworkError(CloudServiceError):
    """网络请求异常"""
    pass


class APIError(CloudServiceError):
    """API调用异常"""
    
    def __init__(self, message, cloud_type=None, error_code=None, response=None):
        """
        初始化API异常
        
        Args:
            message: 错误消息
            cloud_type: 云盘类型
            error_code: 错误码
            response: API响应对象
        """
        super().__init__(message, cloud_type, error_code)
        self.response = response


class TaskTimeoutError(CloudServiceError):
    """任务超时异常"""
    pass


class ConflictError(CloudServiceError):
    """文件冲突异常"""
    pass


class InvalidParameterError(CloudServiceError):
    """参数无效异常"""
    pass


def handle_cloud_error(func):
    """
    云盘服务错误处理装饰器
    
    用法:
        @handle_cloud_error
        def some_cloud_operation():
            # 云盘操作代码
            pass
    """
    from functools import wraps
    from utils.logger import logger
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except CloudServiceError as e:
            # 云盘服务异常，记录日志并重新抛出
            logger.error(f"云盘服务异常: {e}", exc_info=True)
            raise
        except Exception as e:
            # 其他异常，包装为CloudServiceError
            logger.error(f"未预期的异常: {e}", exc_info=True)
            raise CloudServiceError(f"操作失败: {str(e)}") from e
    
    return wrapper

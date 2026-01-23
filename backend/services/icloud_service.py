# -*- coding: utf-8 -*-
"""
云盘服务统一接口
定义所有云盘服务必须实现的抽象方法
"""
from abc import ABC, abstractmethod


class ICloudService(ABC):
    """云盘服务统一接口"""
    
    @abstractmethod
    def get_account_info(self):
        """
        获取账号信息
        
        Returns:
            dict: 账号信息，包含nickname, total_capacity, use_capacity等字段
        """
        pass
    
    @abstractmethod
    def get_file_list(self, folder_id, page=1, size=50):
        """
        获取文件列表
        
        Args:
            folder_id: 文件夹ID
            page: 页码
            size: 每页数量
        
        Returns:
            dict: 文件列表响应
        """
        pass
    
    def list_files(self, folder_id):
        """
        获取文件列表(简化版本,供TaskExecutor使用)
        
        Args:
            folder_id: 文件夹ID
        
        Returns:
            list: 文件列表,每个元素包含统一的字段(id, name, isFolder, size等)
                  如果失败返回None
        """
        result = self.get_file_list(folder_id=folder_id, page=1, size=100)
        if result.get('code') == 0:
            return result.get('data', {}).get('list', [])
        return None
    
    @abstractmethod
    def mkdir(self, folder_name, parent_id):
        """
        创建文件夹
        
        Args:
            folder_name: 文件夹名称
            parent_id: 父文件夹ID
        
        Returns:
            dict: 创建结果
        """
        pass
    
    @abstractmethod
    def delete(self, file_ids):
        """
        删除文件/文件夹
        
        Args:
            file_ids: 文件ID列表
        
        Returns:
            dict: 删除结果
        """
        pass
    
    @abstractmethod
    def rename(self, file_id, new_name):
        """
        重命名文件/文件夹
        
        Args:
            file_id: 文件ID
            new_name: 新名称
        
        Returns:
            dict: 重命名结果
        """
        pass
    
    @abstractmethod
    def create_share(self, file_ids, expire_days, need_password, password):
        """
        创建分享链接
        
        Args:
            file_ids: 文件ID列表
            expire_days: 有效期天数
            need_password: 是否需要密码
            password: 分享密码
        
        Returns:
            dict: 分享链接信息
        """
        pass
    
    @abstractmethod
    def get_download_url(self, file_ids):
        """
        获取下载链接
        
        Args:
            file_ids: 文件ID列表
        
        Returns:
            tuple: (result_dict, cookie_str)
        """
        pass
    
    def prepare_download_headers(self, file_id: str) -> dict:
        """
        准备下载请求头（不同云盘有不同的认证方式）
        
        Args:
            file_id: 文件ID
        
        Returns:
            dict: 下载请求头
        """
        # 默认实现：返回空字典
        # 子类可以重写此方法以提供特定的认证信息
        return {}
    
    @abstractmethod
    def parse_share_url(self, url):
        """
        解析分享链接
        
        Args:
            url: 分享链接
        
        Returns:
            tuple: 解析结果（格式因云盘类型而异）
        """
        pass
    
    @abstractmethod
    def save_share(self, share_url, target_folder_id, password):
        """
        转存分享文件
        
        Args:
            share_url: 分享链接
            target_folder_id: 目标文件夹ID
            password: 分享密码
        
        Returns:
            dict: 转存结果
        """
        pass

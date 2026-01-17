# -*- coding: utf-8 -*-
"""
插件注册中心

管理所有已启动插件的实例，提供插件查询和获取功能。
使用线程锁保证并发安全。
"""
import threading
from typing import Dict, List, Optional, Type
from plugins.base_plugin import BasePlugin


class PluginRegistry:
    """
    插件注册中心
    
    管理所有已启动插件的类引用，提供线程安全的注册、注销和查询功能。
    
    使用示例:
        >>> PluginRegistry.register('email_notify', EmailNotifyPlugin)
        >>> plugin_class = PluginRegistry.get('email_notify')
        >>> plugin = plugin_class(config, context)
        >>> plugin.execute()
    """
    
    # 存储插件类引用 {plugin_id: plugin_class}
    _plugins: Dict[str, Type[BasePlugin]] = {}
    
    # 存储插件元信息 {plugin_id: meta_info}
    _plugin_meta: Dict[str, dict] = {}
    
    # 线程锁，保证并发安全
    _lock = threading.Lock()
    
    @classmethod
    def register(cls, plugin_id: str, plugin_class: Type[BasePlugin], 
                 meta_info: dict = None) -> bool:
        """
        注册插件
        
        Args:
            plugin_id: 插件唯一标识
            plugin_class: 插件类（必须是 BasePlugin 的子类）
            meta_info: 插件元信息（可选）
        
        Returns:
            bool: 注册是否成功
        
        Raises:
            ValueError: 如果 plugin_class 不是 BasePlugin 的子类
        """
        # 验证插件类
        if not isinstance(plugin_class, type) or not issubclass(plugin_class, BasePlugin):
            raise ValueError(f"插件类必须是 BasePlugin 的子类: {plugin_class}")
        
        with cls._lock:
            if plugin_id in cls._plugins:
                # 已存在，更新
                cls._plugins[plugin_id] = plugin_class
                if meta_info:
                    cls._plugin_meta[plugin_id] = meta_info
                return True
            
            cls._plugins[plugin_id] = plugin_class
            if meta_info:
                cls._plugin_meta[plugin_id] = meta_info
            return True
    
    @classmethod
    def unregister(cls, plugin_id: str) -> bool:
        """
        注销插件
        
        Args:
            plugin_id: 插件唯一标识
        
        Returns:
            bool: 注销是否成功（如果插件不存在返回 False）
        """
        with cls._lock:
            if plugin_id not in cls._plugins:
                return False
            
            del cls._plugins[plugin_id]
            cls._plugin_meta.pop(plugin_id, None)
            return True
    
    @classmethod
    def get(cls, plugin_id: str) -> Optional[Type[BasePlugin]]:
        """
        获取插件类
        
        Args:
            plugin_id: 插件唯一标识
        
        Returns:
            插件类，如果不存在返回 None
        """
        with cls._lock:
            return cls._plugins.get(plugin_id)
    
    @classmethod
    def get_meta(cls, plugin_id: str) -> Optional[dict]:
        """
        获取插件元信息
        
        Args:
            plugin_id: 插件唯一标识
        
        Returns:
            插件元信息字典，如果不存在返回 None
        """
        with cls._lock:
            return cls._plugin_meta.get(plugin_id)
    
    @classmethod
    def is_registered(cls, plugin_id: str) -> bool:
        """
        检查插件是否已注册
        
        Args:
            plugin_id: 插件唯一标识
        
        Returns:
            bool: 插件是否已注册
        """
        with cls._lock:
            return plugin_id in cls._plugins
    
    @classmethod
    def get_all_plugin_ids(cls) -> List[str]:
        """
        获取所有已注册的插件ID列表
        
        Returns:
            list: 插件ID列表
        """
        with cls._lock:
            return list(cls._plugins.keys())
    
    @classmethod
    def get_active_plugins(cls) -> List[dict]:
        """
        获取所有已注册插件的信息列表
        
        Returns:
            list: 插件信息列表，每项包含 plugin_id 和 meta_info
        """
        with cls._lock:
            result = []
            for plugin_id, plugin_class in cls._plugins.items():
                info = {
                    'plugin_id': plugin_id,
                    'plugin_class': plugin_class.__name__,
                    'meta_info': cls._plugin_meta.get(plugin_id, {})
                }
                result.append(info)
            return result
    
    @classmethod
    def count(cls) -> int:
        """
        获取已注册插件数量
        
        Returns:
            int: 插件数量
        """
        with cls._lock:
            return len(cls._plugins)
    
    @classmethod
    def clear(cls) -> int:
        """
        清空所有已注册的插件
        
        Returns:
            int: 被清除的插件数量
        """
        with cls._lock:
            count = len(cls._plugins)
            cls._plugins.clear()
            cls._plugin_meta.clear()
            return count
    
    @classmethod
    def create_instance(cls, plugin_id: str, plugin_config: dict = None,
                       task_context: dict = None) -> Optional[BasePlugin]:
        """
        创建插件实例
        
        便捷方法，获取插件类并创建实例。
        
        Args:
            plugin_id: 插件唯一标识
            plugin_config: 插件配置
            task_context: 任务上下文
        
        Returns:
            插件实例，如果插件不存在返回 None
        """
        plugin_class = cls.get(plugin_id)
        if plugin_class is None:
            return None
        
        return plugin_class(
            plugin_config=plugin_config or {},
            task_context=task_context or {}
        )

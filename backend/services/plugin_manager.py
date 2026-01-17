# -*- coding: utf-8 -*-
"""
插件管理器

负责插件的安装、卸载、导入、导出等生命周期管理。
"""
import os
import re
import json
import shutil
import zipfile
import tempfile
import importlib.util
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from models.plugin import PluginInfo, TaskPluginRelation, PluginExecLog, cascade_delete_plugin
from services.plugin_registry import PluginRegistry
from plugins.base_plugin import BasePlugin


class PluginManager:
    """
    插件管理器
    
    负责插件的完整生命周期管理，包括：
    - 安装/卸载
    - 启动/停止
    - 导入/导出
    - 配置管理
    """
    
    # 插件存储目录（相对于 backend 目录）
    PLUGIN_DIR = "plugins"
    
    # 必需的文件
    REQUIRED_FILES = ["plugin_meta.json", "backend/main.py"]
    
    # 插件ID格式正则（只允许字母、数字、下划线）
    PLUGIN_ID_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*$')
    
    # 版本号格式正则（语义化版本）
    VERSION_PATTERN = re.compile(r'^\d+\.\d+\.\d+$')
    
    @classmethod
    def get_plugin_base_dir(cls) -> str:
        """获取插件基础目录的绝对路径"""
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(backend_dir, cls.PLUGIN_DIR)
    
    @classmethod
    def get_plugin_dir(cls, plugin_id: str) -> str:
        """获取指定插件的目录路径"""
        return os.path.join(cls.get_plugin_base_dir(), plugin_id)
    
    # ==================== 插件包校验 ====================
    
    @classmethod
    def validate_package(cls, zip_data: bytes) -> dict:
        """
        校验插件包结构
        
        Args:
            zip_data: 插件包二进制数据
        
        Returns:
            {
                "valid": bool,
                "errors": list,  # 错误信息列表
                "meta": dict     # 解析的元信息（如果有效）
            }
        """
        errors = []
        meta = None
        
        try:
            # 创建临时文件保存 zip 数据
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
                tmp.write(zip_data)
                tmp_path = tmp.name
            
            try:
                # 检查是否是有效的 zip 文件
                if not zipfile.is_zipfile(tmp_path):
                    errors.append("无效的插件包格式，请上传.zip文件")
                    return {"valid": False, "errors": errors, "meta": None}
                
                with zipfile.ZipFile(tmp_path, 'r') as zf:
                    file_list = zf.namelist()
                    
                    # 检查必需文件
                    # 支持两种结构：直接在根目录或在子目录中
                    root_prefix = cls._find_root_prefix(file_list)
                    
                    for required_file in cls.REQUIRED_FILES:
                        full_path = f"{root_prefix}{required_file}" if root_prefix else required_file
                        if full_path not in file_list:
                            errors.append(f"插件包缺少必要文件: {required_file}")
                    
                    if errors:
                        return {"valid": False, "errors": errors, "meta": None}
                    
                    # 解析元信息
                    meta_path = f"{root_prefix}plugin_meta.json" if root_prefix else "plugin_meta.json"
                    try:
                        meta_content = zf.read(meta_path).decode('utf-8')
                        meta = json.loads(meta_content)
                    except json.JSONDecodeError as e:
                        errors.append(f"plugin_meta.json 格式错误: {str(e)}")
                        return {"valid": False, "errors": errors, "meta": None}
                    
                    # 验证元信息必需字段
                    meta_errors = cls._validate_meta(meta)
                    if meta_errors:
                        errors.extend(meta_errors)
                        return {"valid": False, "errors": errors, "meta": meta}
                    
                    # 记录根目录前缀供后续使用
                    meta['_root_prefix'] = root_prefix
                    
            finally:
                os.unlink(tmp_path)
            
            return {"valid": True, "errors": [], "meta": meta}
            
        except Exception as e:
            errors.append(f"校验插件包时发生错误: {str(e)}")
            return {"valid": False, "errors": errors, "meta": None}
    
    @classmethod
    def _find_root_prefix(cls, file_list: List[str]) -> str:
        """
        查找插件包的根目录前缀
        
        支持两种结构：
        1. 文件直接在根目录：plugin_meta.json, backend/main.py
        2. 文件在子目录中：plugin_name/plugin_meta.json, plugin_name/backend/main.py
        """
        # 检查是否直接在根目录
        if "plugin_meta.json" in file_list:
            return ""
        
        # 查找可能的子目录
        for f in file_list:
            if f.endswith("/plugin_meta.json"):
                return f.rsplit("/plugin_meta.json", 1)[0] + "/"
        
        return ""
    
    @classmethod
    def _validate_meta(cls, meta: dict) -> List[str]:
        """验证元信息必需字段"""
        errors = []
        
        required_fields = ['plugin_id', 'plugin_name', 'plugin_version']
        for field in required_fields:
            if field not in meta or not meta[field]:
                errors.append(f"plugin_meta.json 缺少必需字段: {field}")
        
        if errors:
            return errors
        
        # 验证 plugin_id 格式
        if not cls.PLUGIN_ID_PATTERN.match(meta['plugin_id']):
            errors.append("plugin_id 只能包含字母、数字和下划线，且必须以字母开头")
        
        # 验证版本号格式
        if not cls.VERSION_PATTERN.match(meta['plugin_version']):
            errors.append("plugin_version 必须是语义化版本格式 (如 1.0.0)")
        
        return errors
    
    @classmethod
    def parse_meta(cls, meta_json: str) -> dict:
        """
        解析插件元信息 JSON
        
        Args:
            meta_json: JSON 字符串
        
        Returns:
            解析后的字典
        
        Raises:
            ValueError: 如果 JSON 格式错误或缺少必需字段
        """
        try:
            meta = json.loads(meta_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 格式错误: {str(e)}")
        
        errors = cls._validate_meta(meta)
        if errors:
            raise ValueError("; ".join(errors))
        
        return meta

    
    # ==================== 插件安装/卸载 ====================
    
    @classmethod
    def install(cls, zip_data: bytes, force: bool = False) -> dict:
        """
        安装插件
        
        Args:
            zip_data: 插件包二进制数据
            force: 是否强制覆盖已存在的插件
        
        Returns:
            {"success": bool, "message": str, "plugin_id": str}
        """
        # 校验插件包
        validation = cls.validate_package(zip_data)
        if not validation['valid']:
            return {
                "success": False,
                "message": "; ".join(validation['errors']),
                "plugin_id": None
            }
        
        meta = validation['meta']
        plugin_id = meta['plugin_id']
        root_prefix = meta.get('_root_prefix', '')
        
        # 检查是否已安装
        existing = PluginInfo.get_by_plugin_id(plugin_id)
        if existing and not force:
            return {
                "success": False,
                "message": f"插件 {plugin_id} 已安装，如需覆盖请使用强制安装",
                "plugin_id": plugin_id
            }
        
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
                tmp.write(zip_data)
                tmp_path = tmp.name
            
            try:
                plugin_dir = cls.get_plugin_dir(plugin_id)
                
                # 如果已存在，先删除
                if os.path.exists(plugin_dir):
                    shutil.rmtree(plugin_dir)
                
                # 解压插件包
                with zipfile.ZipFile(tmp_path, 'r') as zf:
                    # 创建插件目录
                    os.makedirs(plugin_dir, exist_ok=True)
                    
                    # 解压文件（处理根目录前缀）
                    for member in zf.namelist():
                        if root_prefix and member.startswith(root_prefix):
                            # 去掉根目录前缀
                            target_path = member[len(root_prefix):]
                        else:
                            target_path = member
                        
                        if not target_path:
                            continue
                        
                        # 构建目标路径
                        full_target = os.path.join(plugin_dir, target_path)
                        
                        if member.endswith('/'):
                            # 目录
                            os.makedirs(full_target, exist_ok=True)
                        else:
                            # 文件
                            os.makedirs(os.path.dirname(full_target), exist_ok=True)
                            with zf.open(member) as src, open(full_target, 'wb') as dst:
                                dst.write(src.read())
                
                # 创建或更新数据库记录
                if existing:
                    PluginInfo.update(
                        plugin_id,
                        plugin_name=meta.get('plugin_name'),
                        plugin_version=meta.get('plugin_version'),
                        plugin_author=meta.get('plugin_author'),
                        plugin_desc=meta.get('plugin_desc'),
                        meta_json=meta,
                        install_path=plugin_dir,
                        status=PluginInfo.STATUS_INSTALLED
                    )
                else:
                    PluginInfo.create(
                        plugin_id=plugin_id,
                        plugin_name=meta.get('plugin_name'),
                        plugin_version=meta.get('plugin_version'),
                        plugin_author=meta.get('plugin_author'),
                        plugin_desc=meta.get('plugin_desc'),
                        meta_json=meta,
                        install_path=plugin_dir
                    )
                
                return {
                    "success": True,
                    "message": f"插件 {meta.get('plugin_name')} 安装成功",
                    "plugin_id": plugin_id
                }
                
            finally:
                os.unlink(tmp_path)
                
        except Exception as e:
            return {
                "success": False,
                "message": f"安装插件时发生错误: {str(e)}",
                "plugin_id": plugin_id
            }
    
    @classmethod
    def uninstall(cls, plugin_id: str, force: bool = False) -> dict:
        """
        卸载插件
        
        Args:
            plugin_id: 插件唯一标识
            force: 是否强制卸载（即使有任务在使用）
        
        Returns:
            {"success": bool, "message": str}
        """
        # 检查插件是否存在
        plugin = PluginInfo.get_by_plugin_id(plugin_id)
        if not plugin:
            return {
                "success": False,
                "message": f"插件 {plugin_id} 不存在"
            }
        
        # 检查是否有任务在使用
        if not force:
            relations = TaskPluginRelation.get_by_plugin(plugin_id)
            if relations:
                task_info = [f"{r.task_type}:{r.task_id}" for r in relations[:5]]
                more = f"等 {len(relations)} 个任务" if len(relations) > 5 else ""
                return {
                    "success": False,
                    "message": f"插件正在被任务使用: {', '.join(task_info)}{more}，请先解除关联或使用强制卸载"
                }
        
        try:
            # 先停止插件
            if plugin.status == PluginInfo.STATUS_STARTED:
                cls.stop(plugin_id)
            
            # 删除插件文件
            plugin_dir = cls.get_plugin_dir(plugin_id)
            if os.path.exists(plugin_dir):
                shutil.rmtree(plugin_dir)
            
            # 级联删除数据库记录
            cascade_delete_plugin(plugin_id)
            
            return {
                "success": True,
                "message": f"插件 {plugin.plugin_name} 卸载成功"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"卸载插件时发生错误: {str(e)}"
            }

    
    # ==================== 插件启动/停止 ====================
    
    @classmethod
    def start(cls, plugin_id: str) -> dict:
        """
        启动插件
        
        加载插件代码、初始化配置、注册到 Plugin_Registry
        
        Args:
            plugin_id: 插件唯一标识
        
        Returns:
            {"success": bool, "message": str}
        """
        # 检查插件是否存在
        plugin = PluginInfo.get_by_plugin_id(plugin_id)
        if not plugin:
            return {
                "success": False,
                "message": f"插件 {plugin_id} 不存在"
            }
        
        # 检查是否已启动
        if plugin.status == PluginInfo.STATUS_STARTED:
            return {
                "success": True,
                "message": f"插件 {plugin.plugin_name} 已经是启动状态"
            }
        
        try:
            # 加载插件类
            plugin_class = cls._load_plugin_class(plugin_id)
            if plugin_class is None:
                return {
                    "success": False,
                    "message": f"无法加载插件 {plugin_id} 的代码"
                }
            
            # 注册到 Registry
            PluginRegistry.register(plugin_id, plugin_class, plugin.meta_json)
            
            # 更新数据库状态
            PluginInfo.update_status(plugin_id, PluginInfo.STATUS_STARTED)
            
            return {
                "success": True,
                "message": f"插件 {plugin.plugin_name} 启动成功"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"启动插件时发生错误: {str(e)}"
            }
    
    @classmethod
    def stop(cls, plugin_id: str) -> dict:
        """
        停止插件
        
        从 Plugin_Registry 注销、释放插件资源
        
        Args:
            plugin_id: 插件唯一标识
        
        Returns:
            {"success": bool, "message": str}
        """
        # 检查插件是否存在
        plugin = PluginInfo.get_by_plugin_id(plugin_id)
        if not plugin:
            return {
                "success": False,
                "message": f"插件 {plugin_id} 不存在"
            }
        
        # 检查是否已停止
        if plugin.status != PluginInfo.STATUS_STARTED:
            return {
                "success": True,
                "message": f"插件 {plugin.plugin_name} 已经是停止状态"
            }
        
        try:
            # 从 Registry 注销
            PluginRegistry.unregister(plugin_id)
            
            # 更新数据库状态
            PluginInfo.update_status(plugin_id, PluginInfo.STATUS_STOPPED)
            
            return {
                "success": True,
                "message": f"插件 {plugin.plugin_name} 已停止"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"停止插件时发生错误: {str(e)}"
            }
    
    @classmethod
    def _load_plugin_class(cls, plugin_id: str) -> Optional[type]:
        """
        动态加载插件类
        
        Args:
            plugin_id: 插件唯一标识
        
        Returns:
            插件类，如果加载失败返回 None
        """
        plugin_dir = cls.get_plugin_dir(plugin_id)
        main_file = os.path.join(plugin_dir, "backend", "main.py")
        
        if not os.path.exists(main_file):
            return None
        
        try:
            # 动态加载模块
            spec = importlib.util.spec_from_file_location(
                f"plugins.{plugin_id}.backend.main",
                main_file
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找 register_plugin 函数
            if hasattr(module, 'register_plugin'):
                plugin_class = module.register_plugin()
                if isinstance(plugin_class, type) and issubclass(plugin_class, BasePlugin):
                    return plugin_class
            
            # 如果没有 register_plugin，查找 BasePlugin 的子类
            for name in dir(module):
                obj = getattr(module, name)
                if (isinstance(obj, type) and 
                    issubclass(obj, BasePlugin) and 
                    obj is not BasePlugin):
                    return obj
            
            return None
            
        except Exception as e:
            print(f"加载插件 {plugin_id} 失败: {str(e)}")
            return None
    
    @classmethod
    def restore_started_plugins(cls) -> dict:
        """
        恢复之前已启动的插件（系统重启时调用）
        
        Returns:
            {"total": int, "success": int, "failed": int, "errors": list}
        """
        result = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "errors": []
        }
        
        # 获取所有状态为 started 的插件
        started_plugins = PluginInfo.get_by_status(PluginInfo.STATUS_STARTED)
        result["total"] = len(started_plugins)
        
        for plugin in started_plugins:
            try:
                plugin_class = cls._load_plugin_class(plugin.plugin_id)
                if plugin_class:
                    PluginRegistry.register(plugin.plugin_id, plugin_class, plugin.meta_json)
                    result["success"] += 1
                else:
                    result["failed"] += 1
                    result["errors"].append(f"无法加载插件 {plugin.plugin_id}")
            except Exception as e:
                result["failed"] += 1
                result["errors"].append(f"恢复插件 {plugin.plugin_id} 失败: {str(e)}")
        
        return result

    
    # ==================== 插件配置管理 ====================
    
    @classmethod
    def get_plugin_config(cls, plugin_id: str) -> dict:
        """
        获取插件配置
        
        Args:
            plugin_id: 插件唯一标识
        
        Returns:
            {"success": bool, "config": dict, "schema": list, "message": str}
        """
        plugin = PluginInfo.get_by_plugin_id(plugin_id)
        if not plugin:
            return {
                "success": False,
                "config": {},
                "schema": [],
                "message": f"插件 {plugin_id} 不存在"
            }
        
        # 获取配置模式
        schema = plugin.meta_json.get('config_schema', [])
        
        return {
            "success": True,
            "config": plugin.config,
            "schema": schema,
            "message": "获取成功"
        }
    
    @classmethod
    def save_plugin_config(cls, plugin_id: str, config: dict) -> dict:
        """
        保存插件配置
        
        Args:
            plugin_id: 插件唯一标识
            config: 配置字典
        
        Returns:
            {"success": bool, "message": str}
        """
        plugin = PluginInfo.get_by_plugin_id(plugin_id)
        if not plugin:
            return {
                "success": False,
                "message": f"插件 {plugin_id} 不存在"
            }
        
        # 验证配置
        validation = cls._validate_config(config, plugin.meta_json.get('config_schema', []))
        if not validation['valid']:
            return {
                "success": False,
                "message": "; ".join(validation['errors'])
            }
        
        # 转换配置值类型
        converted_config = cls._convert_config_types(config, plugin.meta_json.get('config_schema', []))
        
        # 保存配置
        PluginInfo.update_config(plugin_id, converted_config)
        
        return {
            "success": True,
            "message": "配置保存成功"
        }
    
    @classmethod
    def _validate_config(cls, config: dict, schema: list) -> dict:
        """验证配置是否符合模式"""
        errors = []
        
        for field in schema:
            key = field.get('param_key')
            required = field.get('required', False)
            
            if required and (key not in config or config[key] is None or config[key] == ''):
                errors.append(f"缺少必填配置项: {field.get('param_name', key)}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    @classmethod
    def _convert_config_types(cls, config: dict, schema: list) -> dict:
        """根据模式转换配置值类型"""
        result = config.copy()
        
        schema_map = {f.get('param_key'): f for f in schema}
        
        for key, value in config.items():
            if key in schema_map:
                param_type = schema_map[key].get('param_type', 'string')
                
                if param_type == 'number' and value is not None:
                    try:
                        if '.' in str(value):
                            result[key] = float(value)
                        else:
                            result[key] = int(value)
                    except (ValueError, TypeError):
                        pass
                
                elif param_type == 'boolean':
                    if isinstance(value, str):
                        result[key] = value.lower() in ('true', '1', 'yes', 'on')
                    else:
                        result[key] = bool(value)
        
        return result

    
    # ==================== 插件导入/导出 ====================
    
    @classmethod
    def export_plugin(cls, plugin_id: str) -> Tuple[Optional[bytes], str]:
        """
        导出插件为 zip 包
        
        Args:
            plugin_id: 插件唯一标识
        
        Returns:
            (zip_data, filename) 或 (None, error_message)
        """
        plugin = PluginInfo.get_by_plugin_id(plugin_id)
        if not plugin:
            return None, f"插件 {plugin_id} 不存在"
        
        plugin_dir = cls.get_plugin_dir(plugin_id)
        if not os.path.exists(plugin_dir):
            return None, f"插件目录不存在: {plugin_dir}"
        
        try:
            # 创建临时 zip 文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
                tmp_path = tmp.name
            
            # 打包插件目录
            with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(plugin_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_name = os.path.relpath(file_path, plugin_dir)
                        zf.write(file_path, arc_name)
            
            # 读取 zip 数据
            with open(tmp_path, 'rb') as f:
                zip_data = f.read()
            
            os.unlink(tmp_path)
            
            # 生成文件名
            filename = f"{plugin_id}_v{plugin.plugin_version}.zip"
            
            return zip_data, filename
            
        except Exception as e:
            return None, f"导出插件时发生错误: {str(e)}"
    
    @classmethod
    def import_plugin(cls, zip_data: bytes, overwrite: bool = False) -> dict:
        """
        导入插件包
        
        Args:
            zip_data: 插件包二进制数据
            overwrite: 是否覆盖已存在的插件
        
        Returns:
            {"success": bool, "message": str, "plugin_id": str, "need_confirm": bool}
        """
        # 校验插件包
        validation = cls.validate_package(zip_data)
        if not validation['valid']:
            return {
                "success": False,
                "message": "; ".join(validation['errors']),
                "plugin_id": None,
                "need_confirm": False
            }
        
        meta = validation['meta']
        plugin_id = meta['plugin_id']
        new_version = meta['plugin_version']
        
        # 检查是否已安装
        existing = PluginInfo.get_by_plugin_id(plugin_id)
        if existing:
            # 比较版本
            comparison = cls.compare_versions(new_version, existing.plugin_version)
            
            if comparison < 0 and not overwrite:
                # 新版本低于已安装版本
                return {
                    "success": False,
                    "message": f"导入的插件版本 ({new_version}) 低于已安装版本 ({existing.plugin_version})，请确认是否覆盖",
                    "plugin_id": plugin_id,
                    "need_confirm": True
                }
            
            if comparison == 0 and not overwrite:
                return {
                    "success": False,
                    "message": f"插件 {plugin_id} 已安装相同版本 ({new_version})，请确认是否覆盖",
                    "plugin_id": plugin_id,
                    "need_confirm": True
                }
        
        # 执行安装
        return cls.install(zip_data, force=overwrite or (existing is not None))
    
    @classmethod
    def compare_versions(cls, v1: str, v2: str) -> int:
        """
        比较两个语义化版本号
        
        Args:
            v1: 版本号1
            v2: 版本号2
        
        Returns:
            -1 如果 v1 < v2
             0 如果 v1 == v2
             1 如果 v1 > v2
        """
        def parse_version(v):
            parts = v.split('.')
            return tuple(int(p) for p in parts)
        
        try:
            p1 = parse_version(v1)
            p2 = parse_version(v2)
            
            if p1 < p2:
                return -1
            elif p1 > p2:
                return 1
            else:
                return 0
        except (ValueError, AttributeError):
            # 如果解析失败，按字符串比较
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1
            else:
                return 0
    
    # ==================== 辅助方法 ====================
    
    @classmethod
    def get_all_plugins(cls) -> List[dict]:
        """获取所有已安装的插件"""
        plugins = PluginInfo.get_all()
        return [p.to_dict() for p in plugins]
    
    @classmethod
    def get_active_plugins(cls) -> List[dict]:
        """获取所有已启动的插件"""
        plugins = PluginInfo.get_active_plugins()
        return [p.to_dict() for p in plugins]
    
    @classmethod
    def get_plugin(cls, plugin_id: str) -> Optional[dict]:
        """获取指定插件信息"""
        plugin = PluginInfo.get_by_plugin_id(plugin_id)
        return plugin.to_dict() if plugin else None
    
    @classmethod
    def scan_local_plugins(cls) -> dict:
        """
        扫描本地插件目录，自动注册未安装的插件
        
        Returns:
            {"total": int, "installed": int, "skipped": int, "errors": list}
        """
        result = {
            "total": 0,
            "installed": 0,
            "skipped": 0,
            "errors": []
        }
        
        plugin_base_dir = cls.get_plugin_base_dir()
        if not os.path.exists(plugin_base_dir):
            return result
        
        # 遍历插件目录
        for item in os.listdir(plugin_base_dir):
            # 跳过特殊目录和文件
            if item.startswith('_') or item.startswith('.') or item == '__pycache__':
                continue
            
            plugin_dir = os.path.join(plugin_base_dir, item)
            if not os.path.isdir(plugin_dir):
                continue
            
            meta_file = os.path.join(plugin_dir, 'plugin_meta.json')
            main_file = os.path.join(plugin_dir, 'backend', 'main.py')
            
            # 检查必要文件是否存在
            if not os.path.exists(meta_file) or not os.path.exists(main_file):
                continue
            
            result["total"] += 1
            
            try:
                # 读取元信息
                with open(meta_file, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                
                plugin_id = meta.get('plugin_id')
                if not plugin_id:
                    result["errors"].append(f"目录 {item} 的 plugin_meta.json 缺少 plugin_id")
                    continue
                
                # 检查是否已安装
                existing = PluginInfo.get_by_plugin_id(plugin_id)
                if existing:
                    result["skipped"] += 1
                    continue
                
                # 创建数据库记录
                PluginInfo.create(
                    plugin_id=plugin_id,
                    plugin_name=meta.get('plugin_name', plugin_id),
                    plugin_version=meta.get('plugin_version', '1.0.0'),
                    plugin_author=meta.get('plugin_author'),
                    plugin_desc=meta.get('plugin_desc'),
                    meta_json=meta,
                    install_path=plugin_dir
                )
                
                result["installed"] += 1
                
            except json.JSONDecodeError as e:
                result["errors"].append(f"目录 {item} 的 plugin_meta.json 格式错误: {str(e)}")
            except Exception as e:
                result["errors"].append(f"注册插件 {item} 失败: {str(e)}")
        
        return result

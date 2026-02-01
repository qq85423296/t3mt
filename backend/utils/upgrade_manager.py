# -*- coding: utf-8 -*-
"""
升级管理器
负责检查更新、下载更新包、备份、升级、回退等功能
"""
import os
import shutil
import hashlib
import zipfile
import requests
from datetime import datetime
from pathlib import Path
from utils.logger import logger
from config import Config

class UpgradeManager:
    """升级管理器"""
    
    # 当前版本号
    CURRENT_VERSION = "3.0.5"
    
    # 备份目录
    BACKUP_DIR = Path(__file__).parent.parent.parent / 'backups'
    
    # 临时下载目录
    TEMP_DIR = Path(__file__).parent.parent.parent / 'temp_upgrade'
    
    def __init__(self):
        """初始化升级管理器"""
        # 从配置文件读取许可证服务器地址
        from config import Config
        self.license_server_url = Config.LICENSE_SERVER_URL
        
        if not self.license_server_url:
            logger.error("许可证服务器地址未配置,请检查 config.ini 文件")
            raise ValueError("许可证服务器地址未配置")
        
        logger.info("升级管理器初始化完成")
        
        # 创建必要的目录
        self.BACKUP_DIR.mkdir(exist_ok=True)
        self.TEMP_DIR.mkdir(exist_ok=True)
    
    def check_update(self, machine_id):
        """
        检查更新
        
        Args:
            machine_id: 机器码
            
        Returns:
            dict: 更新信息
        """
        try:
            logger.info(f"检查更新: 当前版本 {self.CURRENT_VERSION}")
            
            response = requests.post(
                f'{self.license_server_url}/api/upgrade/check',
                json={
                    'current_version': self.CURRENT_VERSION,
                    'machine_id': machine_id
                },
                timeout=10
            )
            
            result = response.json()
            
            if result['code'] == 200:
                logger.info(f"检查更新成功: {result['data']}")
                return result['data']
            else:
                logger.error(f"检查更新失败: {result['message']}")
                return {'has_update': False, 'message': result['message']}
                
        except Exception as e:
            logger.error(f"检查更新异常: {e}")
            return {'has_update': False, 'message': f'检查更新失败: {str(e)}'}
    
    def download_package(self, package_url, package_md5=None):
        """
        下载更新包
        
        Args:
            package_url: 更新包URL
            package_md5: MD5校验值
            
        Returns:
            str: 下载的文件路径
        """
        try:
            logger.info(f"开始下载更新包: {package_url}")
            
            # 下载文件
            response = requests.get(package_url, stream=True, timeout=300)
            response.raise_for_status()
            
            # 保存到临时目录
            package_path = self.TEMP_DIR / 'update.zip'
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(package_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # 记录进度
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            if downloaded % (1024 * 1024) == 0:  # 每1MB记录一次
                                logger.info(f"下载进度: {progress:.1f}%")
            
            logger.info(f"下载完成: {package_path}")
            
            # 校验MD5
            if package_md5:
                logger.info("开始校验MD5...")
                file_md5 = self._calculate_md5(package_path)
                
                if file_md5.lower() != package_md5.lower():
                    logger.error(f"MD5校验失败: 期望 {package_md5}, 实际 {file_md5}")
                    raise Exception("更新包MD5校验失败")
                
                logger.info("MD5校验通过")
            
            return str(package_path)
            
        except Exception as e:
            logger.error(f"下载更新包失败: {e}")
            raise
    
    def create_backup(self):
        """
        创建备份
        
        Returns:
            str: 备份目录路径
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f'backup_{self.CURRENT_VERSION}_{timestamp}'
            backup_path = self.BACKUP_DIR / backup_name
            
            logger.info(f"开始创建备份: {backup_path}")
            
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent
            
            # 需要备份的目录
            dirs_to_backup = ['backend', 'frontend']
            
            # 创建备份目录
            backup_path.mkdir(exist_ok=True)
            
            # 复制文件
            for dir_name in dirs_to_backup:
                src_dir = project_root / dir_name
                if src_dir.exists():
                    dst_dir = backup_path / dir_name
                    logger.info(f"备份目录: {src_dir} -> {dst_dir}")
                    shutil.copytree(src_dir, dst_dir, ignore=shutil.ignore_patterns(
                        '__pycache__', '*.pyc', '*.pyo', '.git', 'node_modules', 
                        '*.log', 'logs', 'temp*', 'backups'
                    ))
            
            # 备份数据库
            db_path = project_root / 'backend' / 'data' / 'quark_manager.db'
            if db_path.exists():
                dst_db = backup_path / 'quark_manager.db'
                logger.info(f"备份数据库: {db_path} -> {dst_db}")
                shutil.copy2(db_path, dst_db)
            
            # 备份配置文件
            config_files = ['backend/.env', 'backend/config.py']
            for config_file in config_files:
                src_file = project_root / config_file
                if src_file.exists():
                    dst_file = backup_path / Path(config_file).name
                    logger.info(f"备份配置: {src_file} -> {dst_file}")
                    shutil.copy2(src_file, dst_file)
            
            logger.info(f"备份创建成功: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            raise
    
    def apply_upgrade(self, package_path):
        """
        应用升级
        
        Args:
            package_path: 更新包路径
        """
        try:
            logger.info(f"开始应用升级: {package_path}")
            
            # 解压更新包
            extract_dir = self.TEMP_DIR / 'extracted'
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir()
            
            logger.info(f"解压更新包到: {extract_dir}")
            with zipfile.ZipFile(package_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent
            
            # 复制文件到项目目录
            for item in extract_dir.iterdir():
                if item.is_dir():
                    dst = project_root / item.name
                    logger.info(f"更新目录: {item} -> {dst}")
                    
                    # 跳过不需要更新的目录
                    if item.name in ['data', 'logs', 'backups', 'downloads']:
                        logger.info(f"跳过目录: {item.name}")
                        continue
                    
                    # 删除旧目录
                    if dst.exists():
                        try:
                            shutil.rmtree(dst)
                        except Exception as e:
                            logger.warning(f"删除旧目录失败: {e}，尝试覆盖")
                    
                    # 复制新文件
                    shutil.copytree(item, dst, dirs_exist_ok=True)
                elif item.is_file():
                    dst = project_root / item.name
                    logger.info(f"更新文件: {item} -> {dst}")
                    shutil.copy2(item, dst)
            
            logger.info("升级应用成功")
            
        except Exception as e:
            logger.error(f"应用升级失败: {e}")
            raise
    
    def rollback(self, backup_path):
        """
        回退到备份版本
        
        Args:
            backup_path: 备份目录路径
        """
        try:
            logger.info(f"开始回退到备份: {backup_path}")
            
            backup_dir = Path(backup_path)
            if not backup_dir.exists():
                raise Exception(f"备份目录不存在: {backup_path}")
            
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent
            
            # 恢复目录
            for item in backup_dir.iterdir():
                if item.is_dir() and item.name in ['backend', 'frontend']:
                    dst = project_root / item.name
                    logger.info(f"恢复目录: {item} -> {dst}")
                    
                    # 删除当前目录
                    if dst.exists():
                        shutil.rmtree(dst)
                    
                    # 复制备份
                    shutil.copytree(item, dst)
            
            # 恢复数据库
            backup_db = backup_dir / 'quark_manager.db'
            if backup_db.exists():
                dst_db = project_root / 'backend' / 'data' / 'quark_manager.db'
                logger.info(f"恢复数据库: {backup_db} -> {dst_db}")
                shutil.copy2(backup_db, dst_db)
            
            # 恢复配置文件
            for config_file in backup_dir.glob('*.env'):
                dst = project_root / 'backend' / config_file.name
                logger.info(f"恢复配置: {config_file} -> {dst}")
                shutil.copy2(config_file, dst)
            
            logger.info("回退成功")
            
        except Exception as e:
            logger.error(f"回退失败: {e}")
            raise
    
    def cleanup(self):
        """清理临时文件"""
        try:
            if self.TEMP_DIR.exists():
                logger.info(f"清理临时目录: {self.TEMP_DIR}")
                shutil.rmtree(self.TEMP_DIR)
                self.TEMP_DIR.mkdir()
        except Exception as e:
            logger.error(f"清理临时文件失败: {e}")
    
    def get_backups(self):
        """
        获取备份列表
        
        Returns:
            list: 备份信息列表
        """
        try:
            backups = []
            
            if not self.BACKUP_DIR.exists():
                return backups
            
            for backup_dir in sorted(self.BACKUP_DIR.iterdir(), reverse=True):
                if backup_dir.is_dir() and backup_dir.name.startswith('backup_'):
                    # 解析备份信息
                    parts = backup_dir.name.split('_')
                    if len(parts) >= 3:
                        version = parts[1]
                        timestamp = '_'.join(parts[2:])
                        
                        # 计算备份大小
                        size = sum(f.stat().st_size for f in backup_dir.rglob('*') if f.is_file())
                        
                        backups.append({
                            'path': str(backup_dir),
                            'name': backup_dir.name,
                            'version': version,
                            'timestamp': timestamp,
                            'size': size,
                            'created_at': datetime.fromtimestamp(backup_dir.stat().st_ctime).strftime('%Y-%m-%d %H:%M:%S')
                        })
            
            return backups
            
        except Exception as e:
            logger.error(f"获取备份列表失败: {e}")
            return []
    
    def delete_backup(self, backup_path):
        """
        删除备份
        
        Args:
            backup_path: 备份路径
        """
        try:
            backup_dir = Path(backup_path)
            if backup_dir.exists() and backup_dir.parent == self.BACKUP_DIR:
                logger.info(f"删除备份: {backup_path}")
                shutil.rmtree(backup_dir)
            else:
                raise Exception("无效的备份路径")
        except Exception as e:
            logger.error(f"删除备份失败: {e}")
            raise
    
    def log_upgrade(self, machine_id, from_version, to_version, status, error_message=None):
        """
        记录升级日志到服务器
        
        Args:
            machine_id: 机器码
            from_version: 原版本
            to_version: 目标版本
            status: 状态 (success/failed)
            error_message: 错误信息
        """
        try:
            requests.post(
                f'{self.license_server_url}/api/upgrade/log',
                json={
                    'machine_id': machine_id,
                    'from_version': from_version,
                    'to_version': to_version,
                    'upgrade_status': status,
                    'error_message': error_message
                },
                timeout=10
            )
        except Exception as e:
            logger.error(f"记录升级日志失败: {e}")
    
    def _calculate_md5(self, file_path):
        """计算文件MD5"""
        md5_hash = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()


# 全局实例
upgrade_manager = UpgradeManager()

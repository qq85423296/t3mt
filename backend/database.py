# -*- coding: utf-8 -*-
"""
数据库管理模块
"""
import sqlite3
import os
from contextlib import contextmanager


class Database:
    """数据库管理类"""
    
    def __init__(self):
        # 延迟导入避免循环依赖
        from config import Config
        self.db_path = Config.DATABASE_PATH
        self._ensure_data_dir()
    
    def _ensure_data_dir(self):
        """确保数据目录存在"""
        data_dir = os.path.dirname(self.db_path)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_database(self):
        """初始化数据库表结构"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建用户表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建夸克账号表（包含member_type、member_exp_at和cloud_type字段）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS quark_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    remark VARCHAR(100) NOT NULL,
                    cookie TEXT NOT NULL,
                    account_name VARCHAR(50),
                    is_vip TINYINT DEFAULT 0,
                    member_type VARCHAR(20) DEFAULT 'free',
                    member_exp_at VARCHAR(20),
                    total_size BIGINT,
                    used_size BIGINT,
                    is_main TINYINT DEFAULT 0,
                    status TINYINT DEFAULT 1,
                    cloud_type VARCHAR(20) DEFAULT 'quark',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建唯一索引：只能有一个主账号
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_main_account 
                ON quark_accounts(is_main) WHERE is_main = 1
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_status 
                ON quark_accounts(status)
            ''')
            
            # 创建转存任务表（包含schedule_period字段、正则替换字段和cloud_type字段）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transfer_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(200) NOT NULL,
                    share_urls TEXT NOT NULL,
                    target_account_id INTEGER NOT NULL,
                    target_path VARCHAR(500) NOT NULL,
                    save_mode VARCHAR(20) DEFAULT 'current',
                    target_folder_name VARCHAR(200) DEFAULT '',
                    rules TEXT,
                    filter_extensions TEXT,
                    include_extensions TEXT,
                    update_dirs TEXT,
                    file_start_date DATE,
                    overwrite_mode TINYINT DEFAULT 0,
                    end_date DATE,
                    cron_expression VARCHAR(50) NOT NULL,
                    schedule_period VARCHAR(20) DEFAULT 'daily',
                    status VARCHAR(20) DEFAULT 'running',
                    last_execute_time DATETIME,
                    next_execute_time DATETIME,
                    regex_pattern TEXT,
                    replacement_pattern TEXT,
                    check_mode VARCHAR(20) DEFAULT 'replaced',
                    cloud_type VARCHAR(20) DEFAULT 'quark',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (target_account_id) REFERENCES quark_accounts(id)
                )
            ''')
            
            # 迁移：为已存在的transfer_tasks表添加正则替换字段
            try:
                cursor.execute("SELECT regex_pattern FROM transfer_tasks LIMIT 1")
            except sqlite3.OperationalError:
                # 字段不存在，需要添加
                cursor.execute("ALTER TABLE transfer_tasks ADD COLUMN regex_pattern TEXT")
                cursor.execute("ALTER TABLE transfer_tasks ADD COLUMN replacement_pattern TEXT")
                cursor.execute("ALTER TABLE transfer_tasks ADD COLUMN check_mode VARCHAR(20) DEFAULT 'replaced'")
                print("✅ transfer_tasks表已添加正则替换字段")
            
            # 迁移：为已存在的transfer_tasks表添加目标文件夹ID字段
            try:
                cursor.execute("SELECT target_folder_id FROM transfer_tasks LIMIT 1")
            except sqlite3.OperationalError:
                # 字段不存在，需要添加
                cursor.execute("ALTER TABLE transfer_tasks ADD COLUMN target_folder_id VARCHAR(100)")
                print("✅ transfer_tasks表已添加target_folder_id字段（用于快速定位目录）")
            
            # 迁移：为已存在的transfer_tasks表添加排除关键词字段
            try:
                cursor.execute("SELECT exclude_keywords FROM transfer_tasks LIMIT 1")
            except sqlite3.OperationalError:
                # 字段不存在，需要添加
                cursor.execute("ALTER TABLE transfer_tasks ADD COLUMN exclude_keywords TEXT")
                print("✅ transfer_tasks表已添加排除关键词字段")
            
            # 迁移：为已存在的transfer_tasks表添加最后内容更新时间字段（用于自动失效检查）
            try:
                cursor.execute("SELECT last_content_update_time FROM transfer_tasks LIMIT 1")
            except sqlite3.OperationalError:
                # 字段不存在，需要添加
                cursor.execute("ALTER TABLE transfer_tasks ADD COLUMN last_content_update_time DATETIME")
                # 为已存在的记录设置初始值为当前时间（而不是创建时间，避免立即失效）
                cursor.execute("UPDATE transfer_tasks SET last_content_update_time = datetime('now') WHERE last_content_update_time IS NULL")
                print("✅ transfer_tasks表已添加最后内容更新时间字段")
            
            # 创建下载任务表（包含filter_extensions、include_extensions、正则替换字段和cloud_type字段）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS download_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(200) NOT NULL,
                    source_account_id INTEGER NOT NULL,
                    source_path VARCHAR(500) NOT NULL,
                    target_path VARCHAR(500) NOT NULL,
                    cron_expression VARCHAR(50) NOT NULL,
                    filter_extensions TEXT,
                    include_extensions TEXT,
                    only_new_files TINYINT DEFAULT 1,
                    keep_structure TINYINT DEFAULT 1,
                    delete_after_download TINYINT DEFAULT 0,
                    regex_pattern TEXT,
                    replacement_pattern TEXT,
                    status VARCHAR(20) DEFAULT 'running',
                    progress INTEGER DEFAULT 0,
                    last_execute_time DATETIME,
                    next_execute_time DATETIME,
                    cloud_type VARCHAR(20) DEFAULT 'quark',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_account_id) REFERENCES quark_accounts(id)
                )
            ''')
            
            # 迁移：为已存在的download_tasks表添加正则替换字段
            try:
                cursor.execute("SELECT regex_pattern FROM download_tasks LIMIT 1")
            except sqlite3.OperationalError:
                # 字段不存在，需要添加
                cursor.execute("ALTER TABLE download_tasks ADD COLUMN regex_pattern TEXT")
                cursor.execute("ALTER TABLE download_tasks ADD COLUMN replacement_pattern TEXT")
                print("✅ download_tasks表已添加正则替换字段")
            
            # 迁移：为已存在的download_tasks表添加源文件夹ID字段
            try:
                cursor.execute("SELECT source_folder_id FROM download_tasks LIMIT 1")
            except sqlite3.OperationalError:
                # 字段不存在，需要添加
                cursor.execute("ALTER TABLE download_tasks ADD COLUMN source_folder_id VARCHAR(100)")
                print("✅ download_tasks表已添加source_folder_id字段（用于快速定位目录）")
            
            # 迁移：为已存在的download_tasks表添加排除关键词字段
            try:
                cursor.execute("SELECT exclude_keywords FROM download_tasks LIMIT 1")
            except sqlite3.OperationalError:
                # 字段不存在，需要添加
                cursor.execute("ALTER TABLE download_tasks ADD COLUMN exclude_keywords TEXT")
                print("✅ download_tasks表已添加排除关键词字段")
            
            # 迁移：为已存在的download_tasks表添加最后内容更新时间字段（用于自动失效检查）
            try:
                cursor.execute("SELECT last_content_update_time FROM download_tasks LIMIT 1")
            except sqlite3.OperationalError:
                # 字段不存在，需要添加
                cursor.execute("ALTER TABLE download_tasks ADD COLUMN last_content_update_time DATETIME")
                # 为已存在的记录设置初始值为当前时间（而不是创建时间，避免立即失效）
                cursor.execute("UPDATE download_tasks SET last_content_update_time = datetime('now') WHERE last_content_update_time IS NULL")
                print("✅ download_tasks表已添加最后内容更新时间字段")
            
            # 创建影视下载任务表（包含create_subfolder、集数选择、影视类型和cloud_type字段）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(200) NOT NULL,
                    website_url VARCHAR(500) NOT NULL,
                    video_id VARCHAR(50),
                    clip_id VARCHAR(50),
                    save_directory VARCHAR(500) NOT NULL,
                    cron_expression VARCHAR(100) NOT NULL,
                    episodes_json TEXT,
                    video_info_json TEXT,
                    status VARCHAR(20) DEFAULT 'waiting',
                    progress INTEGER DEFAULT 0,
                    downloaded_episodes INTEGER DEFAULT 0,
                    create_subfolder INTEGER DEFAULT 0,
                    selected_episodes TEXT,
                    last_downloaded_episode INTEGER DEFAULT 0,
                    platform VARCHAR(20) DEFAULT 'mango',
                    video_type VARCHAR(20) DEFAULT '电视剧',
                    cloud_type VARCHAR(20) DEFAULT 'quark',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 迁移：为已存在的video_tasks表添加正则替换字段
            try:
                cursor.execute("SELECT regex_pattern FROM video_tasks LIMIT 1")
            except sqlite3.OperationalError:
                # 字段不存在，需要添加
                cursor.execute("ALTER TABLE video_tasks ADD COLUMN regex_pattern TEXT")
                cursor.execute("ALTER TABLE video_tasks ADD COLUMN replacement_pattern TEXT")
                print("✅ video_tasks表已添加正则替换字段")
            
            # 迁移：为已存在的video_tasks表添加文件大小限制字段
            try:
                cursor.execute("SELECT enable_file_size_check FROM video_tasks LIMIT 1")
            except sqlite3.OperationalError:
                # 字段不存在，需要添加
                cursor.execute("ALTER TABLE video_tasks ADD COLUMN enable_file_size_check INTEGER DEFAULT 0")
                cursor.execute("ALTER TABLE video_tasks ADD COLUMN min_file_size INTEGER DEFAULT 100")
                print("✅ video_tasks表已添加文件大小限制字段")
            
            # 迁移：为已存在的video_tasks表添加失败重试字段
            try:
                cursor.execute("SELECT enable_retry FROM video_tasks LIMIT 1")
            except sqlite3.OperationalError:
                # 字段不存在，需要添加
                cursor.execute("ALTER TABLE video_tasks ADD COLUMN enable_retry INTEGER DEFAULT 0")
                cursor.execute("ALTER TABLE video_tasks ADD COLUMN max_retry_count INTEGER DEFAULT 3")
                cursor.execute("ALTER TABLE video_tasks ADD COLUMN retry_interval INTEGER DEFAULT 5")
                print("✅ video_tasks表已添加失败重试字段")
            
            # 迁移：为已存在的video_tasks表添加排除关键词字段
            try:
                cursor.execute("SELECT exclude_keywords FROM video_tasks LIMIT 1")
            except sqlite3.OperationalError:
                # 字段不存在，需要添加
                cursor.execute("ALTER TABLE video_tasks ADD COLUMN exclude_keywords TEXT")
                print("✅ video_tasks表已添加排除关键词字段")
            
            # 迁移：为已存在的video_tasks表添加最后新增剧集时间字段
            try:
                cursor.execute("SELECT last_episode_update_time FROM video_tasks LIMIT 1")
            except sqlite3.OperationalError:
                # 字段不存在，需要添加
                cursor.execute("ALTER TABLE video_tasks ADD COLUMN last_episode_update_time DATETIME")
                # 为已存在的记录设置初始值为当前时间（而不是创建时间，避免立即失效）
                cursor.execute("UPDATE video_tasks SET last_episode_update_time = datetime('now') WHERE last_episode_update_time IS NULL")
                print("✅ video_tasks表已添加最后新增剧集时间字段")
            
            # 创建任务执行历史表（包含schedule_period字段和唯一约束）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS task_execution_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    task_type VARCHAR(20) NOT NULL,
                    task_name VARCHAR(200) NOT NULL,
                    schedule_period VARCHAR(20),
                    status VARCHAR(20) DEFAULT 'pending',
                    start_time DATETIME,
                    end_time DATETIME,
                    duration INTEGER,
                    total_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    logs TEXT,
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建正则规则库表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS regex_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL,
                    regex_pattern TEXT NOT NULL,
                    replacement_pattern TEXT NOT NULL,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_regex_rules_name
                ON regex_rules(name)
            ''')
            
            # 创建唯一约束索引
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_task_execution_unique
                ON task_execution_history(task_id, task_type, schedule_period)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_task_execution_status
                ON task_execution_history(status)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_task_execution_time
                ON task_execution_history(start_time)
            ''')
            
            # 创建日志表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS log_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type VARCHAR(20) NOT NULL,
                    task_id INTEGER,
                    task_name VARCHAR(200) NOT NULL,
                    log_level VARCHAR(10) NOT NULL,
                    log_content TEXT NOT NULL,
                    execution_time INTEGER,
                    file_count INTEGER,
                    file_size BIGINT,
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_task_type 
                ON log_records(task_type)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_log_level 
                ON log_records(log_level)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON log_records(created_at)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_task_id 
                ON log_records(task_id)
            ''')
            
            # 创建系统配置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_key VARCHAR(50) NOT NULL UNIQUE,
                    config_value TEXT NOT NULL,
                    config_type VARCHAR(20) NOT NULL,
                    description VARCHAR(200),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_config_key 
                ON system_config(config_key)
            ''')
            
            # 插入默认管理员账号（密码：admin123）
            # 检查是否已存在admin用户
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
            if cursor.fetchone()[0] == 0:
                # 动态生成密码哈希
                from utils.crypto import CryptoUtil
                default_password_hash = CryptoUtil.hash_password('admin123')
                cursor.execute(
                    "INSERT INTO users (username, password) VALUES ('admin', ?)",
                    (default_password_hash,)
                )
            
            # 插入默认系统配置
            default_configs = [
                ('schedule_log_retention_days', '30', 'log', '调度日志保留天数'),
                ('download_default_dir', 'D:\\Downloads', 'download', '默认下载目录'),
                ('download_max_concurrent', '3', 'download', '最大并发下载数'),
                ('download_speed_limit', '0', 'download', '下载速度限制(MB/s)'),
                ('download_chunk_size', '10', 'download', '分块下载大小(MB)'),
                ('download_retry_count', '3', 'download', '下载重试次数'),
                ('pansou_api_url', 'http://pans.fn.22l2.com/', 'pansou', '盘搜API地址'),
                ('video_download_default_dir', '/app/backend/downloads/官网下载', 'video_download', '影视下载默认目录'),
                ('video_download_temp_dir', '/app/backend/downloads/temp', 'video_download', '影视下载临时目录'),
                ('video_download_max_threads', '3', 'video_download', '视频片段下载线程数（1-10）'),
            ]
            
            for key, value, type_, desc in default_configs:
                cursor.execute('''
                    INSERT OR IGNORE INTO system_config 
                    (config_key, config_value, config_type, description) 
                    VALUES (?, ?, ?, ?)
                ''', (key, value, type_, desc))
            
            conn.commit()
            print("✅ 数据库初始化成功")
    
    def reset_database(self):
        """重置数据库（删除所有表）"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            print("✅ 数据库已重置")
        self.init_database()


# 全局数据库实例(延迟初始化)
db = None


def _get_db_instance():
    """获取数据库实例(单例模式)"""
    global db
    if db is None:
        db = Database()
    return db


def get_db():
    """获取数据库连接的便捷函数"""
    return _get_db_instance().get_connection()


if __name__ == '__main__':
    # 初始化数据库
    _get_db_instance().init_database()

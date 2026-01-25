# -*- coding: utf-8 -*-
"""
Flask应用主文件
"""
from flask import Flask, session, request, send_from_directory
from flask_cors import CORS
import os
import warnings

# 禁用urllib3的SSL警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from config import Config
from database import get_db
from utils.logger import logger

# 导入所有API蓝图
from api import (
    auth_bp, accounts_bp, quark_bp, search_bp,
    transfer_bp, download_bp, config_bp
)
from api.video import video_bp


def create_app():
    """创建Flask应用"""
    # 获取项目根目录
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frontend_dir = os.path.join(base_dir, 'frontend')
    
    app = Flask(__name__, 
                static_folder=frontend_dir,
                static_url_path='')
    app.config.from_object(Config)
    
    # 禁用Flask的HTTP请求日志
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    # 启用CORS（API接口需要）
    CORS(app, 
         supports_credentials=True,
         resources={r"/api/*": {
             "origins": "*",
             "allow_headers": ["Content-Type", "Authorization"],
             "expose_headers": ["Set-Cookie"],
             "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
             "supports_credentials": True
         }})
    
    # 添加响应处理器，确保CORS头正确设置
    @app.after_request
    def after_request(response):
        # API请求添加CORS头
        if request.path.startswith('/api/'):
            response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response
    
    # 注册蓝图
    app.register_blueprint(auth_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(quark_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(transfer_bp)
    app.register_blueprint(download_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(video_bp)
    
    # 注册统一文件管理蓝图
    from api.files import files_bp
    app.register_blueprint(files_bp)
    
    # 注册正则规则库蓝图
    from api.regex_rules import regex_rules_bp
    app.register_blueprint(regex_rules_bp)
    
    # 注册监控蓝图
    from api.monitor import monitor_bp
    app.register_blueprint(monitor_bp)
    
    # 注册影视排行榜蓝图
    from api.video_ranking import video_ranking_bp
    app.register_blueprint(video_ranking_bp)
    
    # 注册许可证蓝图
    from api.license import license_bp
    app.register_blueprint(license_bp)
    
    # 注册升级管理蓝图
    from api.upgrade import upgrade_bp
    app.register_blueprint(upgrade_bp)
    
    # 注册插件管理蓝图
    from api.plugins import plugins_bp
    app.register_blueprint(plugins_bp)
    
    # 注册下载代理蓝图
    from api.download_proxy import download_proxy_bp
    app.register_blueprint(download_proxy_bp)
    
    # 健康检查接口
    @app.route('/health', methods=['GET'])
    def health_check():
        return {'status': 'ok', 'message': '服务运行正常'}
    
    # 静态文件路由
    @app.route('/')
    def index():
        """首页"""
        return send_from_directory(frontend_dir, 'index.html')
    
    @app.route('/<path:path>')
    def serve_static(path):
        """提供静态文件"""
        # 如果是API请求，不处理
        if path.startswith('api/'):
            return {'error': 'Not Found'}, 404
        
        # 检查文件是否存在
        file_path = os.path.join(frontend_dir, path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return send_from_directory(frontend_dir, path)
        
        # 如果是页面路由（不包含扩展名），返回index.html
        if '.' not in path:
            return send_from_directory(frontend_dir, 'index.html')
        
        return {'error': 'Not Found'}, 404
    
    logger.info("Flask应用创建成功")
    logger.info(f"静态文件目录: {frontend_dir}")
    return app


def main():
    """主函数"""
    try:
        # 初始化许可证管理器并获取解密密钥
        try:
            from utils.license_manager import license_manager
            if license_manager.ensure_decryption_key():
                # 加载夸克API配置
                try:
                    Config.ensure_quark_config()
                except Exception as e:
                    logger.error(f"夸克API配置加载失败: {e}")
            else:
                logger.warning("解密密钥获取失败，部分功能可能受限")
        except Exception as e:
            logger.error(f"许可证管理器初始化失败: {e}")
            logger.warning("将以降级模式运行，部分功能可能不可用")
        
        # 确保数据库已初始化（每次启动都执行，包含迁移逻辑）
        logger.info("正在初始化数据库...")
        from database import _get_db_instance
        _get_db_instance().init_database()
        
        # 执行数据库迁移（必须成功）
        migration_success = False
        try:
            from migrations.run_migrations import run_migrations
            migration_success = run_migrations()
            if not migration_success:
                logger.error("数据库迁移执行失败")
        except Exception as e:
            logger.error(f"数据库迁移检查失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 强制检查并创建插件表（兼容旧数据库）
        if not migration_success:
            logger.info("执行强制插件表创建...")
            try:
                from migrations.force_create_plugin_tables import check_and_create_plugin_tables
                if check_and_create_plugin_tables():
                    migration_success = True
                    logger.info("强制插件表创建成功")
                else:
                    logger.error("强制插件表创建失败")
            except Exception as force_e:
                logger.error(f"强制插件表创建异常: {force_e}")
                import traceback
                traceback.print_exc()
        
        # 清理异常中断的任务状态
        logger.info("清理异常中断的任务状态...")
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # 将所有running状态的执行历史更新为interrupted
                cursor.execute('''
                    UPDATE task_execution_history 
                    SET status = 'interrupted',
                        end_time = datetime('now', 'localtime'),
                        error_message = '服务重启，任务被中断'
                    WHERE status = 'running'
                ''')
                interrupted_count = cursor.rowcount
                if interrupted_count > 0:
                    logger.info(f"已清理 {interrupted_count} 个异常中断的任务")
                
                # 将所有downloading状态的影视下载任务更新为draft（而不是waiting）
                cursor.execute('''
                    UPDATE video_tasks 
                    SET status = 'draft', progress = 0
                    WHERE status = 'downloading'
                ''')
                video_interrupted_count = cursor.rowcount
                if video_interrupted_count > 0:
                    logger.info(f"已重置 {video_interrupted_count} 个影视下载任务状态为draft")
                
        except Exception as e:
            logger.error(f"清理任务状态失败: {e}")
        
        # 创建应用
        app = create_app()
        
        # 初始化插件系统（无论迁移是否成功都尝试）
        logger.info("扫描本地插件目录...")
        try:
            from services.plugin_manager import PluginManager
            scan_result = PluginManager.scan_local_plugins()
            if scan_result['total'] > 0:
                logger.info(f"插件扫描完成: 发现 {scan_result['total']} 个，"
                           f"新安装 {scan_result['installed']} 个，"
                           f"已存在 {scan_result['skipped']} 个")
                if scan_result['errors']:
                    for error in scan_result['errors']:
                        logger.warning(f"插件扫描警告: {error}")
            else:
                logger.info("没有发现本地插件")
        except Exception as e:
            logger.error(f"插件扫描失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 恢复已启动的插件
        logger.info("恢复已启动的插件...")
        try:
            from services.plugin_manager import PluginManager
            restore_result = PluginManager.restore_started_plugins()
            if restore_result['total'] > 0:
                logger.info(f"插件恢复完成: 总计 {restore_result['total']} 个，"
                           f"成功 {restore_result['success']} 个，"
                           f"失败 {restore_result['failed']} 个")
                if restore_result['errors']:
                    for error in restore_result['errors']:
                        logger.warning(f"插件恢复警告: {error}")
            else:
                logger.info("没有需要恢复的插件")
        except Exception as e:
            logger.error(f"插件恢复失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 启动任务调度服务
        logger.info("启动任务调度服务...")
        from services.scheduler_service import SchedulerService
        SchedulerService.start()
        
        # 启动服务
        host = Config.HOST
        port = Config.PORT
        debug = Config.DEBUG
        
        logger.info(f"启动Flask服务: http://{host}:{port}")
        # 启用多线程模式，避免请求阻塞
        app.run(host=host, port=port, debug=debug, threaded=True)
        
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
        raise


if __name__ == '__main__':
    main()

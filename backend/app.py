# -*- coding: utf-8 -*-
"""
Flask应用主文件
"""
from flask import Flask, session, request, send_from_directory
from flask_cors import CORS
import os

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
        logger.info("初始化许可证管理器...")
        try:
            from utils.license_manager import license_manager
            if license_manager.ensure_decryption_key():
                logger.info("解密密钥获取成功，配置已就绪")
                # 加载夸克API配置
                try:
                    Config.ensure_quark_config()
                    logger.info("夸克API配置加载完成")
                except Exception as e:
                    logger.error(f"夸克API配置加载失败: {e}")
            else:
                logger.warning("解密密钥获取失败，部分功能可能受限")
        except Exception as e:
            logger.error(f"许可证管理器初始化失败: {e}")
            logger.warning("将以降级模式运行，部分功能可能不可用")
        
        # 确保数据库已初始化
        logger.info("检查数据库...")
        if not os.path.exists(Config.DATABASE_PATH):
            logger.info("数据库不存在，正在初始化...")
            from database import _get_db_instance
            _get_db_instance().init_database()
        logger.info("数据库检查完成")
        
        # 执行数据库迁移
        logger.info("检查数据库迁移...")
        try:
            from migrations.run_migrations import run_migrations
            if run_migrations():
                logger.info("数据库迁移检查完成")
            else:
                logger.warning("数据库迁移执行失败，但应用将继续启动")
        except Exception as e:
            logger.error(f"数据库迁移检查失败: {e}")
            logger.warning("将继续启动应用，但新功能可能不可用")
        
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
                
                # 将所有downloading状态的影视下载任务更新为waiting
                cursor.execute('''
                    UPDATE video_tasks 
                    SET status = 'waiting', progress = 0
                    WHERE status = 'downloading'
                ''')
                video_interrupted_count = cursor.rowcount
                if video_interrupted_count > 0:
                    logger.info(f"已重置 {video_interrupted_count} 个影视下载任务状态")
                
        except Exception as e:
            logger.error(f"清理任务状态失败: {e}")
        
        # 创建应用
        app = create_app()
        
        # 启动任务调度服务
        logger.info("启动任务调度服务...")
        from services.scheduler_service import SchedulerService
        SchedulerService.start()
        
        # 启动服务
        host = Config.HOST
        port = Config.PORT
        debug = Config.DEBUG
        
        logger.info(f"启动Flask服务: http://{host}:{port}")
        app.run(host=host, port=port, debug=debug)
        
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
        raise


if __name__ == '__main__':
    main()

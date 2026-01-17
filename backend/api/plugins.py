# -*- coding: utf-8 -*-
"""
插件管理API

提供插件的安装、卸载、启动、停止、配置管理等接口。
"""
from flask import Blueprint, request, jsonify, send_file
from io import BytesIO

from services.plugin_manager import PluginManager
from services.plugin_executor import PluginExecutor
from models.plugin import PluginInfo, TaskPluginRelation, PluginExecLog
from utils.logger import logger

plugins_bp = Blueprint('plugins', __name__, url_prefix='/api/plugins')


# ==================== 插件列表接口 ====================

@plugins_bp.route('', methods=['GET'])
def get_plugins():
    """获取所有已安装的插件"""
    try:
        plugins = PluginManager.get_all_plugins()
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': plugins
        })
    except Exception as e:
        logger.error(f"获取插件列表失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取插件列表失败: {str(e)}'
        }), 500


@plugins_bp.route('/active', methods=['GET'])
def get_active_plugins():
    """获取所有已启动的插件"""
    try:
        plugins = PluginManager.get_active_plugins()
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': plugins
        })
    except Exception as e:
        logger.error(f"获取活动插件列表失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取活动插件列表失败: {str(e)}'
        }), 500


@plugins_bp.route('/<plugin_id>', methods=['GET'])
def get_plugin(plugin_id):
    """获取指定插件详情"""
    try:
        plugin = PluginManager.get_plugin(plugin_id)
        if not plugin:
            return jsonify({
                'code': 404,
                'message': f'插件 {plugin_id} 不存在'
            }), 404
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': plugin
        })
    except Exception as e:
        logger.error(f"获取插件详情失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取插件详情失败: {str(e)}'
        }), 500


# ==================== 插件安装/卸载接口 ====================

@plugins_bp.route('/install', methods=['POST'])
def install_plugin():
    """
    安装插件
    
    请求方式：multipart/form-data
    参数：
        - file: 插件包文件（.zip）
        - force: 是否强制覆盖（可选，默认false）
    """
    try:
        # 检查文件
        if 'file' not in request.files:
            return jsonify({
                'code': 400,
                'message': '请上传插件包文件'
            }), 400
        
        file = request.files['file']
        if not file.filename:
            return jsonify({
                'code': 400,
                'message': '请选择要上传的文件'
            }), 400
        
        if not file.filename.endswith('.zip'):
            return jsonify({
                'code': 400,
                'message': '插件包必须是.zip格式'
            }), 400
        
        # 读取文件内容
        zip_data = file.read()
        
        # 获取强制覆盖参数
        force = request.form.get('force', 'false').lower() == 'true'
        
        # 安装插件
        result = PluginManager.install(zip_data, force=force)
        
        if result['success']:
            return jsonify({
                'code': 200,
                'message': result['message'],
                'data': {'plugin_id': result['plugin_id']}
            })
        else:
            return jsonify({
                'code': 400,
                'message': result['message'],
                'data': {'plugin_id': result.get('plugin_id')}
            }), 400
            
    except Exception as e:
        logger.error(f"安装插件失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'安装插件失败: {str(e)}'
        }), 500


@plugins_bp.route('/<plugin_id>', methods=['DELETE'])
def uninstall_plugin(plugin_id):
    """
    卸载插件
    
    参数：
        - force: 是否强制卸载（可选，默认false）
    """
    try:
        force = request.args.get('force', 'false').lower() == 'true'
        
        result = PluginManager.uninstall(plugin_id, force=force)
        
        if result['success']:
            return jsonify({
                'code': 200,
                'message': result['message']
            })
        else:
            return jsonify({
                'code': 400,
                'message': result['message']
            }), 400
            
    except Exception as e:
        logger.error(f"卸载插件失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'卸载插件失败: {str(e)}'
        }), 500


# ==================== 插件启动/停止接口 ====================

@plugins_bp.route('/<plugin_id>/start', methods=['POST'])
def start_plugin(plugin_id):
    """启动插件"""
    try:
        result = PluginManager.start(plugin_id)
        
        if result['success']:
            return jsonify({
                'code': 200,
                'message': result['message']
            })
        else:
            return jsonify({
                'code': 400,
                'message': result['message']
            }), 400
            
    except Exception as e:
        logger.error(f"启动插件失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'启动插件失败: {str(e)}'
        }), 500


@plugins_bp.route('/<plugin_id>/stop', methods=['POST'])
def stop_plugin(plugin_id):
    """停止插件"""
    try:
        result = PluginManager.stop(plugin_id)
        
        if result['success']:
            return jsonify({
                'code': 200,
                'message': result['message']
            })
        else:
            return jsonify({
                'code': 400,
                'message': result['message']
            }), 400
            
    except Exception as e:
        logger.error(f"停止插件失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'停止插件失败: {str(e)}'
        }), 500


# ==================== 插件配置接口 ====================

@plugins_bp.route('/<plugin_id>/config', methods=['GET'])
def get_plugin_config(plugin_id):
    """获取插件配置"""
    try:
        result = PluginManager.get_plugin_config(plugin_id)
        
        if result['success']:
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {
                    'config': result['config'],
                    'schema': result['schema']
                }
            })
        else:
            return jsonify({
                'code': 404,
                'message': result['message']
            }), 404
            
    except Exception as e:
        logger.error(f"获取插件配置失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取插件配置失败: {str(e)}'
        }), 500


@plugins_bp.route('/<plugin_id>/config', methods=['PUT'])
def save_plugin_config(plugin_id):
    """保存插件配置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'message': '请提供配置数据'
            }), 400
        
        result = PluginManager.save_plugin_config(plugin_id, data)
        
        if result['success']:
            return jsonify({
                'code': 200,
                'message': result['message']
            })
        else:
            return jsonify({
                'code': 400,
                'message': result['message']
            }), 400
            
    except Exception as e:
        logger.error(f"保存插件配置失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'保存插件配置失败: {str(e)}'
        }), 500


@plugins_bp.route('/<plugin_id>/test', methods=['POST'])
def test_plugin(plugin_id):
    """
    测试插件功能
    
    对于邮件插件，发送一封测试邮件
    """
    try:
        # 检查插件是否存在
        plugin = PluginManager.get_plugin(plugin_id)
        if not plugin:
            return jsonify({
                'code': 404,
                'message': f'插件 {plugin_id} 不存在'
            }), 404
        
        # 获取请求中的临时配置（用于测试未保存的配置）
        data = request.get_json() or {}
        temp_config = data.get('config')
        
        # 执行测试
        result = PluginExecutor.test_plugin(plugin_id, temp_config)
        
        if result['success']:
            return jsonify({
                'code': 200,
                'message': result['message'],
                'data': {'logs': result.get('logs', [])}
            })
        else:
            return jsonify({
                'code': 400,
                'message': result['message'],
                'data': {'logs': result.get('logs', [])}
            }), 400
            
    except Exception as e:
        logger.error(f"测试插件失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'测试插件失败: {str(e)}'
        }), 500


# ==================== 插件导入/导出接口 ====================

@plugins_bp.route('/<plugin_id>/export', methods=['GET'])
def export_plugin(plugin_id):
    """导出插件为zip包"""
    try:
        zip_data, result = PluginManager.export_plugin(plugin_id)
        
        if zip_data is None:
            return jsonify({
                'code': 404,
                'message': result  # result 是错误信息
            }), 404
        
        # 返回文件下载
        return send_file(
            BytesIO(zip_data),
            mimetype='application/zip',
            as_attachment=True,
            download_name=result  # result 是文件名
        )
            
    except Exception as e:
        logger.error(f"导出插件失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'导出插件失败: {str(e)}'
        }), 500


@plugins_bp.route('/import', methods=['POST'])
def import_plugin():
    """
    导入插件
    
    请求方式：multipart/form-data
    参数：
        - file: 插件包文件（.zip）
        - overwrite: 是否覆盖已存在的插件（可选，默认false）
    """
    try:
        # 检查文件
        if 'file' not in request.files:
            return jsonify({
                'code': 400,
                'message': '请上传插件包文件'
            }), 400
        
        file = request.files['file']
        if not file.filename:
            return jsonify({
                'code': 400,
                'message': '请选择要上传的文件'
            }), 400
        
        if not file.filename.endswith('.zip'):
            return jsonify({
                'code': 400,
                'message': '插件包必须是.zip格式'
            }), 400
        
        # 读取文件内容
        zip_data = file.read()
        
        # 获取覆盖参数
        overwrite = request.form.get('overwrite', 'false').lower() == 'true'
        
        # 导入插件
        result = PluginManager.import_plugin(zip_data, overwrite=overwrite)
        
        if result['success']:
            return jsonify({
                'code': 200,
                'message': result['message'],
                'data': {'plugin_id': result['plugin_id']}
            })
        elif result.get('need_confirm'):
            # 需要用户确认覆盖
            return jsonify({
                'code': 409,
                'message': result['message'],
                'data': {
                    'plugin_id': result['plugin_id'],
                    'need_confirm': True
                }
            }), 409
        else:
            return jsonify({
                'code': 400,
                'message': result['message'],
                'data': {'plugin_id': result.get('plugin_id')}
            }), 400
            
    except Exception as e:
        logger.error(f"导入插件失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'导入插件失败: {str(e)}'
        }), 500


# ==================== 插件执行统计接口 ====================

@plugins_bp.route('/<plugin_id>/stats', methods=['GET'])
def get_plugin_stats(plugin_id):
    """获取插件执行统计"""
    try:
        # 检查插件是否存在
        plugin = PluginManager.get_plugin(plugin_id)
        if not plugin:
            return jsonify({
                'code': 404,
                'message': f'插件 {plugin_id} 不存在'
            }), 404
        
        stats = PluginExecutor.get_plugin_stats(plugin_id)
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': stats
        })
            
    except Exception as e:
        logger.error(f"获取插件统计失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取插件统计失败: {str(e)}'
        }), 500


# ==================== 任务插件关联接口 ====================

@plugins_bp.route('/task/<task_type>/<int:task_id>', methods=['GET'])
def get_task_plugins(task_type, task_id):
    """
    获取任务关联的插件列表
    
    Args:
        task_type: 任务类型（transfer/download/video）
        task_id: 任务ID
    """
    try:
        # 验证任务类型
        valid_types = ['transfer', 'download', 'video']
        if task_type not in valid_types:
            return jsonify({
                'code': 400,
                'message': f'无效的任务类型，支持: {", ".join(valid_types)}'
            }), 400
        
        relations = TaskPluginRelation.get_by_task(task_id, task_type)
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': [r.to_dict() for r in relations]
        })
            
    except Exception as e:
        logger.error(f"获取任务插件关联失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取任务插件关联失败: {str(e)}'
        }), 500


@plugins_bp.route('/task/<task_type>/<int:task_id>', methods=['PUT'])
def save_task_plugins(task_type, task_id):
    """
    保存任务的插件关联
    
    Args:
        task_type: 任务类型（transfer/download/video）
        task_id: 任务ID
    
    请求体：
        {
            "plugins": [
                {
                    "plugin_id": "email_notify",
                    "sort_order": 0,
                    "pass_task_param": true,
                    "delay_seconds": 0,
                    "plugin_config": {}
                }
            ]
        }
    """
    try:
        # 验证任务类型
        valid_types = ['transfer', 'download', 'video']
        if task_type not in valid_types:
            return jsonify({
                'code': 400,
                'message': f'无效的任务类型，支持: {", ".join(valid_types)}'
            }), 400
        
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'message': '请提供插件关联数据'
            }), 400
        
        plugins = data.get('plugins', [])
        
        # 验证插件是否存在
        for plugin in plugins:
            plugin_id = plugin.get('plugin_id')
            if not plugin_id:
                return jsonify({
                    'code': 400,
                    'message': '插件ID不能为空'
                }), 400
            
            if not PluginInfo.exists(plugin_id):
                return jsonify({
                    'code': 400,
                    'message': f'插件 {plugin_id} 不存在'
                }), 400
        
        # 保存关联
        count = TaskPluginRelation.save_task_plugins(task_id, task_type, plugins)
        
        return jsonify({
            'code': 200,
            'message': f'成功保存 {count} 个插件关联'
        })
            
    except Exception as e:
        logger.error(f"保存任务插件关联失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'保存任务插件关联失败: {str(e)}'
        }), 500


@plugins_bp.route('/task/<task_type>/<int:task_id>', methods=['DELETE'])
def delete_task_plugins(task_type, task_id):
    """
    删除任务的所有插件关联
    
    Args:
        task_type: 任务类型（transfer/download/video）
        task_id: 任务ID
    """
    try:
        # 验证任务类型
        valid_types = ['transfer', 'download', 'video']
        if task_type not in valid_types:
            return jsonify({
                'code': 400,
                'message': f'无效的任务类型，支持: {", ".join(valid_types)}'
            }), 400
        
        count = TaskPluginRelation.delete_by_task(task_id, task_type)
        
        return jsonify({
            'code': 200,
            'message': f'成功删除 {count} 个插件关联'
        })
            
    except Exception as e:
        logger.error(f"删除任务插件关联失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'删除任务插件关联失败: {str(e)}'
        }), 500


# ==================== 插件执行日志接口 ====================

@plugins_bp.route('/logs/execution/<int:execution_id>', methods=['GET'])
def get_execution_logs(execution_id):
    """获取执行记录的插件日志"""
    try:
        logs = PluginExecutor.get_execution_logs(execution_id)
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': logs
        })
            
    except Exception as e:
        logger.error(f"获取执行日志失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取执行日志失败: {str(e)}'
        }), 500


@plugins_bp.route('/logs/plugin/<plugin_id>', methods=['GET'])
def get_plugin_logs(plugin_id):
    """获取插件的执行日志"""
    try:
        # 检查插件是否存在
        plugin = PluginManager.get_plugin(plugin_id)
        if not plugin:
            return jsonify({
                'code': 404,
                'message': f'插件 {plugin_id} 不存在'
            }), 404
        
        limit = request.args.get('limit', 100, type=int)
        logs = PluginExecLog.get_by_plugin(plugin_id, limit=limit)
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': [log.to_dict() for log in logs]
        })
            
    except Exception as e:
        logger.error(f"获取插件日志失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取插件日志失败: {str(e)}'
        }), 500


@plugins_bp.route('/logs/recent', methods=['GET'])
def get_recent_logs():
    """获取最近的插件执行日志"""
    try:
        limit = request.args.get('limit', 100, type=int)
        logs = PluginExecLog.get_recent(limit=limit)
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': [log.to_dict() for log in logs]
        })
            
    except Exception as e:
        logger.error(f"获取最近日志失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取最近日志失败: {str(e)}'
        }), 500

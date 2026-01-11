# -*- coding: utf-8 -*-
"""
正则规则库API
"""
from flask import Blueprint, request, jsonify
from services.regex_rule_service import RegexRuleService
from utils.filename_replacer import FilenameReplacer
from utils.logger import logger

regex_rules_bp = Blueprint('regex_rules', __name__, url_prefix='/api/regex-rules')


@regex_rules_bp.route('/rules', methods=['GET'])
def get_rules():
    """获取所有规则"""
    try:
        rules = RegexRuleService.get_all_rules()
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': rules
        })
    except Exception as e:
        logger.error(f"获取规则列表失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取规则列表失败: {str(e)}'
        }), 500


@regex_rules_bp.route('/rule', methods=['POST'])
def create_rule():
    """创建规则"""
    try:
        data = request.get_json()
        
        # 验证必填字段
        if not data.get('name'):
            return jsonify({
                'code': 400,
                'message': '规则名称不能为空'
            }), 400
        
        if not data.get('regex_pattern'):
            return jsonify({
                'code': 400,
                'message': '正则表达式不能为空'
            }), 400
        
        if not data.get('replacement_pattern'):
            return jsonify({
                'code': 400,
                'message': '替换表达式不能为空'
            }), 400
        
        # 创建规则
        rule_id = RegexRuleService.create_rule(
            data['name'],
            data['regex_pattern'],
            data['replacement_pattern'],
            data.get('description')
        )
        
        return jsonify({
            'code': 200,
            'message': '规则创建成功',
            'data': {'id': rule_id}
        })
    except ValueError as e:
        return jsonify({
            'code': 400,
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"创建规则失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'创建规则失败: {str(e)}'
        }), 500


@regex_rules_bp.route('/rule/<int:rule_id>', methods=['GET'])
def get_rule(rule_id):
    """获取规则详情"""
    try:
        rule = RegexRuleService.get_rule_by_id(rule_id)
        if not rule:
            return jsonify({
                'code': 404,
                'message': '规则不存在'
            }), 404
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': rule
        })
    except Exception as e:
        logger.error(f"获取规则详情失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'获取规则详情失败: {str(e)}'
        }), 500


@regex_rules_bp.route('/rule/<int:rule_id>', methods=['PUT'])
def update_rule(rule_id):
    """更新规则"""
    try:
        data = request.get_json()
        
        # 验证规则是否存在
        rule = RegexRuleService.get_rule_by_id(rule_id)
        if not rule:
            return jsonify({
                'code': 404,
                'message': '规则不存在'
            }), 404
        
        # 更新规则
        RegexRuleService.update_rule(rule_id, **data)
        
        return jsonify({
            'code': 200,
            'message': '规则更新成功'
        })
    except ValueError as e:
        return jsonify({
            'code': 400,
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"更新规则失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'更新规则失败: {str(e)}'
        }), 500


@regex_rules_bp.route('/rule/<int:rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    """删除规则"""
    try:
        # 验证规则是否存在
        rule = RegexRuleService.get_rule_by_id(rule_id)
        if not rule:
            return jsonify({
                'code': 404,
                'message': '规则不存在'
            }), 404
        
        # 删除规则
        RegexRuleService.delete_rule(rule_id)
        
        return jsonify({
            'code': 200,
            'message': '规则删除成功'
        })
    except Exception as e:
        logger.error(f"删除规则失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'删除规则失败: {str(e)}'
        }), 500


@regex_rules_bp.route('/preview', methods=['POST'])
def preview_replacement():
    """预览替换效果"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        regex_pattern = data.get('regex_pattern')
        replacement_pattern = data.get('replacement_pattern', '')  # 替换表达式可以为空（表示删除匹配内容）
        
        if not filename:
            return jsonify({
                'code': 400,
                'message': '文件名不能为空'
            }), 400
        
        if not regex_pattern:
            return jsonify({
                'code': 400,
                'message': '正则表达式不能为空'
            }), 400
        
        # 应用替换
        success, new_filename, message = FilenameReplacer.apply_regex_replacement(
            filename, regex_pattern, replacement_pattern
        )
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'matched': success,
                'original': filename,
                'result': new_filename,
                'message': message
            }
        })
    except Exception as e:
        logger.error(f"预览替换效果失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'预览失败: {str(e)}'
        }), 500

# -*- coding: utf-8 -*-
"""
正则规则库服务
"""
from models.regex_rule import RegexRule
from utils.filename_replacer import FilenameReplacer


class RegexRuleService:
    """正则规则库服务"""
    
    @staticmethod
    def get_all_rules():
        """获取所有规则"""
        return RegexRule.get_all()
    
    @staticmethod
    def get_rule_by_id(rule_id):
        """根据ID获取规则"""
        return RegexRule.get_by_id(rule_id)
    
    @staticmethod
    def create_rule(name, regex_pattern, replacement_pattern, description=None):
        """
        创建规则
        
        参数:
            name: 规则名称
            regex_pattern: 正则表达式
            replacement_pattern: 替换表达式
            description: 规则描述
            
        返回:
            规则ID
        """
        # 验证正则表达式
        valid, error_msg = FilenameReplacer.validate_regex(regex_pattern)
        if not valid:
            raise ValueError(error_msg)
        
        return RegexRule.create(name, regex_pattern, replacement_pattern, description)
    
    @staticmethod
    def update_rule(rule_id, **kwargs):
        """
        更新规则
        
        参数:
            rule_id: 规则ID
            **kwargs: 要更新的字段
            
        返回:
            是否更新成功
        """
        # 如果更新了正则表达式,需要验证
        if 'regex_pattern' in kwargs:
            valid, error_msg = FilenameReplacer.validate_regex(kwargs['regex_pattern'])
            if not valid:
                raise ValueError(error_msg)
        
        return RegexRule.update(rule_id, **kwargs)
    
    @staticmethod
    def delete_rule(rule_id):
        """删除规则"""
        return RegexRule.delete(rule_id)

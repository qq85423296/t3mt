# -*- coding: utf-8 -*-
"""
正则规则模型
"""
from database import get_db
from datetime import datetime


class RegexRule:
    """正则规则模型"""
    
    @staticmethod
    def get_all():
        """获取所有规则"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM regex_rules 
                ORDER BY created_at DESC
            ''')
            rules = cursor.fetchall()
            return [dict(rule) for rule in rules]
    
    @staticmethod
    def get_by_id(rule_id):
        """根据ID获取规则"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM regex_rules WHERE id = ?
            ''', (rule_id,))
            rule = cursor.fetchone()
            return dict(rule) if rule else None
    
    @staticmethod
    def create(name, regex_pattern, replacement_pattern, description=None):
        """创建规则"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO regex_rules 
                (name, regex_pattern, replacement_pattern, description)
                VALUES (?, ?, ?, ?)
            ''', (name, regex_pattern, replacement_pattern, description))
            return cursor.lastrowid
    
    @staticmethod
    def update(rule_id, **kwargs):
        """更新规则"""
        # 添加更新时间
        kwargs['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 构建更新语句
        fields = ', '.join([f'{k} = ?' for k in kwargs.keys()])
        values = list(kwargs.values()) + [rule_id]
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f'UPDATE regex_rules SET {fields} WHERE id = ?',
                values
            )
            return cursor.rowcount > 0
    
    @staticmethod
    def delete(rule_id):
        """删除规则"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM regex_rules WHERE id = ?', (rule_id,))
            return cursor.rowcount > 0

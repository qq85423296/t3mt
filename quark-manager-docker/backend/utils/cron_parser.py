# -*- coding: utf-8 -*-
"""
Cron表达式解析工具
"""
from datetime import datetime, timedelta
from croniter import croniter


class CronParser:
    """Cron表达式解析器"""
    
    @staticmethod
    def is_valid(cron_expression):
        """验证Cron表达式是否有效"""
        try:
            croniter(cron_expression)
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_next_run_time(cron_expression, base_time=None):
        """获取下次运行时间"""
        if base_time is None:
            base_time = datetime.now()
        
        try:
            cron = croniter(cron_expression, base_time)
            return cron.get_next(datetime)
        except Exception as e:
            print(f"解析Cron表达式失败: {e}")
            return None
    
    @staticmethod
    def get_next_n_run_times(cron_expression, n=5, base_time=None):
        """获取未来N次运行时间"""
        if base_time is None:
            base_time = datetime.now()
        
        try:
            cron = croniter(cron_expression, base_time)
            times = []
            for _ in range(n):
                times.append(cron.get_next(datetime))
            return times
        except Exception as e:
            print(f"解析Cron表达式失败: {e}")
            return []
    
    @staticmethod
    def get_description(cron_expression):
        """获取Cron表达式的描述"""
        # 简单的描述生成，可以使用cron-descriptor库增强
        parts = cron_expression.split()
        if len(parts) < 5:
            return "无效的Cron表达式"
        
        minute, hour, day, month, weekday = parts[:5]
        
        desc_parts = []
        
        # 分钟
        if minute == '*':
            desc_parts.append("每分钟")
        elif minute.isdigit():
            desc_parts.append(f"第{minute}分钟")
        
        # 小时
        if hour == '*':
            desc_parts.append("每小时")
        elif hour.isdigit():
            desc_parts.append(f"{hour}点")
        
        # 日期
        if day == '*':
            desc_parts.append("每天")
        elif day.isdigit():
            desc_parts.append(f"每月{day}日")
        
        # 月份
        if month != '*' and month.isdigit():
            desc_parts.append(f"{month}月")
        
        # 星期
        if weekday != '*' and weekday != '?':
            weekday_map = {
                '0': '周日', '1': '周一', '2': '周二', '3': '周三',
                '4': '周四', '5': '周五', '6': '周六'
            }
            if weekday in weekday_map:
                desc_parts.append(weekday_map[weekday])
        
        return ' '.join(desc_parts) if desc_parts else "自定义时间"

# -*- coding: utf-8 -*-
"""
任务调度器
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from utils.logger import logger


class TaskScheduler:
    """任务调度器类"""
    
    def __init__(self):
        """初始化调度器"""
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logger.info("任务调度器已启动")
    
    def add_transfer_task(self, task_id, cron_expression, execute_func):
        """
        添加转存任务
        
        Args:
            task_id: 任务ID
            cron_expression: Cron表达式
            execute_func: 执行函数
        """
        try:
            job_id = f'transfer_{task_id}'
            trigger = CronTrigger.from_crontab(cron_expression)
            
            self.scheduler.add_job(
                func=execute_func,
                trigger=trigger,
                id=job_id,
                args=[task_id],
                replace_existing=True
            )
            
            logger.info(f"添加转存任务到调度器: ID {task_id}, Cron: {cron_expression}")
        except Exception as e:
            logger.error(f"添加转存任务失败: {e}")
            raise
    
    def add_download_task(self, task_id, cron_expression, execute_func):
        """
        添加下载任务
        
        Args:
            task_id: 任务ID
            cron_expression: Cron表达式
            execute_func: 执行函数
        """
        try:
            job_id = f'download_{task_id}'
            trigger = CronTrigger.from_crontab(cron_expression)
            
            self.scheduler.add_job(
                func=execute_func,
                trigger=trigger,
                id=job_id,
                args=[task_id],
                replace_existing=True
            )
            
            logger.info(f"添加下载任务到调度器: ID {task_id}, Cron: {cron_expression}")
        except Exception as e:
            logger.error(f"添加下载任务失败: {e}")
            raise
    
    def remove_task(self, task_id, task_type='transfer'):
        """
        移除任务
        
        Args:
            task_id: 任务ID
            task_type: 任务类型 (transfer/download)
        """
        try:
            job_id = f'{task_type}_{task_id}'
            self.scheduler.remove_job(job_id)
            logger.info(f"从调度器移除任务: {job_id}")
        except Exception as e:
            logger.error(f"移除任务失败: {e}")
            raise
    
    def pause_task(self, task_id, task_type='transfer'):
        """
        暂停任务
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
        """
        try:
            job_id = f'{task_type}_{task_id}'
            self.scheduler.pause_job(job_id)
            logger.info(f"暂停任务: {job_id}")
        except Exception as e:
            logger.error(f"暂停任务失败: {e}")
            raise
    
    def resume_task(self, task_id, task_type='transfer'):
        """
        恢复任务
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
        """
        try:
            job_id = f'{task_type}_{task_id}'
            self.scheduler.resume_job(job_id)
            logger.info(f"恢复任务: {job_id}")
        except Exception as e:
            logger.error(f"恢复任务失败: {e}")
            raise
    
    def get_job(self, task_id, task_type='transfer'):
        """
        获取任务信息
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
        
        Returns:
            任务信息
        """
        try:
            job_id = f'{task_type}_{task_id}'
            job = self.scheduler.get_job(job_id)
            return job
        except Exception as e:
            logger.error(f"获取任务信息失败: {e}")
            return None
    
    def shutdown(self):
        """关闭调度器"""
        try:
            self.scheduler.shutdown()
            logger.info("任务调度器已关闭")
        except Exception as e:
            logger.error(f"关闭调度器失败: {e}")


# 全局调度器实例
task_scheduler = TaskScheduler()

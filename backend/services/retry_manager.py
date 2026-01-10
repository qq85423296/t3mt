# -*- coding: utf-8 -*-
"""
重试管理器
用于管理剧集下载失败记录和重试逻辑
"""
from datetime import datetime, timedelta
from typing import Tuple, Dict, List, Optional
from models.episode_failure_record import EpisodeFailureRecord
from utils.logger import logger


class RetryManager:
    """重试管理器"""
    
    def __init__(self):
        """初始化重试管理器"""
        pass
    
    def should_retry(self, task_id: int, episode_url: str, 
                     max_retry_count: int, retry_interval: int) -> Tuple[bool, int, str]:
        """
        判断是否应该重试
        
        Args:
            task_id: 任务ID
            episode_url: 剧集URL
            max_retry_count: 最大重试次数
            retry_interval: 重试间隔(分钟)
            
        Returns:
            (should_retry, current_count, reason)
            - should_retry: 是否应该重试
            - current_count: 当前失败次数
            - reason: 不重试的原因(如果不应该重试)
        """
        try:
            # 获取失败记录
            record = EpisodeFailureRecord.get_by_task_and_url(task_id, episode_url)
            
            # 如果没有失败记录，可以下载
            if not record:
                return True, 0, ""
            
            current_count = record.failure_count
            
            # 检查是否已达最大重试次数
            if current_count >= max_retry_count:
                reason = f"已达最大重试次数({max_retry_count}次)，停止重试"
                logger.info(f"剧集 {episode_url} {reason}")
                return False, current_count, reason
            
            # 检查是否到达重试时间
            if record.last_failure_time:
                try:
                    last_failure_time = datetime.strptime(
                        record.last_failure_time, 
                        '%Y-%m-%d %H:%M:%S'
                    )
                    retry_time = last_failure_time + timedelta(minutes=retry_interval)
                    
                    if datetime.now() < retry_time:
                        remaining_minutes = int((retry_time - datetime.now()).total_seconds() / 60)
                        reason = f"未到重试时间，还需等待{remaining_minutes}分钟"
                        logger.info(f"剧集 {episode_url} {reason}")
                        return False, current_count, reason
                except Exception as e:
                    logger.warning(f"解析失败时间失败: {str(e)}")
                    # 解析失败时允许重试
            
            # 可以重试
            return True, current_count, ""
            
        except Exception as e:
            logger.error(f"判断是否重试失败: {str(e)}", exc_info=True)
            # 出错时允许重试，避免阻断下载流程
            return True, 0, ""
    
    def record_failure(self, task_id: int, episode_url: str, 
                      episode_name: str, reason: str) -> int:
        """
        记录失败
        
        Args:
            task_id: 任务ID
            episode_url: 剧集URL
            episode_name: 剧集名称
            reason: 失败原因
            
        Returns:
            当前失败次数
        """
        try:
            # 更新失败次数（如果不存在则创建）
            failure_count = EpisodeFailureRecord.update_failure_count(
                task_id, 
                episode_url, 
                episode_name, 
                reason
            )
            
            logger.info(f"记录失败: {episode_name}, 失败次数: {failure_count}, 原因: {reason}")
            return failure_count
            
        except Exception as e:
            logger.error(f"记录失败信息失败: {str(e)}", exc_info=True)
            # 返回1作为默认值，避免阻断流程
            return 1
    
    def record_success(self, task_id: int, episode_url: str):
        """
        记录成功，清除失败记录
        
        Args:
            task_id: 任务ID
            episode_url: 剧集URL
        """
        try:
            EpisodeFailureRecord.delete(task_id, episode_url)
            logger.info(f"清除失败记录: task_id={task_id}, url={episode_url}")
        except Exception as e:
            logger.error(f"清除失败记录失败: {str(e)}", exc_info=True)
    
    def get_retry_info(self, task_id: int, episode_url: str) -> Optional[Dict]:
        """
        获取重试信息
        
        Args:
            task_id: 任务ID
            episode_url: 剧集URL
            
        Returns:
            重试信息字典，如果没有失败记录则返回None
        """
        try:
            record = EpisodeFailureRecord.get_by_task_and_url(task_id, episode_url)
            
            if not record:
                return None
            
            return {
                'failure_count': record.failure_count,
                'last_failure_time': record.last_failure_time,
                'last_failure_reason': record.last_failure_reason,
                'episode_name': record.episode_name
            }
        except Exception as e:
            logger.error(f"获取重试信息失败: {str(e)}", exc_info=True)
            return None
    
    def clear_task_failures(self, task_id: int):
        """
        清除任务的所有失败记录
        
        Args:
            task_id: 任务ID
        """
        try:
            EpisodeFailureRecord.delete_by_task(task_id)
            logger.info(f"清除任务 {task_id} 的所有失败记录")
        except Exception as e:
            logger.error(f"清除任务失败记录失败: {str(e)}", exc_info=True)
    
    def get_failed_episodes(self, task_id: int, max_retry_count: int) -> List[Dict]:
        """
        获取需要重试的失败剧集列表
        
        Args:
            task_id: 任务ID
            max_retry_count: 最大重试次数
            
        Returns:
            失败剧集信息列表
        """
        try:
            # 获取未达最大重试次数的失败剧集
            records = EpisodeFailureRecord.get_failed_episodes(task_id, max_retry_count)
            
            result = []
            for record in records:
                result.append({
                    'episode_url': record.episode_url,
                    'episode_name': record.episode_name,
                    'failure_count': record.failure_count,
                    'last_failure_time': record.last_failure_time,
                    'last_failure_reason': record.last_failure_reason
                })
            
            logger.info(f"任务 {task_id} 有 {len(result)} 个剧集需要重试")
            return result
            
        except Exception as e:
            logger.error(f"获取失败剧集列表失败: {str(e)}", exc_info=True)
            return []


# 创建全局实例
retry_manager = RetryManager()

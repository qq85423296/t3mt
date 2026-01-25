# -*- coding: utf-8 -*-
"""
任务自动失效服务
负责检测并处理超时的影视下载、定时转存、定时下载任务
"""
from datetime import datetime, timedelta
from database import get_db
from utils.logger import logger
from models.config import ConfigModel
from models.video_task import VideoTask
from models.episode_failure_record import EpisodeFailureRecord


class AutoExpirationService:
    """自动失效服务"""
    
    @classmethod
    def check_and_expire_tasks(cls):
        """
        检查并处理超时任务
        
        主入口方法，由SchedulerService在任务执行后调用
        """
        try:
            logger.info("[AutoExpiration] 开始检查任务过期")
            
            # 获取配置，使用默认值防止配置缺失
            try:
                # 影视下载配置
                video_enabled = ConfigModel.get_config('video_auto_expiration_enabled', '1')
                video_days_str = ConfigModel.get_config('video_auto_expiration_days', '7')
                video_days = int(video_days_str)
                
                # 定时转存配置
                transfer_enabled = ConfigModel.get_config('transfer_auto_expiration_enabled', '1')
                transfer_days_str = ConfigModel.get_config('transfer_auto_expiration_days', '7')
                transfer_days = int(transfer_days_str)
                
                # 定时下载配置
                download_enabled = ConfigModel.get_config('download_auto_expiration_enabled', '1')
                download_days_str = ConfigModel.get_config('download_auto_expiration_days', '7')
                download_days = int(download_days_str)
                
                # 验证配置值的合法性
                if video_days < 1 or video_days > 365:
                    logger.warning(f"[AutoExpiration] 影视下载配置的超时天数不合法: {video_days}，使用默认值7天")
                    video_days = 7
                
                if transfer_days < 1 or transfer_days > 365:
                    logger.warning(f"[AutoExpiration] 定时转存配置的超时天数不合法: {transfer_days}，使用默认值7天")
                    transfer_days = 7
                
                if download_days < 1 or download_days > 365:
                    logger.warning(f"[AutoExpiration] 定时下载配置的超时天数不合法: {download_days}，使用默认值7天")
                    download_days = 7
                    
            except ValueError as e:
                logger.warning(f"[AutoExpiration] 配置值转换失败: {e}，使用默认值：启用=true, 天数=7")
                video_enabled = transfer_enabled = download_enabled = '1'
                video_days = transfer_days = download_days = 7
            except Exception as e:
                logger.error(f"[AutoExpiration] 获取配置失败: {e}，使用默认值：启用=true, 天数=7")
                video_enabled = transfer_enabled = download_enabled = '1'
                video_days = transfer_days = download_days = 7
            
            # 检查影视下载任务
            if video_enabled == '1':
                logger.info(f"[AutoExpiration] 影视下载配置：启用={video_enabled}, 超时天数={video_days}")
                cls._check_video_tasks(video_days)
            else:
                logger.info("[AutoExpiration] 影视下载自动失效功能已禁用，跳过检查")
            
            # 检查定时转存任务
            if transfer_enabled == '1':
                logger.info(f"[AutoExpiration] 定时转存配置：启用={transfer_enabled}, 超时天数={transfer_days}")
                cls._check_transfer_tasks(transfer_days)
            else:
                logger.info("[AutoExpiration] 定时转存自动失效功能已禁用，跳过检查")
            
            # 检查定时下载任务
            if download_enabled == '1':
                logger.info(f"[AutoExpiration] 定时下载配置：启用={download_enabled}, 超时天数={download_days}")
                cls._check_download_tasks(download_days)
            else:
                logger.info("[AutoExpiration] 定时下载自动失效功能已禁用，跳过检查")
            
            logger.info("[AutoExpiration] 检查完成")
            
        except Exception as e:
            logger.error(f"[AutoExpiration] 检查任务过期失败: {e}", exc_info=True)
    
    @classmethod
    def _check_video_tasks(cls, days):
        """检查影视下载任务"""
        try:
            # 查询所有生效状态的任务
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, name, last_episode_update_time, status
                        FROM video_tasks
                        WHERE status = 'active'
                    """)
                    tasks = cursor.fetchall()
            except Exception as e:
                logger.error(f"[AutoExpiration] 查询影视任务列表失败: {e}", exc_info=True)
                return
            
            if not tasks:
                logger.info("[AutoExpiration] 没有生效状态的影视任务需要检查")
                return
            
            logger.info(f"[AutoExpiration] 发现 {len(tasks)} 个生效影视任务，开始检查")
            
            expired_count = 0
            error_count = 0
            
            # 遍历每个任务
            for task_row in tasks:
                task_id = task_row['id']
                task_name = task_row['name']
                last_update_time = task_row['last_episode_update_time']
                
                try:
                    # 判断任务是否超时（超过配置天数没有新剧集）
                    if not cls._is_task_expired(last_update_time, days):
                        logger.debug(f"[AutoExpiration] 影视任务未超时，跳过: {task_name} (ID: {task_id})")
                        continue
                    
                    logger.info(f"[AutoExpiration] 影视任务已超时: {task_name} (ID: {task_id}), 最后更新时间: {last_update_time}")
                    
                    # 验证所有剧集是否下载成功
                    if not cls._is_all_episodes_downloaded(task_id):
                        logger.info(f"[AutoExpiration] 影视任务存在未下载剧集，不满足失效条件: {task_name} (ID: {task_id})")
                        continue
                    
                    logger.info(f"[AutoExpiration] 影视任务满足失效条件: {task_name} (ID: {task_id})")
                    
                    # 执行失效操作
                    cls._expire_task(task_id, task_name, days, 'video')
                    expired_count += 1
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"[AutoExpiration] 检查影视任务失败: {task_name} (ID: {task_id}), error={e}", exc_info=True)
                    # 继续处理下一个任务，不中断整个检查流程
                    continue
            
            logger.info(f"[AutoExpiration] 影视任务检查完成，共失效 {expired_count} 个任务，失败 {error_count} 个任务")
            
        except Exception as e:
            logger.error(f"[AutoExpiration] 检查影视任务失败: {e}", exc_info=True)
    
    @classmethod
    def _check_transfer_tasks(cls, days):
        """检查定时转存任务"""
        try:
            # 查询所有生效状态的任务
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, name, last_content_update_time, status
                        FROM transfer_tasks
                        WHERE status = 'active'
                    """)
                    tasks = cursor.fetchall()
            except Exception as e:
                logger.error(f"[AutoExpiration] 查询转存任务列表失败: {e}", exc_info=True)
                return
            
            if not tasks:
                logger.info("[AutoExpiration] 没有生效状态的转存任务需要检查")
                return
            
            logger.info(f"[AutoExpiration] 发现 {len(tasks)} 个生效转存任务，开始检查")
            
            expired_count = 0
            error_count = 0
            
            # 遍历每个任务
            for task_row in tasks:
                task_id = task_row['id']
                task_name = task_row['name']
                last_update_time = task_row['last_content_update_time']
                
                try:
                    # 判断任务是否超时（超过配置天数没有新内容）
                    if not cls._is_task_expired(last_update_time, days):
                        logger.debug(f"[AutoExpiration] 转存任务未超时，跳过: {task_name} (ID: {task_id})")
                        continue
                    
                    logger.info(f"[AutoExpiration] 转存任务已超时: {task_name} (ID: {task_id}), 最后更新时间: {last_update_time}")
                    
                    # 验证最近的执行记录是否全部成功
                    if not cls._is_recent_execution_all_success(task_id, 'transfer'):
                        logger.info(f"[AutoExpiration] 转存任务存在失败记录，不满足失效条件: {task_name} (ID: {task_id})")
                        continue
                    
                    logger.info(f"[AutoExpiration] 转存任务满足失效条件: {task_name} (ID: {task_id})")
                    
                    # 执行失效操作
                    cls._expire_task(task_id, task_name, days, 'transfer')
                    expired_count += 1
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"[AutoExpiration] 检查转存任务失败: {task_name} (ID: {task_id}), error={e}", exc_info=True)
                    # 继续处理下一个任务，不中断整个检查流程
                    continue
            
            logger.info(f"[AutoExpiration] 转存任务检查完成，共失效 {expired_count} 个任务，失败 {error_count} 个任务")
            
        except Exception as e:
            logger.error(f"[AutoExpiration] 检查转存任务失败: {e}", exc_info=True)
    
    @classmethod
    def _check_download_tasks(cls, days):
        """检查定时下载任务"""
        try:
            # 查询所有生效状态的任务
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, name, last_content_update_time, status
                        FROM download_tasks
                        WHERE status = 'active'
                    """)
                    tasks = cursor.fetchall()
            except Exception as e:
                logger.error(f"[AutoExpiration] 查询下载任务列表失败: {e}", exc_info=True)
                return
            
            if not tasks:
                logger.info("[AutoExpiration] 没有生效状态的下载任务需要检查")
                return
            
            logger.info(f"[AutoExpiration] 发现 {len(tasks)} 个生效下载任务，开始检查")
            
            expired_count = 0
            error_count = 0
            
            # 遍历每个任务
            for task_row in tasks:
                task_id = task_row['id']
                task_name = task_row['name']
                last_update_time = task_row['last_content_update_time']
                
                try:
                    # 判断任务是否超时（超过配置天数没有新内容）
                    if not cls._is_task_expired(last_update_time, days):
                        logger.debug(f"[AutoExpiration] 下载任务未超时，跳过: {task_name} (ID: {task_id})")
                        continue
                    
                    logger.info(f"[AutoExpiration] 下载任务已超时: {task_name} (ID: {task_id}), 最后更新时间: {last_update_time}")
                    
                    # 验证最近的执行记录是否全部成功
                    if not cls._is_recent_execution_all_success(task_id, 'download'):
                        logger.info(f"[AutoExpiration] 下载任务存在失败记录，不满足失效条件: {task_name} (ID: {task_id})")
                        continue
                    
                    logger.info(f"[AutoExpiration] 下载任务满足失效条件: {task_name} (ID: {task_id})")
                    
                    # 执行失效操作
                    cls._expire_task(task_id, task_name, days, 'download')
                    expired_count += 1
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"[AutoExpiration] 检查下载任务失败: {task_name} (ID: {task_id}), error={e}", exc_info=True)
                    # 继续处理下一个任务，不中断整个检查流程
                    continue
            
            logger.info(f"[AutoExpiration] 下载任务检查完成，共失效 {expired_count} 个任务，失败 {error_count} 个任务")
            
        except Exception as e:
            logger.error(f"[AutoExpiration] 检查下载任务失败: {e}", exc_info=True)
    
    @classmethod
    def _is_recent_execution_all_success(cls, task_id, task_type):
        """
        判断最近的执行记录是否全部成功
        
        Args:
            task_id: 任务ID
            task_type: 任务类型（transfer/download）
            
        Returns:
            bool: 是否所有最近执行都成功
        """
        try:
            # 查询该任务最近的执行记录（最近7天）
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT status, failed_count
                        FROM task_execution_history
                        WHERE task_id = ? AND task_type = ?
                          AND start_time >= datetime('now', '-7 days')
                        ORDER BY start_time DESC
                    """, (task_id, task_type))
                    recent_executions = cursor.fetchall()
            except Exception as e:
                logger.error(f"[AutoExpiration] 查询执行记录失败: task_id={task_id}, task_type={task_type}, error={e}", exc_info=True)
                # 查询失败时保守处理，视为有失败记录
                return False
            
            # 如果没有执行记录，视为不满足条件
            if not recent_executions:
                logger.info(f"[AutoExpiration] 任务没有执行记录: task_id={task_id}, task_type={task_type}")
                return False
            
            # 检查是否存在失败或部分成功的记录
            for execution in recent_executions:
                status = execution['status']
                failed_count = execution['failed_count'] or 0
                
                # 如果状态为失败或部分成功，或者有失败数量，视为不满足条件
                if status in ['failed', 'partial'] or failed_count > 0:
                    logger.info(f"[AutoExpiration] 任务存在失败执行记录: task_id={task_id}, task_type={task_type}, status={status}, failed_count={failed_count}")
                    return False
            
            # 所有执行记录都成功
            return True
            
        except Exception as e:
            logger.error(f"[AutoExpiration] 验证执行记录失败: task_id={task_id}, task_type={task_type}, error={e}", exc_info=True)
            # 发生异常时保守处理，视为未完成
            return False
    
    @classmethod
    def _is_task_expired(cls, last_update_time, timeout_days):
        """
        判断任务是否超时
        
        Args:
            last_update_time: 最后更新时间（字符串格式：YYYY-MM-DD HH:MM:SS）
            timeout_days: 超时天数
            
        Returns:
            bool: 是否超时
        """
        try:
            if not last_update_time:
                logger.warning("[AutoExpiration] 任务没有last_episode_update_time字段，视为未超时")
                return False
            
            # 解析时间
            try:
                last_update_dt = datetime.strptime(last_update_time, '%Y-%m-%d %H:%M:%S')
            except ValueError as e:
                logger.error(f"[AutoExpiration] 时间格式解析失败: last_update_time={last_update_time}, error={e}")
                return False
            
            # 计算超时时间点
            try:
                timeout_threshold = datetime.now() - timedelta(days=timeout_days)
            except (ValueError, OverflowError) as e:
                logger.error(f"[AutoExpiration] 计算超时时间点失败: timeout_days={timeout_days}, error={e}")
                return False
            
            # 判断是否超时
            return last_update_dt < timeout_threshold
            
        except Exception as e:
            logger.error(f"[AutoExpiration] 判断任务超时失败: {e}", exc_info=True)
            return False
    
    @classmethod
    def _is_all_episodes_downloaded(cls, task_id):
        """
        判断所有剧集是否下载成功
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否所有剧集都下载成功
        """
        try:
            # 查询该任务的所有失败记录
            try:
                failed_episodes = EpisodeFailureRecord.get_all_by_task(task_id)
            except Exception as e:
                logger.error(f"[AutoExpiration] 查询失败记录失败: task_id={task_id}, error={e}", exc_info=True)
                # 查询失败时保守处理，视为有失败记录
                return False
            
            # 如果存在失败记录，说明有剧集未下载成功
            if failed_episodes:
                logger.info(f"[AutoExpiration] 任务存在 {len(failed_episodes)} 个失败剧集记录")
                return False
            
            # 获取任务信息
            try:
                task = VideoTask.get_by_id(task_id)
            except Exception as e:
                logger.error(f"[AutoExpiration] 获取任务信息失败: task_id={task_id}, error={e}", exc_info=True)
                return False
            
            if not task:
                logger.warning(f"[AutoExpiration] 任务不存在: task_id={task_id}")
                return False
            
            # 如果任务没有剧集记录，视为不满足条件
            if not task.episodes or len(task.episodes) == 0:
                logger.info(f"[AutoExpiration] 任务没有剧集记录")
                return False
            
            # 所有剧集都下载成功
            return True
            
        except Exception as e:
            logger.error(f"[AutoExpiration] 验证下载完成度失败: task_id={task_id}, error={e}", exc_info=True)
            # 发生异常时保守处理，视为未完成
            return False
    
    @classmethod
    def _expire_task(cls, task_id, task_name, timeout_days, task_type):
        """
        将任务设置为失效
        
        Args:
            task_id: 任务ID
            task_name: 任务名称
            timeout_days: 超时天数
            task_type: 任务类型（video/transfer/download）
        """
        try:
            # 根据任务类型选择对应的表
            if task_type == 'video':
                table_name = 'video_tasks'
            elif task_type == 'transfer':
                table_name = 'transfer_tasks'
            elif task_type == 'download':
                table_name = 'download_tasks'
            else:
                logger.error(f"[AutoExpiration] 未知的任务类型: {task_type}")
                return
            
            # 更新任务状态为disabled
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(f"""
                        UPDATE {table_name} 
                        SET status = 'disabled'
                        WHERE id = ? AND status = 'active'
                    """, (task_id,))
                    
                    if cursor.rowcount == 0:
                        logger.warning(f"[AutoExpiration] 任务状态已被其他进程修改或任务不存在: task_id={task_id}, task_type={task_type}")
                        return
                    
                    conn.commit()
            except Exception as e:
                logger.error(f"[AutoExpiration] 数据库更新失败: task_id={task_id}, task_type={task_type}, error={e}", exc_info=True)
                raise
            
            logger.info(f"[AutoExpiration] 任务已失效：task_id={task_id}, task_name={task_name}, task_type={task_type}, 原因=超时{timeout_days}天且全部执行成功")
            
        except Exception as e:
            logger.error(f"[AutoExpiration] 更新任务状态失败: task_id={task_id}, task_type={task_type}, error={e}", exc_info=True)
            raise

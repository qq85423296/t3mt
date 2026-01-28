# -*- coding: utf-8 -*-
"""
任务调度服务 - 负责生成和执行定时任务
"""
import threading
import time
from datetime import datetime, timedelta
from croniter import croniter
from database import get_db
from utils.logger import logger
from config import Config


class SchedulerService:
    """任务调度服务"""
    
    _instance = None
    _lock = threading.Lock()
    _running = False
    _schedule_thread = None
    _execute_thread = None
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def start(cls):
        """启动调度服务"""
        if cls._running:
            logger.warning("调度服务已在运行中")
            return
        
        cls._running = True
        
        # 恢复被中断的影视下载任务
        cls._resume_interrupted_video_tasks()
        
        # 启动账期生成线程（每天0点执行）
        cls._schedule_thread = threading.Thread(
            target=cls._schedule_loop,
            daemon=True,
            name="ScheduleThread"
        )
        cls._schedule_thread.start()
        logger.info("账期生成线程已启动")
        
        # 启动任务执行线程（每分钟检查一次）
        cls._execute_thread = threading.Thread(
            target=cls._execute_loop,
            daemon=True,
            name="ExecuteThread"
        )
        cls._execute_thread.start()
        logger.info("任务执行线程已启动")
        
        # 启动日志清理线程（每天凌晨2点执行）
        cls._cleanup_thread = threading.Thread(
            target=cls._cleanup_loop,
            daemon=True,
            name="CleanupThread"
        )
        cls._cleanup_thread.start()
        logger.info("日志清理线程已启动")
        
        # 启动自动失效检查线程（每天凌晨3点执行）
        cls._expiration_thread = threading.Thread(
            target=cls._expiration_check_loop,
            daemon=True,
            name="ExpirationCheckThread"
        )
        cls._expiration_thread.start()
        logger.info("自动失效检查线程已启动")
    
    @classmethod
    def stop(cls):
        """停止调度服务"""
        cls._running = False
        logger.info("调度服务已停止")
    
    @classmethod
    def _resume_interrupted_video_tasks(cls):
        """恢复被中断的影视下载任务"""
        try:
            logger.info("检查被中断的影视下载任务...")
            
            with get_db() as conn:
                cursor = conn.cursor()
                
                # 查找最近被中断的影视下载任务（状态为interrupted且是今天的）
                # 每个任务只取最新的一条中断记录
                cursor.execute("""
                    SELECT id, task_id, task_name
                    FROM task_execution_history
                    WHERE task_type = 'video' 
                      AND status = 'interrupted'
                      AND DATE(start_time) = DATE('now', 'localtime')
                      AND id IN (
                          SELECT MAX(id)
                          FROM task_execution_history
                          WHERE task_type = 'video' 
                            AND status = 'interrupted'
                            AND DATE(start_time) = DATE('now', 'localtime')
                          GROUP BY task_id
                      )
                    ORDER BY start_time DESC
                """)
                
                interrupted_tasks = cursor.fetchall()
                
                if not interrupted_tasks:
                    logger.info("没有需要恢复的影视下载任务")
                    return
                
                logger.info(f"发现 {len(interrupted_tasks)} 个被中断的影视下载任务，准备恢复...")
                
                for task in interrupted_tasks:
                    execution_id = task['id']
                    task_id = task['task_id']
                    task_name = task['task_name']
                    
                    try:
                        # 检查任务是否仍然存在且未被禁用
                        cursor.execute("""
                            SELECT id, status FROM video_tasks WHERE id = ?
                        """, (task_id,))
                        video_task = cursor.fetchone()
                        
                        if not video_task:
                            logger.warning(f"任务 {task_name} (ID: {task_id}) 已被删除，跳过恢复")
                            continue
                        
                        if video_task['status'] == 'disabled':
                            logger.warning(f"任务 {task_name} (ID: {task_id}) 已被禁用，跳过恢复")
                            continue
                        
                        # 直接将中断的记录更新为待执行状态，并设置当前时间的账期
                        # 这样可以被_check_and_execute_tasks检测到并执行
                        now = datetime.now()
                        current_period = now.strftime('%Y%m%d%H')
                        
                        cursor.execute("""
                            UPDATE task_execution_history 
                            SET status = 'pending',
                                start_time = ?,
                                schedule_period = ?
                            WHERE id = ?
                        """, (now, current_period, execution_id))
                        conn.commit()
                        
                        logger.info(f"已将中断任务更新为待执行: {task_name} (ID: {task_id}, 执行ID: {execution_id}, 账期: {current_period})")
                        
                    except Exception as e:
                        logger.error(f"恢复任务 {task_name} (ID: {task_id}) 失败: {e}")
                
        except Exception as e:
            logger.error(f"恢复被中断任务失败: {e}", exc_info=True)
    
    @classmethod
    def _schedule_loop(cls):
        """账期生成循环 - 每天0点生成当天的待执行任务"""
        logger.info("账期生成循环已启动")
        
        # 首次启动时立即生成今天的账期
        cls._generate_today_schedules()
        
        while cls._running:
            try:
                now = datetime.now()
                
                # 计算下一个0点的时间
                tomorrow = now.date() + timedelta(days=1)
                next_midnight = datetime.combine(tomorrow, datetime.min.time())
                sleep_seconds = (next_midnight - now).total_seconds()
                
                logger.info(f"下次生成账期时间: {next_midnight}, 等待 {sleep_seconds:.0f} 秒")
                
                # 每分钟检查一次，避免长时间阻塞
                while cls._running and datetime.now() < next_midnight:
                    time.sleep(60)
                
                if cls._running:
                    # 生成今天的账期
                    cls._generate_today_schedules()
                    
            except Exception as e:
                logger.error(f"账期生成循环异常: {e}", exc_info=True)
                time.sleep(60)
    
    @classmethod
    def _execute_loop(cls):
        """任务执行循环 - 每分钟检查待执行任务"""
        logger.info("任务执行循环已启动")
        
        while cls._running:
            try:
                cls._check_and_execute_tasks()
                time.sleep(60)  # 每分钟检查一次
            except Exception as e:
                logger.error(f"任务执行循环异常: {e}", exc_info=True)
                time.sleep(60)
    
    @classmethod
    def _cleanup_loop(cls):
        """日志清理循环 - 每天凌晨2点执行"""
        logger.info("日志清理循环已启动")
        
        while cls._running:
            try:
                now = datetime.now()
                # 计算下次执行时间（明天凌晨2点）
                next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
                if now.hour >= 2:
                    next_run += timedelta(days=1)
                
                # 计算需要等待的秒数
                wait_seconds = (next_run - now).total_seconds()
                
                # 如果是首次启动且已过凌晨2点，立即执行一次
                if wait_seconds > 86000:  # 超过23小时，说明是首次启动
                    logger.info("首次启动，立即执行一次日志清理")
                    cls._cleanup_old_logs()
                
                logger.info(f"下次日志清理时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 等待到下次执行时间
                time.sleep(wait_seconds)
                
                # 执行清理
                cls._cleanup_old_logs()
                
            except Exception as e:
                logger.error(f"日志清理循环异常: {e}", exc_info=True)
                time.sleep(3600)  # 出错后等待1小时再试
    
    @classmethod
    def _cleanup_old_logs(cls):
        """清理超期的调度日志"""
        try:
            from models.config import ConfigModel
            
            # 获取日志保留天数配置
            retention_days = int(ConfigModel.get_config('schedule_log_retention_days', 30))
            
            logger.info(f"开始清理超过 {retention_days} 天的调度日志")
            
            # 计算截止日期
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
            
            with get_db() as conn:
                cursor = conn.cursor()
                
                # 统计要删除的记录数
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM task_execution_history
                    WHERE start_time < ?
                """, (cutoff_str,))
                count_result = cursor.fetchone()
                delete_count = count_result['count'] if count_result else 0
                
                if delete_count == 0:
                    logger.info("没有需要清理的调度日志")
                    return
                
                # 删除超期的执行历史记录
                cursor.execute("""
                    DELETE FROM task_execution_history
                    WHERE start_time < ?
                """, (cutoff_str,))
                
                conn.commit()
                
                logger.info(f"成功清理 {delete_count} 条超期调度日志（截止日期: {cutoff_str}）")
                
        except Exception as e:
            logger.error(f"清理调度日志失败: {e}", exc_info=True)
    
    @classmethod
    def _expiration_check_loop(cls):
        """自动失效检查循环 - 每天凌晨3点执行"""
        logger.info("自动失效检查循环已启动")
        
        while cls._running:
            try:
                now = datetime.now()
                # 计算下次执行时间（明天凌晨3点）
                next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
                if now.hour >= 3:
                    next_run += timedelta(days=1)
                
                # 计算需要等待的秒数
                wait_seconds = (next_run - now).total_seconds()
                
                # 如果是首次启动且已过凌晨3点，立即执行一次
                if wait_seconds > 86000:  # 超过23小时，说明是首次启动
                    logger.info("首次启动，立即执行一次自动失效检查")
                    cls._check_task_expiration()
                
                logger.info(f"下次自动失效检查时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 等待到下次执行时间
                time.sleep(wait_seconds)
                
                # 执行检查
                cls._check_task_expiration()
                
            except Exception as e:
                logger.error(f"自动失效检查循环异常: {e}", exc_info=True)
                time.sleep(3600)  # 出错后等待1小时再试
    
    @classmethod
    def _check_task_expiration(cls):
        """执行自动失效检查"""
        try:
            logger.info("开始执行自动失效检查")
            from services.auto_expiration_service import AutoExpirationService
            AutoExpirationService.check_and_expire_tasks()
            logger.info("自动失效检查完成")
        except Exception as e:
            logger.error(f"自动失效检查失败: {e}", exc_info=True)
    
    @classmethod
    def _generate_today_schedules(cls):
        """生成今天的待执行任务账期"""
        try:
            today = datetime.now().date()
            logger.info(f"开始生成 {today} 的任务账期")
            
            with get_db() as conn:
                cursor = conn.cursor()
                
                # 获取所有生效状态的定时转存任务
                cursor.execute("""
                    SELECT id, name, cron_expression 
                    FROM transfer_tasks 
                    WHERE status = 'active'
                """)
                transfer_tasks = cursor.fetchall()
                
                # 获取所有生效状态的定时下载任务
                cursor.execute("""
                    SELECT id, name, cron_expression 
                    FROM download_tasks 
                    WHERE status = 'active'
                """)
                download_tasks = cursor.fetchall()
                
                # 获取所有生效状态的影视下载任务
                cursor.execute("""
                    SELECT id, name, cron_expression 
                    FROM video_tasks 
                    WHERE status = 'active' AND cron_expression IS NOT NULL AND cron_expression != ''
                """)
                video_tasks = cursor.fetchall()
                
                total_created = 0
                
                # 处理转存任务
                for task in transfer_tasks:
                    count = cls._create_schedules_for_task(
                        task['id'], 
                        task['name'], 
                        task['cron_expression'], 
                        'transfer', 
                        today
                    )
                    total_created += count
                
                # 处理下载任务
                for task in download_tasks:
                    count = cls._create_schedules_for_task(
                        task['id'], 
                        task['name'], 
                        task['cron_expression'], 
                        'download', 
                        today
                    )
                    total_created += count
                
                # 处理影视下载任务
                for task in video_tasks:
                    count = cls._create_schedules_for_task(
                        task['id'], 
                        task['name'], 
                        task['cron_expression'], 
                        'video', 
                        today
                    )
                    total_created += count
                
                logger.info(f"✅ 生成完成，共创建 {total_created} 条待执行记录")
                
        except Exception as e:
            logger.error(f"生成今日账期失败: {e}", exc_info=True)
    
    @classmethod
    def _create_schedules_for_task(cls, task_id, task_name, cron_expression, task_type, target_date):
        """为单个任务创建账期记录（支持多时间点）"""
        try:
            # 支持分号分隔的多个Cron表达式
            if ';' in cron_expression:
                expressions = [expr.strip() for expr in cron_expression.split(';') if expr.strip()]
                total_created = 0
                for expr in expressions:
                    count = cls._create_schedules_for_single_expression(
                        task_id, task_name, expr, task_type, target_date
                    )
                    total_created += count
                return total_created
            else:
                return cls._create_schedules_for_single_expression(
                    task_id, task_name, cron_expression, task_type, target_date
                )
            
        except Exception as e:
            logger.error(f"为任务 {task_name} 创建账期失败: {e}", exc_info=True)
            return 0
    
    @classmethod
    def _create_schedules_for_single_expression(cls, task_id, task_name, cron_expression, task_type, target_date):
        """为单个Cron表达式创建账期记录"""
        try:
            # 跳过一次性执行的任务（ONCE）
            if cron_expression.strip().upper() == 'ONCE':
                logger.info(f"跳过一次性执行任务: {task_name}")
                return 0
            
            # 处理cron表达式格式
            # 数据库中存储的是7字段格式（秒 分 时 日 月 周 年）
            # croniter需要5字段格式（分 时 日 月 周）
            cron_parts = cron_expression.strip().split()
            
            if len(cron_parts) == 7:
                # 7字段格式：移除第一个字段（秒）和最后一个字段（年）
                cron_expression = ' '.join(cron_parts[1:6])
            elif len(cron_parts) == 6:
                # 6字段格式：移除第一个字段（秒）
                cron_expression = ' '.join(cron_parts[1:6])
            elif len(cron_parts) != 5:
                logger.error(f"任务 {task_name} 的cron表达式格式不正确: {cron_expression}")
                return 0
            
            # 将 ? 替换为 * （croniter不支持?）
            cron_expression = cron_expression.replace('?', '*')
            
            # 解析cron表达式
            base_time = datetime.combine(target_date, datetime.min.time())
            cron = croniter(cron_expression, base_time)
            
            created_count = 0
            
            # 获取当天所有的执行时间点
            while True:
                next_time = cron.get_next(datetime)
                
                # 如果超过当天，停止
                if next_time.date() > target_date:
                    break
                
                # 生成账期：YYYYMMDDHH
                schedule_period = next_time.strftime('%Y%m%d%H')
                
                with get_db() as conn:
                    cursor = conn.cursor()
                    
                    # 检查是否已存在
                    cursor.execute("""
                        SELECT id FROM task_execution_history
                        WHERE task_id = ? AND task_type = ? AND schedule_period = ?
                    """, (task_id, task_type, schedule_period))
                    
                    if cursor.fetchone():
                        continue  # 已存在，跳过
                    
                    # 创建待执行记录
                    cursor.execute("""
                        INSERT INTO task_execution_history (
                            task_id, task_type, task_name, schedule_period,
                            status, start_time, logs
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        task_id, 
                        task_type, 
                        task_name, 
                        schedule_period,
                        'pending',  # 待执行状态
                        next_time,
                        '[]'
                    ))
                    conn.commit()
                    created_count += 1
                    
                    logger.info(f"创建待执行任务: {task_name} ({task_type}) - 账期: {schedule_period}")
            
            return created_count
            
        except Exception as e:
            logger.error(f"为任务 {task_name} 创建账期失败: {e}", exc_info=True)
            return 0
    
    @classmethod
    def _check_and_execute_tasks(cls):
        """检查并执行到期的待执行任务"""
        try:
            now = datetime.now()
            current_period = now.strftime('%Y%m%d%H')
            
            with get_db() as conn:
                cursor = conn.cursor()
                
                # 查找所有待执行且已到期的任务
                cursor.execute("""
                    SELECT id, task_id, task_type, task_name, schedule_period
                    FROM task_execution_history
                    WHERE status = 'pending' AND schedule_period <= ?
                    ORDER BY schedule_period ASC
                """, (current_period,))
                
                pending_tasks = cursor.fetchall()
                
                if not pending_tasks:
                    return
                
                logger.info(f"发现 {len(pending_tasks)} 个待执行任务")
                
                for task in pending_tasks:
                    cls._execute_scheduled_task(
                        task['id'],
                        task['task_id'],
                        task['task_type'],
                        task['task_name'],
                        task['schedule_period']
                    )
                    
        except Exception as e:
            logger.error(f"检查待执行任务失败: {e}", exc_info=True)
    
    @classmethod
    def _execute_scheduled_task(cls, execution_id, task_id, task_type, task_name, schedule_period):
        """执行单个调度任务"""
        try:
            logger.info(f"开始执行调度任务: {task_name} ({task_type}) - 账期: {schedule_period}")
            
            # 更新状态为运行中
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE task_execution_history 
                    SET status = 'running', start_time = ?
                    WHERE id = ?
                """, (datetime.now(), execution_id))
                conn.commit()
            
            # 根据任务类型执行
            if task_type == 'transfer':
                cls._execute_transfer_task(execution_id, task_id)
            elif task_type == 'download':
                cls._execute_download_task(execution_id, task_id)
            elif task_type == 'video':
                cls._execute_video_task(execution_id, task_id)
            else:
                logger.error(f"未知的任务类型: {task_type}")
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE task_execution_history 
                        SET status = 'failed', end_time = ?, error_message = ?
                        WHERE id = ?
                    """, (datetime.now(), f'未知的任务类型: {task_type}', execution_id))
                    conn.commit()
                
        except Exception as e:
            logger.error(f"执行调度任务失败: {e}", exc_info=True)
            
            # 更新状态为失败（如果还没有被更新）
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    # 只更新状态仍为running的记录
                    cursor.execute("""
                        UPDATE task_execution_history 
                        SET status = 'failed', end_time = ?, error_message = ?
                        WHERE id = ? AND status = 'running'
                    """, (datetime.now(), str(e), execution_id))
                    conn.commit()
            except Exception as update_error:
                logger.error(f"更新执行状态失败: {update_error}")
    
    @classmethod
    def _execute_transfer_task(cls, execution_id, task_id):
        """执行转存任务"""
        try:
            import requests
            import json
            
            # 调用转存任务执行接口
            response = requests.post(
                f'{Config.API_BASE_URL}/api/transfer/task/{task_id}/execute',
                timeout=300
            )
            
            # 无论HTTP状态码如何，都检查返回的JSON
            result = response.json()
            
            # 转存任务内部已经更新了执行历史记录
            # 这里只需要记录日志即可
            if result.get('code') == 200:
                logger.info(f"转存任务执行完成: execution_id={execution_id}")
            else:
                logger.error(f"转存任务执行失败: {result.get('message')}")
                
        except Exception as e:
            logger.error(f"执行转存任务失败: {e}", exc_info=True)
            
            # 如果HTTP请求失败，记录详细的错误日志
            try:
                import traceback
                
                with get_db() as conn:
                    cursor = conn.cursor()
                    logs = [
                        {
                            'message': '尝试启动转存任务',
                            'type': 'info',
                            'timestamp': datetime.now().strftime('%H:%M:%S')
                        },
                        {
                            'message': f'HTTP请求失败: {str(e)}',
                            'type': 'error',
                            'timestamp': datetime.now().strftime('%H:%M:%S')
                        },
                        {
                            'message': f'详细错误: {traceback.format_exc()}',
                            'type': 'error',
                            'timestamp': datetime.now().strftime('%H:%M:%S')
                        }
                    ]
                    logs_json = json.dumps(logs, ensure_ascii=False)
                    
                    cursor.execute("""
                        UPDATE task_execution_history 
                        SET status = 'failed', 
                            end_time = ?,
                            error_message = ?,
                            logs = ?
                        WHERE id = ?
                    """, (datetime.now(), f'HTTP请求失败: {str(e)}', logs_json, execution_id))
                    conn.commit()
            except Exception as log_error:
                logger.error(f"记录错误日志失败: {log_error}")
    
    @classmethod
    def _execute_download_task(cls, execution_id, task_id):
        """执行下载任务"""
        try:
            from services.task_executor import TaskExecutor
            import json
            
            # 启动下载任务，传入execution_id
            if TaskExecutor.start_task(task_id, execution_id=execution_id):
                logger.info(f"下载任务已启动: task_id={task_id}, execution_id={execution_id}")
                
                # 注意：下载任务是异步执行的，状态更新由TaskExecutor负责
                # execution_id已传递给TaskExecutor，它会负责更新执行历史
            else:
                # 任务已在执行中
                error_msg = "任务已在执行中"
                logger.warning(error_msg)
                
                # 记录日志到执行历史
                with get_db() as conn:
                    cursor = conn.cursor()
                    logs = [
                        {
                            'message': '尝试启动下载任务',
                            'type': 'info',
                            'timestamp': datetime.now().strftime('%H:%M:%S')
                        },
                        {
                            'message': error_msg,
                            'type': 'error',
                            'timestamp': datetime.now().strftime('%H:%M:%S')
                        }
                    ]
                    logs_json = json.dumps(logs, ensure_ascii=False)
                    
                    cursor.execute("""
                        UPDATE task_execution_history 
                        SET status = 'failed', 
                            end_time = ?,
                            error_message = ?,
                            logs = ?
                        WHERE id = ?
                    """, (datetime.now(), error_msg, logs_json, execution_id))
                    conn.commit()
                
        except Exception as e:
            logger.error(f"执行下载任务失败: {e}", exc_info=True)
            
            # 记录详细的错误日志到执行历史
            try:
                import json
                import traceback
                
                with get_db() as conn:
                    cursor = conn.cursor()
                    logs = [
                        {
                            'message': '尝试启动下载任务',
                            'type': 'info',
                            'timestamp': datetime.now().strftime('%H:%M:%S')
                        },
                        {
                            'message': f'启动失败: {str(e)}',
                            'type': 'error',
                            'timestamp': datetime.now().strftime('%H:%M:%S')
                        },
                        {
                            'message': f'详细错误: {traceback.format_exc()}',
                            'type': 'error',
                            'timestamp': datetime.now().strftime('%H:%M:%S')
                        }
                    ]
                    logs_json = json.dumps(logs, ensure_ascii=False)
                    
                    cursor.execute("""
                        UPDATE task_execution_history 
                        SET status = 'failed', 
                            end_time = ?,
                            error_message = ?,
                            logs = ?
                        WHERE id = ?
                    """, (datetime.now(), str(e), logs_json, execution_id))
                    conn.commit()
            except Exception as log_error:
                logger.error(f"记录错误日志失败: {log_error}")
            
            raise
    
    @classmethod
    def _execute_video_task(cls, execution_id, task_id):
        """执行影视下载任务"""
        try:
            import json
            from datetime import datetime
            
            logger.info(f"开始执行影视下载任务: task_id={task_id}, execution_id={execution_id}")
            
            # 直接调用影视下载任务的执行逻辑，避免HTTP请求
            try:
                from models.video_task import VideoTask
                from services.video_download_service import video_download_service
                from services.video_parse_service import video_parse_service
                import os
                import threading
                
                # 获取任务信息
                task = VideoTask.get_by_id(task_id)
                if not task:
                    error_msg = '任务不存在'
                    logger.error(f"影视下载任务不存在: task_id={task_id}")
                    
                    with get_db() as conn:
                        cursor = conn.cursor()
                        logs = [
                            {
                                'message': '尝试启动影视下载任务',
                                'type': 'info',
                                'timestamp': datetime.now().strftime('%H:%M:%S')
                            },
                            {
                                'message': error_msg,
                                'type': 'error',
                                'timestamp': datetime.now().strftime('%H:%M:%S')
                            }
                        ]
                        logs_json = json.dumps(logs, ensure_ascii=False)
                        
                        cursor.execute("""
                            UPDATE task_execution_history 
                            SET status = 'failed', 
                                end_time = ?,
                                error_message = ?,
                                logs = ?
                            WHERE id = ?
                        """, (datetime.now(), error_msg, logs_json, execution_id))
                        conn.commit()
                    return
                
                # ========== 新增：自动追更逻辑 ==========
                logger.info(f"检查是否有新剧集更新: task_id={task_id}, website_url={task.website_url}")
                try:
                    # 重新读取官网获取最新剧集列表
                    website_data = video_parse_service.read_website(task.website_url, task.platform)
                    
                    if website_data.get('success') and website_data.get('episodes'):
                        new_episodes = website_data['episodes']
                        old_episodes = task.episodes or []
                        
                        # 对比剧集数量
                        if len(new_episodes) > len(old_episodes):
                            logger.info(f"发现新剧集: 原有{len(old_episodes)}集, 最新{len(new_episodes)}集")
                            
                            # 更新任务的剧集列表和最后更新时间
                            # 只有当任务状态为active时才更新last_episode_update_time
                            if task.status == 'active':
                                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                VideoTask.update(
                                    task_id, 
                                    episodes=new_episodes,
                                    last_episode_update_time=current_time
                                )
                                logger.info(f"[AutoExpiration] 检测到新剧集，已重置计时器: task_id={task_id}, last_episode_update_time={current_time}")
                            else:
                                # 失效任务只更新剧集列表，不更新时间
                                VideoTask.update(task_id, episodes=new_episodes)
                                logger.info(f"[AutoExpiration] 任务状态为{task.status}，不更新last_episode_update_time")
                            
                            # 重新加载任务以获取最新数据
                            task = VideoTask.get_by_id(task_id)
                            
                            logger.info(f"已更新任务剧集列表: task_id={task_id}, 新增{len(new_episodes) - len(old_episodes)}集")
                        else:
                            logger.info(f"暂无新剧集更新: 当前{len(old_episodes)}集")
                    else:
                        logger.warning(f"获取最新剧集列表失败，使用任务中已保存的剧集列表")
                except Exception as e:
                    logger.error(f"检查新剧集时出错: {str(e)}，将使用任务中已保存的剧集列表继续执行")
                # ========== 自动追更逻辑结束 ==========
                
                # 检查是否有剧集
                if not task.episodes or len(task.episodes) == 0:
                    error_msg = '任务没有可下载的剧集'
                    logger.error(f"影视下载任务没有剧集: task_id={task_id}")
                    
                    with get_db() as conn:
                        cursor = conn.cursor()
                        logs = [
                            {
                                'message': '尝试启动影视下载任务',
                                'type': 'info',
                                'timestamp': datetime.now().strftime('%H:%M:%S')
                            },
                            {
                                'message': error_msg,
                                'type': 'error',
                                'timestamp': datetime.now().strftime('%H:%M:%S')
                            }
                        ]
                        logs_json = json.dumps(logs, ensure_ascii=False)
                        
                        cursor.execute("""
                            UPDATE task_execution_history 
                            SET status = 'failed', 
                                end_time = ?,
                                error_message = ?,
                                logs = ?
                            WHERE id = ?
                        """, (datetime.now(), error_msg, logs_json, execution_id))
                        conn.commit()
                    return
                
                # 更新执行历史状态为running
                start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE task_execution_history 
                        SET status = 'running', start_time = ?, total_count = ?
                        WHERE id = ?
                    """, (start_time, len(task.episodes), execution_id))
                    conn.commit()
                
                # 调度执行任务时不修改任务状态，只重置进度
                # 任务状态只能通过"发布"和"下线"按钮修改
                VideoTask.update(task_id, progress=0)
                
                # 在新线程中执行下载任务
                def download_thread():
                    from utils.task_logger import TaskLogger
                    from services.video_parse_service import video_parse_service  # 在内层函数中导入
                    
                    task_logger = TaskLogger()
                    
                    def update_logs_to_db():
                        try:
                            import json
                            with get_db() as conn:
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE task_execution_history 
                                    SET logs = ?
                                    WHERE id = ?
                                """, (json.dumps(task_logger.get_logs(), ensure_ascii=False), execution_id))
                                conn.commit()
                        except Exception as e:
                            logger.error(f"更新日志到数据库失败: {str(e)}")
                    
                    # 设置日志更新回调
                    task_logger.update_callback = update_logs_to_db
                    
                    try:
                        task_logger.info(f"开始执行影视下载任务")
                        task_logger.info(f"任务名称: {task.name}")
                        task_logger.info(f"正在检查更新...")
                        
                        # 检查更新逻辑（与video.py中的逻辑一致）
                        try:
                            platform = task.platform if hasattr(task, 'platform') and task.platform else 'mango'
                            result = video_parse_service.read_website(task.website_url, platform)
                            
                            if result.get('success'):
                                latest_episodes = result['episodes']
                                task_logger.info(f"官网最新剧集数: {len(latest_episodes)}")
                                
                                # ========== 新增：检查并重置URL已变化的失败记录 ==========
                                if task_config.get('enable_retry'):
                                    try:
                                        from services.retry_manager import retry_manager
                                        reset_count = retry_manager.check_and_reset_url_changed_episodes(
                                            task_id, 
                                            latest_episodes
                                        )
                                        if reset_count > 0:
                                            task_logger.info(f"检测到 {reset_count} 个剧集的下载地址已更新，已清除旧的失败记录，将使用新地址重新下载")
                                    except Exception as e:
                                        logger.error(f"检查URL变化失败: {str(e)}")
                                # ========== URL变化检查结束 ==========
                                
                                # 获取用户选择的剧集索引
                                selected_indices = []
                                if hasattr(task, 'selected_episodes') and task.selected_episodes:
                                    try:
                                        selected_indices = task.selected_episodes if isinstance(task.selected_episodes, list) else []
                                        if selected_indices:
                                            original_count = len(selected_indices)
                                            task_logger.info(f"用户初始选择了 {original_count} 集进行下载")
                                            
                                            # ========== 自动追更：将新剧集索引加入选择列表 ==========
                                            # 如果最新剧集数大于用户选择的数量，自动添加新剧集索引
                                            if len(latest_episodes) > original_count:
                                                # 添加新剧集的索引（从original_count到len(latest_episodes)-1）
                                                for i in range(original_count, len(latest_episodes)):
                                                    if i not in selected_indices:
                                                        selected_indices.append(i)
                                                
                                                new_count = len(selected_indices) - original_count
                                                task_logger.info(f"检测到新更新 {new_count} 集，已自动加入下载列表")
                                                
                                                # 更新数据库中的selected_episodes (使用外层已导入的VideoTask)
                                                try:
                                                    VideoTask.update(task_id, selected_episodes=selected_indices)
                                                    task_logger.info(f"已更新任务选择列表，当前共 {len(selected_indices)} 集")
                                                except Exception as e:
                                                    logger.error(f"更新selected_episodes失败: {str(e)}")
                                            # ========== 自动追更逻辑结束 ==========
                                            
                                            update_logs_to_db()
                                    except Exception as e:
                                        logger.error(f"解析selected_episodes失败: {str(e)}")
                                
                                # 根据用户选择筛选剧集
                                actual_save_directory = task.save_directory
                                if task.create_subfolder:
                                    actual_save_directory = os.path.join(task.save_directory, task.name)
                                
                                # 检查哪些剧集已经下载
                                downloaded_episode_names = set()
                                if os.path.exists(actual_save_directory):
                                    for file in os.listdir(actual_save_directory):
                                        if file.endswith('.mp4'):
                                            episode_name = file[:-4]
                                            downloaded_episode_names.add(episode_name)
                                
                                task_logger.info(f"已下载剧集数: {len(downloaded_episode_names)}")
                                
                                # 筛选出需要下载的剧集
                                episodes_to_download = []
                                if selected_indices:
                                    for index in selected_indices:
                                        if 0 <= index < len(latest_episodes):
                                            ep = latest_episodes[index]
                                            episode_name = ep.get('name', '')
                                            episode_title = ep.get('title', '')
                                            full_name = f"{episode_name} - {episode_title}" if episode_title else episode_name
                                            
                                            illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
                                            safe_name = full_name
                                            for char in illegal_chars:
                                                safe_name = safe_name.replace(char, '_')
                                            safe_name = safe_name.strip()
                                            
                                            if safe_name not in downloaded_episode_names:
                                                episodes_to_download.append(ep)
                                    
                                    task_logger.info(f"根据选择列表，需要下载 {len(episodes_to_download)} 集（已跳过 {len(selected_indices) - len(episodes_to_download)} 集）")
                                else:
                                    for ep in latest_episodes:
                                        episode_name = ep.get('name', '')
                                        episode_title = ep.get('title', '')
                                        full_name = f"{episode_name} - {episode_title}" if episode_title else episode_name
                                        
                                        illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
                                        safe_name = full_name
                                        for char in illegal_chars:
                                            safe_name = safe_name.replace(char, '_')
                                        safe_name = safe_name.strip()
                                        
                                        if safe_name not in downloaded_episode_names:
                                            episodes_to_download.append(ep)
                                
                                if len(episodes_to_download) == 0:
                                    task_logger.info(f"所有剧集均已下载完成，无需下载")
                                    task_logger.info(f"任务执行完成")
                                    
                                    # 任务执行完成，保持active状态（定时任务需要继续执行）
                                    # 不修改任务状态，只更新进度
                                    VideoTask.update(task_id, progress=100)
                                    
                                    end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                                    end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                                    duration = int((end_dt - start_dt).total_seconds())
                                    
                                    with get_db() as conn:
                                        cursor = conn.cursor()
                                        cursor.execute("""
                                            UPDATE task_execution_history 
                                            SET end_time = ?, duration = ?, status = ?, logs = ?,
                                                success_count = ?, failed_count = ?
                                            WHERE id = ?
                                        """, (end_time, duration, 'success', json.dumps(task_logger.get_logs(), ensure_ascii=False), 
                                              len(latest_episodes), 0, execution_id))
                                        conn.commit()
                                    
                                    logger.info(f"影视下载任务 {task_id} 完成：所有剧集均已下载")
                                    return
                                
                                task_logger.info(f"发现 {len(episodes_to_download)} 集新内容")
                                task_logger.info(f"开始下载新增剧集...")
                                
                                VideoTask.update(task_id, episodes=latest_episodes, video_info=result['video_info'])
                                task.episodes = episodes_to_download
                                
                            else:
                                task_logger.info(f"检查更新失败: {result.get('error', '未知错误')}，使用已保存的剧集列表")
                        except Exception as e:
                            task_logger.info(f"检查更新失败: {str(e)}，使用已保存的剧集列表")
                        
                        task_logger.info(f"剧集总数: {len(task.episodes)}")
                        
                        actual_save_directory = task.save_directory
                        if task.create_subfolder:
                            actual_save_directory = os.path.join(task.save_directory, task.name)
                            task_logger.info(f"按名称分类已启用")
                            task_logger.info(f"保存目录: {actual_save_directory}")
                        else:
                            task_logger.info(f"保存目录: {actual_save_directory}")
                        
                        update_logs_to_db()
                        
                        # 进度回调
                        def progress_callback(current, total, episode_name, status, 
                                            downloaded=0, total_size=0, percentage=0):
                            task_progress = int((current / total) * 100)
                            VideoTask.update(
                                task_id, 
                                progress=task_progress,
                                downloaded_episodes=current - 1 if status in ['success', 'skipped'] else current - 1
                            )
                            
                            if status == 'checking':
                                task_logger.info(f"检查文件: {episode_name}")
                            elif status == 'success':
                                task_logger.success(f"下载成功: {episode_name}")
                            elif status == 'skipped':
                                task_logger.warning(f"文件已存在，跳过: {episode_name}")
                            elif status == 'failed':
                                task_logger.error(f"下载失败: {episode_name}")
                        
                        # 获取任务配置
                        task_config = {
                            'enable_file_size_check': task.enable_file_size_check if hasattr(task, 'enable_file_size_check') else False,
                            'min_file_size': task.min_file_size if hasattr(task, 'min_file_size') else 10,
                            'enable_retry': task.enable_retry if hasattr(task, 'enable_retry') else False,
                            'max_retry_count': task.max_retry_count if hasattr(task, 'max_retry_count') else 3,
                            'retry_interval': task.retry_interval if hasattr(task, 'retry_interval') else 30
                        }
                        
                        # 重新获取最新的剧集列表
                        task_logger.info("正在获取最新的剧集列表...")
                        try:
                            from services.video_parse_service import video_parse_service
                            
                            # 使用统一的解析服务获取剧集列表
                            parse_result = video_parse_service.read_website(task.website_url, task.platform)
                            
                            if parse_result.get('success'):
                                latest_episodes = parse_result.get('episodes', [])
                                task_logger.info(f"获取到最新剧集列表，共 {len(latest_episodes)} 集")
                                
                                # 如果任务有选中的剧集索引，只下载选中的剧集
                                if hasattr(task, 'selected_episodes') and task.selected_episodes:
                                    selected_indices = task.selected_episodes
                                    episodes_to_download = [latest_episodes[i] for i in selected_indices if i < len(latest_episodes)]
                                    task_logger.info(f"根据选集配置，将下载 {len(episodes_to_download)} 集")
                                else:
                                    # 没有选集配置，下载所有剧集
                                    episodes_to_download = latest_episodes
                                    task_logger.info(f"将下载所有剧集")
                            else:
                                task_logger.warning(f"获取最新剧集失败: {parse_result.get('error', '未知错误')}，使用任务中保存的剧集列表")
                                episodes_to_download = task.episodes
                        except Exception as e:
                            task_logger.error(f"获取最新剧集异常: {e}，使用任务中保存的剧集列表")
                            episodes_to_download = task.episodes
                        
                        # 执行下载
                        result = video_download_service.download_task_episodes(
                            task_id=task_id,
                            episodes=episodes_to_download,
                            save_directory=actual_save_directory,
                            task_name=task.name,
                            task_config=task_config,
                            progress_callback=progress_callback,
                            log_callback=lambda msg: task_logger.info(msg),
                            regex_pattern=task.regex_pattern,
                            replacement_pattern=task.replacement_pattern,
                            exclude_keywords=task.exclude_keywords
                        )
                        
                        # 更新最终状态
                        end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                        end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                        duration = int((end_dt - start_dt).total_seconds())
                        
                        # 根据下载结果判断最终状态
                        success_count = result['success_count'] + result.get('skipped_count', 0)
                        failed_count = result['failed_count']
                        
                        if failed_count == 0:
                            final_status = 'success'
                        elif success_count == 0:
                            final_status = 'failed'
                        else:
                            final_status = 'partial'  # 部分成功
                        
                        if result['success']:
                            # 任务执行完成，保持active状态（定时任务需要继续执行）
                            # 不修改任务状态，只更新进度和下载数
                            VideoTask.update(
                                task_id,
                                progress=100,
                                downloaded_episodes=success_count
                            )
                            
                            task_logger.info(f"任务执行完成")
                            task_logger.info(f"新下载: {result['success_count']}, 跳过: {result.get('skipped_count', 0)}, 过滤: {result.get('filtered_count', 0)}, 失败: {result['failed_count']}, 总计: {result['total']}")
                            
                            with get_db() as conn:
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE task_execution_history 
                                    SET end_time = ?, duration = ?, status = ?, 
                                        success_count = ?, failed_count = ?, logs = ?
                                    WHERE id = ?
                                """, (end_time, duration, final_status, success_count, 
                                      failed_count, json.dumps(task_logger.get_logs(), ensure_ascii=False), execution_id))
                                conn.commit()
                            
                            # 执行关联的插件
                            cls._execute_task_plugins(
                                task_id=task_id,
                                task_type='video',
                                execution_id=execution_id,
                                task_name=task.name,
                                final_status=final_status,
                                start_time=start_time,
                                end_time=end_time,
                                success_count=success_count,
                                failed_count=failed_count,
                                total_count=result['total'],
                                target_path=actual_save_directory,
                                task_logger=task_logger,
                                duration=duration,  # 传递执行耗时
                                total_size=0  # 影视下载暂不统计大小
                            )
                        else:
                            # 下载失败的情况
                            success_count = result['success_count']
                            failed_count = result['failed_count']
                            
                            # 根据成功/失败数量判断最终状态
                            if failed_count == 0:
                                final_status = 'success'
                            elif success_count == 0:
                                final_status = 'failed'
                            else:
                                final_status = 'partial'  # 部分成功
                            
                            # 任务执行完成，保持active状态（定时任务需要继续执行）
                            # 不修改任务状态，只更新下载数
                            VideoTask.update(
                                task_id,
                                downloaded_episodes=success_count
                            )
                            
                            error_message = f"部分下载失败: 成功 {success_count}/{result['total']}"
                            task_logger.info(f"{error_message}")
                            
                            with get_db() as conn:
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE task_execution_history 
                                    SET end_time = ?, duration = ?, status = ?, 
                                        success_count = ?, failed_count = ?, logs = ?, error_message = ?
                                    WHERE id = ?
                                """, (end_time, duration, final_status, success_count, 
                                      failed_count, json.dumps(task_logger.get_logs(), ensure_ascii=False), error_message, execution_id))
                                conn.commit()
                            
                            # 执行关联的插件（即使任务失败也执行）
                            cls._execute_task_plugins(
                                task_id=task_id,
                                task_type='video',
                                execution_id=execution_id,
                                task_name=task.name,
                                final_status='failed',
                                start_time=start_time,
                                end_time=end_time,
                                success_count=result['success_count'],
                                failed_count=result['failed_count'],
                                total_count=result['total'],
                                target_path=actual_save_directory,
                                task_logger=task_logger,
                                error_message=error_message,
                                duration=duration,  # 传递执行耗时
                                total_size=0  # 影视下载暂不统计大小
                            )
                        
                    except Exception as e:
                        logger.error(f"下载任务 {task_id} 失败: {str(e)}", exc_info=True)
                        # 任务执行失败，保持active状态（定时任务需要继续执行）
                        # 不修改任务状态
                        
                        error_message = str(e)
                        task_logger.info(f"执行异常: {error_message}")
                        
                        end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                        end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                        duration = int((end_dt - start_dt).total_seconds())
                        
                        with get_db() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE task_execution_history 
                                SET end_time = ?, duration = ?, status = ?, logs = ?, error_message = ?
                                WHERE id = ?
                            """, (end_time, duration, 'failed', json.dumps(task_logger.get_logs(), ensure_ascii=False), error_message, execution_id))
                            conn.commit()
                
                # 启动下载线程
                thread = threading.Thread(target=download_thread, daemon=True)
                thread.start()
                
                logger.info(f"影视下载任务已启动: task_id={task_id}, execution_id={execution_id}")
                
            except Exception as e:
                logger.error(f"启动影视下载任务失败: {e}", exc_info=True)
                raise
                
        except Exception as e:
            logger.error(f"执行影视下载任务失败: {e}", exc_info=True)
            
            # 记录详细的错误日志到执行历史
            try:
                import json
                import traceback
                
                with get_db() as conn:
                    cursor = conn.cursor()
                    logs = [
                        {
                            'message': '尝试启动影视下载任务',
                            'type': 'info',
                            'timestamp': datetime.now().strftime('%H:%M:%S')
                        },
                        {
                            'message': f'启动失败: {str(e)}',
                            'type': 'error',
                            'timestamp': datetime.now().strftime('%H:%M:%S')
                        },
                        {
                            'message': f'详细错误: {traceback.format_exc()}',
                            'type': 'error',
                            'timestamp': datetime.now().strftime('%H:%M:%S')
                        }
                    ]
                    logs_json = json.dumps(logs, ensure_ascii=False)
                    
                    cursor.execute("""
                        UPDATE task_execution_history 
                        SET status = 'failed', 
                            end_time = ?,
                            error_message = ?,
                            logs = ?
                        WHERE id = ?
                    """, (datetime.now(), str(e), logs_json, execution_id))
                    conn.commit()
            except Exception as log_error:
                logger.error(f"记录错误日志失败: {log_error}")
            
            raise
    
    @classmethod
    def _execute_task_plugins(cls, task_id, task_type, execution_id, task_name,
                              final_status, start_time, end_time, success_count,
                              failed_count, total_count, target_path,
                              task_logger=None, source_path='', error_message='',
                              duration=0, total_size=0):
        """
        执行任务关联的插件
        
        Args:
            task_id: 任务ID
            task_type: 任务类型（transfer/download/video）
            execution_id: 执行记录ID
            task_name: 任务名称
            final_status: 最终状态（success/failed/partial）
            start_time: 开始时间
            end_time: 结束时间
            success_count: 成功数
            failed_count: 失败数
            total_count: 总数
            target_path: 目标路径
            task_logger: 任务日志记录器（可选）
            source_path: 源路径（可选）
            error_message: 错误信息（可选）
            duration: 执行耗时（秒）
            total_size: 总大小（字节）
        """
        try:
            from services.plugin_executor import PluginExecutor
            
            # 构建任务上下文
            task_context = {
                'task_id': task_id,
                'task_name': task_name,
                'task_type': task_type,
                'status': final_status,
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration,  # 添加执行耗时
                'total_count': total_count,
                'success_count': success_count,
                'failed_count': failed_count,
                'total_size': total_size,  # 添加总大小
                'source_path': source_path,
                'target_path': target_path,
                'error_message': error_message,
            }
            
            if task_logger:
                task_logger.info('开始执行关联插件...')
            
            plugin_result = PluginExecutor.execute_plugins(
                task_id=task_id,
                task_type=task_type,
                execution_id=execution_id,
                task_context=task_context
            )
            
            if plugin_result['total'] > 0:
                msg = (f"插件执行完成: 总计 {plugin_result['total']} 个，"
                       f"成功 {plugin_result['success']} 个，"
                       f"失败 {plugin_result['failed']} 个，"
                       f"跳过 {plugin_result['skipped']} 个")
                if task_logger:
                    task_logger.info(msg)
                logger.info(f"任务 {task_id} ({task_type}) {msg}")
            else:
                if task_logger:
                    task_logger.info('没有关联的插件需要执行')
                    
        except Exception as e:
            error_msg = f"插件执行异常: {str(e)}"
            if task_logger:
                task_logger.warning(error_msg)
            logger.error(f"任务 {task_id} ({task_type}) {error_msg}", exc_info=True)
    
    @classmethod
    def generate_schedules_manually(cls, date_str=None):
        """手动生成指定日期的账期（用于补偿或测试）"""
        try:
            if date_str:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                target_date = datetime.now().date()
            
            logger.info(f"手动生成 {target_date} 的任务账期")
            cls._generate_today_schedules()
            
        except Exception as e:
            logger.error(f"手动生成账期失败: {e}", exc_info=True)
            raise


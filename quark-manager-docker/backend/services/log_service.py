# -*- coding: utf-8 -*-
"""
日志服务
"""
from datetime import datetime, timedelta
from database import get_db
from utils.logger import logger


class LogService:
    """日志服务类"""
    
    @staticmethod
    def create_log(log_data):
        """创建日志记录"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO log_records (
                        task_type, task_id, task_name, log_level,
                        log_content, execution_time, file_count,
                        file_size, error_message, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    log_data['task_type'],
                    log_data.get('task_id'),
                    log_data['task_name'],
                    log_data['log_level'],
                    log_data['log_content'],
                    log_data.get('execution_time'),
                    log_data.get('file_count'),
                    log_data.get('file_size'),
                    log_data.get('error_message'),
                    datetime.now()
                ))
                conn.commit()
                log_id = cursor.lastrowid
                return log_id
        except Exception as e:
            logger.error(f"创建日志记录失败: {e}")
            raise
    
    @staticmethod
    def get_logs(filters=None, page=1, page_size=20):
        """查询日志列表"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # 构建查询条件
                where_clauses = []
                params = []
                
                if filters:
                    if filters.get('task_type') and filters['task_type'] != 'all':
                        where_clauses.append("task_type = ?")
                        params.append(filters['task_type'])
                    
                    if filters.get('log_level') and filters['log_level'] != 'all':
                        where_clauses.append("log_level = ?")
                        params.append(filters['log_level'])
                    
                    if filters.get('start_date'):
                        where_clauses.append("DATE(created_at) >= ?")
                        params.append(filters['start_date'])
                    
                    if filters.get('end_date'):
                        where_clauses.append("DATE(created_at) <= ?")
                        params.append(filters['end_date'])
                
                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
                
                # 查询总数
                cursor.execute(f"SELECT COUNT(*) as total FROM log_records WHERE {where_sql}", params)
                total = cursor.fetchone()['total']
                
                # 查询日志列表
                offset = (page - 1) * page_size
                params.extend([page_size, offset])
                
                cursor.execute(f"""
                    SELECT * FROM log_records
                    WHERE {where_sql}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, params)
                
                logs = cursor.fetchall()
                
                return {
                    'total': total,
                    'page': page,
                    'page_size': page_size,
                    'logs': [dict(log) for log in logs]
                }
        except Exception as e:
            logger.error(f"查询日志列表失败: {e}")
            raise
    
    @staticmethod
    def clear_all_logs():
        """清空所有日志"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM log_records")
                count = cursor.fetchone()['count']
                
                cursor.execute("DELETE FROM log_records")
                conn.commit()
                
                logger.info(f"清空所有日志成功，共删除 {count} 条记录")
                return count
        except Exception as e:
            logger.error(f"清空日志失败: {e}")
            raise
    
    @staticmethod
    def auto_clean_logs(retention_days):
        """自动清理过期日志"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # 计算过期日期
                expire_date = datetime.now() - timedelta(days=retention_days)
                
                # 查询要删除的日志数量
                cursor.execute("""
                    SELECT COUNT(*) as count FROM log_records
                    WHERE created_at < ?
                """, (expire_date,))
                count = cursor.fetchone()['count']
                
                # 删除过期日志
                cursor.execute("""
                    DELETE FROM log_records WHERE created_at < ?
                """, (expire_date,))
                conn.commit()
                
                logger.info(f"自动清理过期日志成功，共删除 {count} 条记录（保留 {retention_days} 天）")
                return count
        except Exception as e:
            logger.error(f"自动清理日志失败: {e}")
            raise
    
    @staticmethod
    def get_task_logs(task_id, task_type):
        """获取指定任务的日志"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM log_records
                    WHERE task_id = ? AND task_type = ?
                    ORDER BY created_at DESC
                """, (task_id, task_type))
                
                logs = cursor.fetchall()
                return [dict(log) for log in logs]
        except Exception as e:
            logger.error(f"获取任务日志失败: {e}")
            raise

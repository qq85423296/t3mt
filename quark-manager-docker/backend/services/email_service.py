# -*- coding: utf-8 -*-
"""
邮件服务
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from utils.logger import logger


class EmailService:
    """邮件服务类"""
    
    @staticmethod
    def send_email(smtp_config, subject, content, receivers):
        """
        发送邮件
        
        Args:
            smtp_config: SMTP配置字典，包含server, port, sender, password
            subject: 邮件主题
            content: 邮件内容
            receivers: 收件人列表
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_config['sender']
            msg['To'] = ', '.join(receivers)
            msg['Subject'] = subject
            
            # 添加邮件正文
            msg.attach(MIMEText(content, 'plain', 'utf-8'))
            
            # 连接SMTP服务器并发送
            with smtplib.SMTP_SSL(smtp_config['server'], smtp_config['port']) as server:
                server.login(smtp_config['sender'], smtp_config['password'])
                server.send_message(msg)
            
            logger.info(f"邮件发送成功: {subject} -> {receivers}")
            return True
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            raise
    
    @staticmethod
    def test_smtp_config(smtp_config, test_receiver):
        """
        测试SMTP配置
        
        Args:
            smtp_config: SMTP配置字典
            test_receiver: 测试收件人
        """
        try:
            subject = "T3MT - 邮件配置测试"
            content = """
这是一封测试邮件。

如果您收到此邮件，说明邮件配置正确。

---
此邮件由T3MT自动发送
            """
            
            EmailService.send_email(smtp_config, subject, content, [test_receiver])
            return True
        except Exception as e:
            logger.error(f"测试邮件配置失败: {e}")
            raise
    
    @staticmethod
    def send_daily_report(smtp_config, receivers, report_data):
        """
        发送每日任务汇总日报
        
        Args:
            smtp_config: SMTP配置
            receivers: 收件人列表
            report_data: 报告数据
        """
        try:
            from datetime import datetime
            
            today = datetime.now().strftime('%Y-%m-%d')
            subject = f"T3MT - 任务执行日报 ({today})"
            
            # 构建邮件内容
            content = f"""
主题：T3MT - 任务执行日报 ({today})

总结：
- 执行任务总数：{report_data['total_tasks']}个
- 成功：{report_data['success_tasks']}个
- 失败：{report_data['failed_tasks']}个

详细信息：

【定时转存任务】
"""
            
            # 添加转存任务详情
            for task in report_data.get('transfer_tasks', []):
                status_icon = "✓" if task['status'] == 'success' else "✗"
                content += f"\n{status_icon} {task['name']}\n"
                content += f"  执行时间：{task['execute_time']}\n"
                
                if task['status'] == 'success':
                    content += f"  转存文件：{task['file_count']}个，总大小 {task['total_size']}\n"
                    content += f"  执行耗时：{task['duration']}\n"
                else:
                    content += f"  失败原因：{task['error_message']}\n"
            
            content += "\n【定时下载任务】\n"
            
            # 添加下载任务详情
            for task in report_data.get('download_tasks', []):
                status_icon = "✓" if task['status'] == 'success' else "✗"
                content += f"\n{status_icon} {task['name']}\n"
                content += f"  执行时间：{task['execute_time']}\n"
                
                if task['status'] == 'success':
                    content += f"  下载文件：{task['file_count']}个，总大小 {task['total_size']}\n"
                    content += f"  保存路径：{task['target_path']}\n"
                else:
                    content += f"  失败原因：{task['error_message']}\n"
            
            content += "\n---\n此邮件由T3MT自动发送\n"
            
            EmailService.send_email(smtp_config, subject, content, receivers)
            logger.info(f"每日报告发送成功")
            return True
        except Exception as e:
            logger.error(f"发送每日报告失败: {e}")
            raise
    
    @staticmethod
    def send_task_failure_alert(smtp_config, receivers, task_info):
        """
        发送任务失败告警邮件
        
        Args:
            smtp_config: SMTP配置
            receivers: 收件人列表
            task_info: 任务信息
        """
        try:
            subject = f"【告警】任务执行失败 - {task_info['name']}"
            
            content = f"""
任务名称：{task_info['name']}
任务类型：{task_info['type']}
执行时间：{task_info['execute_time']}
失败原因：{task_info['error_message']}

建议：{task_info.get('suggestion', '请检查任务配置和网络连接。')}

---
此邮件由T3MT自动发送
            """
            
            EmailService.send_email(smtp_config, subject, content, receivers)
            logger.info(f"任务失败告警邮件发送成功: {task_info['name']}")
            return True
        except Exception as e:
            logger.error(f"发送任务失败告警失败: {e}")
            raise

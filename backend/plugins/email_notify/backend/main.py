# -*- coding: utf-8 -*-
"""
邮件提醒插件

任务执行完成后发送邮件通知。
"""
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
from typing import List, Optional

import sys
import os
# 添加父目录到路径，以便导入 BasePlugin
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from plugins.base_plugin import BasePlugin


class EmailNotifyPlugin(BasePlugin):
    """
    邮件提醒插件
    
    在任务执行完成后发送邮件通知，支持：
    - 自定义发送条件（成功/失败/部分成功）
    - 自定义邮件主题模板
    - 多收件人
    - SSL/TLS加密
    """
    
    # 状态映射
    STATUS_MAP = {
        'success': '成功',
        'failed': '失败',
        'partial': '部分成功',
    }
    
    # 任务类型映射
    TASK_TYPE_MAP = {
        'transfer': '定时转存',
        'download': '定时下载',
        'video': '影视下载',
    }
    
    def execute(self) -> bool:
        """
        执行邮件发送
        
        Returns:
            是否发送成功
        """
        try:
            # 检查是否需要发送
            if not self._should_send():
                self.log("根据配置，当前状态不需要发送邮件")
                return True
            
            # 验证配置
            validation_error = self._validate_config()
            if validation_error:
                self.log(f"配置验证失败: {validation_error}", level='error')
                return False
            
            # 构建邮件
            subject = self._build_subject()
            body = self._build_body()
            
            self.log(f"准备发送邮件: {subject}")
            
            # 发送邮件
            success = self._send_email(subject, body)
            
            if success:
                self.log("邮件发送成功")
            else:
                self.log("邮件发送失败", level='error')
            
            return success
            
        except Exception as e:
            self.log(f"邮件插件执行异常: {str(e)}", level='error')
            return False

    def _should_send(self) -> bool:
        """
        检查是否需要发送邮件
        
        根据任务状态和配置决定是否发送
        """
        status = self.task_context.get('status', '')
        
        # 获取发送条件配置
        send_on_success = self.plugin_config.get('send_on_success', True)
        send_on_failure = self.plugin_config.get('send_on_failure', True)
        send_on_partial = self.plugin_config.get('send_on_partial', True)
        
        if status == 'success' and send_on_success:
            return True
        elif status == 'failed' and send_on_failure:
            return True
        elif status == 'partial' and send_on_partial:
            return True
        
        return False
    
    def _validate_config(self) -> Optional[str]:
        """
        验证配置是否完整
        
        Returns:
            错误信息，如果配置有效则返回 None
        """
        required_fields = [
            ('smtp_server', 'SMTP服务器'),
            ('smtp_port', 'SMTP端口'),
            ('sender_email', '发件人邮箱'),
            ('sender_password', '邮箱密码/授权码'),
            ('receiver_emails', '收件人邮箱'),
        ]
        
        for field, name in required_fields:
            value = self.plugin_config.get(field)
            if not value:
                return f"缺少必填配置: {name}"
        
        # 验证邮箱格式
        sender = self.plugin_config.get('sender_email', '')
        if '@' not in sender:
            return f"发件人邮箱格式不正确: {sender}"
        
        receivers = self._parse_receivers()
        if not receivers:
            return "收件人邮箱不能为空"
        
        for receiver in receivers:
            if '@' not in receiver:
                return f"收件人邮箱格式不正确: {receiver}"
        
        return None
    
    def _parse_receivers(self) -> List[str]:
        """解析收件人列表"""
        receivers_str = self.plugin_config.get('receiver_emails', '')
        if not receivers_str:
            return []
        
        # 支持逗号、分号、空格分隔
        receivers = []
        for sep in [',', ';', ' ']:
            if sep in receivers_str:
                receivers = [r.strip() for r in receivers_str.split(sep) if r.strip()]
                break
        
        if not receivers:
            receivers = [receivers_str.strip()]
        
        return receivers
    
    def _build_subject(self) -> str:
        """构建邮件主题"""
        template = self.plugin_config.get(
            'email_subject_template', 
            '[T3MT] {task_name} 执行{status}'
        )
        
        # 获取格式化后的变量
        variables = self._get_template_variables()
        
        # 替换变量
        try:
            subject = template.format(**variables)
        except KeyError as e:
            self.log(f"主题模板变量替换失败: {e}", level='warning')
            subject = template
        
        return subject
    
    def _get_template_variables(self) -> dict:
        """
        获取模板变量字典
        
        所有变量都会被格式化为用户友好的显示格式
        """
        task_name = self.task_context.get('task_name', '未知任务')
        task_type = self.task_context.get('task_type', 'unknown')
        status = self.task_context.get('status', 'unknown')
        start_time = self.task_context.get('start_time', '')
        end_time = self.task_context.get('end_time', '')
        duration = self.task_context.get('duration', 0)
        total_count = self.task_context.get('total_count', 0)
        success_count = self.task_context.get('success_count', 0)
        failed_count = self.task_context.get('failed_count', 0)
        total_size = self.task_context.get('total_size', 0)
        source_path = self.task_context.get('source_path', '')
        target_path = self.task_context.get('target_path', '')
        error_message = self.task_context.get('error_message', '')
        
        # 影视下载特有字段
        video_name = self.task_context.get('video_name', '')
        platform = self.task_context.get('platform', '')
        video_type = self.task_context.get('video_type', '')
        
        return {
            'task_id': self.task_context.get('task_id', 0),
            'task_name': task_name,
            'task_type': self.TASK_TYPE_MAP.get(task_type, task_type),
            'status': self.STATUS_MAP.get(status, status),
            'start_time': start_time,
            'end_time': end_time,
            'duration': self._format_duration(duration),
            'total_count': total_count,
            'success_count': success_count,
            'failed_count': failed_count,
            'total_size': self._format_size(total_size),
            'source_path': source_path or '无',
            'target_path': target_path or '无',
            'error_message': error_message or '无',
            # 影视下载特有
            'video_name': video_name,
            'platform': platform,
            'video_type': video_type,
        }

    def _build_body(self) -> str:
        """构建邮件正文"""
        use_html = self.plugin_config.get('use_html_template', True)
        custom_template = self.plugin_config.get('email_body_template', '')
        
        # 获取格式化后的变量
        variables = self._get_template_variables()
        
        if use_html:
            # 使用内置HTML模板
            return self._build_html_body(variables)
        else:
            # 使用自定义纯文本模板
            if custom_template:
                try:
                    return custom_template.format(**variables)
                except KeyError as e:
                    self.log(f"正文模板变量替换失败: {e}", level='warning')
                    return custom_template
            else:
                # 默认纯文本模板
                return self._build_default_text_body(variables)
    
    def _build_default_text_body(self, variables: dict) -> str:
        """构建默认纯文本正文"""
        return f'''{variables['task_type']}-{variables['task_name']}任务: {variables['status']}
来源目录: {variables['source_path']}
目标目录: {variables['target_path']}
的作业执行结束。

共 {variables['total_count']} 个需要同步的文件，成功 {variables['success_count']} 个，失败 {variables['failed_count']} 个。
本次同步共耗时：{variables['duration']}，成功同步 {variables['total_size']} 文件。

开始时间: {variables['start_time']}
结束时间: {variables['end_time']}
'''
    
    def _build_html_body(self, variables: dict) -> str:
        """构建HTML格式邮件正文"""
        status = self.task_context.get('status', 'unknown')
        
        # 状态颜色
        status_colors = {
            'success': '#28a745',
            'failed': '#dc3545',
            'partial': '#ffc107',
        }
        status_color = status_colors.get(status, '#6c757d')
        
        # 原始数值（用于统计卡片）
        total_count = self.task_context.get('total_count', 0)
        success_count = self.task_context.get('success_count', 0)
        failed_count = self.task_context.get('failed_count', 0)
        total_size = self.task_context.get('total_size', 0)
        error_message = self.task_context.get('error_message', '')
        
        # 构建HTML邮件
        html = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 24px; }}
        .header h2 {{ margin: 0 0 8px 0; font-size: 20px; }}
        .header .task-name {{ font-size: 16px; opacity: 0.9; }}
        .status {{ display: inline-block; padding: 4px 12px; border-radius: 4px; color: white; font-weight: bold; background: {status_color}; font-size: 14px; }}
        .content {{ padding: 24px; }}
        .summary {{ background: #f8f9fa; border-radius: 8px; padding: 16px; margin-bottom: 20px; line-height: 1.8; }}
        .summary .label {{ color: #666; }}
        .summary .value {{ color: #333; font-weight: 500; }}
        .stats {{ display: flex; gap: 12px; margin-bottom: 20px; }}
        .stat-item {{ flex: 1; text-align: center; padding: 16px; border-radius: 8px; }}
        .stat-item.success {{ background: #d1fae5; }}
        .stat-item.failed {{ background: #fee2e2; }}
        .stat-item.total {{ background: #e0e7ff; }}
        .stat-item .number {{ font-size: 24px; font-weight: bold; }}
        .stat-item.success .number {{ color: #059669; }}
        .stat-item.failed .number {{ color: #dc2626; }}
        .stat-item.total .number {{ color: #4f46e5; }}
        .stat-item .text {{ font-size: 12px; color: #666; margin-top: 4px; }}
        .detail {{ font-size: 14px; color: #666; line-height: 1.6; }}
        .detail-row {{ display: flex; padding: 8px 0; border-bottom: 1px solid #f0f0f0; }}
        .detail-row:last-child {{ border-bottom: none; }}
        .detail-row .label {{ width: 80px; color: #999; flex-shrink: 0; }}
        .detail-row .value {{ color: #333; word-break: break-all; }}
        .footer {{ text-align: center; padding: 16px; color: #999; font-size: 12px; border-top: 1px solid #f0f0f0; }}
        .error-box {{ background: #fee2e2; border: 1px solid #fecaca; border-radius: 6px; padding: 12px; margin-top: 16px; color: #dc2626; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>{variables['task_type']} - {variables['task_name']}</h2>
            <span class="status">{variables['status']}</span>
        </div>
        <div class="content">
            <div class="summary">
                <div><span class="label">来源目录：</span><span class="value">{variables['source_path']}</span></div>
                <div><span class="label">目标目录：</span><span class="value">{variables['target_path']}</span></div>
                <div style="margin-top: 12px;">
                    共 <strong>{total_count}</strong> 个需要同步的文件，成功 <strong style="color: #059669;">{success_count}</strong> 个，失败 <strong style="color: #dc2626;">{failed_count}</strong> 个。
                </div>
                <div>
                    本次同步共耗时：<strong>{variables['duration']}</strong>'''
        
        if total_size > 0:
            html += f'''，成功同步 <strong>{variables['total_size']}</strong> 文件。'''
        else:
            html += '。'
        
        html += '''
                </div>
            </div>
            
            <div class="stats">
                <div class="stat-item total">
                    <div class="number">''' + str(total_count) + '''</div>
                    <div class="text">总文件数</div>
                </div>
                <div class="stat-item success">
                    <div class="number">''' + str(success_count) + '''</div>
                    <div class="text">成功</div>
                </div>
                <div class="stat-item failed">
                    <div class="number">''' + str(failed_count) + '''</div>
                    <div class="text">失败</div>
                </div>
            </div>
            
            <div class="detail">
                <div class="detail-row">
                    <span class="label">开始时间</span>
                    <span class="value">''' + variables['start_time'] + '''</span>
                </div>
                <div class="detail-row">
                    <span class="label">结束时间</span>
                    <span class="value">''' + variables['end_time'] + '''</span>
                </div>
                <div class="detail-row">
                    <span class="label">执行耗时</span>
                    <span class="value">''' + variables['duration'] + '''</span>
                </div>
            </div>
'''
        
        if error_message:
            html += f'''
            <div class="error-box">
                <strong>错误信息：</strong>{error_message}
            </div>
'''
        
        html += '''
        </div>
        <div class="footer">
            此邮件由 T3MT 自动发送，请勿回复
        </div>
    </div>
</body>
</html>
'''
        return html
    
    def _format_duration(self, seconds: int) -> str:
        """格式化耗时"""
        if not seconds:
            return '0 秒'
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        parts = []
        if hours > 0:
            parts.append(f'{hours} 小时')
        if minutes > 0 or hours > 0:
            parts.append(f'{minutes} 分')
        parts.append(f'{secs} 秒')
        
        return ' '.join(parts)
    
    def _format_size(self, bytes_size: int) -> str:
        """格式化文件大小"""
        if not bytes_size:
            return '0 B'
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size = float(bytes_size)
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f'{int(size)} {units[unit_index]}'
        else:
            return f'{size:.2f} {units[unit_index]}'

    def _send_email(self, subject: str, body: str) -> bool:
        """
        发送邮件
        
        Args:
            subject: 邮件主题
            body: 邮件正文（HTML）
        
        Returns:
            是否发送成功
        """
        smtp_server = self.plugin_config.get('smtp_server')
        smtp_port = int(self.plugin_config.get('smtp_port', 465))
        use_ssl = self.plugin_config.get('smtp_ssl', True)
        sender_email = self.plugin_config.get('sender_email')
        sender_password = self.plugin_config.get('sender_password')
        receivers = self._parse_receivers()
        timeout = int(self.plugin_config.get('timeout', 30))
        
        try:
            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = Header(subject, 'utf-8')
            msg['From'] = sender_email
            msg['To'] = ', '.join(receivers)
            
            # 添加HTML正文
            html_part = MIMEText(body, 'html', 'utf-8')
            msg.attach(html_part)
            
            self.log(f"连接SMTP服务器: {smtp_server}:{smtp_port}")
            
            # 连接SMTP服务器
            if use_ssl:
                # SSL连接（端口465）
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=timeout, context=context)
            else:
                # TLS连接（端口587）
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=timeout)
                server.starttls()
            
            try:
                # 登录
                self.log("正在登录SMTP服务器...")
                server.login(sender_email, sender_password)
                
                # 发送邮件
                self.log(f"正在发送邮件到: {', '.join(receivers)}")
                server.sendmail(sender_email, receivers, msg.as_string())
                
                return True
                
            finally:
                server.quit()
                
        except smtplib.SMTPAuthenticationError as e:
            self.log(f"SMTP认证失败: {str(e)}", level='error')
            self.log("请检查邮箱地址和密码/授权码是否正确", level='error')
            return False
            
        except smtplib.SMTPConnectError as e:
            self.log(f"SMTP连接失败: {str(e)}", level='error')
            self.log("请检查SMTP服务器地址和端口是否正确", level='error')
            return False
            
        except smtplib.SMTPRecipientsRefused as e:
            self.log(f"收件人被拒绝: {str(e)}", level='error')
            self.log("请检查收件人邮箱地址是否正确", level='error')
            return False
            
        except TimeoutError:
            self.log(f"SMTP连接超时（{timeout}秒）", level='error')
            self.log("请检查网络连接或增加超时时间", level='error')
            return False
            
        except Exception as e:
            self.log(f"发送邮件异常: {str(e)}", level='error')
            return False


def register_plugin():
    """注册插件（供插件管理器调用）"""
    return EmailNotifyPlugin

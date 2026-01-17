# -*- coding: utf-8 -*-
"""
企业微信提醒插件

任务执行完成后通过企业微信群机器人发送通知。
"""
import requests
import json
from typing import List, Optional, Dict, Any

import sys
import os
# 添加父目录到路径，以便导入 BasePlugin
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from plugins.base_plugin import BasePlugin


class WecomNotifyPlugin(BasePlugin):
    """
    企业微信提醒插件
    
    在任务执行完成后通过企业微信群机器人发送通知，支持：
    - 自定义发送条件（成功/失败/部分成功）
    - 多种消息格式（文本/Markdown）
    - @指定成员或所有人
    - 自定义消息模板
    """
    
    # 状态映射
    STATUS_MAP = {
        'success': '✅ 成功',
        'failed': '❌ 失败',
        'partial': '⚠️ 部分成功',
    }
    
    # 任务类型映射
    TASK_TYPE_MAP = {
        'transfer': '定时转存',
        'download': '定时下载',
        'video': '影视下载',
    }
    
    # 状态颜色（Markdown）
    STATUS_COLOR_MAP = {
        'success': 'info',
        'failed': 'warning',
        'partial': 'comment',
    }
    
    def execute(self) -> bool:
        """
        执行企业微信消息发送
        
        Returns:
            是否发送成功
        """
        try:
            # 检查是否需要发送
            if not self._should_send():
                self.log("根据配置，当前状态不需要发送通知")
                return True
            
            # 验证配置
            validation_error = self._validate_config()
            if validation_error:
                self.log(f"配置验证失败: {validation_error}", level='error')
                return False
            
            # 构建消息
            message_data = self._build_message()
            
            self.log(f"准备发送企业微信通知")
            
            # 发送消息
            success = self._send_message(message_data)
            
            if success:
                self.log("企业微信通知发送成功")
            else:
                self.log("企业微信通知发送失败", level='error')
            
            return success
            
        except Exception as e:
            self.log(f"企业微信插件执行异常: {str(e)}", level='error')
            return False

    def _should_send(self) -> bool:
        """
        检查是否需要发送通知
        
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
        webhook_url = self.plugin_config.get('webhook_url', '')
        
        if not webhook_url:
            return "缺少必填配置: Webhook地址"
        
        # 验证Webhook URL格式
        if not webhook_url.startswith('https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key='):
            return "Webhook地址格式不正确，应为: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxx"
        
        return None
    
    def _parse_list(self, list_str: str) -> List[str]:
        """解析逗号分隔的列表"""
        if not list_str:
            return []
        
        # 支持逗号、分号、空格分隔
        items = []
        for sep in [',', ';', ' ']:
            if sep in list_str:
                items = [item.strip() for item in list_str.split(sep) if item.strip()]
                break
        
        if not items and list_str.strip():
            items = [list_str.strip()]
        
        return items
    
    def _get_template_variables(self) -> Dict[str, Any]:
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
            'task_type_raw': task_type,
            'status': self.STATUS_MAP.get(status, status),
            'status_raw': status,
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

    def _build_message(self) -> Dict[str, Any]:
        """
        构建企业微信消息体
        
        Returns:
            消息数据字典
        """
        message_type = self.plugin_config.get('message_type', 'markdown')
        
        if message_type == 'text':
            return self._build_text_message()
        else:
            return self._build_markdown_message()
    
    def _build_text_message(self) -> Dict[str, Any]:
        """构建文本消息"""
        variables = self._get_template_variables()
        custom_template = self.plugin_config.get('message_template', '')
        
        # 构建消息内容
        if custom_template:
            try:
                content = custom_template.format(**variables)
            except KeyError as e:
                self.log(f"消息模板变量替换失败: {e}", level='warning')
                content = custom_template
        else:
            # 默认文本模板
            content = self._build_default_text_content(variables)
        
        # 构建消息体
        message_data = {
            "msgtype": "text",
            "text": {
                "content": content
            }
        }
        
        # 添加@成员列表
        mentioned_list = self._parse_list(self.plugin_config.get('mentioned_list', ''))
        mentioned_mobile_list = self._parse_list(self.plugin_config.get('mentioned_mobile_list', ''))
        
        if mentioned_list:
            message_data["text"]["mentioned_list"] = mentioned_list
        
        if mentioned_mobile_list:
            message_data["text"]["mentioned_mobile_list"] = mentioned_mobile_list
        
        return message_data
    
    def _build_default_text_content(self, variables: Dict[str, Any]) -> str:
        """构建默认文本内容"""
        content = f"""【T3MT任务通知】

任务名称：{variables['task_name']}
任务类型：{variables['task_type']}
执行状态：{variables['status']}

来源目录：{variables['source_path']}
目标目录：{variables['target_path']}

文件统计：
- 总文件数：{variables['total_count']}
- 成功：{variables['success_count']}
- 失败：{variables['failed_count']}

执行信息：
- 开始时间：{variables['start_time']}
- 结束时间：{variables['end_time']}
- 执行耗时：{variables['duration']}
- 同步大小：{variables['total_size']}"""
        
        if variables['error_message'] != '无':
            content += f"\n\n错误信息：{variables['error_message']}"
        
        return content
    
    def _build_markdown_message(self) -> Dict[str, Any]:
        """构建Markdown消息"""
        variables = self._get_template_variables()
        custom_template = self.plugin_config.get('message_template', '')
        
        # 构建消息内容
        if custom_template:
            try:
                content = custom_template.format(**variables)
            except KeyError as e:
                self.log(f"消息模板变量替换失败: {e}", level='warning')
                content = custom_template
        else:
            # 默认Markdown模板
            content = self._build_default_markdown_content(variables)
        
        # 构建消息体
        message_data = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }
        
        return message_data
    
    def _build_default_markdown_content(self, variables: Dict[str, Any]) -> str:
        """构建默认Markdown内容"""
        status_raw = variables['status_raw']
        status_color = self.STATUS_COLOR_MAP.get(status_raw, 'comment')
        
        content = f"""## 【T3MT任务通知】

> **任务名称**：{variables['task_name']}
> **任务类型**：{variables['task_type']}
> **执行状态**：<font color="{status_color}">{variables['status']}</font>

### 📁 目录信息
- 来源目录：`{variables['source_path']}`
- 目标目录：`{variables['target_path']}`

### 📊 文件统计
- 总文件数：**{variables['total_count']}**
- 成功：<font color="info">{variables['success_count']}</font>
- 失败：<font color="warning">{variables['failed_count']}</font>

### ⏱️ 执行信息
- 开始时间：{variables['start_time']}
- 结束时间：{variables['end_time']}
- 执行耗时：{variables['duration']}
- 同步大小：{variables['total_size']}"""
        
        if variables['error_message'] != '无':
            content += f"\n\n### ❌ 错误信息\n```\n{variables['error_message']}\n```"
        
        return content
    
    def _format_duration(self, seconds: int) -> str:
        """格式化耗时"""
        if not seconds:
            return '0秒'
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        parts = []
        if hours > 0:
            parts.append(f'{hours}小时')
        if minutes > 0 or hours > 0:
            parts.append(f'{minutes}分')
        parts.append(f'{secs}秒')
        
        return ''.join(parts)
    
    def _format_size(self, bytes_size: int) -> str:
        """格式化文件大小"""
        if not bytes_size:
            return '0B'
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size = float(bytes_size)
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f'{int(size)}{units[unit_index]}'
        else:
            return f'{size:.2f}{units[unit_index]}'

    def _send_message(self, message_data: Dict[str, Any]) -> bool:
        """
        发送企业微信消息
        
        Args:
            message_data: 消息数据字典
        
        Returns:
            是否发送成功
        """
        webhook_url = self.plugin_config.get('webhook_url')
        timeout = int(self.plugin_config.get('timeout', 10))
        
        try:
            self.log(f"正在发送企业微信通知...")
            
            # 发送POST请求
            headers = {'Content-Type': 'application/json'}
            response = requests.post(
                webhook_url,
                data=json.dumps(message_data, ensure_ascii=False).encode('utf-8'),
                headers=headers,
                timeout=timeout
            )
            
            # 检查响应
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    self.log("企业微信API返回成功")
                    return True
                else:
                    error_msg = result.get('errmsg', '未知错误')
                    self.log(f"企业微信API返回错误: {error_msg}", level='error')
                    return False
            else:
                self.log(f"HTTP请求失败，状态码: {response.status_code}", level='error')
                return False
                
        except requests.exceptions.Timeout:
            self.log(f"请求超时（{timeout}秒）", level='error')
            return False
            
        except requests.exceptions.ConnectionError as e:
            self.log(f"网络连接失败: {str(e)}", level='error')
            return False
            
        except requests.exceptions.RequestException as e:
            self.log(f"HTTP请求异常: {str(e)}", level='error')
            return False
            
        except Exception as e:
            self.log(f"发送消息异常: {str(e)}", level='error')
            return False


def register_plugin():
    """注册插件（供插件管理器调用）"""
    return WecomNotifyPlugin

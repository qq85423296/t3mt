# -*- coding: utf-8 -*-
"""
Aria2 RPC服务封装
提供与Aria2 RPC交互的统一接口
"""
import json
import requests
from utils.logger import logger


class Aria2Service:
    """Aria2 RPC服务类"""
    
    def __init__(self, rpc_url='http://127.0.0.1:6800/jsonrpc'):
        """
        初始化Aria2服务
        
        Args:
            rpc_url: Aria2 RPC地址
        """
        self.rpc_url = rpc_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
    
    def _call_rpc(self, method, params=None):
        """
        调用Aria2 RPC方法
        
        Args:
            method: RPC方法名
            params: 方法参数列表
        
        Returns:
            dict: RPC响应结果
        """
        if params is None:
            params = []
        
        payload = {
            'jsonrpc': '2.0',
            'id': 'kiro',
            'method': method,
            'params': params
        }
        
        try:
            logger.debug(f"Aria2 RPC调用: method={method}, url={self.rpc_url}")
            response = self.session.post(
                self.rpc_url,
                data=json.dumps(payload),
                timeout=10
            )
            
            logger.debug(f"Aria2 RPC响应: status={response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Aria2 RPC请求失败: status={response.status_code}, response={response.text[:200]}")
                return None
            
            result = response.json()
            
            if 'error' in result:
                error = result['error']
                logger.error(f"Aria2 RPC错误: code={error.get('code')}, message={error.get('message')}")
                return None
            
            return result.get('result')
            
        except requests.exceptions.Timeout:
            logger.error(f"Aria2 RPC请求超时: method={method}, url={self.rpc_url}")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"无法连接到Aria2 RPC服务: {e}")
            return None
        except Exception as e:
            logger.error(f"Aria2 RPC调用异常: {e}", exc_info=True)
            return None
    
    def add_download(self, url, options=None):
        """
        添加下载任务
        
        Args:
            url: 下载链接
            options: 下载选项字典，例如:
                {
                    'dir': '/path/to/download',
                    'out': 'filename.ext',
                    'header': ['User-Agent: xxx', 'Cookie: xxx']
                }
        
        Returns:
            str: Aria2任务GID，失败返回None
        """
        if options is None:
            options = {}
        
        params = [[url], options]
        gid = self._call_rpc('aria2.addUri', params)
        
        if gid:
            logger.info(f"Aria2添加下载任务成功: gid={gid}, url={url[:100]}...")
        else:
            logger.error(f"Aria2添加下载任务失败: url={url[:100]}...")
        
        return gid
    
    def get_status(self, gid):
        """
        获取任务状态
        
        Args:
            gid: Aria2任务GID
        
        Returns:
            dict: 任务状态信息，包含:
                - status: active|waiting|paused|error|complete|removed
                - totalLength: 文件总大小（字节）
                - completedLength: 已下载大小（字节）
                - downloadSpeed: 下载速度（字节/秒）
                - connections: 活动连接数
                - errorCode: 错误码（如果失败）
                - errorMessage: 错误信息
                - files: 文件列表
        """
        result = self._call_rpc('aria2.tellStatus', [gid])
        
        if result:
            return {
                'gid': result.get('gid'),
                'status': result.get('status'),
                'totalLength': int(result.get('totalLength', 0)),
                'completedLength': int(result.get('completedLength', 0)),
                'downloadSpeed': int(result.get('downloadSpeed', 0)),
                'connections': int(result.get('connections', 0)),
                'errorCode': result.get('errorCode'),
                'errorMessage': result.get('errorMessage'),
                'files': result.get('files', [])
            }
        
        return None
    
    def pause_task(self, gid):
        """
        暂停任务
        
        Args:
            gid: Aria2任务GID
        
        Returns:
            bool: 是否成功
        """
        result = self._call_rpc('aria2.pause', [gid])
        success = result == gid
        
        if success:
            logger.info(f"Aria2暂停任务成功: gid={gid}")
        else:
            logger.error(f"Aria2暂停任务失败: gid={gid}")
        
        return success
    
    def resume_task(self, gid):
        """
        恢复任务
        
        Args:
            gid: Aria2任务GID
        
        Returns:
            bool: 是否成功
        """
        result = self._call_rpc('aria2.unpause', [gid])
        success = result == gid
        
        if success:
            logger.info(f"Aria2恢复任务成功: gid={gid}")
        else:
            logger.error(f"Aria2恢复任务失败: gid={gid}")
        
        return success
    
    def remove_task(self, gid, force=False):
        """
        删除任务
        
        Args:
            gid: Aria2任务GID
            force: 是否强制删除
        
        Returns:
            bool: 是否成功
        """
        method = 'aria2.forceRemove' if force else 'aria2.remove'
        result = self._call_rpc(method, [gid])
        success = result == gid
        
        if success:
            logger.info(f"Aria2删除任务成功: gid={gid}, force={force}")
        else:
            logger.error(f"Aria2删除任务失败: gid={gid}")
        
        return success
    
    def get_global_stat(self):
        """
        获取全局统计信息
        
        Returns:
            dict: 全局统计信息，包含:
                - downloadSpeed: 总下载速度
                - uploadSpeed: 总上传速度
                - numActive: 活动任务数
                - numWaiting: 等待任务数
                - numStopped: 已停止任务数
        """
        result = self._call_rpc('aria2.getGlobalStat')
        
        if result:
            return {
                'downloadSpeed': int(result.get('downloadSpeed', 0)),
                'uploadSpeed': int(result.get('uploadSpeed', 0)),
                'numActive': int(result.get('numActive', 0)),
                'numWaiting': int(result.get('numWaiting', 0)),
                'numStopped': int(result.get('numStopped', 0))
            }
        
        return None
    
    def get_version(self):
        """
        获取Aria2版本信息
        
        Returns:
            dict: 版本信息
        """
        return self._call_rpc('aria2.getVersion')
    
    def test_connection(self):
        """
        测试与Aria2的连接
        
        Returns:
            bool: 是否连接成功
        """
        version = self.get_version()
        if version:
            logger.info(f"Aria2连接成功: version={version.get('version')}")
            return True
        else:
            logger.error("Aria2连接失败")
            return False

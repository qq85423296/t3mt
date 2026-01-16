# -*- coding: utf-8 -*-
"""
夸克网盘API服务
"""
import re
import time
import random
import requests
import urllib.parse
from datetime import datetime
from config import Config
from utils.logger import logger


class QuarkService:
    """夸克网盘API服务类"""
    
    def __init__(self, cookie):
        self.cookie = cookie.strip()
        
        # 确保夸克API配置已加载
        from config import Config
        if not Config.ensure_quark_config():
            error_msg = "夸克API配置未加载,请联系管理员获取配置"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        self.base_url = Config.QUARK_BASE_URL
        self.base_url_app = Config.QUARK_BASE_URL_APP
        self.user_agent = Config.QUARK_USER_AGENT
        self.mparam = self._extract_mparam_from_cookie(cookie)
    
    def _extract_mparam_from_cookie(self, cookie):
        """从Cookie中提取移动端参数"""
        mparam = {}
        kps_match = re.search(r"(?<!\w)kps=([a-zA-Z0-9%+/=]+)[;&]?", cookie)
        sign_match = re.search(r"(?<!\w)sign=([a-zA-Z0-9%+/=]+)[;&]?", cookie)
        vcode_match = re.search(r"(?<!\w)vcode=([a-zA-Z0-9%+/=]+)[;&]?", cookie)
        
        if kps_match and sign_match and vcode_match:
            mparam = {
                "kps": kps_match.group(1).replace("%25", "%"),
                "sign": sign_match.group(1).replace("%25", "%"),
                "vcode": vcode_match.group(1).replace("%25", "%"),
            }
        return mparam
    
    def _send_request(self, method, url, **kwargs):
        """发送HTTP请求"""
        headers = {
            "cookie": self.cookie,
            "content-type": "application/json",
            "user-agent": self.user_agent,
        }
        
        if "headers" in kwargs:
            headers.update(kwargs["headers"])
            del kwargs["headers"]
        
        # 移动端接口处理
        if self.mparam and "share" in url and self.base_url in url:
            url = url.replace(self.base_url, self.base_url_app)
            mobile_params = {
                "device_model": "M2011K2C",
                "entry": "default_clouddrive",
                "fr": "android",
                "pr": "ucpro",
                "kps": self.mparam.get("kps"),
                "sign": self.mparam.get("sign"),
                "vcode": self.mparam.get("vcode"),
            }
            if "params" in kwargs:
                kwargs["params"].update(mobile_params)
            else:
                kwargs["params"] = mobile_params
            del headers["cookie"]
        
        try:
            response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
            return response
        except Exception as e:
            logger.error(f"请求失败: {e}")
            raise
    
    # ========== 账号相关 ==========
    
    def get_account_info(self):
        """获取账号信息（包含会员信息和昵称）"""
        nickname = ""
        
        # 先获取基础账号信息（包含昵称）
        try:
            # 使用base_url构建账号信息接口地址
            url_basic = f"{self.base_url.replace('drive-pc', 'pan')}/account/info"
            params_basic = {"fr": "pc", "platform": "pc"}
            response_basic = self._send_request("GET", url_basic, params=params_basic)
            
            # 检查响应状态
            if response_basic.status_code == 200:
                result = response_basic.json()
                
                # 处理不同的返回格式
                if result.get("code") == "OK" and result.get("data"):
                    nickname = result["data"].get("nickname", "")
                elif result.get("success") and result.get("data"):
                    nickname = result["data"].get("nickname", "")
                elif result.get("data"):
                    nickname = result["data"].get("nickname", "")
                    
                logger.info(f"成功获取账号昵称: {nickname}")
        except Exception as e:
            logger.warning(f"获取基础账号信息失败: {e}，将继续获取会员信息")
        
        # 使用新的会员信息接口
        url = f"{self.base_url}/1/clouddrive/member"
        params = {
            "pr": "ucpro",
            "fr": "pc",
            "fetch_subscribe": "true",
            "_ch": "home",
            "fetch_identity": "true"
        }
        
        try:
            response = self._send_request("GET", url, params=params)
            
            if response.status_code != 200:
                logger.error(f"获取会员信息失败，状态码: {response.status_code}")
                return None
                
            result = response.json()
            
            if result.get("code") == 0 and result.get("data"):
                data = result["data"]
                
                # 解析会员类型
                member_type = data.get("member_type", "")
                member_type_map = {
                    "SUPER_VIP": "超级会员",
                    "VIP": "普通会员",
                    "MINI_VIP": "迷你会员",
                    "Z_VIP": "至尊会员"
                }
                member_type_text = member_type_map.get(member_type, "普通用户")
                
                # 解析会员到期时间
                exp_at = data.get("exp_at", 0)
                if exp_at:
                    from datetime import datetime
                    exp_time = datetime.fromtimestamp(exp_at / 1000).strftime('%Y-%m-%d')
                else:
                    exp_time = None
                
                # 返回格式化的账号信息
                return {
                    "nickname": nickname,  # 从基础接口获取的昵称
                    "member_type": 1 if member_type else 0,  # 是否会员
                    "member_type_text": member_type_text,
                    "member_type_raw": member_type,
                    "exp_at": exp_time,
                    "total_capacity": data.get("total_capacity", 0),
                    "use_capacity": data.get("use_capacity", 0),
                    "is_vip": 1 if member_type else 0,
                    "created_at": data.get("created_at", 0)
                }
            else:
                logger.error(f"获取会员信息返回错误: {result}")
                return None
            
        except Exception as e:
            logger.error(f"获取账号信息失败: {e}")
            return None
    
    def get_growth_info(self):
        """获取容量成长信息"""
        url = f"{self.base_url_app}/1/clouddrive/capacity/growth/info"
        params = {
            "pr": "ucpro",
            "fr": "android",
            "kps": self.mparam.get("kps"),
            "sign": self.mparam.get("sign"),
            "vcode": self.mparam.get("vcode"),
        }
        response = self._send_request("GET", url, params=params).json()
        
        if response.get("data"):
            return response["data"]
        return None
    
    def do_sign(self):
        """执行签到"""
        url = f"{self.base_url_app}/1/clouddrive/capacity/growth/sign"
        params = {
            "pr": "ucpro",
            "fr": "android",
            "kps": self.mparam.get("kps"),
            "sign": self.mparam.get("sign"),
            "vcode": self.mparam.get("vcode"),
        }
        payload = {"sign_cyclic": True}
        response = self._send_request("POST", url, json=payload, params=params).json()
        
        if response.get("data"):
            return True, response["data"].get("sign_daily_reward", 0)
        return False, response.get("message", "签到失败")
    
    # ========== 文件管理 ==========
    
    def get_file_list(self, pdir_fid="0", page=1, size=50):
        """获取文件列表"""
        url = f"{self.base_url}/1/clouddrive/file/sort"
        params = {
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
            "pdir_fid": pdir_fid,
            "_page": page,
            "_size": size,
            "_fetch_total": "1",
            "_fetch_sub_dirs": "0",
            "_sort": "file_type:asc,updated_at:desc",
        }
        response = self._send_request("GET", url, params=params).json()
        return response
    
    def get_fids_by_paths(self, file_paths):
        """根据路径获取文件ID"""
        fids = []
        batch_size = 50
        
        for i in range(0, len(file_paths), batch_size):
            batch = file_paths[i:i+batch_size]
            url = f"{self.base_url}/1/clouddrive/file/info/path_list"
            params = {"pr": "ucpro", "fr": "pc"}
            payload = {"file_path": batch, "namespace": "0"}
            
            response = self._send_request("POST", url, json=payload, params=params).json()
            if response["code"] == 0:
                fids.extend(response["data"])
        
        return fids
    
    def mkdir(self, dir_path, pdir_fid="0"):
        """
        创建文件夹
        
        Args:
            dir_path: 文件夹名称或路径
            pdir_fid: 父目录ID，默认为"0"（根目录）
        
        Returns:
            dict: 夸克API返回结果
        """
        url = f"{self.base_url}/1/clouddrive/file"
        params = {"pr": "ucpro", "fr": "pc", "uc_param_str": ""}
        payload = {
            "pdir_fid": pdir_fid,
            "file_name": dir_path,
            "dir_path": "",
            "dir_init_lock": False,
        }
        response = self._send_request("POST", url, json=payload, params=params).json()
        return response
    
    def rename(self, fid, file_name):
        """重命名文件/文件夹"""
        url = f"{self.base_url}/1/clouddrive/file/rename"
        params = {"pr": "ucpro", "fr": "pc", "uc_param_str": ""}
        payload = {"fid": fid, "file_name": file_name}
        response = self._send_request("POST", url, json=payload, params=params).json()
        return response
    
    def delete(self, filelist):
        """
        删除文件/文件夹
        
        Args:
            filelist: 文件ID列表，例如: ["file_id_1", "file_id_2"]
        
        Returns:
            dict: 删除结果
        """
        url = f"{self.base_url}/1/clouddrive/file/delete"
        params = {
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": ""
        }
        
        # 确保filelist是列表格式
        if not isinstance(filelist, list):
            filelist = [filelist]
        
        payload = {
            "action_type": 2,
            "filelist": filelist,
            "exclude_fids": []
        }
        
        logger.info(f"删除文件请求: URL={url}")
        logger.info(f"删除文件请求参数: {params}")
        logger.info(f"删除文件请求体: {payload}")
        
        try:
            response = self._send_request("POST", url, json=payload, params=params)
            
            logger.info(f"删除文件响应状态码: {response.status_code}")
            logger.info(f"删除文件响应头: {dict(response.headers)}")
            
            # 先获取响应文本
            response_text = response.text
            logger.info(f"删除文件响应内容: {response_text[:1000]}")
            
            if response.status_code == 400:
                logger.error(f"删除文件请求错误(400)")
                return {
                    'code': -1,
                    'message': f'请求参数错误(400): {response_text[:200]}'
                }
            
            if response.status_code != 200:
                logger.error(f"删除文件失败，状态码: {response.status_code}")
                return {
                    'code': -1,
                    'message': f'删除失败: HTTP {response.status_code}'
                }
            
            # 检查响应内容是否为空
            if not response_text or response_text.strip() == '':
                logger.warning("删除文件响应内容为空，但状态码200，认为删除成功")
                return {
                    'code': 0,
                    'message': '删除成功'
                }
            
            # 尝试解析JSON
            try:
                result = response.json()
                logger.info(f"删除文件API返回: {result}")
                
                if result.get('code') == 0 and result.get('data'):
                    data = result['data']
                    task_id = data.get('task_id')
                    
                    # 如果是异步任务，查询任务状态
                    if task_id:
                        logger.info(f"删除是异步任务，task_id: {task_id}，开始查询任务结果")
                        task_result = self.query_task(task_id)
                        logger.info(f"删除任务查询结果: {task_result}")
                        
                        if task_result.get('status') == 200 and task_result.get('data'):
                            task_data = task_result['data']
                            task_status = task_data.get('status')
                            
                            if task_status == 2:  # 任务完成
                                return {
                                    'code': 0,
                                    'message': '删除成功',
                                    'data': task_data
                                }
                            else:
                                return {
                                    'code': -1,
                                    'message': f'删除任务状态异常: {task_status}',
                                    'data': task_data
                                }
                        else:
                            return {
                                'code': -1,
                                'message': '删除任务查询失败',
                                'data': task_result
                            }
                    
                    # 如果直接完成（finish=true）
                    if data.get('finish'):
                        return {
                            'code': 0,
                            'message': '删除成功',
                            'data': data
                        }
                    
                    return {
                        'code': 0,
                        'message': '删除成功',
                        'data': data
                    }
                else:
                    return {
                        'code': -1,
                        'message': result.get('message', '删除失败'),
                        'data': result
                    }
            except ValueError as e:
                logger.error(f"解析删除响应JSON失败: {e}")
                logger.error(f"响应内容类型: {response.headers.get('content-type')}")
                return {
                    'code': -1,
                    'message': f'响应格式错误: {str(e)}'
                }
                
        except Exception as e:
            logger.error(f"删除文件异常: {e}", exc_info=True)
            return {
                'code': -1,
                'message': f'删除失败: {str(e)}'
            }
    
    def get_download_url(self, fids):
        """获取下载链接"""
        url = f"{self.base_url}/1/clouddrive/file/download"
        params = {"pr": "ucpro", "fr": "pc", "uc_param_str": ""}
        payload = {"fids": fids}
        response = self._send_request("POST", url, json=payload, params=params)
        
        # 获取新的Cookie
        set_cookie = response.cookies.get_dict()
        cookie_str = "; ".join([f"{key}={value}" for key, value in set_cookie.items()])
        
        return response.json(), cookie_str
    
    # ========== 分享与转存 ==========
    
    def get_stoken(self, pwd_id, passcode=""):
        """获取分享令牌"""
        url = f"{self.base_url}/1/clouddrive/share/sharepage/token"
        params = {"pr": "ucpro", "fr": "pc"}
        payload = {"pwd_id": pwd_id, "passcode": passcode}
        response = self._send_request("POST", url, json=payload, params=params).json()
        return response
    
    def check_share_link(self, share_url):
        """
        检查分享链接有效性
        
        Args:
            share_url: 分享链接
        
        Returns:
            dict: 包含is_valid和相关信息的字典
        """
        try:
            # 解析分享链接
            pwd_id, passcode, folder_id = self.parse_share_url(share_url)
            
            if not pwd_id:
                return {
                    'is_valid': False,
                    'message': '无效的分享链接格式'
                }
            
            # 获取分享令牌
            token_result = self.get_stoken(pwd_id, passcode)
            
            if token_result.get('code') != 0:
                return {
                    'is_valid': False,
                    'message': token_result.get('message', '链接已失效或不存在')
                }
            
            stoken = token_result.get('data', {}).get('stoken')
            if not stoken:
                return {
                    'is_valid': False,
                    'message': '无法获取分享令牌'
                }
            
            # 获取分享详情
            detail_result = self.get_share_detail(pwd_id, stoken)
            
            if detail_result.get('code') != 0:
                return {
                    'is_valid': False,
                    'message': detail_result.get('message', '无法获取分享详情')
                }
            
            # 链接有效，返回文件信息
            data = detail_result.get('data', {})
            file_list = data.get('list', [])
            
            return {
                'is_valid': True,
                'message': '链接有效',
                'file_count': len(file_list),
                'share_title': data.get('title', ''),
                'share_author': data.get('nickname', '')
            }
            
        except Exception as e:
            logger.error(f"检查分享链接失败: {e}")
            return {
                'is_valid': False,
                'message': f'检测失败: {str(e)}'
            }
    
    def get_share_detail(self, pwd_id, stoken, pdir_fid="0"):
        """获取分享详情"""
        list_merge = []
        page = 1
        
        while True:
            url = f"{self.base_url}/1/clouddrive/share/sharepage/detail"
            params = {
                "pr": "ucpro",
                "fr": "pc",
                "pwd_id": pwd_id,
                "stoken": stoken,
                "pdir_fid": pdir_fid,
                "force": "0",
                "_page": page,
                "_size": "50",
                "_fetch_banner": "0",
                "_fetch_share": "0",
                "_fetch_total": "1",
                "_sort": "file_type:asc,updated_at:desc",
                "ver": "2",
            }
            response = self._send_request("GET", url, params=params).json()
            
            if response["code"] != 0:
                return response
            
            if response["data"]["list"]:
                list_merge.extend(response["data"]["list"])
                page += 1
            else:
                break
            
            if len(list_merge) >= response["metadata"]["_total"]:
                break
        
        response["data"]["list"] = list_merge
        return response
    
    def save_share_file(self, fid_list, fid_token_list, to_pdir_fid, pwd_id, stoken):
        """转存分享文件"""
        url = f"{self.base_url}/1/clouddrive/share/sharepage/save"
        params = {
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
            "app": "clouddrive",
            "__dt": int(random.uniform(1, 5) * 60 * 1000),
            "__t": datetime.now().timestamp(),
        }
        payload = {
            "fid_list": fid_list,
            "fid_token_list": fid_token_list,
            "to_pdir_fid": to_pdir_fid,
            "pwd_id": pwd_id,
            "stoken": stoken,
            "pdir_fid": "0",
            "scene": "link",
        }
        response = self._send_request("POST", url, json=payload, params=params).json()
        return response
    
    def save_share(self, share_url, target_folder_id='0', password=''):
        """
        转存分享文件（完整流程）
        
        Args:
            share_url: 分享链接
            target_folder_id: 目标文件夹ID
            password: 分享密码
        
        Returns:
            dict: 转存结果
        """
        try:
            # 1. 解析分享链接
            pwd_id, passcode, folder_id = self.parse_share_url(share_url)
            if password:
                passcode = password
            
            if not pwd_id:
                return {
                    'success': False,
                    'message': '无效的分享链接格式'
                }
            
            logger.info(f"开始转存夸克分享: pwd_id={pwd_id}")
            
            # 2. 获取分享令牌
            token_result = self.get_stoken(pwd_id, passcode)
            if token_result.get('code') != 0:
                return {
                    'success': False,
                    'message': token_result.get('message', '获取分享令牌失败')
                }
            
            stoken = token_result.get('data', {}).get('stoken')
            if not stoken:
                return {
                    'success': False,
                    'message': '无法获取分享令牌'
                }
            
            # 3. 获取分享详情
            detail_result = self.get_share_detail(pwd_id, stoken, folder_id or '0')
            if detail_result.get('code') != 0:
                return {
                    'success': False,
                    'message': detail_result.get('message', '获取分享详情失败')
                }
            
            file_list = detail_result.get('data', {}).get('list', [])
            if not file_list:
                return {
                    'success': False,
                    'message': '分享链接中没有文件'
                }
            
            # 4. 构造转存参数
            fid_list = [f['fid'] for f in file_list]
            fid_token_list = [f['share_fid_token'] for f in file_list]
            
            # 5. 执行转存
            save_result = self.save_share_file(
                fid_list, fid_token_list, target_folder_id, pwd_id, stoken
            )
            
            if save_result.get('code') == 0:
                # 如果是异步任务，查询任务状态
                task_id = save_result.get('data', {}).get('task_id')
                if task_id:
                    logger.info(f"夸克转存是异步任务，task_id: {task_id}")
                    task_result = self.query_task(task_id)
                    
                    if task_result.get('status') == 200:
                        return {
                            'success': True,
                            'message': '转存成功',
                            'task_id': task_id
                        }
                    else:
                        return {
                            'success': False,
                            'message': '转存任务失败'
                        }
                else:
                    return {
                        'success': True,
                        'message': '转存成功'
                    }
            else:
                return {
                    'success': False,
                    'message': save_result.get('message', '转存失败')
                }
                
        except Exception as e:
            logger.error(f"夸克转存失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'转存失败: {str(e)}'
            }
    
    def get_share_url(self, share_id):
        """
        通过share_id获取最终的分享链接
        
        Args:
            share_id: 分享ID
        
        Returns:
            dict: 包含分享链接等信息
        """
        url = f"{self.base_url}/1/clouddrive/share/password"
        params = {"pr": "ucpro", "fr": "pc", "uc_param_str": ""}
        payload = {"share_id": share_id}
        
        try:
            response = self._send_request("POST", url, json=payload, params=params).json()
            logger.info(f"获取分享链接响应: {response}")
            return response
        except Exception as e:
            logger.error(f"获取分享链接失败: {e}", exc_info=True)
            return {
                'code': -1,
                'message': f'获取分享链接失败: {str(e)}'
            }
    
    def create_share(self, fid_list, expire_days=7, need_password=False, password=None):
        """
        创建分享链接
        
        Args:
            fid_list: 文件ID列表
            expire_days: 有效期天数，0表示永久
            need_password: 是否需要提取码
            password: 提取码，为空则自动生成
        
        Returns:
            dict: 包含分享链接、提取码、过期时间等信息
        """
        url = f"{self.base_url}/1/clouddrive/share"
        params = {"pr": "ucpro", "fr": "pc"}
        
        # 计算过期时间（毫秒级时间戳）
        if expire_days == 0:
            # 永久有效，设置为很久以后的时间
            expired_at = int((datetime.now().timestamp() + 365 * 24 * 3600 * 10) * 1000)
        else:
            expired_at = int((datetime.now().timestamp() + expire_days * 24 * 3600) * 1000)
        
        # 构建请求数据
        payload = {
            "fid_list": fid_list,
            "title": "",
            "url_type": 1,
            "expired_type": 4 if expire_days == 0 else 1,
            "expired_at": expired_at,
        }
        
        # 如果需要密码
        if need_password:
            if password:
                payload["passcode"] = password
            else:
                # 自动生成4位数字密码
                payload["passcode"] = ''.join([str(random.randint(0, 9)) for _ in range(4)])
        
        try:
            response = self._send_request("POST", url, json=payload, params=params).json()
            
            logger.info(f"夸克分享API返回: {response}")
            
            if response.get('code') == 0 and response.get('data'):
                data = response['data']
                
                logger.info(f"夸克分享data字段: {data}, 类型: {type(data)}")
                
                # 检查是否是异步任务
                task_id = data.get('task_id')
                if task_id:
                    logger.info(f"分享是异步任务，task_id: {task_id}，开始查询任务结果")
                    
                    # 查询任务结果获取share_id
                    task_result = self.query_task(task_id)
                    logger.info(f"任务查询完整结果: {task_result}")
                    
                    if task_result.get('status') == 200 and task_result.get('data'):
                        task_data = task_result['data']
                        logger.info(f"任务data字段: {task_data}")
                        
                        # 从任务结果中获取share_id
                        share_id = task_data.get('share_id')
                        logger.info(f"从任务结果获取到share_id: {share_id}")
                        
                        if share_id:
                            # 调用/share/password接口获取最终的分享链接
                            share_result = self.get_share_url(share_id)
                            
                            if share_result.get('code') == 0 and share_result.get('data'):
                                share_data = share_result['data']
                                share_url = share_data.get('share_url')
                                
                                logger.info(f"最终获取到的分享链接: {share_url}")
                                
                                return {
                                    'code': 0,
                                    'data': {
                                        'share_id': share_id,
                                        'share_url': share_url,
                                        'shareUrl': share_url,
                                        'password': share_data.get('passcode', payload.get('passcode', '')),
                                        'expire_time': datetime.fromtimestamp(expired_at / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                                        'expireTime': datetime.fromtimestamp(expired_at / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                                    }
                                }
                            else:
                                logger.error(f"获取分享链接失败: {share_result}")
                                return {
                                    'code': -1,
                                    'message': share_result.get('message', '获取分享链接失败'),
                                    'raw_data': share_result
                                }
                        else:
                            logger.error(f"任务完成但无法获取share_id，任务数据: {task_data}")
                            return {
                                'code': -1,
                                'message': '任务完成但无法获取分享ID',
                                'raw_data': task_data
                            }
                    else:
                        logger.error(f"任务查询失败: {task_result}")
                        return {
                            'code': -1,
                            'message': '任务查询失败',
                            'raw_data': task_result
                        }
                
                # 如果不是异步任务，尝试直接获取分享URL
                share_url = data.get('share_url') or data.get('url') or data.get('link')
                
                if share_url:
                    logger.info(f"从API直接获取到分享链接: {share_url}")
                    # 如果需要密码，添加到URL
                    if need_password and payload.get('passcode') and '?' not in share_url:
                        share_url += f"?pwd={payload['passcode']}"
                    
                    # 从URL中提取share_id
                    import re
                    match = re.search(r'/s/([a-zA-Z0-9]+)', share_url)
                    share_id = match.group(1) if match else None
                    
                    return {
                        'code': 0,
                        'data': {
                            'share_id': share_id,
                            'share_url': share_url,
                            'shareUrl': share_url,
                            'password': payload.get('passcode', ''),
                            'expire_time': datetime.fromtimestamp(expired_at / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                            'expireTime': datetime.fromtimestamp(expired_at / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                        }
                    }
                
                # 如果都没有，返回错误
                return {
                    'code': -1,
                    'message': '无法从返回数据中获取分享信息',
                    'raw_data': data
                }
            else:
                logger.error(f"夸克分享API返回错误: {response}")
                return response
                
        except Exception as e:
            logger.error(f"创建分享失败: {e}", exc_info=True)
            return {
                'code': -1,
                'message': f'创建分享失败: {str(e)}'
            }
    
    def query_task(self, task_id):
        """查询任务状态"""
        retry_index = 0
        
        while True:
            url = f"{self.base_url}/1/clouddrive/task"
            params = {
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "task_id": task_id,
                "retry_index": retry_index,
                "__dt": int(random.uniform(1, 5) * 60 * 1000),
                "__t": datetime.now().timestamp(),
            }
            response = self._send_request("GET", url, params=params).json()
            
            logger.info(f"任务查询 task_id={task_id}, retry_index={retry_index}, 响应: {response}")
            
            if response["status"] != 200:
                return response
            
            # status: 0-等待中, 1-进行中, 2-已完成, 3-失败
            task_status = response.get("data", {}).get("status")
            if task_status == 2:
                logger.info(f"任务完成: {response}")
                break
            elif task_status == 3:
                logger.error(f"任务失败: {response}")
                return response
            
            retry_index += 1
            time.sleep(0.5)
            
            # 超时保护
            if retry_index > 120:
                logger.warning(f"任务查询超时: {task_id}")
                break
        
        return response
    
    # ========== 辅助方法 ==========
    
    @staticmethod
    def parse_share_url(url):
        """
        解析分享链接
        
        Returns:
            tuple: (pwd_id, passcode, folder_id)
                - pwd_id: 分享ID
                - passcode: 提取码
                - folder_id: 文件夹ID（如果URL包含#/list/share/xxx格式）
        """
        # 提取pwd_id
        match_id = re.search(r"/s/(\w+)", url)
        pwd_id = match_id.group(1) if match_id else None
        
        # 提取passcode
        match_pwd = re.search(r"pwd=(\w+)", url)
        passcode = match_pwd.group(1) if match_pwd else ""
        
        # 提取文件夹ID（从#/list/share/xxx格式）
        folder_id = None
        match_folder = re.search(r"#/list/share/([a-f0-9]+)", url)
        if match_folder:
            folder_id = match_folder.group(1)
        
        return pwd_id, passcode, folder_id

# -*- coding: utf-8 -*-
"""
天翼189云盘API服务
实现天翼云盘的完整API封装，包括登录认证
"""
import json
import re
import time
import uuid
import base64
import requests
from datetime import datetime
from services.icloud_service import ICloudService
from utils.logger import logger

# RSA加密相关
try:
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_v1_5
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logger.warning("未安装pycryptodome库，无法使用账号密码登录功能。请运行: pip install pycryptodome")


class Cloud189Service(ICloudService):
    """天翼189云盘服务实现"""
    
    # 配置缓存
    _config = None
    
    @classmethod
    def _get_config(cls):
        """获取天翼云盘配置"""
        if cls._config is None:
            try:
                from utils.config_crypto import config_crypto
                cls._config = config_crypto.get_config('cloud189_api', {})
                if not cls._config:
                    raise Exception("cloud189_api配置段不存在")
            except Exception as e:
                logger.error(f"无法读取天翼云盘加密配置: {e}")
                raise Exception(f"天翼云盘配置加载失败: {e}")
        return cls._config
    
    @classmethod
    def _get_api_url(cls, key):
        """获取API地址(不提供默认值)"""
        config = cls._get_config()
        value = config.get(key)
        if not value:
            raise Exception(f"天翼云盘配置缺少必需字段: {key}")
        return value
    
    # base64映射表
    _B64_MAP = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    _BI_RM = list("0123456789abcdefghijklmnopqrstuvwxyz")
    
    @staticmethod
    def _int2char(a):
        """整数转字符"""
        return Cloud189Service._BI_RM[a]
    
    @staticmethod
    def _b64tohex(a):
        """base64转十六进制（天翼云盘特殊格式）"""
        d = ""
        e = 0
        b64map = Cloud189Service._B64_MAP
        int2char = Cloud189Service._int2char
        
        for i in range(len(a)):
            if list(a)[i] != "=":
                v = b64map.index(list(a)[i])
                if 0 == e:
                    e = 1
                    d += int2char(v >> 2)
                    c = 3 & v
                elif 1 == e:
                    e = 2
                    d += int2char(c << 2 | v >> 4)
                    c = 15 & v
                elif 2 == e:
                    e = 3
                    d += int2char(c)
                    d += int2char(v >> 2)
                    c = 3 & v
                else:
                    e = 0
                    d += int2char(c << 2 | v >> 4)
                    d += int2char(15 & v)
        if e == 1:
            d += int2char(c << 2)
        return d
    
    def __init__(self, cookie=None, username=None, password=None, session_key=None, access_token=None):
        """
        初始化189云盘服务
        
        Args:
            cookie: 天翼云盘Cookie（可选）
            username: 用户名/手机号（可选，用于登录）
            password: 密码（可选，用于登录）
            session_key: 会话密钥（可选，登录后获取）
            access_token: 访问令牌（可选，登录后获取）
        """
        self.username = username
        self.password = password
        self.session_key = session_key
        self.access_token = access_token
        
        # 从加密配置读取API地址
        config = self._get_config()
        self.base_url = config.get('base_url')
        user_agent = config.get('user_agent')
        referer = config.get('referer')
        origin = config.get('origin')
        
        # 验证必需配置
        if not all([self.base_url, user_agent, referer, origin]):
            raise Exception("天翼云盘配置不完整，请检查加密配置文件")
        
        self.session = requests.Session()
        
        # 设置基础请求头
        self.session.headers.update({
            'Accept': 'application/json;charset=UTF-8',
            'User-Agent': user_agent,
            'Referer': referer,
            'Origin': origin,
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        })
        
        # 如果提供了cookie，设置cookie
        if cookie:
            self.cookie = cookie.strip()
            self._set_cookies(cookie)
        # 如果提供了账号密码，尝试登录
        elif username and password:
            login_result = self.login(username, password)
            if not login_result.get('success'):
                raise Exception(f"登录失败: {login_result.get('message')}")
            self.cookie = login_result.get('cookies', '')
            self.session_key = login_result.get('session_key', '')
            self.access_token = login_result.get('access_token', '')
        else:
            self.cookie = ''
    
    def _set_cookies(self, cookie_str):
        """设置cookies到session"""
        if cookie_str:
            # 解析cookie字符串
            cookie_dict = {}
            for item in cookie_str.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookie_dict[key.strip()] = value.strip()
            
            # 设置到session（使用.cloud.189.cn域名,与参考项目一致）
            for key, value in cookie_dict.items():
                self.session.cookies.set(key, value, domain='.cloud.189.cn')
            
            logger.info(f"已设置 {len(cookie_dict)} 个Cookie字段")
    
    # ========== 登录认证 ==========
    
    @staticmethod
    def login(username, password, captcha=''):
        """
        使用账号密码登录天翼云盘（基于cloud189-sdk实现）
        
        Args:
            username: 用户名（手机号）
            password: 密码
            captcha: 验证码（如需要）
        
        Returns:
            dict: 登录结果，包含success, cookies, message等字段
        """
        if not HAS_CRYPTO:
            return {
                'success': False,
                'message': '缺少pycryptodome库，无法使用密码登录。请运行: pip install pycryptodome'
            }
        
        try:
            # 从加密配置读取API地址
            try:
                from utils.config_crypto import config_crypto
                cloud189_config = config_crypto.get_config('cloud189_api', {})
            except Exception as e:
                logger.error(f"无法读取天翼云盘加密配置: {e}")
                return {'success': False, 'message': '配置加载失败'}
            
            # 获取配置值(不提供默认值,强制从配置读取)
            app_id = cloud189_config.get('app_id')
            client_type = cloud189_config.get('client_type')
            return_url = cloud189_config.get('return_url')
            account_type = cloud189_config.get('account_type')
            api_url = cloud189_config.get('api_url')
            login_form_url = cloud189_config.get('login_form_url')
            rsa_key_url = cloud189_config.get('rsa_key_url')
            login_url = cloud189_config.get('login_url')
            user_agent = cloud189_config.get('user_agent')
            base_url = cloud189_config.get('base_url')
            referer = cloud189_config.get('referer')
            
            # 验证必需配置
            if not all([app_id, client_type, return_url, account_type, api_url, 
                       login_form_url, rsa_key_url, login_url, user_agent, base_url, referer]):
                logger.error("天翼云盘配置不完整")
                return {'success': False, 'message': '配置不完整'}
            
            session = requests.Session()
            session.headers.update({
                'User-Agent': user_agent,
                'Referer': base_url,
                'Accept': 'application/json;charset=UTF-8'
            })
            
            # 步骤1: 获取登录表单参数
            logger.info("步骤1: 获取登录表单参数...")
            params = {
                'appId': app_id,
                'clientType': client_type,
                'returnURL': return_url,
                'timeStamp': str(int(time.time() * 1000))
            }
            
            response = session.get(login_form_url, params=params, timeout=10)
            html = response.text
            logger.info(f"  状态码: {response.status_code}, 内容长度: {len(html)}")
            
            # 提取表单参数
            captcha_token_match = re.search(r"'captchaToken'\s+value='([^']+)'", html)
            lt_match = re.search(r'var\s+lt\s*=\s*"([^"]+)"', html)
            param_id_match = re.search(r'var\s+paramId\s*=\s*"([^"]+)"', html)
            req_id_match = re.search(r'var\s+reqId\s*=\s*"([^"]+)"', html)
            
            if not (captcha_token_match and lt_match and param_id_match and req_id_match):
                logger.error("  ✗ 解析登录表单参数失败")
                return {'success': False, 'message': '解析登录表单失败'}
            
            captcha_token = captcha_token_match.group(1)
            lt = lt_match.group(1)
            param_id = param_id_match.group(1)
            req_id = req_id_match.group(1)
            
            logger.info(f"  ✓ captchaToken: {captcha_token[:20]}...")
            logger.info(f"  ✓ lt: {lt[:20]}...")
            logger.info(f"  ✓ paramId: {param_id}")
            logger.info(f"  ✓ reqId: {req_id}")
            
            # 步骤2: 获取RSA公钥
            logger.info("步骤2: 获取RSA公钥...")
            response = session.post(rsa_key_url, timeout=10)
            result = response.json()
            
            logger.info(f"  状态码: {response.status_code}")
            logger.info(f"  返回码: {result.get('result')}")
            
            if result.get('result') != 0:
                logger.error(f"  ✗ 获取RSA公钥失败: {result}")
                return {'success': False, 'message': '获取RSA公钥失败'}
            
            public_key = result.get('data', {}).get('pubKey', '')
            pre_key = result.get('data', {}).get('pre', '')
            
            if not public_key:
                return {'success': False, 'message': 'RSA公钥为空'}
            
            logger.info(f"  ✓ 公钥长度: {len(public_key)}")
            logger.info(f"  ✓ pre前缀: {pre_key}")
            
            # 步骤3: 加密用户名和密码
            logger.info("步骤3: 加密用户名和密码...")
            try:
                key_data = f'-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----'
                rsa_key = RSA.import_key(key_data)
                cipher = PKCS1_v1_5.new(rsa_key)
                
                # 加密用户名 - RSA加密 → base64 → b64tohex
                username_encrypted = cipher.encrypt(username.encode('utf-8'))
                username_b64 = base64.b64encode(username_encrypted).decode('utf-8')
                username_hex = Cloud189Service._b64tohex(username_b64)  # base64转十六进制
                rsa_username = f'{pre_key}{username_hex}'
                
                # 加密密码 - RSA加密 → base64 → b64tohex
                password_encrypted = cipher.encrypt(password.encode('utf-8'))
                password_b64 = base64.b64encode(password_encrypted).decode('utf-8')
                password_hex = Cloud189Service._b64tohex(password_b64)  # base64转十六进制
                rsa_password = f'{pre_key}{password_hex}'
                
                logger.info(f"  ✓ 用户名加密成功，长度: {len(rsa_username)}")
                logger.info(f"  ✓ 密码加密成功，长度: {len(rsa_password)}")
                
            except Exception as e:
                logger.error(f"  ✗ 加密失败: {e}")
                return {'success': False, 'message': f'加密失败: {str(e)}'}
            
            # 步骤4: 提交登录请求
            logger.info("步骤4: 提交登录请求...")
            
            login_headers = {
                'User-Agent': user_agent,
                'Referer': 'https://open.e.189.cn',
                'Accept': 'application/json;charset=UTF-8',
                'lt': lt,
                'REQID': req_id
            }
            
            login_data = {
                'version': 'v2.0',
                'appKey': app_id,
                'pageKey': 'normal',
                'apToken': '',
                'accountType': account_type,
                'userName': rsa_username,
                'epd': rsa_password,  # 关键修复: 使用epd而不是password
                'captchaType': '',
                'validateCode': captcha,
                'smsValidateCode': '',
                'captchaToken': captcha_token,
                'returnUrl': return_url,
                'mailSuffix': '@189.cn',
                'dynamicCheck': 'FALSE',
                'clientType': '1',
                'cb_SaveName': '3',
                'isOauth2': 'false',
                'state': '',
                'paramId': param_id
            }
            
            response = session.post(login_url, headers=login_headers, data=login_data, timeout=10)
            result = response.json()
            
            logger.info(f"  状态码: {response.status_code}")
            logger.info(f"  返回码: {result.get('result')}")
            logger.info(f"  返回消息: {result.get('msg')}")
            
            # 步骤5: 处理登录结果
            if result.get('result') == 0:
                # 登录成功
                to_url = result.get('toUrl', '')
                
                if not to_url:
                    return {'success': False, 'message': '登录成功但未获取到重定向URL'}
                
                logger.info(f"  ✓ 登录成功！")
                logger.info(f"  重定向URL: {to_url[:100]}...")
                
                # 步骤6: 调用getSessionForPC API获取sessionKey和accessToken
                logger.info("步骤6: 调用getSessionForPC获取会话凭证...")
                session_url = f'{api_url}/getSessionForPC.action'
                session_params = {
                    'appId': app_id,
                    'clientType': 'TELEPC',
                    'version': '6.2',
                    'channelId': 'web_cloud.189.cn',
                    'redirectURL': to_url
                }
                
                response = session.post(session_url, params=session_params, timeout=10)
                logger.info(f"  状态码: {response.status_code}")
                
                if response.status_code != 200:
                    logger.error(f"  ✗ 获取会话失败: {response.text}")
                    return {'success': False, 'message': '获取会话失败'}
                
                session_result = response.json()
                session_key = session_result.get('sessionKey', '')
                access_token = session_result.get('accessToken', '')
                
                if not session_key:
                    logger.error(f"  ✗ 未获取到sessionKey: {session_result}")
                    return {'success': False, 'message': '未获取到sessionKey'}
                
                logger.info(f"  ✓ sessionKey: {session_key[:20]}...")
                logger.info(f"  ✓ accessToken: {access_token[:20] if access_token else 'N/A'}...")
                
                # 步骤7: 使用sessionKey访问cloud.189.cn建立会话并获取Cookie
                logger.info("步骤7: 使用sessionKey建立cloud.189.cn会话...")
                
                # 方法1: 访问主页
                main_url = f'https://cloud.189.cn/web/main/'
                response = session.get(main_url, params={'sessionKey': session_key}, timeout=10, allow_redirects=True)
                logger.info(f"  主页状态码: {response.status_code}")
                
                # 方法2: 访问API接口
                api_url_test = f'https://cloud.189.cn/api/portal/getUserSizeInfo.action'
                response2 = session.get(api_url_test, params={'sessionKey': session_key}, timeout=10)
                logger.info(f"  API状态码: {response2.status_code}")
                
                # 提取所有Cookie（现在应该包含.cloud.189.cn域名的Cookie）
                cookies_dict = {}
                cloud_cookies = {}  # 专门收集.cloud.189.cn域名的Cookie
                
                logger.info(f"  当前所有Cookie:")
                for cookie in session.cookies:
                    cookies_dict[cookie.name] = cookie.value
                    logger.info(f"    {cookie.name}: domain={cookie.domain}, path={cookie.path}")
                    # 只保存cloud.189.cn域名的Cookie
                    if '.cloud.189.cn' in cookie.domain or 'cloud.189.cn' == cookie.domain:
                        cloud_cookies[cookie.name] = cookie.value
                
                # 优先使用cloud.189.cn域名的Cookie
                if cloud_cookies:
                    cookie_str = '; '.join([f'{k}={v}' for k, v in cloud_cookies.items()])
                    logger.info(f"  ✓ 获取到 {len(cloud_cookies)} 个cloud.189.cn域名的Cookie")
                else:
                    # 如果没有cloud.189.cn的Cookie,使用所有Cookie
                    cookie_str = '; '.join([f'{k}={v}' for k, v in cookies_dict.items()])
                    logger.warning(f"  ⚠ 未获取到cloud.189.cn域名的Cookie,使用所有Cookie ({len(cookies_dict)}个)")
                
                logger.info(f"  Cookie字段: {list(cloud_cookies.keys() if cloud_cookies else cookies_dict.keys())}")
                
                return {
                    'success': True,
                    'cookies': cookie_str,
                    'session_key': session_key,
                    'access_token': access_token,
                    'message': '登录成功'
                }
            
            elif result.get('result') == -2:
                # 需要验证码
                logger.info("  ✗ 需要验证码")
                return {
                    'success': False,
                    'code': 'NEED_CAPTCHA',
                    'message': '需要验证码',
                    'captcha_url': result.get('captchaUrl', '')
                }
            
            else:
                # 登录失败
                logger.error(f"  ✗ 登录失败: {result.get('msg')}")
                return {
                    'success': False,
                    'message': result.get('msg', '登录失败')
                }
                
        except requests.exceptions.Timeout:
            logger.error("✗ 请求超时")
            return {'success': False, 'message': '请求超时'}
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ 网络请求失败: {e}")
            return {'success': False, 'message': f'网络请求失败: {str(e)}'}
        except Exception as e:
            logger.error(f"✗ 登录异常: {e}", exc_info=True)
            return {'success': False, 'message': f'登录异常: {str(e)}'}
    
    def _auto_refresh_cookie(self):
        """
        自动刷新Cookie（当检测到Cookie过期时）
        
        Returns:
            bool: 是否刷新成功
        """
        # 只有在提供了用户名和密码时才能自动刷新
        if not self.username or not self.password:
            logger.warning("无法自动刷新Cookie：未提供用户名或密码")
            return False
        
        try:
            logger.info(f"检测到Cookie过期，尝试自动重新登录: username={self.username[:3]}***")
            
            # 调用登录方法
            login_result = self.login(self.username, self.password)
            
            if not login_result.get('success'):
                logger.error(f"自动重新登录失败: {login_result.get('message')}")
                return False
            
            # 更新实例的认证信息
            new_cookie = login_result.get('cookies', '')
            new_session_key = login_result.get('session_key', '')
            new_access_token = login_result.get('access_token', '')
            
            if not new_cookie:
                logger.error("自动重新登录成功但未获取到Cookie")
                return False
            
            # 更新实例属性
            self.cookie = new_cookie
            self.session_key = new_session_key
            self.access_token = new_access_token
            
            # 重新设置Cookie到session
            self._set_cookies(new_cookie)
            
            logger.info("Cookie自动刷新成功")
            
            # 尝试更新数据库中的Cookie（如果可以找到对应的账号）
            try:
                from models.account import Account
                from utils.crypto import CryptoUtil
                from database import get_db
                
                # 查找使用该用户名的账号
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id FROM quark_accounts 
                        WHERE username = ? AND cloud_type = 'cloud189'
                    """, (self.username,))
                    account = cursor.fetchone()
                    
                    if account:
                        account_id = account['id']
                        # 加密新Cookie
                        encrypted_cookie = CryptoUtil.encrypt(new_cookie)
                        
                        # 更新数据库
                        cursor.execute("""
                            UPDATE quark_accounts 
                            SET cookie = ?, updated_at = datetime('now')
                            WHERE id = ?
                        """, (encrypted_cookie, account_id))
                        conn.commit()
                        
                        logger.info(f"已更新数据库中的Cookie: account_id={account_id}")
                    else:
                        logger.warning(f"未找到用户名为 {self.username} 的天翼账号，无法更新数据库")
                        
            except Exception as db_err:
                logger.warning(f"更新数据库Cookie失败（不影响当前会话）: {db_err}")
            
            return True
            
        except Exception as e:
            logger.error(f"自动刷新Cookie失败: {e}", exc_info=True)
            return False
    
    def _send_request(self, method, url, **kwargs):
        """
        发送HTTP请求 (自动添加sessionKey参数，支持Cookie自动更新)
        
        Args:
            method: 请求方法 (GET/POST)
            url: 请求URL
            **kwargs: 其他请求参数
        
        Returns:
            Response对象
        """
        try:
            # 确保URL是完整的
            if not url.startswith('http'):
                url = self.base_url + url
            
            # 如果有sessionKey,自动添加到URL参数中 (参考cloud189-sdk实现)
            if self.session_key and 'cloud.189.cn' in url:
                # 解析URL,添加sessionKey参数
                from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                
                # 添加sessionKey参数
                params['sessionKey'] = [self.session_key]
                
                # 重新构建URL
                new_query = urlencode(params, doseq=True)
                url = urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment
                ))
                
                logger.debug(f"已添加sessionKey到URL: {url[:100]}...")
            
            # 合并headers（如果kwargs中有headers，与session的headers合并）
            if 'headers' in kwargs:
                headers = self.session.headers.copy()
                headers.update(kwargs['headers'])
                kwargs['headers'] = headers
            
            response = self.session.request(method, url, timeout=30, **kwargs)
            
            logger.debug(f"189 API请求: {method} {url}, 状态码: {response.status_code}")
            
            # 检测Cookie过期（401未授权 或 400错误且返回特定错误码）
            if response.status_code in [401, 400]:
                try:
                    result = response.json()
                    # 天翼云盘的认证失败错误码
                    if result.get('res_code') in [-2, -3] or result.get('errorCode') in ['InvalidSessionKey', 'SessionExpired']:
                        logger.warning(f"检测到Cookie可能已过期: status={response.status_code}, res_code={result.get('res_code')}, errorCode={result.get('errorCode')}")
                        
                        # 尝试自动刷新Cookie
                        if self._auto_refresh_cookie():
                            logger.info("Cookie已自动刷新，重试请求...")
                            # 重新发起请求（递归调用，但只重试一次）
                            # 为了避免无限递归，添加一个标记
                            if not kwargs.get('_retry_after_refresh'):
                                kwargs['_retry_after_refresh'] = True
                                return self._send_request(method, url, **kwargs)
                        else:
                            logger.error("Cookie自动刷新失败，请手动更新账号")
                except:
                    pass  # 如果不是JSON响应，忽略
            
            return response
            
        except Exception as e:
            logger.error(f"189 API请求失败: {e}")
            raise

    
    # ========== 账号相关 ==========
    
    def get_account_info(self):
        """
        获取账号信息
        
        Returns:
            dict: 账号信息，包含nickname, total_capacity, use_capacity等
        """
        try:
            # 获取用户容量信息
            url = "/api/portal/getUserSizeInfo.action"
            response = self._send_request("GET", url)
            
            logger.info(f"189账号容量响应: status={response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"获取189账号信息失败，状态码: {response.status_code}")
                return None
            
            result = response.json()
            logger.info(f"189账号信息结果: {result}")
            
            if result.get('res_code') == 0:
                # 从容量信息中提取
                cloud_info = result.get('cloudCapacityInfo', {})
                family_info = result.get('familyCapacityInfo', {})
                account = result.get('account', '')
                
                # 个人空间容量
                personal_total = cloud_info.get('totalSize', 0)
                personal_used = cloud_info.get('usedSize', 0)
                
                # 家庭空间容量
                family_total = family_info.get('totalSize', 0)
                family_used = family_info.get('usedSize', 0)
                
                # 总容量（个人+家庭）
                total_capacity = personal_total + family_total
                use_capacity = personal_used + family_used
                
                # 从account字段提取昵称（手机号脱敏显示）
                nickname = account if account else '天翼用户'
                
                return {
                    'nickname': nickname,
                    'total_capacity': total_capacity,
                    'use_capacity': use_capacity,
                    'is_vip': 1 if result.get('superVip') else 0,
                    'member_type': '天翼云盘',
                    # 额外信息
                    'personal_total': personal_total,
                    'personal_used': personal_used,
                    'family_total': family_total,
                    'family_used': family_used,
                }
            else:
                logger.error(f"获取189账号信息返回错误: {result}")
                return None
                
        except Exception as e:
            logger.error(f"获取189账号信息失败: {e}")
            return None

    
    # ========== 文件管理 ==========
    
    def get_file_list(self, folder_id='-11', page=1, size=50):
        """
        获取文件列表
        
        Args:
            folder_id: 文件夹ID（根目录为-11）
            page: 页码
            size: 每页数量
        
        Returns:
            dict: 文件列表响应（格式与QuarkService保持一致）
        """
        try:
            url = "/api/open/file/listFiles.action"
            params = {
                'folderId': folder_id,
                'mediaType': 0,
                'orderBy': 'lastOpTime',
                'descending': 'true',
                'pageNum': page,
                'pageSize': size
            }
            
            logger.info(f"189获取文件列表请求: folder_id={folder_id}, page={page}, size={size}")
            
            response = self._send_request("GET", url, params=params)
            
            logger.info(f"189文件列表响应状态码: {response.status_code}")
            
            # 检查响应状态码
            if response.status_code != 200:
                logger.error(f"189文件列表请求失败，状态码: {response.status_code}")
                return {
                    'code': -1,
                    'message': f'请求失败，状态码: {response.status_code}'
                }
            
            # 检查响应内容
            if not response.text or not response.text.strip():
                logger.error("189文件列表响应内容为空")
                return {
                    'code': -1,
                    'message': '响应内容为空'
                }
            
            try:
                result = response.json()
            except Exception as json_err:
                logger.error(f"189文件列表解析JSON失败: {json_err}, 响应内容: {response.text[:500]}")
                return {
                    'code': -1,
                    'message': f'解析响应失败: {str(json_err)}'
                }
            
            logger.debug(f"189文件列表响应: {result}")
            
            if result.get('res_code') == 0:
                # 转换为统一格式
                file_list_ao = result.get('fileListAO', {})
                folder_list = file_list_ao.get('folderList', [])  # 文件夹列表
                file_list = file_list_ao.get('fileList', [])      # 文件列表
                
                items = []
                
                # 先添加文件夹
                for folder in folder_list:
                    # 将ID转换为字符串，避免JavaScript大数字精度丢失
                    items.append({
                        'id': str(folder.get('id')),
                        'name': folder.get('name'),
                        'isFolder': True,
                        'size': 0,
                        'modifiedTime': folder.get('lastOpTime'),
                        'mimeType': '',
                    })
                
                # 再添加文件
                for file in file_list:
                    # 将ID转换为字符串，避免JavaScript大数字精度丢失
                    items.append({
                        'id': str(file.get('id')),
                        'name': file.get('name'),
                        'isFolder': False,
                        'size': file.get('size', 0),
                        'modifiedTime': file.get('lastOpTime'),
                        'mimeType': file.get('mediaType', ''),
                    })
                
                total_count = file_list_ao.get('count', len(items))
                
                logger.info(f"189文件列表获取成功: 文件夹{len(folder_list)}个, 文件{len(file_list)}个")
                
                return {
                    'code': 0,
                    'data': {
                        'list': items,
                        'metadata': {
                            '_total': total_count
                        }
                    }
                }
            else:
                logger.error(f"189文件列表API返回错误: res_code={result.get('res_code')}, res_message={result.get('res_message')}")
                return {
                    'code': -1,
                    'message': result.get('res_message', '获取文件列表失败')
                }
                
        except Exception as e:
            logger.error(f"获取189文件列表失败: {e}")
            return {
                'code': -1,
                'message': f'获取文件列表失败: {str(e)}'
            }
    
    def list_files(self, folder_id='-11', page=1, size=200):
        """
        获取文件列表（统一接口）
        
        Args:
            folder_id: 文件夹ID，默认为根目录（-11）
            page: 页码
            size: 每页数量
        
        Returns:
            list: 文件列表，失败返回 None
        """
        try:
            response = self.get_file_list(folder_id=folder_id, page=page, size=size)
            if response.get('code') == 0:
                return response.get('data', {}).get('list', [])
            else:
                logger.error(f"获取文件列表失败: {response.get('message', '未知错误')}")
                return None
        except Exception as e:
            logger.error(f"获取文件列表异常: {e}")
            return None

    
    def get_or_create_folder_by_path(self, path):
        """
        根据路径获取或创建文件夹，返回文件夹ID
        
        Args:
            path: 目标路径，如 "/测试" 或 "/测试/子目录"
        
        Returns:
            str: 文件夹ID，失败返回 '-11'（根目录）
        """
        try:
            # 处理空路径或根目录
            if not path or path == '/' or path.strip() == '':
                return '-11'
            
            # 规范化路径：去除首尾空格和多余斜杠
            path = path.strip().strip('/')
            if not path:
                return '-11'
            
            # 分割路径
            path_parts = [p for p in path.split('/') if p]
            if not path_parts:
                return '-11'
            
            logger.info(f"189云盘路径解析: path={path}, parts={path_parts}")
            
            current_folder_id = '-11'  # 从根目录开始
            
            for folder_name in path_parts:
                # 在当前目录下查找目标文件夹
                found_folder_id = self._find_folder_in_parent(folder_name, current_folder_id)
                
                if found_folder_id:
                    # 找到了，继续下一级
                    current_folder_id = found_folder_id
                    logger.info(f"189云盘找到文件夹: {folder_name} -> {current_folder_id}")
                else:
                    # 没找到，创建文件夹
                    create_result = self.mkdir(folder_name, current_folder_id)
                    if create_result.get('code') == 0:
                        current_folder_id = str(create_result.get('data'))
                        logger.info(f"189云盘创建文件夹: {folder_name} -> {current_folder_id}")
                    else:
                        logger.error(f"189云盘创建文件夹失败: {folder_name}, error={create_result.get('message')}")
                        return '-11'
            
            return current_folder_id
            
        except Exception as e:
            logger.error(f"189云盘路径处理失败: {e}", exc_info=True)
            return '-11'
    
    def get_folder_id_by_path(self, path):
        """
        根据路径获取文件夹ID（不创建，仅查找）
        
        Args:
            path: 目标路径，如 "/测试" 或 "/测试/子目录"
        
        Returns:
            str: 文件夹ID，未找到返回 None
        """
        try:
            # 处理空路径或根目录
            if not path or path == '/' or path.strip() == '':
                return '-11'
            
            # 规范化路径：去除首尾空格和多余斜杠
            path = path.strip().strip('/')
            if not path:
                return '-11'
            
            # 分割路径
            path_parts = [p for p in path.split('/') if p]
            if not path_parts:
                return '-11'
            
            logger.debug(f"189云盘查找路径: path={path}, parts={path_parts}")
            
            current_folder_id = '-11'  # 从根目录开始
            
            for folder_name in path_parts:
                # 在当前目录下查找目标文件夹
                found_folder_id = self._find_folder_in_parent(folder_name, current_folder_id)
                
                if found_folder_id:
                    current_folder_id = found_folder_id
                    logger.debug(f"189云盘找到文件夹: {folder_name} -> {current_folder_id}")
                else:
                    # 没找到，返回 None
                    logger.warning(f"189云盘未找到文件夹: {folder_name} in {current_folder_id}")
                    return None
            
            return current_folder_id
            
        except Exception as e:
            logger.error(f"189云盘路径查找失败: {e}", exc_info=True)
            return None
    
    def _find_folder_in_parent(self, folder_name, parent_id):
        """
        在父目录下查找指定名称的文件夹
        
        Args:
            folder_name: 文件夹名称
            parent_id: 父目录ID
        
        Returns:
            str: 文件夹ID，未找到返回 None
        """
        try:
            result = self.get_file_list(parent_id, page=1, size=1000)
            if result.get('code') != 0:
                return None
            
            items = result.get('data', {}).get('list', [])
            for item in items:
                if item.get('isFolder') and item.get('name') == folder_name:
                    return str(item.get('id'))
            
            return None
            
        except Exception as e:
            logger.error(f"189云盘查找文件夹失败: {e}")
            return None
    
    def mkdir(self, folder_name, parent_id='-11'):
        """
        创建文件夹
        
        Args:
            folder_name: 文件夹名称
            parent_id: 父文件夹ID（根目录为-11）
        
        Returns:
            dict: 创建结果
        """
        try:
            logger.info(f"189创建文件夹: name={folder_name}, parent_id={parent_id}")
            
            url = "/api/open/file/createFolder.action"
            # 使用POST方法和表单数据
            data = {
                'parentFolderId': parent_id,
                'folderName': folder_name
            }
            
            response = self._send_request("POST", url, data=data)
            result = response.json()
            
            logger.info(f"189创建文件夹响应: {result}")
            
            if result.get('res_code') == 0:
                return {
                    'code': 0,
                    'message': '创建成功',
                    'data': result.get('id')
                }
            else:
                return {
                    'code': -1,
                    'message': result.get('res_message', '创建文件夹失败')
                }
                
        except Exception as e:
            logger.error(f"创建189文件夹失败: {e}", exc_info=True)
            return {
                'code': -1,
                'message': f'创建文件夹失败: {str(e)}'
            }
    
    def delete(self, file_ids, file_infos=None):
        """
        删除文件/文件夹
        
        Args:
            file_ids: 文件ID列表
            file_infos: 文件信息列表（可选），包含name和isFolder字段
        
        Returns:
            dict: 删除结果
        """
        try:
            # 确保file_ids是列表
            if not isinstance(file_ids, list):
                file_ids = [file_ids]
            
            logger.info(f"189删除文件: file_ids={file_ids}, file_infos={file_infos}")
            
            # 如果没有提供文件信息，先查询获取
            if not file_infos:
                file_infos = self._get_file_infos(file_ids)
            
            # 使用批量任务接口
            url = "/api/open/batch/createBatchTask.action"
            
            # 构造任务信息
            task_infos = []
            for i, fid in enumerate(file_ids):
                # 如果提供了文件信息，使用它；否则使用默认值
                if file_infos and i < len(file_infos):
                    info = file_infos[i]
                    task_infos.append({
                        'fileId': str(fid),
                        'fileName': info.get('name', ''),
                        'isFolder': 1 if info.get('isFolder', False) else 0
                    })
                else:
                    task_infos.append({
                        'fileId': str(fid),
                        'fileName': '',
                        'isFolder': 0
                    })
            
            # 使用表单数据提交
            data = {
                'type': 'DELETE',
                'targetFolderId': '',  # 删除操作不需要目标文件夹
                'taskInfos': json.dumps(task_infos)
            }
            
            logger.info(f"189删除请求数据: {data}")
            
            response = self._send_request("POST", url, data=data)
            
            logger.info(f"189删除响应状态码: {response.status_code}")
            logger.info(f"189删除响应内容: {response.text[:500] if response.text else '空响应'}")
            
            # 检查响应状态码
            if response.status_code != 200:
                return {
                    'code': -1,
                    'message': f'删除请求失败，状态码: {response.status_code}'
                }
            
            # 检查响应内容是否为空
            if not response.text or not response.text.strip():
                return {
                    'code': -1,
                    'message': '删除请求返回空响应'
                }
            
            try:
                result = response.json()
            except Exception as json_err:
                logger.error(f"解析删除响应JSON失败: {json_err}, 响应内容: {response.text[:200]}")
                return {
                    'code': -1,
                    'message': f'解析响应失败: {str(json_err)}'
                }
            
            logger.info(f"189删除响应: {result}")
            
            if result.get('res_code') == 0:
                task_id = result.get('taskId')
                
                # 等待任务完成
                for _ in range(30):
                    time.sleep(0.5)
                    status = self.check_task_status(task_id, 'DELETE')
                    if status.get('taskStatus') == 4:  # 完成
                        return {
                            'code': 0,
                            'message': '删除成功'
                        }
                    elif status.get('taskStatus') == 3:  # 失败
                        return {
                            'code': -1,
                            'message': '删除任务失败'
                        }
                
                return {
                    'code': 0,
                    'message': '删除任务已提交'
                }
            else:
                return {
                    'code': -1,
                    'message': result.get('res_message', '删除失败')
                }
                
        except Exception as e:
            logger.error(f"删除189文件失败: {e}", exc_info=True)
            return {
                'code': -1,
                'message': f'删除失败: {str(e)}'
            }
    
    def _get_file_infos(self, file_ids):
        """
        根据文件ID列表获取文件信息
        
        Args:
            file_ids: 文件ID列表
        
        Returns:
            list: 文件信息列表
        """
        try:
            file_infos = []
            for fid in file_ids:
                # 尝试获取文件信息
                url = "/api/open/file/getFileInfo.action"
                params = {'fileId': str(fid)}
                
                response = self._send_request("GET", url, params=params)
                result = response.json()
                
                if result.get('res_code') == 0:
                    file_infos.append({
                        'name': result.get('name', ''),
                        'isFolder': result.get('isFolder', False)
                    })
                else:
                    # 如果获取失败，尝试作为文件夹获取
                    url = "/api/open/file/getFolderInfo.action"
                    params = {'folderId': str(fid)}
                    
                    response = self._send_request("GET", url, params=params)
                    result = response.json()
                    
                    if result.get('res_code') == 0:
                        file_infos.append({
                            'name': result.get('name', ''),
                            'isFolder': True
                        })
                    else:
                        # 都失败了，使用默认值
                        file_infos.append({
                            'name': '',
                            'isFolder': False
                        })
            
            return file_infos
            
        except Exception as e:
            logger.error(f"获取文件信息失败: {e}")
            return []
    
    def rename(self, file_id, new_name):
        """
        重命名文件/文件夹
        
        Args:
            file_id: 文件ID
            new_name: 新名称
        
        Returns:
            dict: 重命名结果
        """
        try:
            url = "/api/open/file/renameFile.action"
            data = {
                'fileId': file_id,
                'destFileName': new_name
            }
            
            response = self._send_request("POST", url, data=data)
            result = response.json()
            
            if result.get('res_code') == 0:
                return {
                    'code': 0,
                    'message': '重命名成功'
                }
            else:
                return {
                    'code': -1,
                    'message': result.get('res_message', '重命名失败')
                }
                
        except Exception as e:
            logger.error(f"重命名189文件失败: {e}")
            return {
                'code': -1,
                'message': f'重命名失败: {str(e)}'
            }

    
    # ========== 分享与转存 ==========
    
    @staticmethod
    def parse_share_url(url):
        """
        解析分享链接
        
        Args:
            url: 分享链接
        
        Returns:
            tuple: (share_code, access_code)
        
        支持的链接格式:
        - https://cloud.189.cn/web/share?code=xxx
        - https://cloud.189.cn/t/xxx
        - https://h5.cloud.189.cn/share.html#/t/xxx
        - https://cloud.189.cn/web/share/xxx
        """
        share_code = None
        access_code = ''
        
        # 格式1: code=xxx
        match_code = re.search(r'[?&]code=([a-zA-Z0-9]+)', url)
        if match_code:
            share_code = match_code.group(1)
        
        # 格式2: /t/xxx 或 #/t/xxx (h5版本)
        if not share_code:
            match_path = re.search(r'[/#]t/([a-zA-Z0-9]+)', url)
            if match_path:
                share_code = match_path.group(1)
        
        # 格式3: /share/xxx
        if not share_code:
            match_share = re.search(r'/share/([a-zA-Z0-9]+)', url)
            if match_share:
                share_code = match_share.group(1)
        
        # 提取access_code (提取码)
        match_pwd = re.search(r'[?&]pwd=([a-zA-Z0-9]+)', url)
        if match_pwd:
            access_code = match_pwd.group(1)
        
        logger.info(f"解析天翼分享链接: url={url}, share_code={share_code}, access_code={access_code}")
        
        return share_code, access_code
    
    def get_share_info(self, share_code):
        """
        获取分享信息
        
        Args:
            share_code: 分享码
        
        Returns:
            dict: 分享信息
        """
        try:
            url = "/api/open/share/getShareInfoByCodeV2.action"
            params = {'shareCode': share_code}
            
            response = self._send_request("GET", url, params=params)
            result = response.json()
            
            return result
            
        except Exception as e:
            logger.error(f"获取189分享信息失败: {e}")
            return {'res_code': -1, 'res_message': str(e)}
    
    def check_access_code(self, share_code, access_code):
        """
        验证分享访问码
        
        Args:
            share_code: 分享码
            access_code: 访问码
        
        Returns:
            dict: 验证结果
        """
        try:
            url = "/api/open/share/checkAccessCode.action"
            params = {
                'shareCode': share_code,
                'accessCode': access_code,
                'uuid': str(uuid.uuid4())
            }
            
            response = self._send_request("GET", url, params=params)
            result = response.json()
            
            return result
            
        except Exception as e:
            logger.error(f"验证189访问码失败: {e}")
            return {'res_code': -1, 'res_message': str(e)}
    
    def list_share_dir(self, share_id, file_id, share_mode, access_code='', is_folder=True, share_code='', root_file_id=''):
        """
        列出分享目录文件
        
        Args:
            share_id: 分享ID
            file_id: 当前文件夹ID（子目录时使用）
            share_mode: 分享模式
            access_code: 访问码
            is_folder: 是否为文件夹
            share_code: 分享码
            root_file_id: 分享根目录的fileId（从getShareInfo获取）
        
        Returns:
            dict: 文件列表
        """
        try:
            url = "/api/open/share/listShareDir.action"
            params = {
                'shareId': share_id,
                'isFolder': 'true' if is_folder else 'false',
                'shareMode': share_mode,
                'orderBy': 'lastOpTime',
                'descending': 'true',
                'pageNum': 1,
                'pageSize': 1000
            }
            
            # 关键修复：fileId参数必须传入，优先使用file_id，其次使用root_file_id
            if file_id and file_id != '0' and file_id != '':
                params['fileId'] = str(file_id)
            elif root_file_id and root_file_id != '0' and root_file_id != '':
                params['fileId'] = str(root_file_id)
            else:
                # 如果都没有，记录警告但继续尝试
                logger.warning("list_share_dir: 未提供有效的fileId参数")
            
            # 如果有访问码
            if access_code:
                params['accessCode'] = access_code
            
            logger.info(f"列出分享目录请求: {params}")
            
            response = self._send_request("GET", url, params=params)
            result = response.json()
            
            logger.info(f"列出分享目录响应: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"列出189分享目录失败: {e}", exc_info=True)
            return {'res_code': -1, 'res_message': str(e)}

    
    def create_batch_task(self, batch_task_dto):
        """
        创建批量转存任务
        
        Args:
            batch_task_dto: 批量任务参数
        
        Returns:
            dict: 任务ID等信息
        """
        try:
            url = "/api/open/batch/createBatchTask.action"
            
            logger.info(f"创建批量任务请求: {batch_task_dto}")
            
            # 关键修复：设置与网页端完全一致的请求头
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': 'https://cloud.189.cn/web/main/',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = self._send_request("POST", url, data=batch_task_dto, headers=headers)
            
            logger.info(f"创建批量任务响应状态码: {response.status_code}")
            logger.info(f"创建批量任务响应头: {dict(response.headers)}")
            logger.info(f"创建批量任务响应内容: {response.text[:500] if response.text else '空响应'}")
            
            # 检查响应状态码
            if response.status_code != 200:
                return {
                    'res_code': -1,
                    'res_message': f'请求失败，状态码: {response.status_code}'
                }
            
            # 检查响应内容
            if not response.text or not response.text.strip():
                return {
                    'res_code': -1,
                    'res_message': '响应内容为空'
                }
            
            try:
                result = response.json()
                logger.info(f"创建批量任务结果: {result}")
                return result
            except Exception as json_err:
                logger.error(f"解析JSON失败: {json_err}, 响应内容: {response.text[:200]}")
                return {
                    'res_code': -1,
                    'res_message': f'解析响应失败: {str(json_err)}'
                }
            
        except Exception as e:
            logger.error(f"创建189批量任务失败: {e}", exc_info=True)
            return {'res_code': -1, 'res_message': str(e)}
    
    def check_task_status(self, task_id, task_type="SHARE_SAVE"):
        """
        查询转存任务状态
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
        
        Returns:
            dict: 任务状态
        """
        try:
            url = "/api/open/batch/checkBatchTask.action"
            data = {
                'taskId': task_id,
                'type': task_type
            }
            
            response = self._send_request("POST", url, data=data)
            result = response.json()
            
            return result
            
        except Exception as e:
            logger.error(f"查询189任务状态失败: {e}")
            return {'res_code': -1, 'res_message': str(e)}
    
    def get_conflict_task_info(self, task_id, task_type="SHARE_SAVE"):
        """
        获取转存冲突文件信息
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
        
        Returns:
            dict: 冲突文件信息
        """
        try:
            url = "/api/open/batch/getConflictTaskInfo.action"
            data = {
                'taskId': task_id,
                'type': task_type
            }
            
            response = self._send_request("POST", url, data=data)
            result = response.json()
            
            return result
            
        except Exception as e:
            logger.error(f"获取189冲突信息失败: {e}")
            return {'res_code': -1, 'res_message': str(e)}
    
    def manage_batch_task(self, task_id, target_folder_id, task_infos, task_type="SHARE_SAVE"):
        """
        处理转存冲突
        
        Args:
            task_id: 任务ID
            target_folder_id: 目标文件夹ID
            task_infos: 冲突文件处理列表
            task_type: 任务类型
        
        Returns:
            dict: 处理结果
        """
        try:
            url = "/api/open/batch/manageBatchTask.action"
            data = {
                'taskId': task_id,
                'type': task_type,
                'targetFolderId': target_folder_id,
                'taskInfos': task_infos
            }
            
            response = self._send_request("POST", url, json=data)
            result = response.json()
            
            return result
            
        except Exception as e:
            logger.error(f"处理189冲突失败: {e}")
            return {'res_code': -1, 'res_message': str(e)}

    
    def save_share(self, share_url, target_folder_id='-11', password=''):
        """
        转存分享文件（完整流程）
        
        Args:
            share_url: 分享链接
            target_folder_id: 目标文件夹ID
            password: 分享密码
        
        Returns:
            dict: 转存结果
        """
        print(f"[DEBUG] save_share被调用: url={share_url}, target={target_folder_id}")
        logger.info(f"[save_share] 开始执行: url={share_url}, target_folder_id={target_folder_id}")
        try:
            # 1. 解析分享链接
            share_code, access_code = self.parse_share_url(share_url)
            if password:
                access_code = password
            
            if not share_code:
                return {
                    'success': False,
                    'message': '无效的分享链接格式'
                }
            
            logger.info(f"开始转存189分享: share_code={share_code}")
            
            # 2. 获取分享信息
            share_info = self.get_share_info(share_code)
            if share_info.get('res_code') != 0:
                return {
                    'success': False,
                    'message': share_info.get('res_message', '获取分享信息失败')
                }
            
            share_id = share_info.get('shareId')
            share_mode = share_info.get('shareMode')
            root_file_id = str(share_info.get('fileId', ''))  # 分享根目录的fileId
            
            logger.info(f"分享信息: shareId={share_id}, shareMode={share_mode}, rootFileId={root_file_id}")
            
            # 3. 验证访问码（如果需要）
            if access_code:
                check_result = self.check_access_code(share_code, access_code)
                if check_result.get('res_code') != 0:
                    return {
                        'success': False,
                        'message': '访问码错误'
                    }
            
            # 4. 获取分享文件列表
            # 关键修复：使用root_file_id作为fileId参数
            # 注意：file_id和root_file_id都传入root_file_id的值
            file_list_result = self.list_share_dir(
                share_id=share_id,
                file_id=root_file_id,  # 当前目录ID
                share_mode=share_mode,
                access_code=access_code,
                is_folder=True,
                share_code=share_code,
                root_file_id=root_file_id  # 分享根目录ID
            )
            
            if file_list_result.get('res_code') != 0:
                logger.error(f"获取分享文件列表失败: {file_list_result}")
                return {
                    'success': False,
                    'message': f"获取文件列表失败: {file_list_result.get('res_message', '未知错误')}"
                }
            
            # 获取文件和文件夹列表
            file_list_ao = file_list_result.get('fileListAO', {})
            file_list = file_list_ao.get('fileList', [])
            folder_list = file_list_ao.get('folderList', [])
            
            # 合并文件和文件夹
            all_items = []
            for folder in folder_list:
                all_items.append({
                    'id': folder.get('id'),
                    'name': folder.get('name'),
                    'isFolder': True
                })
            for file in file_list:
                all_items.append({
                    'id': file.get('id'),
                    'name': file.get('name'),
                    'isFolder': False
                })
            
            if not all_items:
                # 如果分享的是单个文件/文件夹，直接使用分享信息中的fileId
                if share_info.get('isFolder'):
                    all_items.append({
                        'id': share_info.get('fileId'),
                        'name': share_info.get('fileName'),
                        'isFolder': True
                    })
                else:
                    all_items.append({
                        'id': share_info.get('fileId'),
                        'name': share_info.get('fileName'),
                        'isFolder': False
                    })
            
            if not all_items:
                return {
                    'success': False,
                    'message': '分享链接中没有文件'
                }
            
            logger.info(f"准备转存 {len(all_items)} 个文件/文件夹")
            
            # 5. 构造转存任务参数
            # 构造taskInfos数组，每个元素包含fileId、fileName、isFolder
            task_infos = []
            for item in all_items:
                task_infos.append({
                    'fileId': str(item['id']),
                    'fileName': item['name'],
                    'isFolder': 1 if item['isFolder'] else 0
                })
            
            # 确保taskInfos是JSON字符串格式
            task_infos_json = json.dumps(task_infos)
            
            batch_task_dto = {
                'type': 'SHARE_SAVE',
                'shareId': str(share_id),
                'taskInfos': task_infos_json,
                'targetFolderId': str(target_folder_id),
                'shareMode': str(share_mode)
            }
            
            # 关键修复：如果有访问码，必须添加到请求参数中
            if access_code:
                batch_task_dto['accessCode'] = access_code
            
            logger.info(f"189转存任务参数: type={batch_task_dto['type']}, shareId={batch_task_dto['shareId']}, targetFolderId={batch_task_dto['targetFolderId']}, shareMode={batch_task_dto['shareMode']}, accessCode={'***' if access_code else 'None'}")
            logger.info(f"189转存文件列表: {task_infos_json}")
            
            # 6. 创建转存任务
            task_result = self.create_batch_task(batch_task_dto)
            if task_result.get('res_code') != 0:
                return {
                    'success': False,
                    'message': task_result.get('res_message', '创建转存任务失败')
                }
            
            task_id = task_result.get('taskId')
            logger.info(f"189转存任务创建成功: task_id={task_id}, 完整响应: {task_result}")
            
            # 7. 查询任务状态（轮询）
            max_retries = 60  # 增加重试次数：60次 × 2秒 = 120秒
            invalid_status_count = 0  # 连续无效状态计数
            conflict_handled = False  # 冲突处理标记
            
            for i in range(max_retries):
                time.sleep(2)
                
                status_result = self.check_task_status(task_id)
                logger.info(f"189转存任务状态查询 [{i+1}/{max_retries}]: {status_result}")
                
                if status_result.get('res_code') != 0:
                    logger.warning(f"查询任务状态失败: {status_result}")
                    continue
                
                task_status = status_result.get('taskStatus')
                error_code = status_result.get('errorCode', '')
                logger.info(f"任务状态: {task_status}, errorCode: {error_code}")
                
                if task_status == 4:  # 完成
                    logger.info(f"189转存任务完成: task_id={task_id}")
                    return {
                        'success': True,
                        'message': '转存成功',
                        'task_id': task_id
                    }
                elif task_status == 3:  # 失败
                    error_msg = f"转存任务失败: {error_code}" if error_code else "转存任务失败"
                    logger.error(f"189转存任务失败: {error_msg}")
                    return {
                        'success': False,
                        'message': error_msg
                    }
                elif task_status == 1:  # 处理中
                    # 重置无效状态计数
                    invalid_status_count = 0
                    logger.info(f"189转存任务处理中: task_id={task_id}")
                    continue
                elif task_status == 2:  # 冲突（文件已存在）
                    if conflict_handled:
                        # 冲突已处理，继续等待
                        logger.info(f"189转存任务冲突已处理，继续等待: task_id={task_id}")
                        continue
                    
                    logger.info(f"189转存任务检测到文件已存在: task_id={task_id}")
                    # 获取冲突信息并自动处理（跳过）
                    conflict_info = self.get_conflict_task_info(task_id)
                    logger.info(f"冲突信息原始响应: {conflict_info}")
                    
                    if conflict_info.get('res_code') == 0:
                        # taskInfos 可能是 JSON 字符串，需要解析
                        task_infos_raw = conflict_info.get('taskInfos', [])
                        
                        # 如果是字符串，解析为列表
                        if isinstance(task_infos_raw, str):
                            try:
                                task_infos = json.loads(task_infos_raw)
                                logger.info(f"解析后的taskInfos: {task_infos}")
                            except json.JSONDecodeError as e:
                                logger.error(f"解析taskInfos失败: {e}, 原始数据: {task_infos_raw}")
                                # 即使解析失败，也视为文件已存在，返回成功
                                logger.info(f"189转存完成（文件已存在，已跳过）: task_id={task_id}")
                                return {
                                    'success': True,
                                    'message': '文件已存在，已跳过',
                                    'task_id': task_id,
                                    'skipped': True
                                }
                        else:
                            task_infos = task_infos_raw
                        
                        # 设置为跳过冲突文件
                        for info in task_infos:
                            info['dealWay'] = 2  # 2=跳过
                        
                        logger.info(f"准备处理冲突（跳过已存在文件），task_infos: {task_infos}")
                        
                        # 处理冲突
                        manage_result = self.manage_batch_task(
                            task_id, target_folder_id, task_infos
                        )
                        logger.info(f"冲突处理结果: {manage_result}")
                        
                        if manage_result.get('res_code') != 0:
                            error_msg = manage_result.get('res_message', '处理冲突失败')
                            logger.warning(f"处理冲突API调用失败: {error_msg}，但仍视为成功（文件已存在）")
                            # 即使处理冲突失败，也视为成功（文件已存在）
                            return {
                                'success': True,
                                'message': '文件已存在，已跳过',
                                'task_id': task_id,
                                'skipped': True
                            }
                        
                        conflict_handled = True
                        logger.info(f"189转存冲突处理完成（已跳过），继续轮询: task_id={task_id}")
                        # 继续轮询，等待任务完成
                        continue
                    else:
                        error_msg = conflict_info.get('res_message', '获取冲突信息失败')
                        logger.warning(f"获取冲突信息失败: {error_msg}，但仍视为成功（文件已存在）")
                        # 即使获取冲突信息失败，也视为成功（文件已存在）
                        return {
                            'success': True,
                            'message': '文件已存在，已跳过',
                            'task_id': task_id,
                            'skipped': True
                        }
                elif task_status == -1:  # 无效状态
                    invalid_status_count += 1
                    # 如果连续5次返回无效状态，说明任务参数有问题
                    if invalid_status_count >= 5:
                        error_msg = f"任务参数无效: {error_code}" if error_code else "任务状态异常"
                        logger.error(f"189转存任务异常: {error_msg}")
                        return {
                            'success': False,
                            'message': error_msg
                        }
                    logger.warning(f"189转存任务状态无效，继续重试: task_id={task_id}")
                    continue
                else:
                    # 未知状态
                    logger.warning(f"189转存任务未知状态: {task_status}")
                    continue
            
            return {
                'success': False,
                'message': '转存任务超时（超过120秒）'
            }
            
        except Exception as e:
            logger.error(f"189转存失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'转存失败: {str(e)}'
            }

    
    # ========== 分享和下载 ==========
    
    def create_share(self, file_ids, expire_days=7, need_password=False, password=None):
        """
        创建分享链接
        
        Args:
            file_ids: 文件ID列表
            expire_days: 有效期天数
            need_password: 是否需要密码
            password: 分享密码
        
        Returns:
            dict: 分享链接信息
        """
        try:
            # 确保file_ids是列表
            if not isinstance(file_ids, list):
                file_ids = [file_ids]
            
            logger.info(f"189创建分享: file_ids={file_ids}, expire_days={expire_days}, need_password={need_password}")
            
            url = "/api/open/share/createShareLink.action"
            
            # 计算过期时间（天翼云盘使用有效期类型而非时间戳）
            # expireTime: 1=1天, 2=7天, 3=永久
            if expire_days == 0:
                expire_type = 3  # 永久
            elif expire_days <= 1:
                expire_type = 1  # 1天
            else:
                expire_type = 2  # 7天
            
            # 天翼云盘分享参数格式
            data = {
                'fileId': ','.join(str(fid) for fid in file_ids),
                'expireTime': expire_type
            }
            
            # 如果需要提取码
            if need_password:
                data['shareType'] = 3  # 需要提取码
                if password:
                    data['accessCode'] = password
            else:
                data['shareType'] = 1  # 公开分享
            
            logger.info(f"189分享请求数据: {data}")
            
            response = self._send_request("POST", url, data=data)
            
            logger.info(f"189分享响应状态码: {response.status_code}")
            logger.info(f"189分享响应内容: {response.text[:500] if response.text else '空响应'}")
            
            # 检查响应
            if response.status_code != 200:
                # 尝试使用GET方法
                logger.info("POST方法失败，尝试GET方法...")
                response = self._send_request("GET", url, params=data)
                logger.info(f"189分享GET响应状态码: {response.status_code}")
                logger.info(f"189分享GET响应内容: {response.text[:500] if response.text else '空响应'}")
                
                if response.status_code != 200:
                    return {
                        'code': -1,
                        'message': f'分享请求失败，状态码: {response.status_code}'
                    }
            
            if not response.text or not response.text.strip():
                return {
                    'code': -1,
                    'message': '分享请求返回空响应'
                }
            
            try:
                result = response.json()
            except Exception as json_err:
                logger.error(f"189分享解析JSON失败: {json_err}")
                return {
                    'code': -1,
                    'message': f'解析响应失败: {str(json_err)}'
                }
            
            logger.info(f"189分享响应: {result}")
            
            if result.get('res_code') == 0:
                # 天翼云盘返回的是shareLinkList数组
                share_link_list = result.get('shareLinkList', [])
                
                if share_link_list:
                    # 取第一个分享链接
                    share_info = share_link_list[0]
                    share_url = share_info.get('accessUrl', '') or share_info.get('url', '')
                    access_code = share_info.get('accessCode', '')
                else:
                    # 兼容旧格式
                    share_url = result.get('shortShareUrl', '') or result.get('shareUrl', '')
                    access_code = result.get('accessCode', '')
                
                # 计算过期时间显示
                if expire_days == 0:
                    expire_time_str = '永久'
                else:
                    expire_time = int(time.time() * 1000) + expire_days * 24 * 3600 * 1000
                    expire_time_str = datetime.fromtimestamp(expire_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
                
                return {
                    'code': 0,
                    'data': {
                        'share_url': share_url,
                        'shareUrl': share_url,
                        'password': access_code,
                        'expire_time': expire_time_str,
                        'expireTime': expire_time_str
                    }
                }
            else:
                return {
                    'code': -1,
                    'message': result.get('res_message', '创建分享失败')
                }
                
        except Exception as e:
            logger.error(f"创建189分享失败: {e}")
            return {
                'code': -1,
                'message': f'创建分享失败: {str(e)}'
            }
    
    def get_download_url(self, file_ids):
        """
        获取下载链接
        
        Args:
            file_ids: 文件ID列表
        
        Returns:
            tuple: (result_dict, cookie_str)
        """
        try:
            # 确保file_ids是列表
            if not isinstance(file_ids, list):
                file_ids = [file_ids]
            
            download_urls = []
            
            for file_id in file_ids:
                # 先尝试使用标准API
                url = "/api/open/file/getFileDownloadUrl.action"
                params = {'fileId': file_id}
                
                response = self._send_request("GET", url, params=params)
                logger.info(f"189下载链接响应: status={response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"189下载链接结果: {result}")
                    
                    if result.get('res_code') == 0:
                        download_url = result.get('fileDownloadUrl', '')
                        if download_url:
                            download_urls.append({
                                'file_id': file_id,
                                'download_url': download_url,
                                'downloadUrl': download_url
                            })
                            logger.info(f"成功获取文件 {file_id} 的下载链接")
                            continue
                
                # 如果标准API失败(如文件太大),尝试使用备用API
                if response.status_code == 400:
                    result = response.json()
                    if result.get('res_code') == 'FileTooLarge':
                        logger.info(f"文件 {file_id} 太大,尝试使用备用API...")
                        
                        # 使用视频播放URL API(支持大文件)
                        url2 = "/api/portal/getNewVlcVideoPlayUrl.action"
                        params2 = {
                            'fileId': file_id,
                            'type': 2,  # 2=个人文件
                            'dt': 1
                        }
                        
                        response2 = self._send_request("GET", url2, params=params2)
                        logger.info(f"189备用API响应: status={response2.status_code}")
                        
                        if response2.status_code == 200:
                            result2 = response2.json()
                            logger.info(f"189备用API结果: {result2}")
                            
                            if result2.get('res_code') == 0:
                                # 备用API返回的数据结构: {'normal': {'url': '...'}}
                                normal_info = result2.get('normal', {})
                                download_url = normal_info.get('url', '')
                                if download_url:
                                    download_urls.append({
                                        'file_id': file_id,
                                        'download_url': download_url,
                                        'downloadUrl': download_url
                                    })
                                    logger.info(f"使用备用API成功获取文件 {file_id} 的下载链接")
                                    continue
                
                logger.warning(f"文件 {file_id} 的下载链接获取失败")
            
            if download_urls:
                return {
                    'code': 0,
                    'data': download_urls
                }, self.cookie
            else:
                return {
                    'code': -1,
                    'message': '未获取到任何下载链接'
                }, self.cookie
            
        except Exception as e:
            logger.error(f"获取189下载链接失败: {e}", exc_info=True)
            return {
                'code': -1,
                'message': f'获取下载链接失败: {str(e)}'
            }, self.cookie

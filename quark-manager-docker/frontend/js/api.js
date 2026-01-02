/**
 * API调用封装
 */

// 自动识别API基础URL
function getApiBaseUrl() {
    // 前后端合并部署,直接使用当前域名
    return '';  // 空字符串表示使用相对路径
}

const API_BASE_URL = getApiBaseUrl();

// 在控制台输出当前使用的API地址，方便调试
console.log('API Base URL:', API_BASE_URL || '(相对路径)');

// API工具类
class API {
    /**
     * 发送HTTP请求
     */
    static async request(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include' // 携带Cookie
        };

        const finalOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers
            }
        };

        try {
            const response = await fetch(`${API_BASE_URL}${url}`, finalOptions);
            const data = await response.json();

            // 处理未登录状态
            if (data.code === 401) {
                window.location.href = 'login.html';
                throw new Error('未登录');
            }

            return data;
        } catch (error) {
            console.error('API请求失败:', error);
            throw error;
        }
    }

    /**
     * GET请求
     */
    static async get(url, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const fullUrl = queryString ? `${url}?${queryString}` : url;
        return this.request(fullUrl, { method: 'GET' });
    }

    /**
     * POST请求
     */
    static async post(url, data = {}) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    /**
     * PUT请求
     */
    static async put(url, data = {}) {
        return this.request(url, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    /**
     * DELETE请求
     */
    static async delete(url, data = null) {
        const options = { method: 'DELETE' };
        
        // 如果有数据，添加到请求体
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        return this.request(url, options);
    }
}

// 认证API
const AuthAPI = {
    // 登录
    login: (username, password) => API.post('/api/auth/login', { username, password }),
    
    // 登出
    logout: () => API.post('/api/auth/logout'),
    
    // 检查登录状态
    check: () => API.get('/api/auth/check'),
    
    // 修改密码
    changePassword: (currentPassword, newPassword) => API.post('/api/auth/change-password', { 
        current_password: currentPassword, 
        new_password: newPassword 
    })
};

// 账号管理API
const AccountAPI = {
    // 获取账号列表
    getList: () => API.get('/api/accounts'),
    
    // 获取账号详情
    getDetail: (id) => API.get(`/api/accounts/${id}`),
    
    // 测试账号
    test: (cookie) => API.post('/api/accounts/test', { cookie }),
    
    // 添加账号
    create: (data) => API.post('/api/accounts', data),
    
    // 更新账号
    update: (id, data) => API.put(`/api/accounts/${id}`, data),
    
    // 删除账号
    delete: (id) => API.delete(`/api/accounts/${id}`),
    
    // 设为主账号
    setMain: (id) => API.put(`/api/accounts/${id}/set-main`),
    
    // 刷新账号信息
    refresh: (id) => API.post(`/api/accounts/${id}/refresh`)
};

// 夸克网盘API
const QuarkAPI = {
    // 获取文件列表
    getFiles: (accountId, folderId = '0', page = 1, pageSize = 50) => 
        API.get('/api/quark/files', { account_id: accountId, folder_id: folderId, page, page_size: pageSize }),
    
    // 创建文件夹
    createFolder: (accountId, parentId, name) => 
        API.post('/api/quark/folder', { account_id: accountId, parent_id: parentId, name }),
    
    // 删除文件
    deleteFiles: (accountId, fileIds) => 
        API.post('/api/quark/delete', { account_id: accountId, file_ids: fileIds }),
    
    // 分享文件
    shareFiles: (accountId, fileIds, expireDays, needPassword, password) => 
        API.post('/api/quark/share', { account_id: accountId, file_ids: fileIds, expire_days: expireDays, need_password: needPassword, password }),
    
    // 获取下载链接
    getDownloadUrl: (accountId, fileId) => 
        API.get('/api/quark/download', { account_id: accountId, file_id: fileId }),
    
    // 转存分享文件
    saveShare: (accountId, shareUrl, targetFolderId, password) => 
        API.post('/api/quark/save-share', { account_id: accountId, share_url: shareUrl, target_folder_id: targetFolderId, password })
};

// 资源搜索API
const SearchAPI = {
    // 搜索资源
    search: (keyword, type, page = 1, pageSize = 20) => 
        API.get('/api/search', { keyword, type, page, page_size: pageSize }),
    
    // 检测链接有效性
    checkValidity: (url) => 
        API.post('/api/search/check-validity', { url })
};

// 转存任务API
const TransferAPI = {
    // 获取任务列表
    getList: () => API.get('/api/transfer/tasks'),
    
    // 获取任务详情
    getDetail: (id) => API.get(`/api/transfer/task/${id}`),
    
    // 创建任务
    create: (data) => API.post('/api/transfer/task', data),
    
    // 更新任务
    update: (id, data) => API.put(`/api/transfer/task/${id}`, data),
    
    // 删除任务
    delete: (id) => API.delete(`/api/transfer/task/${id}`),
    
    // 暂停/启动任务
    toggle: (id) => API.post(`/api/transfer/task/${id}/toggle`),
    
    // 立即执行任务
    execute: (id) => API.post(`/api/transfer/task/${id}/execute`),
    
    // 检查分享链接状态
    checkShares: (id) => API.post(`/api/transfer/task/${id}/check-shares`),
    
    // 解析分享链接
    parseShare: (url) => API.post('/api/transfer/parse-share', { url }),
    
    // 浏览分享文件
    browseShare: (data) => API.post('/api/transfer/browse-share', data)
};

// 下载任务API
const DownloadAPI = {
    // 获取任务列表
    getList: () => API.get('/api/download/tasks'),
    
    // 获取任务详情
    getDetail: (id) => API.get(`/api/download/task/${id}`),
    
    // 创建任务
    create: (data) => API.post('/api/download/task', data),
    
    // 更新任务
    update: (id, data) => API.put(`/api/download/task/${id}`, data),
    
    // 删除任务
    delete: (id) => API.delete(`/api/download/task/${id}`),
    
    // 暂停/启动任务
    toggle: (id) => API.post(`/api/download/task/${id}/toggle`),
    
    // 立即执行任务
    execute: (id) => API.post(`/api/download/task/${id}/execute`),
    
    // 获取下载进度
    getProgress: (id) => API.get(`/api/download/task/${id}/progress`)
};

// 日志管理API
const LogAPI = {
    // 查询日志列表
    getList: (filters, page = 1, pageSize = 20) => 
        API.get('/api/logs', { ...filters, page, page_size: pageSize }),
    
    // 清空日志
    clear: () => API.delete('/api/logs/clear'),
    
    // 自动清理日志
    autoClean: (retentionDays) => API.post('/api/logs/auto-clean', { retention_days: retentionDays }),
    
    // 导出日志
    export: (filters, format) => API.get('/api/logs/export', { ...filters, format })
};

// 系统配置API
const ConfigAPI = {
    // 获取所有配置
    get: () => API.get('/api/config'),
    
    // 保存配置
    save: (data) => API.post('/api/config', data),
    
    // 测试邮件配置
    testEmail: (data) => API.post('/api/config/email/test', data)
};

// 影视下载API
const VideoAPI = {
    // 读取官网信息
    readWebsite: (url, platform) => API.post('/api/video/read-website', { url, platform }),
    
    // 获取任务列表
    getList: () => API.get('/api/video/task'),
    
    // 获取任务详情
    getDetail: (id) => API.get(`/api/video/task/${id}`),
    
    // 创建任务
    create: (data) => API.post('/api/video/task', data),
    
    // 更新任务
    update: (id, data) => API.put(`/api/video/task/${id}`, data),
    
    // 删除任务
    delete: (id) => API.delete(`/api/video/task/${id}`),
    
    // 暂停/启动任务
    toggle: (id) => API.post(`/api/video/task/${id}/toggle`),
    
    // 立即执行任务
    execute: (id) => API.post(`/api/video/task/${id}/execute`)
};

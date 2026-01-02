/**
 * 全局升级检查模块
 * 在登录后自动检查更新,显示更新提示
 */

(function() {
    const SKIP_VERSION_KEY = 'skip_update_version'; // 跳过的版本号
    
    // 检查更新
    async function checkForceUpdate() {
        try {
            const result = await API.get('/api/upgrade/check');
            
            if (result.code === 200 && result.data.has_update) {
                const updateData = result.data;
                
                // 检查是否跳过此版本
                const skipVersion = localStorage.getItem(SKIP_VERSION_KEY);
                if (!updateData.is_force_update && skipVersion === updateData.latest_version) {
                    console.log('用户已选择跳过此版本:', skipVersion);
                    return;
                }
                
                // 显示更新提示
                if (updateData.is_force_update) {
                    showForceUpdateModal(updateData);
                } else {
                    showNormalUpdateModal(updateData);
                }
            }
        } catch (error) {
            console.error('检查更新失败:', error);
        }
    }
    
    // 显示普通更新模态框
    function showNormalUpdateModal(updateData) {
        const modalHTML = `
            <div id="normalUpdateModal" style="
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.5);
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
            " onclick="if(event.target.id==='normalUpdateModal') closeNormalUpdate()">
                <div style="
                    background: white;
                    border-radius: 12px;
                    padding: 40px;
                    max-width: 600px;
                    width: 90%;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.3);
                    position: relative;
                " onclick="event.stopPropagation()">
                    <button onclick="closeNormalUpdate()" style="
                        position: absolute;
                        top: 16px;
                        right: 16px;
                        width: 32px;
                        height: 32px;
                        border: none;
                        background: #f0f0f0;
                        border-radius: 50%;
                        cursor: pointer;
                        font-size: 20px;
                        line-height: 1;
                        color: #666;
                        transition: all 0.2s;
                    " onmouseover="this.style.background='#e0e0e0'" onmouseout="this.style.background='#f0f0f0'">×</button>
                    
                    <div style="text-align: center; margin-bottom: 30px;">
                        <div style="font-size: 60px; margin-bottom: 20px;">🎉</div>
                        <h2 style="margin: 0 0 10px 0; font-size: 24px; color: #333;">发现新版本</h2>
                        <p style="margin: 0; color: #666; font-size: 16px;">
                            当前版本: ${updateData.current_version} → 最新版本: ${updateData.latest_version}
                        </p>
                    </div>
                    
                    <div style="
                        background: #f8f9fa;
                        padding: 20px;
                        border-radius: 8px;
                        margin-bottom: 30px;
                        max-height: 200px;
                        overflow-y: auto;
                    ">
                        <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #333;">更新内容</h3>
                        <div style="white-space: pre-wrap; font-size: 14px; line-height: 1.6; color: #555;">
                            ${updateData.release_notes || '暂无更新说明'}
                        </div>
                    </div>
                    
                    <div id="normalUpdateProgress" style="display: none; margin-bottom: 20px;">
                        <div style="
                            width: 100%;
                            height: 40px;
                            background: #f0f0f0;
                            border-radius: 20px;
                            overflow: hidden;
                            position: relative;
                        ">
                            <div id="normalUpdateProgressBar" style="
                                height: 100%;
                                background: linear-gradient(90deg, #4CAF50 0%, #45a049 100%);
                                width: 0%;
                                transition: width 0.3s;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                color: white;
                                font-weight: bold;
                                font-size: 16px;
                            ">0%</div>
                        </div>
                        <div id="normalUpdateMessage" style="
                            text-align: center;
                            margin-top: 12px;
                            color: #666;
                            font-size: 14px;
                        ">准备升级...</div>
                    </div>
                    
                    <div style="display: flex; gap: 12px;">
                        <button onclick="skipThisVersion('${updateData.latest_version}')" style="
                            flex: 1;
                            padding: 14px;
                            background: white;
                            color: #666;
                            border: 1px solid #ddd;
                            border-radius: 8px;
                            font-size: 15px;
                            cursor: pointer;
                            transition: all 0.2s;
                        " onmouseover="this.style.background='#f5f5f5'" onmouseout="this.style.background='white'">
                            不再提醒
                        </button>
                        <button onclick="closeNormalUpdate()" style="
                            flex: 1;
                            padding: 14px;
                            background: white;
                            color: #666;
                            border: 1px solid #ddd;
                            border-radius: 8px;
                            font-size: 15px;
                            cursor: pointer;
                            transition: all 0.2s;
                        " onmouseover="this.style.background='#f5f5f5'" onmouseout="this.style.background='white'">
                            稍后提醒
                        </button>
                        <button id="startNormalUpdateBtn" onclick="window.startNormalUpdate()" style="
                            flex: 2;
                            padding: 14px;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            border: none;
                            border-radius: 8px;
                            font-size: 16px;
                            font-weight: bold;
                            cursor: pointer;
                            transition: transform 0.2s;
                        " onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'">
                            立即升级
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        window.normalUpdateData = updateData;
    }
    
    // 关闭普通更新提示
    window.closeNormalUpdate = function() {
        const modal = document.getElementById('normalUpdateModal');
        if (modal) {
            modal.remove();
        }
    };
    
    // 跳过此版本
    window.skipThisVersion = function(version) {
        localStorage.setItem(SKIP_VERSION_KEY, version);
        window.closeNormalUpdate();
        alert('已设置不再提醒此版本更新');
    };
    
    // 开始普通更新
    window.startNormalUpdate = async function() {
        const updateData = window.normalUpdateData;
        if (!updateData) return;
        
        const btn = document.getElementById('startNormalUpdateBtn');
        btn.disabled = true;
        btn.style.opacity = '0.6';
        btn.style.cursor = 'not-allowed';
        btn.textContent = '升级中...';
        
        document.getElementById('normalUpdateProgress').style.display = 'block';
        
        try {
            const result = await API.post('/api/upgrade/start', {
                package_url: updateData.package_url,
                package_md5: updateData.package_md5,
                to_version: updateData.latest_version
            });
            
            if (result.code === 200) {
                pollNormalUpdateStatus();
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            alert('启动升级失败: ' + error.message);
            btn.disabled = false;
            btn.style.opacity = '1';
            btn.style.cursor = 'pointer';
            btn.textContent = '立即升级';
        }
    };
    
    // 轮询普通更新状态
    function pollNormalUpdateStatus() {
        const interval = setInterval(async () => {
            try {
                const result = await API.get('/api/upgrade/status');
                
                if (result.code === 200) {
                    const status = result.data;
                    
                    const progress = status.progress || 0;
                    const progressBar = document.getElementById('normalUpdateProgressBar');
                    const progressMessage = document.getElementById('normalUpdateMessage');
                    
                    if (progressBar) {
                        progressBar.style.width = progress + '%';
                        progressBar.textContent = progress + '%';
                    }
                    
                    if (progressMessage) {
                        progressMessage.textContent = status.message || '';
                    }
                    
                    if (!status.is_upgrading) {
                        clearInterval(interval);
                        
                        if (status.error) {
                            alert('升级失败: ' + status.error);
                            window.closeNormalUpdate();
                        } else {
                            alert('升级完成！\n\n系统将在3秒后自动刷新页面');
                            setTimeout(() => {
                                window.location.reload();
                            }, 3000);
                        }
                    }
                }
            } catch (error) {
                console.error('获取升级状态失败:', error);
            }
        }, 1000);
    }
    
    // 显示强制更新模态框
    function showForceUpdateModal(updateData) {
        const modalHTML = `
            <div id="forceUpdateModal" style="
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.8);
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
            ">
                <div style="
                    background: white;
                    border-radius: 12px;
                    padding: 40px;
                    max-width: 600px;
                    width: 90%;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.3);
                ">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <div style="font-size: 60px; margin-bottom: 20px;">🚀</div>
                        <h2 style="margin: 0 0 10px 0; font-size: 24px; color: #333;">发现新版本</h2>
                        <p style="margin: 0; color: #666; font-size: 16px;">
                            当前版本: ${updateData.current_version} → 最新版本: ${updateData.latest_version}
                        </p>
                    </div>
                    
                    <div style="
                        background: #f8f9fa;
                        padding: 20px;
                        border-radius: 8px;
                        margin-bottom: 30px;
                        max-height: 200px;
                        overflow-y: auto;
                    ">
                        <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #333;">更新内容</h3>
                        <div style="white-space: pre-wrap; font-size: 14px; line-height: 1.6; color: #555;">
                            ${updateData.release_notes || '暂无更新说明'}
                        </div>
                    </div>
                    
                    <div id="forceUpdateProgress" style="display: none; margin-bottom: 20px;">
                        <div style="
                            width: 100%;
                            height: 40px;
                            background: #f0f0f0;
                            border-radius: 20px;
                            overflow: hidden;
                            position: relative;
                        ">
                            <div id="forceUpdateProgressBar" style="
                                height: 100%;
                                background: linear-gradient(90deg, #4CAF50 0%, #45a049 100%);
                                width: 0%;
                                transition: width 0.3s;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                color: white;
                                font-weight: bold;
                                font-size: 16px;
                            ">0%</div>
                        </div>
                        <div id="forceUpdateMessage" style="
                            text-align: center;
                            margin-top: 12px;
                            color: #666;
                            font-size: 14px;
                        ">准备升级...</div>
                    </div>
                    
                    <div style="
                        background: #fff3cd;
                        border: 1px solid #ffc107;
                        border-radius: 6px;
                        padding: 16px;
                        margin-bottom: 20px;
                        display: flex;
                        align-items: center;
                        gap: 12px;
                    ">
                        <span style="font-size: 24px;">⚠️</span>
                        <div style="flex: 1;">
                            <strong style="color: #856404;">强制更新</strong>
                            <p style="margin: 4px 0 0 0; font-size: 13px; color: #856404;">
                                此版本为强制更新,升级前会自动备份,升级过程中请勿关闭程序
                            </p>
                        </div>
                    </div>
                    
                    <button id="startForceUpdateBtn" onclick="window.startForceUpdate()" style="
                        width: 100%;
                        padding: 16px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        border: none;
                        border-radius: 8px;
                        font-size: 18px;
                        font-weight: bold;
                        cursor: pointer;
                        transition: transform 0.2s;
                    " onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'">
                        立即升级
                    </button>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        window.forceUpdateData = updateData;
    }
    
    // 开始强制更新
    window.startForceUpdate = async function() {
        const updateData = window.forceUpdateData;
        if (!updateData) return;
        
        const btn = document.getElementById('startForceUpdateBtn');
        btn.disabled = true;
        btn.style.opacity = '0.6';
        btn.style.cursor = 'not-allowed';
        btn.textContent = '升级中...';
        
        document.getElementById('forceUpdateProgress').style.display = 'block';
        
        try {
            const result = await API.post('/api/upgrade/start', {
                package_url: updateData.package_url,
                package_md5: updateData.package_md5,
                to_version: updateData.latest_version
            });
            
            if (result.code === 200) {
                pollForceUpdateStatus();
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            alert('启动升级失败: ' + error.message);
            btn.disabled = false;
            btn.style.opacity = '1';
            btn.style.cursor = 'pointer';
            btn.textContent = '立即升级';
        }
    };
    
    // 轮询强制更新状态
    function pollForceUpdateStatus() {
        const interval = setInterval(async () => {
            try {
                const result = await API.get('/api/upgrade/status');
                
                if (result.code === 200) {
                    const status = result.data;
                    
                    const progress = status.progress || 0;
                    const progressBar = document.getElementById('forceUpdateProgressBar');
                    const progressMessage = document.getElementById('forceUpdateMessage');
                    
                    if (progressBar) {
                        progressBar.style.width = progress + '%';
                        progressBar.textContent = progress + '%';
                    }
                    
                    if (progressMessage) {
                        progressMessage.textContent = status.message || '';
                    }
                    
                    if (!status.is_upgrading) {
                        clearInterval(interval);
                        
                        if (status.error) {
                            alert('升级失败: ' + status.error + '\n\n请联系管理员或手动升级');
                        } else {
                            alert('升级完成！\n\n系统将在3秒后自动刷新页面');
                            setTimeout(() => {
                                window.location.reload();
                            }, 3000);
                        }
                    }
                }
            } catch (error) {
                console.error('获取升级状态失败:', error);
            }
        }, 1000);
    }
    
    // 暴露检查函数
    window.checkForceUpdate = checkForceUpdate;
})();

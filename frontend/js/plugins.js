/**
 * 插件管理页面 JavaScript
 */

// 当前配置的插件ID
let currentConfigPluginId = null;
let currentConfigSchema = [];

// 页面加载时获取插件列表
document.addEventListener('DOMContentLoaded', function() {
    loadPlugins();
});

/**
 * 加载插件列表
 */
async function loadPlugins() {
    try {
        const response = await fetch('/api/plugins');
        const result = await response.json();
        
        if (result.code === 200) {
            renderPluginList(result.data);
        } else {
            showToast(result.message || '获取插件列表失败', 'error');
        }
    } catch (error) {
        console.error('加载插件列表失败:', error);
        showToast('加载插件列表失败', 'error');
    }
}

/**
 * 渲染插件列表
 */
function renderPluginList(plugins) {
    const container = document.getElementById('pluginList');
    
    if (!plugins || plugins.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🔌</div>
                <div class="empty-state-text">暂无已安装的插件</div>
                <button class="btn btn-primary" onclick="showInstallModal()">安装第一个插件</button>
            </div>
        `;
        return;
    }
    
    container.innerHTML = plugins.map(plugin => `
        <div class="plugin-card" data-plugin-id="${plugin.plugin_id}">
            <div class="plugin-header">
                <div class="plugin-info">
                    <h3 class="plugin-name">
                        ${plugin.plugin_name}
                        <span class="status-badge ${plugin.status}">${getStatusText(plugin.status)}</span>
                    </h3>
                    <div class="plugin-meta">
                        <span>ID: ${plugin.plugin_id}</span>
                        <span>版本: ${plugin.plugin_version}</span>
                        ${plugin.plugin_author ? `<span>作者: ${plugin.plugin_author}</span>` : ''}
                    </div>
                </div>
                <div class="plugin-actions">
                    ${plugin.status === 'started' 
                        ? `<button class="btn btn-warning btn-sm" onclick="stopPlugin('${plugin.plugin_id}')">停止</button>`
                        : `<button class="btn btn-success btn-sm" onclick="startPlugin('${plugin.plugin_id}')">启动</button>`
                    }
                    <button class="btn btn-outline btn-sm" onclick="showConfigModal('${plugin.plugin_id}')">配置</button>
                    <button class="btn btn-outline btn-sm" onclick="showStatsModal('${plugin.plugin_id}')">统计</button>
                    <button class="btn btn-outline btn-sm" onclick="exportPlugin('${plugin.plugin_id}')">导出</button>
                    <button class="btn btn-danger btn-sm" onclick="uninstallPlugin('${plugin.plugin_id}')">卸载</button>
                </div>
            </div>
            ${plugin.plugin_desc ? `<div class="plugin-desc">${plugin.plugin_desc}</div>` : ''}
        </div>
    `).join('');
}

/**
 * 获取状态文本
 */
function getStatusText(status) {
    const statusMap = {
        'installed': '已安装',
        'started': '运行中',
        'stopped': '已停止'
    };
    return statusMap[status] || status;
}


/**
 * 显示安装弹窗
 */
function showInstallModal() {
    document.getElementById('installModal').style.display = 'flex';
    document.getElementById('pluginFile').value = '';
    document.getElementById('forceInstall').checked = false;
}

/**
 * 隐藏安装弹窗
 */
function hideInstallModal() {
    document.getElementById('installModal').style.display = 'none';
}

/**
 * 安装插件
 */
async function installPlugin() {
    const fileInput = document.getElementById('pluginFile');
    const forceInstall = document.getElementById('forceInstall').checked;
    
    if (!fileInput.files || fileInput.files.length === 0) {
        showToast('请选择插件包文件', 'warning');
        return;
    }
    
    const file = fileInput.files[0];
    if (!file.name.endsWith('.zip')) {
        showToast('插件包必须是.zip格式', 'warning');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('force', forceInstall ? 'true' : 'false');
    
    try {
        showToast('正在安装插件...', 'info');
        
        const response = await fetch('/api/plugins/install', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        
        if (result.code === 200) {
            showToast(result.message || '插件安装成功', 'success');
            hideInstallModal();
            loadPlugins();
        } else {
            showToast(result.message || '安装失败', 'error');
        }
    } catch (error) {
        console.error('安装插件失败:', error);
        showToast('安装插件失败', 'error');
    }
}

/**
 * 启动插件
 */
async function startPlugin(pluginId) {
    try {
        const response = await fetch(`/api/plugins/${pluginId}/start`, {
            method: 'POST'
        });
        const result = await response.json();
        
        if (result.code === 200) {
            showToast(result.message || '插件已启动', 'success');
            loadPlugins();
        } else {
            showToast(result.message || '启动失败', 'error');
        }
    } catch (error) {
        console.error('启动插件失败:', error);
        showToast('启动插件失败', 'error');
    }
}

/**
 * 停止插件
 */
async function stopPlugin(pluginId) {
    try {
        const response = await fetch(`/api/plugins/${pluginId}/stop`, {
            method: 'POST'
        });
        const result = await response.json();
        
        if (result.code === 200) {
            showToast(result.message || '插件已停止', 'success');
            loadPlugins();
        } else {
            showToast(result.message || '停止失败', 'error');
        }
    } catch (error) {
        console.error('停止插件失败:', error);
        showToast('停止插件失败', 'error');
    }
}

/**
 * 卸载插件
 */
async function uninstallPlugin(pluginId) {
    if (!confirm('确定要卸载此插件吗？此操作不可恢复。')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/plugins/${pluginId}`, {
            method: 'DELETE'
        });
        const result = await response.json();
        
        if (result.code === 200) {
            showToast(result.message || '插件已卸载', 'success');
            loadPlugins();
        } else {
            // 如果是因为有任务在使用，询问是否强制卸载
            if (result.message && result.message.includes('正在被任务使用')) {
                if (confirm(result.message + '\n\n是否强制卸载？')) {
                    const forceResponse = await fetch(`/api/plugins/${pluginId}?force=true`, {
                        method: 'DELETE'
                    });
                    const forceResult = await forceResponse.json();
                    
                    if (forceResult.code === 200) {
                        showToast(forceResult.message || '插件已强制卸载', 'success');
                        loadPlugins();
                    } else {
                        showToast(forceResult.message || '卸载失败', 'error');
                    }
                }
            } else {
                showToast(result.message || '卸载失败', 'error');
            }
        }
    } catch (error) {
        console.error('卸载插件失败:', error);
        showToast('卸载插件失败', 'error');
    }
}

/**
 * 导出插件
 */
async function exportPlugin(pluginId) {
    try {
        const response = await fetch(`/api/plugins/${pluginId}/export`);
        
        if (response.ok) {
            // 获取文件名
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = `${pluginId}.zip`;
            if (contentDisposition) {
                const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
                if (match && match[1]) {
                    filename = match[1].replace(/['"]/g, '');
                }
            }
            
            // 下载文件
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showToast('插件导出成功', 'success');
        } else {
            const result = await response.json();
            showToast(result.message || '导出失败', 'error');
        }
    } catch (error) {
        console.error('导出插件失败:', error);
        showToast('导出插件失败', 'error');
    }
}


/**
 * 显示配置弹窗
 */
async function showConfigModal(pluginId) {
    try {
        const response = await fetch(`/api/plugins/${pluginId}/config`);
        const result = await response.json();
        
        if (result.code === 200) {
            currentConfigPluginId = pluginId;
            currentConfigSchema = result.data.schema || [];
            const config = result.data.config || {};
            
            document.getElementById('configModalTitle').textContent = '插件配置 - ' + pluginId;
            document.getElementById('configModalBody').innerHTML = renderConfigForm(currentConfigSchema, config);
            document.getElementById('configModal').style.display = 'flex';
        } else {
            showToast(result.message || '获取配置失败', 'error');
        }
    } catch (error) {
        console.error('获取插件配置失败:', error);
        showToast('获取插件配置失败', 'error');
    }
}

/**
 * 隐藏配置弹窗
 */
function hideConfigModal() {
    document.getElementById('configModal').style.display = 'none';
    currentConfigPluginId = null;
    currentConfigSchema = [];
}

/**
 * 渲染配置表单
 */
function renderConfigForm(schema, config) {
    if (!schema || schema.length === 0) {
        return '<div style="text-align: center; color: #999; padding: 20px;">此插件无需配置</div>';
    }
    
    return schema.map(field => {
        const value = config[field.param_key] !== undefined ? config[field.param_key] : (field.default_value || '');
        const required = field.required ? '<span style="color: #ef4444;">*</span>' : '';
        
        let input = '';
        switch (field.param_type) {
            case 'boolean':
                input = `
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                        <input type="checkbox" id="config_${field.param_key}" ${value ? 'checked' : ''}>
                        <span>${field.param_name}</span>
                    </label>
                `;
                break;
            case 'number':
                input = `<input type="number" id="config_${field.param_key}" value="${value}" style="width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 4px;">`;
                break;
            case 'select':
                const options = field.options || [];
                input = `
                    <select id="config_${field.param_key}" style="width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 4px;">
                        ${options.map(opt => `<option value="${opt.value}" ${value === opt.value ? 'selected' : ''}>${opt.label}</option>`).join('')}
                    </select>
                `;
                break;
            default: // string
                input = `<input type="text" id="config_${field.param_key}" value="${value}" style="width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 4px;">`;
        }
        
        return `
            <div class="form-group" style="margin-bottom: 16px;">
                ${field.param_type !== 'boolean' ? `<label style="display: block; margin-bottom: 6px; font-weight: 500;">${field.param_name} ${required}</label>` : ''}
                ${input}
                ${field.param_desc ? `<div style="font-size: 12px; color: #999; margin-top: 4px;">${field.param_desc}</div>` : ''}
            </div>
        `;
    }).join('');
}

/**
 * 保存插件配置
 */
async function savePluginConfig() {
    if (!currentConfigPluginId) return;
    
    // 收集配置值
    const config = {};
    for (const field of currentConfigSchema) {
        const element = document.getElementById(`config_${field.param_key}`);
        if (element) {
            if (field.param_type === 'boolean') {
                config[field.param_key] = element.checked;
            } else if (field.param_type === 'number') {
                config[field.param_key] = element.value ? Number(element.value) : null;
            } else {
                config[field.param_key] = element.value;
            }
        }
    }
    
    try {
        const response = await fetch(`/api/plugins/${currentConfigPluginId}/config`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        const result = await response.json();
        
        if (result.code === 200) {
            showToast(result.message || '配置保存成功', 'success');
            hideConfigModal();
        } else {
            showToast(result.message || '保存失败', 'error');
        }
    } catch (error) {
        console.error('保存插件配置失败:', error);
        showToast('保存插件配置失败', 'error');
    }
}

/**
 * 显示统计弹窗
 */
async function showStatsModal(pluginId) {
    try {
        const response = await fetch(`/api/plugins/${pluginId}/stats`);
        const result = await response.json();
        
        if (result.code === 200) {
            const stats = result.data;
            document.getElementById('statsModalTitle').textContent = '执行统计 - ' + pluginId;
            document.getElementById('statsModalBody').innerHTML = `
                <div style="display: grid; gap: 16px;">
                    <div style="display: flex; justify-content: space-between; padding: 12px; background: #f9fafb; border-radius: 6px;">
                        <span style="color: #666;">总执行次数</span>
                        <span style="font-weight: 600;">${stats.total || 0}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 12px; background: #d1fae5; border-radius: 6px;">
                        <span style="color: #059669;">成功次数</span>
                        <span style="font-weight: 600; color: #059669;">${stats.success_count || 0}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 12px; background: #fee2e2; border-radius: 6px;">
                        <span style="color: #dc2626;">失败次数</span>
                        <span style="font-weight: 600; color: #dc2626;">${stats.failed_count || 0}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 12px; background: #f9fafb; border-radius: 6px;">
                        <span style="color: #666;">平均耗时</span>
                        <span style="font-weight: 600;">${stats.avg_duration ? Math.round(stats.avg_duration) + ' ms' : '-'}</span>
                    </div>
                </div>
            `;
            document.getElementById('statsModal').style.display = 'flex';
        } else {
            showToast(result.message || '获取统计失败', 'error');
        }
    } catch (error) {
        console.error('获取插件统计失败:', error);
        showToast('获取插件统计失败', 'error');
    }
}

/**
 * 隐藏统计弹窗
 */
function hideStatsModal() {
    document.getElementById('statsModal').style.display = 'none';
}

/**
 * 显示提示消息
 */
function showToast(message, type = 'info') {
    // 使用全局的 showToast 函数（如果存在）
    if (window.parent && window.parent.showToast) {
        window.parent.showToast(message, type);
    } else if (typeof window.showGlobalToast === 'function') {
        window.showGlobalToast(message, type);
    } else {
        // 简单的 alert 作为后备
        alert(message);
    }
}

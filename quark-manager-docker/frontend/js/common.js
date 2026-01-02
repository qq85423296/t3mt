/**
 * 公共函数库
 */

// 消息提示
const Message = {
    show(text, type = 'info', duration = 3000) {
        // 移除已存在的消息
        const existingMessage = document.querySelector('.message');
        if (existingMessage) {
            existingMessage.remove();
        }

        // 创建消息元素
        const message = document.createElement('div');
        message.className = `message message-${type} show`;
        message.textContent = text;
        document.body.appendChild(message);

        // 自动隐藏
        setTimeout(() => {
            message.classList.remove('show');
            setTimeout(() => message.remove(), 300);
        }, duration);
    },

    success(text, duration) {
        this.show(text, 'success', duration);
    },

    error(text, duration) {
        this.show(text, 'error', duration);
    },

    warning(text, duration) {
        this.show(text, 'warning', duration);
    },

    info(text, duration) {
        this.show(text, 'info', duration);
    }
};

// 模态框管理
class Modal {
    constructor(modalId) {
        this.modal = document.getElementById(modalId);
        if (!this.modal) {
            console.error(`Modal ${modalId} not found`);
            return;
        }

        // 绑定关闭事件
        const closeBtn = this.modal.querySelector('.modal-close');
        if (closeBtn) {
            closeBtn.onclick = () => this.hide();
        }

        // 点击背景关闭
        this.modal.onclick = (e) => {
            if (e.target === this.modal) {
                this.hide();
            }
        };
    }

    show() {
        if (this.modal) {
            this.modal.classList.add('show');
        }
    }

    hide() {
        if (this.modal) {
            this.modal.classList.remove('show');
        }
    }
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const k = 1024;
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + units[i];
}

// 格式化日期时间
function formatDateTime(dateString) {
    if (!dateString) return '-';
    
    const date = new Date(dateString);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

// 格式化日期
function formatDate(dateString) {
    if (!dateString) return '-';
    
    const date = new Date(dateString);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    
    return `${year}-${month}-${day}`;
}

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 节流函数
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// 复制到剪贴板
async function copyToClipboard(text) {
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
            Message.success('已复制到剪贴板');
        } else {
            // 降级方案
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            Message.success('已复制到剪贴板');
        }
    } catch (error) {
        console.error('复制失败:', error);
        Message.error('复制失败');
    }
}

// 检查登录状态
async function checkLogin() {
    try {
        const result = await AuthAPI.check();
        if (result.code !== 200) {
            window.location.href = 'login.html';
            return false;
        }
        return true;
    } catch (error) {
        window.location.href = 'login.html';
        return false;
    }
}

// 登出
async function logout() {
    if (!confirm('确定要退出吗？')) {
        return;
    }

    try {
        await AuthAPI.logout();
        Message.success('已退出登录');
        setTimeout(() => {
            window.location.href = 'login.html';
        }, 500);
    } catch (error) {
        console.error('登出失败:', error);
        Message.error('登出失败');
    }
}

// 加载状态管理
const Loading = {
    show(container) {
        if (typeof container === 'string') {
            container = document.getElementById(container);
        }
        if (container) {
            container.innerHTML = '<div class="loading">加载中...</div>';
        }
    },

    hide(container) {
        if (typeof container === 'string') {
            container = document.getElementById(container);
        }
        if (container) {
            const loading = container.querySelector('.loading');
            if (loading) {
                loading.remove();
            }
        }
    }
};

// 空状态显示
function showEmptyState(container, message = '暂无数据', icon = '📭') {
    if (typeof container === 'string') {
        container = document.getElementById(container);
    }
    if (container) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">${icon}</div>
                <div>${message}</div>
            </div>
        `;
    }
}

// 解析Cron表达式为可读文本
function parseCronExpression(cron) {
    // 简单的Cron表达式解析
    const parts = cron.split(' ');
    if (parts.length < 5) return cron;

    const [second, minute, hour, day, month, week] = parts;

    if (minute === '*' && hour === '*') {
        return '每分钟执行';
    }
    if (hour === '*' && minute !== '*') {
        return `每小时第${minute}分钟执行`;
    }
    if (hour !== '*' && minute !== '*') {
        return `每天${hour}:${minute}执行`;
    }

    return cron;
}

// 验证邮箱格式
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

// 验证URL格式
function validateUrl(url) {
    try {
        new URL(url);
        return true;
    } catch {
        return false;
    }
}

// 获取文件图标
function getFileIcon(fileName, isFolder) {
    if (isFolder) return '📁';
    
    const ext = fileName.split('.').pop().toLowerCase();
    const iconMap = {
        'mp4': '🎬',
        'mkv': '🎬',
        'avi': '🎬',
        'mov': '🎬',
        'jpg': '🖼️',
        'jpeg': '🖼️',
        'png': '🖼️',
        'gif': '🖼️',
        'pdf': '📄',
        'doc': '📄',
        'docx': '📄',
        'txt': '📄',
        'zip': '📦',
        'rar': '📦',
        '7z': '📦',
        'mp3': '🎵',
        'flac': '🎵',
        'wav': '🎵'
    };
    
    return iconMap[ext] || '📄';
}


// 移动端表格卡片化 - 来源地址展开/收起功能
if (window.innerWidth <= 768) {
    document.addEventListener('DOMContentLoaded', function() {
        // 为来源地址单元格添加点击事件
        function initMobileTableCards() {
            const sourceUrlCells = document.querySelectorAll('.data-table tbody tr td:nth-child(2)');
            
            sourceUrlCells.forEach(cell => {
                // 移除旧的事件监听器
                const newCell = cell.cloneNode(true);
                cell.parentNode.replaceChild(newCell, cell);
                
                // 添加点击展开/收起功能
                newCell.addEventListener('click', function(e) {
                    e.stopPropagation();
                    this.classList.toggle('expanded');
                });
            });
        }

        // 初始化
        initMobileTableCards();

        // 监听DOM变化(如AJAX加载新数据)
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.addedNodes.length > 0) {
                    initMobileTableCards();
                }
            });
        });

        // 观察表格容器
        const tableContainers = document.querySelectorAll('.data-table tbody');
        tableContainers.forEach(container => {
            observer.observe(container, {
                childList: true,
                subtree: true
            });
        });
    });
}

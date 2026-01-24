/**
 * 正则配置管理模块 v2
 */
(function() {
    'use strict';
    
    var RegexConfig = {
        shareCache: null,

        showExampleModal: function() {
            var modal = document.getElementById('regexExampleModal');
            if (modal) modal.classList.add('show');
        },

        hideExampleModal: function() {
            var modal = document.getElementById('regexExampleModal');
            if (modal) modal.classList.remove('show');
        },

        switchTab: function(tabName) {
            var tabs = document.querySelectorAll('.example-tab');
            for (var i = 0; i < tabs.length; i++) {
                var isActive = (tabName === 'basic' && i === 0) || (tabName === 'advanced' && i === 1);
                tabs[i].classList.toggle('active', isActive);
            }
            var basicContent = document.getElementById('basicExamples');
            var advancedContent = document.getElementById('advancedExamples');
            if (basicContent) basicContent.classList.toggle('active', tabName === 'basic');
            if (advancedContent) advancedContent.classList.toggle('active', tabName === 'advanced');
        },

        copyRule: function(regex, replacement) {
            // 检测当前页面：下载页面使用 dl 前缀，影视页面使用 video 前缀，转存页面使用无前缀
            var dlRegexInput = document.getElementById('dlRegexPattern');
            var dlReplacementInput = document.getElementById('dlReplacementPattern');
            var videoRegexInput = document.getElementById('videoRegexPattern');
            var videoReplacementInput = document.getElementById('videoReplacementPattern');
            var regexInput = document.getElementById('regexPattern');
            var replacementInput = document.getElementById('replacementPattern');
            
            // 优先检查下载页面的元素（如果存在且可见）
            if (dlRegexInput && dlRegexInput.offsetParent !== null) {
                dlRegexInput.value = regex;
                if (dlReplacementInput) dlReplacementInput.value = replacement;
            } else if (videoRegexInput && videoRegexInput.offsetParent !== null) {
                // 影视下载页面
                videoRegexInput.value = regex;
                if (videoReplacementInput) videoReplacementInput.value = replacement;
            } else if (regexInput) {
                // 回退到转存页面的元素
                regexInput.value = regex;
                if (replacementInput) replacementInput.value = replacement;
            }
            
            this.hideExampleModal();
            if (window.Message) Message.success('规则已复制到输入框');
        },

        previewReplacement: function() {
            var self = this;
            var regexEl = document.getElementById('regexPattern');
            var replaceEl = document.getElementById('replacementPattern');
            var filenameEl = document.getElementById('previewFilename');
            
            var regex = regexEl ? regexEl.value.trim() : '';
            var replacement = replaceEl ? replaceEl.value.trim() : '';
            var filename = filenameEl ? filenameEl.value.trim() : '';
            
            if (!regex) { if (window.Message) Message.warning('请输入正则表达式'); return; }
            if (!filename) { if (window.Message) Message.warning('请输入要预览的文件名'); return; }
            
            RegexAPI.preview({ regex_pattern: regex, replacement_pattern: replacement, filename: filename })
                .then(function(result) {
                    var previewResult = document.getElementById('previewResult');
                    if (previewResult && result.code === 200 && result.data) {
                        if (result.data.matched) {
                            previewResult.innerHTML = '<div style="color:#059669;font-weight:500;">✓ 匹配成功</div>' +
                                '<div style="margin-top:8px;"><span style="color:#6B7280;">原文件名：</span><span style="color:#374151;">' + self.escapeHtml(result.data.original) + '</span></div>' +
                                '<div style="margin-top:4px;"><span style="color:#6B7280;">新文件名：</span><span style="color:#059669;font-weight:500;">' + self.escapeHtml(result.data.result) + '</span></div>';
                        } else {
                            previewResult.innerHTML = '<div style="color:#D97706;font-weight:500;">○ 不匹配</div><div style="margin-top:8px;color:#6B7280;">正则表达式不匹配该文件名，将保持原样</div>';
                        }
                        previewResult.style.display = 'block';
                    }
                })
                .catch(function(err) {
                    console.error('预览失败:', err);
                    if (window.Message) Message.error('预览失败');
                });
        },

        loadShareFiles: function() {
            var self = this;
            
            // 在pageContainer内查找元素（SPA动态加载的页面）
            var container = document.getElementById('pageContainer');
            if (!container) {
                container = document;
            }
            
            // 获取表单元素
            var shareUrlInput = container.querySelector('.share-url-input');
            var accountIdEl = container.querySelector('#targetAccount');
            var regexEl = container.querySelector('#regexPattern');
            
            var shareUrl = shareUrlInput ? shareUrlInput.value.trim() : '';
            var accountId = accountIdEl ? accountIdEl.value : '';
            var regex = regexEl ? regexEl.value.trim() : '';
            
            console.log('loadShareFiles:', { shareUrl: shareUrl, accountId: accountId, regex: regex });
            
            // 验证必填字段
            if (!shareUrl) { 
                Message.warning('请先填写分享链接'); 
                if (shareUrlInput) shareUrlInput.focus();
                return; 
            }
            if (!accountId) { 
                Message.warning('请先选择转存账号'); 
                if (accountIdEl) accountIdEl.focus();
                return; 
            }
            if (!regex) { 
                Message.warning('请先输入正则表达式'); 
                if (regexEl) regexEl.focus();
                return; 
            }

            // 前端直接格式化天翼云盘链接（将括号形式的密码转换为URL参数格式）
            var normalizedUrl = this.normalizeCloud189Url(shareUrl);
            if (normalizedUrl !== shareUrl) {
                console.log('链接已格式化:', shareUrl, '->', normalizedUrl);
                shareUrl = normalizedUrl;
                if (shareUrlInput) {
                    shareUrlInput.value = normalizedUrl;
                }
                Message.success('链接已自动格式化为标准格式');
            }

            // 显示浏览弹窗并加载文件
            this.showShareBrowserModal();
            this.browseShareFolder(shareUrl, accountId, '0', []);
        },

        // 格式化天翼云盘链接（将括号形式的密码转换为URL参数格式）
        normalizeCloud189Url: function(url) {
            if (!url || typeof url !== 'string') {
                return url;
            }

            // 只处理天翼云盘链接
            if (!url.includes('cloud.189.cn') && !url.includes('189.cn')) {
                return url;
            }

            // 先去除首尾空格
            url = url.trim();

            var shareCode = null;
            var accessCode = '';

            // 提取 share_code
            // 格式1: code=xxx
            var matchCode = url.match(/[?&]code=([a-zA-Z0-9]+)/);
            if (matchCode) {
                shareCode = matchCode[1];
            }

            // 格式2: /t/xxx 或 #/t/xxx (h5版本)
            if (!shareCode) {
                var matchPath = url.match(/[/#]t\/([a-zA-Z0-9]+)/);
                if (matchPath) {
                    shareCode = matchPath[1];
                }
            }

            // 格式3: /share/xxx
            if (!shareCode) {
                var matchShare = url.match(/\/share\/([a-zA-Z0-9]+)/);
                if (matchShare) {
                    shareCode = matchShare[1];
                }
            }

            if (!shareCode) {
                return url; // 无法解析，返回原链接
            }

            // 提取 access_code (密码)
            // 方式1: URL参数格式 ?pwd=xxxx 或 &pwd=xxxx
            var matchPwd = url.match(/[?&]pwd=([a-zA-Z0-9]+)/);
            if (matchPwd) {
                accessCode = matchPwd[1];
            }

            // 方式2: 括号形式（中文括号或英文括号）
            if (!accessCode) {
                var matchBracket = url.match(/[（(](?:访问码|提取码|密码)[:：\s]*([a-zA-Z0-9]+)[）)]/);
                if (matchBracket) {
                    accessCode = matchBracket[1];
                }
            }

            // 方式3: 无括号格式
            if (!accessCode) {
                var matchPlain = url.match(/(?:访问码|提取码|密码)[:：\s]+([a-zA-Z0-9]+)/);
                if (matchPlain) {
                    accessCode = matchPlain[1];
                }
            }

            // 构建标准格式的链接
            if (accessCode) {
                // 检查原链接是否已经是标准格式
                var standardFormat = 'https://cloud.189.cn/web/share?code=' + shareCode + '&pwd=' + accessCode;
                if (url.includes('?code=' + shareCode + '&pwd=' + accessCode) || 
                    url.includes('&pwd=' + accessCode)) {
                    // 已经是标准格式，不需要修改
                    return url;
                }
                return standardFormat;
            } else {
                // 无密码，返回标准格式
                return 'https://cloud.189.cn/web/share?code=' + shareCode;
            }
        },

        showShareBrowserModal: function() {
            var modal = document.getElementById('regexShareBrowserModal');
            if (!modal) {
                modal = document.createElement('div');
                modal.id = 'regexShareBrowserModal';
                modal.className = 'modal';
                modal.innerHTML = '<div class="modal-content" style="max-width:800px;">' +
                    '<div class="modal-header"><div class="modal-title">浏览分享文件</div>' +
                    '<button class="modal-close" onclick="RegexConfig.hideShareBrowserModal()">×</button></div>' +
                    '<div class="modal-body">' +
                    '<div id="regexShareBreadcrumb" style="margin-bottom:12px;padding:8px;background:#f5f5f5;border-radius:4px;">' +
                    '<span style="color:#666;">路径：</span><span id="regexBreadcrumbPath">根目录</span></div>' +
                    '<div id="regexShareFileList" style="max-height:400px;overflow-y:auto;border:1px solid #e5e7eb;border-radius:4px;">' +
                    '<div style="padding:40px;text-align:center;color:#999;">加载中...</div></div></div>' +
                    '<div class="modal-footer"><button class="btn" onclick="RegexConfig.hideShareBrowserModal()">关闭</button>' +
                    '<button class="btn btn-primary" onclick="RegexConfig.testCurrentFolder()">测试当前目录文件</button></div></div>';
                document.body.appendChild(modal);
            }
            modal.classList.add('show');
        },

        hideShareBrowserModal: function() {
            var modal = document.getElementById('regexShareBrowserModal');
            if (modal) modal.classList.remove('show');
        },

        browseShareFolder: function(shareUrl, accountId, pdirFid, pathStack) {
            var self = this;
            var fileListEl = document.getElementById('regexShareFileList');
            if (!fileListEl) {
                console.error('regexShareFileList not found');
                return;
            }

            fileListEl.innerHTML = '<div style="padding:40px;text-align:center;color:#999;">加载中...</div>';

            TransferAPI.browseShare({ url: shareUrl, account_id: accountId, pdir_fid: pdirFid })
                .then(function(result) {
                    console.log('browseShare result:', result);
                    if (result.code === 200 && result.data && result.data.files) {
                        var files = result.data.files;
                        self.shareCache = { shareUrl: shareUrl, accountId: accountId, pdirFid: pdirFid, pathStack: pathStack, files: files };
                        self.updateBreadcrumb(pathStack);
                        self.renderFileList(files, pathStack);
                    } else {
                        fileListEl.innerHTML = '<div style="padding:40px;text-align:center;color:#f87171;">' + (result.message || '加载失败') + '</div>';
                    }
                })
                .catch(function(err) {
                    console.error('浏览分享文件失败:', err);
                    fileListEl.innerHTML = '<div style="padding:40px;text-align:center;color:#f87171;">加载失败: ' + err.message + '</div>';
                });
        },

        renderFileList: function(files, pathStack) {
            var self = this;
            var fileListEl = document.getElementById('regexShareFileList');
            if (!fileListEl) {
                console.error('regexShareFileList not found in renderFileList');
                return;
            }

            if (files.length === 0) {
                fileListEl.innerHTML = '<div style="padding:40px;text-align:center;color:#999;">该目录为空</div>';
                return;
            }

            var html = '<table style="width:100%;border-collapse:collapse;">' +
                '<thead><tr style="background:#f9fafb;"><th style="padding:10px;text-align:left;border-bottom:1px solid #e5e7eb;">文件名</th>' +
                '<th style="padding:10px;text-align:right;border-bottom:1px solid #e5e7eb;width:100px;">大小</th></tr></thead><tbody>';

            if (pathStack.length > 0) {
                html += '<tr style="cursor:pointer;" onclick="RegexConfig.goBack()">' +
                    '<td style="padding:10px;border-bottom:1px solid #f3f4f6;"><span style="color:#2563eb;">📁 ..</span></td>' +
                    '<td style="padding:10px;text-align:right;border-bottom:1px solid #f3f4f6;color:#999;">返回上级</td></tr>';
            }

            var folders = files.filter(function(f) { return f.dir; });
            var fileItems = files.filter(function(f) { return !f.dir; });

            for (var i = 0; i < folders.length; i++) {
                var folder = folders[i];
                html += '<tr style="cursor:pointer;" onclick="RegexConfig.enterFolder(\'' + folder.fid + '\', \'' + self.escapeHtml(folder.file_name).replace(/'/g, "\\'") + '\')">' +
                    '<td style="padding:10px;border-bottom:1px solid #f3f4f6;"><span style="color:#2563eb;">📁 ' + self.escapeHtml(folder.file_name) + '</span></td>' +
                    '<td style="padding:10px;text-align:right;border-bottom:1px solid #f3f4f6;color:#999;">文件夹</td></tr>';
            }

            for (var j = 0; j < fileItems.length; j++) {
                var file = fileItems[j];
                html += '<tr><td style="padding:10px;border-bottom:1px solid #f3f4f6;"><span style="color:#374151;">📄 ' + self.escapeHtml(file.file_name) + '</span></td>' +
                    '<td style="padding:10px;text-align:right;border-bottom:1px solid #f3f4f6;color:#999;">' + self.formatFileSize(file.size) + '</td></tr>';
            }

            html += '</tbody></table>';
            fileListEl.innerHTML = html;
        },

        enterFolder: function(fid, folderName) {
            if (!this.shareCache) return;
            var newPathStack = this.shareCache.pathStack.slice();
            newPathStack.push({ fid: this.shareCache.pdirFid, name: folderName });
            this.browseShareFolder(this.shareCache.shareUrl, this.shareCache.accountId, fid, newPathStack);
        },

        goBack: function() {
            if (!this.shareCache || this.shareCache.pathStack.length === 0) return;
            var newPathStack = this.shareCache.pathStack.slice();
            var parent = newPathStack.pop();
            this.browseShareFolder(this.shareCache.shareUrl, this.shareCache.accountId, parent.fid, newPathStack);
        },

        goToRoot: function() {
            if (!this.shareCache) return;
            this.browseShareFolder(this.shareCache.shareUrl, this.shareCache.accountId, '0', []);
        },

        updateBreadcrumb: function(pathStack) {
            var breadcrumbEl = document.getElementById('regexBreadcrumbPath');
            if (!breadcrumbEl) return;
            var html = '<span style="color:#2563eb;cursor:pointer;" onclick="RegexConfig.goToRoot()">根目录</span>';
            for (var i = 0; i < pathStack.length; i++) {
                html += ' / <span style="color:#374151;">' + this.escapeHtml(pathStack[i].name) + '</span>';
            }
            breadcrumbEl.innerHTML = html;
        },

        testCurrentFolder: function() {
            var self = this;
            if (!this.shareCache || !this.shareCache.files) {
                if (window.Message) Message.warning('请先加载分享文件');
                return;
            }

            var files = this.shareCache.files.filter(function(f) { return !f.dir; });
            if (files.length === 0) {
                if (window.Message) Message.warning('当前目录没有文件');
                return;
            }

            var regexEl = document.getElementById('regexPattern');
            var replaceEl = document.getElementById('replacementPattern');
            var regex = regexEl ? regexEl.value.trim() : '';
            var replacement = replaceEl ? replaceEl.value.trim() : '';

            if (!regex) {
                if (window.Message) Message.warning('请先输入正则表达式');
                return;
            }

            this.hideShareBrowserModal();
            this.batchPreview(files, regex, replacement);
        },

        batchPreview: function(files, regex, replacement) {
            var self = this;
            var previewResult = document.getElementById('previewResult');
            if (!previewResult) return;

            var html = '<div style="color:#2563EB;font-weight:500;margin-bottom:12px;">📁 批量预览 (共' + files.length + '个文件)</div>';
            html += '<div style="max-height:300px;overflow-y:auto;" id="batchPreviewList"><div style="padding:20px;text-align:center;color:#999;">处理中...</div></div>';
            previewResult.innerHTML = html;
            previewResult.style.display = 'block';

            var listEl = document.getElementById('batchPreviewList');
            var results = [];
            var processed = 0;
            var total = Math.min(files.length, 30);

            for (var i = 0; i < total; i++) {
                (function(index) {
                    var file = files[index];
                    RegexAPI.preview({ regex_pattern: regex, replacement_pattern: replacement, filename: file.file_name })
                        .then(function(result) {
                            results[index] = { file: file, result: result };
                            processed++;
                            if (processed === total) {
                                self.renderBatchResults(results, files.length);
                            }
                        })
                        .catch(function(err) {
                            results[index] = { file: file, error: err };
                            processed++;
                            if (processed === total) {
                                self.renderBatchResults(results, files.length);
                            }
                        });
                })(i);
            }
        },

        renderBatchResults: function(results, totalFiles) {
            var self = this;
            var listEl = document.getElementById('batchPreviewList');
            if (!listEl) return;

            var html = '';
            for (var i = 0; i < results.length; i++) {
                var item = results[i];
                if (!item) continue;
                
                var file = item.file;
                var result = item.result;
                
                if (result && result.code === 200 && result.data) {
                    var matched = result.data.matched;
                    var icon = matched ? '✓' : '○';
                    var color = matched ? '#059669' : '#D97706';
                    
                    html += '<div style="padding:8px 0;border-bottom:1px solid #E5E7EB;">';
                    html += '<div style="display:flex;align-items:center;gap:8px;">';
                    html += '<span style="color:' + color + ';">' + icon + '</span>';
                    html += '<span style="color:#6B7280;font-size:12px;">原:</span>';
                    html += '<span style="color:#374151;font-size:13px;">' + self.escapeHtml(file.file_name) + '</span></div>';
                    
                    if (matched) {
                        html += '<div style="display:flex;align-items:center;gap:8px;margin-top:4px;padding-left:20px;">';
                        html += '<span style="color:#6B7280;font-size:12px;">新:</span>';
                        html += '<span style="color:#059669;font-size:13px;font-weight:500;">' + self.escapeHtml(result.data.result) + '</span></div>';
                    }
                    html += '</div>';
                }
            }

            if (totalFiles > 30) {
                html += '<div style="padding:8px 0;color:#6B7280;font-size:12px;">... 还有 ' + (totalFiles - 30) + ' 个文件未显示</div>';
            }

            listEl.innerHTML = html;
            if (window.Message) Message.success('已测试 ' + results.length + ' 个文件');
        },

        escapeHtml: function(str) {
            if (!str) return '';
            return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        },

        formatFileSize: function(bytes) {
            if (!bytes || bytes === 0) return '0 B';
            var k = 1024;
            var sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
            var i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        },

        init: function() {
            console.log('RegexConfig v2 已加载');
        }
    };

    window.RegexConfig = RegexConfig;
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() { RegexConfig.init(); });
    } else {
        RegexConfig.init();
    }
})();

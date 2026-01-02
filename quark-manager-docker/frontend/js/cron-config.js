/**
 * 简化版Cron配置组件
 * 支持每日执行和每周执行两种模式，可添加多个时间点
 */

(function(window) {
    'use strict';

    // Cron配置状态
    let cronConfig = {
        type: 'daily',      // 'daily' 或 'weekly'
        dailyTimes: [],     // [{hour: 5, minute: 30}, {hour: 10, minute: 25}]
        weeklyTimes: []     // [{weekDays: [1,3,5], hour: 8, minute: 0}]
    };

    // 初始化小时和分钟下拉选择器
    function initCronSelectors() {
        // 初始化小时选择器（0-23）
        const dailyHourSelect = document.getElementById('dailyHour');
        const weeklyHourSelect = document.getElementById('weeklyHour');
        
        if (!dailyHourSelect || !weeklyHourSelect) return;
        
        for (let i = 0; i <= 23; i++) {
            const option = `<option value="${i}">${String(i).padStart(2, '0')}</option>`;
            dailyHourSelect.innerHTML += option;
            weeklyHourSelect.innerHTML += option;
        }
        
        // 初始化分钟选择器（0-59）
        const dailyMinuteSelect = document.getElementById('dailyMinute');
        const weeklyMinuteSelect = document.getElementById('weeklyMinute');
        
        for (let i = 0; i <= 59; i++) {
            const option = `<option value="${i}">${String(i).padStart(2, '0')}</option>`;
            dailyMinuteSelect.innerHTML += option;
            weeklyMinuteSelect.innerHTML += option;
        }
    }

    // 处理执行类型切换
    function handleCronTypeChange(type) {
        cronConfig.type = type;
        
        // 显示/隐藏对应的配置区域
        const dailyConfig = document.getElementById('dailyConfig');
        const weeklyConfig = document.getElementById('weeklyConfig');
        const onceConfig = document.getElementById('onceConfig');
        
        if (type === 'daily') {
            dailyConfig.style.display = 'block';
            weeklyConfig.style.display = 'none';
            if (onceConfig) onceConfig.style.display = 'none';
        } else if (type === 'weekly') {
            dailyConfig.style.display = 'none';
            weeklyConfig.style.display = 'block';
            if (onceConfig) onceConfig.style.display = 'none';
        } else if (type === 'once') {
            dailyConfig.style.display = 'none';
            weeklyConfig.style.display = 'none';
            if (onceConfig) onceConfig.style.display = 'block';
        }
        
        updateNextExecutionTime();
    }

    // 添加每日时间点
    function addDailyTime() {
        const hour = parseInt(document.getElementById('dailyHour').value);
        const minute = parseInt(document.getElementById('dailyMinute').value);
        
        // 检查是否已存在相同时间点
        const exists = cronConfig.dailyTimes.some(t => t.hour === hour && t.minute === minute);
        if (exists) {
            if (window.Message) {
                window.Message.warning('该时间点已存在');
            } else {
                alert('该时间点已存在');
            }
            return;
        }
        
        cronConfig.dailyTimes.push({ hour, minute });
        renderDailyTimeList();
        updateNextExecutionTime();
    }

    // 删除每日时间点
    function removeDailyTime(index) {
        cronConfig.dailyTimes.splice(index, 1);
        renderDailyTimeList();
        updateNextExecutionTime();
    }

    // 渲染每日时间点列表
    function renderDailyTimeList() {
        const container = document.getElementById('dailyTimeList');
        if (!container) return;
        
        if (cronConfig.dailyTimes.length === 0) {
            container.innerHTML = '';
            return;
        }
        
        // 按时间排序
        const sortedTimes = [...cronConfig.dailyTimes].sort((a, b) => {
            if (a.hour !== b.hour) return a.hour - b.hour;
            return a.minute - b.minute;
        });
        
        container.innerHTML = sortedTimes.map((time, index) => {
            const originalIndex = cronConfig.dailyTimes.findIndex(t => t.hour === time.hour && t.minute === time.minute);
            return `
                <div class="cron-time-tag">
                    <span>${String(time.hour).padStart(2, '0')}:${String(time.minute).padStart(2, '0')}</span>
                    <button class="cron-time-tag-remove" onclick="CronConfig.removeDailyTime(${originalIndex})">×</button>
                </div>
            `;
        }).join('');
    }

    // 切换星期选择
    function toggleWeekDay(day) {
        const btn = document.querySelector(`.cron-week-btn[data-day="${day}"]`);
        if (btn) {
            btn.classList.toggle('selected');
        }
        updateNextExecutionTime();
    }

    // 获取选中的星期
    function getSelectedWeekDays() {
        const selectedBtns = document.querySelectorAll('.cron-week-btn.selected');
        return Array.from(selectedBtns).map(btn => parseInt(btn.dataset.day));
    }

    // 添加每周时间点
    function addWeeklyTime() {
        const weekDays = getSelectedWeekDays();
        
        if (weekDays.length === 0) {
            if (window.Message) {
                window.Message.warning('请先选择星期');
            } else {
                alert('请先选择星期');
            }
            return;
        }
        
        const hour = parseInt(document.getElementById('weeklyHour').value);
        const minute = parseInt(document.getElementById('weeklyMinute').value);
        
        // 检查是否已存在相同配置
        const exists = cronConfig.weeklyTimes.some(t => 
            t.hour === hour && 
            t.minute === minute && 
            JSON.stringify(t.weekDays.sort()) === JSON.stringify(weekDays.sort())
        );
        
        if (exists) {
            if (window.Message) {
                window.Message.warning('该时间点配置已存在');
            } else {
                alert('该时间点配置已存在');
            }
            return;
        }
        
        cronConfig.weeklyTimes.push({ weekDays: [...weekDays], hour, minute });
        renderWeeklyTimeList();
        updateNextExecutionTime();
    }

    // 删除每周时间点
    function removeWeeklyTime(index) {
        cronConfig.weeklyTimes.splice(index, 1);
        renderWeeklyTimeList();
        updateNextExecutionTime();
    }

    // 渲染每周时间点列表
    function renderWeeklyTimeList() {
        const container = document.getElementById('weeklyTimeList');
        if (!container) return;
        
        if (cronConfig.weeklyTimes.length === 0) {
            container.innerHTML = '';
            return;
        }
        
        const weekNames = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
        
        container.innerHTML = cronConfig.weeklyTimes.map((time, index) => {
            const weekStr = time.weekDays.map(d => weekNames[d]).join(',');
            return `
                <div class="cron-time-tag">
                    <span>${weekStr} ${String(time.hour).padStart(2, '0')}:${String(time.minute).padStart(2, '0')}</span>
                    <button class="cron-time-tag-remove" onclick="CronConfig.removeWeeklyTime(${index})">×</button>
                </div>
            `;
        }).join('');
    }

    // 计算并更新下次执行时间
    function updateNextExecutionTime() {
        const nextTimeElement = document.getElementById('nextExecutionTime');
        if (!nextTimeElement) return;
        
        // 一次性执行
        if (cronConfig.type === 'once') {
            nextTimeElement.textContent = '保存后立即执行';
            return;
        }
        
        const now = new Date();
        let nextTimes = [];
        
        if (cronConfig.type === 'daily') {
            if (cronConfig.dailyTimes.length === 0) {
                nextTimeElement.textContent = '请添加至少一个时间点';
                return;
            }
            
            // 计算每个时间点的下次执行时间
            cronConfig.dailyTimes.forEach(time => {
                let nextTime = new Date(now.getFullYear(), now.getMonth(), now.getDate(), time.hour, time.minute, 0);
                
                // 如果今天的时间已过，则设置为明天
                if (nextTime <= now) {
                    nextTime.setDate(nextTime.getDate() + 1);
                }
                
                nextTimes.push(nextTime);
            });
        } else {
            if (cronConfig.weeklyTimes.length === 0) {
                nextTimeElement.textContent = '请添加至少一个时间点';
                return;
            }
            
            // 计算每个周时间点的下次执行时间
            cronConfig.weeklyTimes.forEach(time => {
                const sortedDays = time.weekDays.sort((a, b) => a - b);
                const currentDay = now.getDay();
                
                // 查找下一个执行日
                let targetDay = null;
                for (const day of sortedDays) {
                    if (day > currentDay) {
                        targetDay = day;
                        break;
                    } else if (day === currentDay) {
                        // 如果是今天，检查时间是否已过
                        const todayTime = new Date(now.getFullYear(), now.getMonth(), now.getDate(), time.hour, time.minute, 0);
                        if (todayTime > now) {
                            targetDay = day;
                            break;
                        }
                    }
                }
                
                // 如果没找到，使用下周的第一个执行日
                if (targetDay === null) {
                    targetDay = sortedDays[0];
                }
                
                // 计算日期差
                let daysToAdd = targetDay - currentDay;
                if (daysToAdd <= 0) {
                    daysToAdd += 7;
                }
                
                const nextTime = new Date(now.getFullYear(), now.getMonth(), now.getDate() + daysToAdd, time.hour, time.minute, 0);
                nextTimes.push(nextTime);
            });
        }
        
        // 找到最近的执行时间
        if (nextTimes.length > 0) {
            nextTimes.sort((a, b) => a - b);
            const nearestTime = nextTimes[0];
            
            const weekNames = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
            nextTimeElement.textContent = 
                `${formatDateTime(nearestTime)} (${weekNames[nearestTime.getDay()]})`;
        }
    }

    // 显示Cron模态框
    function showCronModal() {
        // 初始化选择器（如果还没初始化）
        if (document.getElementById('dailyHour').options.length === 0) {
            initCronSelectors();
        }
        
        // 解析现有的Cron表达式并回填
        const currentCron = document.getElementById('cronExpression').value;
        if (currentCron) {
            parseCronToConfig(currentCron);
        } else {
            // 默认值：清空配置
            cronConfig = {
                type: 'daily',
                dailyTimes: [],
                weeklyTimes: []
            };
            const dailyRadio = document.querySelector('input[name="cronType"][value="daily"]');
            if (dailyRadio) {
                dailyRadio.checked = true;
                handleCronTypeChange('daily');
            }
        }
        
        // 渲染时间点列表
        renderDailyTimeList();
        renderWeeklyTimeList();
        
        const modal = document.getElementById('cronModal');
        if (modal) {
            modal.classList.add('show');
        }
        updateNextExecutionTime();
    }
    
    // 隐藏Cron模态框
    function hideCronModal() {
        const modal = document.getElementById('cronModal');
        if (modal) {
            modal.classList.remove('show');
        }
        
        // 清除星期选择状态
        document.querySelectorAll('.cron-week-btn').forEach(btn => {
            btn.classList.remove('selected');
        });
    }

    // 解析Cron表达式到配置
    function parseCronToConfig(cronExpression) {
        // 支持分号分隔的多个表达式
        if (cronExpression.includes(';')) {
            const expressions = cronExpression.split(';').map(e => e.trim());
            // 解析第一个表达式来判断类型
            const firstExpr = expressions[0];
            const parts = firstExpr.split(/\s+/);
            if (parts.length < 7) return;
            
            const week = parts[5];
            if (week !== '?' && week !== '*') {
                // 每周执行
                cronConfig.type = 'weekly';
                cronConfig.weeklyTimes = [];
                
                expressions.forEach(expr => {
                    const p = expr.split(/\s+/);
                    if (p.length >= 7) {
                        const weekDays = p[5].split(',').map(d => parseInt(d));
                        cronConfig.weeklyTimes.push({
                            weekDays: weekDays,
                            hour: parseInt(p[2]),
                            minute: parseInt(p[1])
                        });
                    }
                });
                
                const weeklyRadio = document.querySelector('input[name="cronType"][value="weekly"]');
                if (weeklyRadio) {
                    weeklyRadio.checked = true;
                    handleCronTypeChange('weekly');
                }
            } else {
                // 每日执行
                cronConfig.type = 'daily';
                cronConfig.dailyTimes = [];
                
                expressions.forEach(expr => {
                    const p = expr.split(/\s+/);
                    if (p.length >= 7) {
                        cronConfig.dailyTimes.push({
                            hour: parseInt(p[2]),
                            minute: parseInt(p[1])
                        });
                    }
                });
                
                const dailyRadio = document.querySelector('input[name="cronType"][value="daily"]');
                if (dailyRadio) {
                    dailyRadio.checked = true;
                    handleCronTypeChange('daily');
                }
            }
            return;
        }
        
        // 单个表达式
        const parts = cronExpression.trim().split(/\s+/);
        if (parts.length < 7) return;
        
        const [second, minute, hour, day, month, week, year] = parts;
        
        // 判断是每日还是每周
        if (week !== '?' && week !== '*') {
            // 每周执行
            cronConfig.type = 'weekly';
            cronConfig.weeklyTimes = [];
            
            // 解析小时和分钟（可能是逗号分隔的多个值）
            const hours = hour.split(',').map(h => parseInt(h));
            const minutes = minute.split(',').map(m => parseInt(m));
            const weekDays = week.split(',').map(d => parseInt(d));
            
            // 如果小时和分钟数量相同，认为是配对的
            if (hours.length === minutes.length) {
                for (let i = 0; i < hours.length; i++) {
                    cronConfig.weeklyTimes.push({
                        weekDays: [...weekDays],
                        hour: hours[i],
                        minute: minutes[i]
                    });
                }
            } else {
                // 否则使用第一个小时和分钟
                cronConfig.weeklyTimes.push({
                    weekDays: [...weekDays],
                    hour: hours[0],
                    minute: minutes[0]
                });
            }
            
            const weeklyRadio = document.querySelector('input[name="cronType"][value="weekly"]');
            if (weeklyRadio) {
                weeklyRadio.checked = true;
                handleCronTypeChange('weekly');
            }
        } else {
            // 每日执行
            cronConfig.type = 'daily';
            cronConfig.dailyTimes = [];
            
            // 解析小时和分钟（可能是逗号分隔的多个值）
            const hours = hour.split(',').map(h => parseInt(h));
            const minutes = minute.split(',').map(m => parseInt(m));
            
            // 如果小时和分钟数量相同，认为是配对的
            if (hours.length === minutes.length) {
                for (let i = 0; i < hours.length; i++) {
                    cronConfig.dailyTimes.push({
                        hour: hours[i],
                        minute: minutes[i]
                    });
                }
            } else if (hours.length === 1 && minutes.length > 1) {
                // 一个小时，多个分钟
                minutes.forEach(m => {
                    cronConfig.dailyTimes.push({
                        hour: hours[0],
                        minute: m
                    });
                });
            } else if (hours.length > 1 && minutes.length === 1) {
                // 多个小时，一个分钟
                hours.forEach(h => {
                    cronConfig.dailyTimes.push({
                        hour: h,
                        minute: minutes[0]
                    });
                });
            }
            
            const dailyRadio = document.querySelector('input[name="cronType"][value="daily"]');
            if (dailyRadio) {
                dailyRadio.checked = true;
                handleCronTypeChange('daily');
            }
        }
    }

    // 应用Cron配置
    function applyCronSimple() {
        let cron = '';
        let description = '';
        
        if (cronConfig.type === 'once') {
            // 一次性执行：使用特殊标记
            cron = 'ONCE';
            description = '立即执行一次（不重复）';
        } else if (cronConfig.type === 'daily') {
            if (cronConfig.dailyTimes.length === 0) {
                if (window.Message) {
                    window.Message.warning('请添加至少一个时间点');
                } else {
                    alert('请添加至少一个时间点');
                }
                return;
            }
            
            // 按时间排序
            const sortedTimes = [...cronConfig.dailyTimes].sort((a, b) => {
                if (a.hour !== b.hour) return a.hour - b.hour;
                return a.minute - b.minute;
            });
            
            if (sortedTimes.length === 1) {
                const time = sortedTimes[0];
                cron = `0 ${time.minute} ${time.hour} * * ? *`;
                description = `每天 ${String(time.hour).padStart(2, '0')}:${String(time.minute).padStart(2, '0')} 执行`;
            } else {
                // 多个时间点：尝试合并相同小时的分钟
                const hourGroups = {};
                sortedTimes.forEach(time => {
                    if (!hourGroups[time.hour]) {
                        hourGroups[time.hour] = [];
                    }
                    hourGroups[time.hour].push(time.minute);
                });
                
                // 如果所有时间点的小时都不同，可以用逗号分隔
                const hours = Object.keys(hourGroups).map(h => parseInt(h));
                const allMinutesSame = Object.values(hourGroups).every(mins => mins.length === 1 && mins[0] === hourGroups[hours[0]][0]);
                
                if (allMinutesSame) {
                    // 所有分钟相同，只有小时不同
                    const minute = hourGroups[hours[0]][0];
                    cron = `0 ${minute} ${hours.join(',')} * * ? *`;
                } else {
                    // 复杂情况：生成多个表达式用分号分隔
                    const cronList = sortedTimes.map(time => `0 ${time.minute} ${time.hour} * * ? *`);
                    cron = cronList.join(';');
                }
                
                const timeStrs = sortedTimes.map(t => `${String(t.hour).padStart(2, '0')}:${String(t.minute).padStart(2, '0')}`);
                description = `每天 ${timeStrs.join('、')} 执行`;
            }
        } else {
            if (cronConfig.weeklyTimes.length === 0) {
                if (window.Message) {
                    window.Message.warning('请添加至少一个时间点');
                } else {
                    alert('请添加至少一个时间点');
                }
                return;
            }
            
            // 生成每周执行的Cron表达式
            if (cronConfig.weeklyTimes.length === 1) {
                const time = cronConfig.weeklyTimes[0];
                const weekStr = time.weekDays.sort((a, b) => a - b).join(',');
                cron = `0 ${time.minute} ${time.hour} ? * ${weekStr} *`;
                
                const weekNames = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
                const weekDesc = time.weekDays.map(d => weekNames[d]).join('、');
                description = `每周 ${weekDesc} ${String(time.hour).padStart(2, '0')}:${String(time.minute).padStart(2, '0')} 执行`;
            } else {
                // 多个周时间点：生成多个表达式用分号分隔
                const cronList = cronConfig.weeklyTimes.map(time => {
                    const weekStr = time.weekDays.sort((a, b) => a - b).join(',');
                    return `0 ${time.minute} ${time.hour} ? * ${weekStr} *`;
                });
                cron = cronList.join(';');
                
                const weekNames = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
                const descList = cronConfig.weeklyTimes.map(time => {
                    const weekDesc = time.weekDays.map(d => weekNames[d]).join(',');
                    return `${weekDesc} ${String(time.hour).padStart(2, '0')}:${String(time.minute).padStart(2, '0')}`;
                });
                description = `每周 ${descList.join('；')} 执行`;
            }
        }
        
        const cronExpressionInput = document.getElementById('cronExpression');
        const cronDisplaySpan = document.getElementById('cronDisplay');
        
        if (cronExpressionInput) cronExpressionInput.value = cron;
        if (cronDisplaySpan) cronDisplaySpan.textContent = description;
        
        hideCronModal();
    }

    // 解析Cron表达式为可读描述
    function parseCronExpression(cron) {
        if (!cron) return '未设置执行时间';
        
        // 一次性执行
        if (cron === 'ONCE') {
            return '立即执行一次（不重复）';
        }
        
        // 支持分号分隔的多个表达式
        if (cron.includes(';')) {
            const expressions = cron.split(';');
            const descriptions = expressions.map(expr => parseSingleCronExpression(expr.trim()));
            return descriptions.join('；');
        }
        
        return parseSingleCronExpression(cron);
    }
    
    // 解析单个Cron表达式
    function parseSingleCronExpression(cron) {
        const parts = cron.trim().split(/\s+/);
        if (parts.length < 7) return '无效的Cron表达式';
        
        const [second, minute, hour, day, month, week, year] = parts;
        const weekNames = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
        
        // 每天指定时间执行
        if (day === '*' && month === '*' && week === '?' && hour !== '*' && minute !== '*') {
            // 支持逗号分隔的多个小时或分钟
            const hours = hour.split(',');
            const minutes = minute.split(',');
            
            if (hours.length > 1 || minutes.length > 1) {
                if (hours.length === minutes.length) {
                    const times = hours.map((h, i) => `${String(h).padStart(2, '0')}:${String(minutes[i]).padStart(2, '0')}`);
                    return `每天 ${times.join('、')} 执行`;
                } else if (hours.length > 1) {
                    return `每天 ${hours.map(h => String(h).padStart(2, '0')).join('、')}:${String(minutes[0]).padStart(2, '0')} 执行`;
                } else {
                    return `每天 ${String(hours[0]).padStart(2, '0')}:${minutes.map(m => String(m).padStart(2, '0')).join('、')} 执行`;
                }
            }
            
            return `每天 ${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')} 执行`;
        }
        
        // 每周指定时间执行
        if (week !== '?' && week !== '*' && month === '*') {
            const weekStr = week.split(',').map(w => weekNames[parseInt(w)]).join('、');
            return `每周 ${weekStr} ${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')} 执行`;
        }
        
        return cron;
    }

    // 格式化日期时间
    function formatDateTime(date) {
        const yyyy = date.getFullYear();
        const mm = String(date.getMonth() + 1).padStart(2, '0');
        const dd = String(date.getDate()).padStart(2, '0');
        const hh = String(date.getHours()).padStart(2, '0');
        const mi = String(date.getMinutes()).padStart(2, '0');
        const ss = String(date.getSeconds()).padStart(2, '0');
        
        return `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}`;
    }

    // 导出公共API
    window.CronConfig = {
        showCronModal: showCronModal,
        hideCronModal: hideCronModal,
        handleCronTypeChange: handleCronTypeChange,
        toggleWeekDay: toggleWeekDay,
        addDailyTime: addDailyTime,
        removeDailyTime: removeDailyTime,
        addWeeklyTime: addWeeklyTime,
        removeWeeklyTime: removeWeeklyTime,
        applyCronSimple: applyCronSimple,
        parseCronExpression: parseCronExpression
    };

})(window);

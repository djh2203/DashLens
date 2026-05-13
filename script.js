const REFRESH_INTERVAL = 3000;
const GAUGE_CIRCUMFERENCE = 263.89;

let refreshTimer = null;

function updateDateTime() {
    const now = new Date();
    const dateStr = now.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        weekday: 'long'
    });
    const timeStr = now.toLocaleTimeString('zh-CN', { hour12: false });

    const dateEl = document.getElementById('current-date');
    const timeEl = document.getElementById('current-time');

    if (dateEl) dateEl.textContent = dateStr;
    if (timeEl) timeEl.textContent = timeStr;
}

function formatBytes(bytes) {
    if (bytes === 0 || bytes === undefined || bytes === null) return '--';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatUptime(seconds) {
    if (seconds === undefined || seconds === null || seconds < 0) return '--';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (days > 0) {
        return `${days}天 ${hours}时 ${minutes}分 ${secs}秒`;
    } else if (hours > 0) {
        return `${hours}时 ${minutes}分 ${secs}秒`;
    } else if (minutes > 0) {
        return `${minutes}分 ${secs}秒`;
    } else {
        return `${secs}秒`;
    }
}

function updateGauge(elementId, value, gradientId) {
    const gauge = document.getElementById(elementId);
    if (!gauge) return;

    const percent = Math.min(100, Math.max(0, value));
    const offset = GAUGE_CIRCUMFERENCE - (percent / 100) * GAUGE_CIRCUMFERENCE;
    gauge.style.strokeDashoffset = offset;

    if (gradientId === 'cpu-gradient') {
        gauge.style.stroke = 'url(#cpu-gradient)';
    } else if (gradientId === 'ram') {
        gauge.style.stroke = 'url(#ram-gradient)';
    }
}

function updateSystemInfo(data) {
    if (data.cpu_usage !== undefined) {
        const cpuValue = Math.round(data.cpu_usage);
        document.getElementById('cpu-value').textContent = cpuValue;
        document.getElementById('cpu-detail').textContent = data.cpu_usage + '%';
        updateGauge('cpu-progress', data.cpu_usage, 'cpu-gradient');
    }

    if (data.memory_used !== undefined && data.memory_total !== undefined) {
        const memPercent = data.memory_total > 0
            ? Math.round((data.memory_used / data.memory_total) * 100)
            : 0;
        document.getElementById('ram-value').textContent = memPercent;
        document.getElementById('ram-detail').textContent =
            formatBytes(data.memory_used) + ' / ' + formatBytes(data.memory_total);
        updateGauge('ram-progress', memPercent, 'ram');
    }

    if (data.disk_used !== undefined && data.disk_total !== undefined) {
        updateStorageBars(data);
    }

    if (data.internal_ip !== undefined) {
        const ipEl = document.getElementById('internal-ip');
        if (ipEl) ipEl.textContent = data.internal_ip;
    }

    if (data.uptime !== undefined) {
        const uptimeEl = document.getElementById('uptime');
        if (uptimeEl) uptimeEl.textContent = formatUptime(data.uptime);
    }
}

function updateStorageBars(data) {
    const container = document.getElementById('storage-bars');
    if (!container) return;

    const diskPercent = data.disk_total > 0
        ? Math.round((data.disk_used / data.disk_total) * 100)
        : 0;

    if (container.children.length === 0) {
        const item = document.createElement('div');
        item.className = 'storage-bar-item';
        item.innerHTML = `
            <span class="storage-bar-label">磁盘</span>
            <div class="storage-bar-container">
                <div class="storage-bar-fill" id="disk-fill" style="width: 0%"></div>
            </div>
            <span class="storage-bar-value" id="disk-value">-- / --</span>
        `;
        container.appendChild(item);
    }

    const diskFill = document.getElementById('disk-fill');
    const diskValue = document.getElementById('disk-value');

    if (diskFill) {
        diskFill.style.width = diskPercent + '%';
    }
    if (diskValue) {
        diskValue.textContent = formatBytes(data.disk_used) + ' / ' + formatBytes(data.disk_total);
    }
}

function updateDesktopStatus(data) {
    const isRunning = data.desktop_running === true;

    const statusCircle = document.getElementById('desktop-status');
    const statusText = document.getElementById('desktop-status-text');
    const desktopUptime = document.getElementById('desktop-uptime');
    const vncLink = document.getElementById('vnc-link');

    const startBtn = document.getElementById('start-desktop');
    const stopBtn = document.getElementById('stop-desktop');

    if (isRunning) {
        statusCircle.classList.add('running');
        statusText.textContent = '运行中';
        statusText.style.color = '#27ae60';

        startBtn.disabled = true;
        stopBtn.disabled = false;

        if (data.desktop_uptime !== undefined) {
            desktopUptime.textContent = formatUptime(data.desktop_uptime);
        }

        if (data.vnc_url !== undefined) {
            vncLink.href = data.vnc_url;
            vncLink.classList.remove('disabled');
        } else {
            vncLink.href = '#';
            vncLink.classList.add('disabled');
        }
    } else {
        statusCircle.classList.remove('running');
        statusText.textContent = '未运行';
        statusText.style.color = '#e74c3c';

        startBtn.disabled = false;
        stopBtn.disabled = true;

        desktopUptime.textContent = '--';
        vncLink.href = '#';
        vncLink.classList.add('disabled');
    }
}

function updateLastRefreshTime() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('zh-CN', { hour12: false });
    const refreshTimeEl = document.getElementById('refresh-time');
    if (refreshTimeEl) {
        refreshTimeEl.textContent = timeStr;
    }
}

function fetchStatus() {
    fetch('/api/status')
        .then(response => {
            if (!response.ok) {
                throw new Error('网络响应不正常');
            }
            return response.json();
        })
        .then(data => {
            updateSystemInfo(data);
            updateDesktopStatus(data);
            updateLastRefreshTime();
        })
        .catch(error => {
            console.error('获取状态失败:', error);
        });
}

function startDesktop() {
    fetch('/api/start-desktop', { method: 'POST' })
        .then(response => {
            if (!response.ok) {
                throw new Error('启动失败');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                fetchStatus();
            }
        })
        .catch(error => {
            console.error('启动桌面失败:', error);
        });
}

function stopDesktop() {
    fetch('/api/stop-desktop', { method: 'POST' })
        .then(response => {
            if (!response.ok) {
                throw new Error('关闭失败');
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                fetchStatus();
            }
        })
        .catch(error => {
            console.error('关闭桌面失败:', error);
        });
}

function init() {
    updateDateTime();
    setInterval(updateDateTime, 1000);

    fetchStatus();
    refreshTimer = setInterval(fetchStatus, REFRESH_INTERVAL);

    const startBtn = document.getElementById('start-desktop');
    const stopBtn = document.getElementById('stop-desktop');
    const refreshBtn = document.getElementById('refresh-btn');

    if (startBtn) startBtn.addEventListener('click', startDesktop);
    if (stopBtn) stopBtn.addEventListener('click', stopDesktop);
    if (refreshBtn) refreshBtn.addEventListener('click', fetchStatus);

    window.addEventListener('beforeunload', () => {
        if (refreshTimer) {
            clearInterval(refreshTimer);
        }
    });
}

document.addEventListener('DOMContentLoaded', init);
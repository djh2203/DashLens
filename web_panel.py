#!/usr/bin/env python3
import os
import sys
import json
import time
import threading
import socket
import subprocess
from datetime import datetime
from typing import Dict, Optional
from flask import Flask, render_template_string, jsonify, request
import psutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desktop_manager import DesktopManager

app = Flask(__name__)
desktop_manager: Optional[DesktopManager] = None
desktop_thread: Optional[threading.Thread] = None
desktop_running = False

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DashLens - 服务器面板</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            opacity: 0.9;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
        }
        
        .stat-title {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }
        
        .stat-unit {
            font-size: 0.5em;
            color: #999;
        }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #eee;
            border-radius: 4px;
            margin-top: 10px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            border-radius: 4px;
            transition: width 0.3s ease;
        }
        
        .control-panel {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        
        .control-panel h2 {
            margin-bottom: 20px;
            color: #333;
        }
        
        .button-group {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 15px 30px;
            border: none;
            border-radius: 10px;
            font-size: 1em;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .btn-start {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-start:hover {
            transform: scale(1.05);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        
        .btn-start:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        
        .btn-stop {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
        }
        
        .btn-stop:hover {
            transform: scale(1.05);
            box-shadow: 0 5px 20px rgba(245, 87, 108, 0.4);
        }
        
        .btn-stop:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        
        .status-online {
            background: #4CAF50;
            box-shadow: 0 0 10px #4CAF50;
        }
        
        .status-offline {
            background: #f44336;
            box-shadow: 0 0 10px #f44336;
        }
        
        .info-panel {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        
        .info-panel h2 {
            margin-bottom: 20px;
            color: #333;
        }
        
        .info-item {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #eee;
        }
        
        .info-item:last-child {
            border-bottom: none;
        }
        
        .info-label {
            color: #666;
        }
        
        .info-value {
            font-weight: bold;
            color: #333;
        }
        
        .desktop-link {
            margin-top: 20px;
            padding: 15px;
            background: #f0f0f0;
            border-radius: 8px;
            text-align: center;
        }
        
        .desktop-link a {
            color: #667eea;
            text-decoration: none;
            font-weight: bold;
        }
        
        .desktop-link a:hover {
            text-decoration: underline;
        }
        
        @media (max-width: 768px) {
            .header h1 {
                font-size: 1.8em;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .button-group {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🖥️ DashLens</h1>
            <p>Termux PRoot 服务器面板</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-title">CPU 使用率</div>
                <div class="stat-value" id="cpu-value">0<span class="stat-unit">%</span></div>
                <div class="progress-bar">
                    <div class="progress-fill" id="cpu-bar" style="width: 0%"></div>
                </div>
            </div>
            
            <div class="stat-card">
                <div class="stat-title">内存使用</div>
                <div class="stat-value" id="memory-value">0<span class="stat-unit">%</span></div>
                <div class="progress-bar">
                    <div class="progress-fill" id="memory-bar" style="width: 0%"></div>
                </div>
            </div>
            
            <div class="stat-card">
                <div class="stat-title">磁盘使用</div>
                <div class="stat-value" id="disk-value">0<span class="stat-unit">%</span></div>
                <div class="progress-bar">
                    <div class="progress-fill" id="disk-bar" style="width: 0%"></div>
                </div>
            </div>
            
            <div class="stat-card">
                <div class="stat-title">网络流量</div>
                <div class="stat-value" id="network-value">0<span class="stat-unit">KB/s</span></div>
            </div>
        </div>
        
        <div class="control-panel">
            <h2>🎮 桌面控制</h2>
            <div class="button-group">
                <button class="btn btn-start" id="start-btn" onclick="startDesktop()">
                    <span class="status-indicator status-offline" id="status-dot"></span>
                    启动桌面
                </button>
                <button class="btn btn-stop" id="stop-btn" onclick="stopDesktop()" disabled>
                    停止桌面
                </button>
            </div>
            <div class="desktop-link" id="desktop-link" style="display: none;">
                <a id="desktop-url" href="#" target="_blank">🚀 打开桌面</a>
            </div>
        </div>
        
        <div class="info-panel">
            <h2>📊 系统信息</h2>
            <div class="info-item">
                <span class="info-label">操作系统</span>
                <span class="info-value" id="os-info">-</span>
            </div>
            <div class="info-item">
                <span class="info-label">运行时间</span>
                <span class="info-value" id="uptime">-</span>
            </div>
            <div class="info-item">
                <span class="info-label">本地 IP</span>
                <span class="info-value" id="local-ip">-</span>
            </div>
            <div class="info-item">
                <span class="info-label">桌面状态</span>
                <span class="info-value" id="desktop-status">未运行</span>
            </div>
        </div>
    </div>
    
    <script>
        let lastNetworkStats = null;
        
        function updateStats() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('cpu-value').innerHTML = data.cpu.toFixed(1) + '<span class="stat-unit">%</span>';
                    document.getElementById('cpu-bar').style.width = data.cpu + '%';
                    
                    document.getElementById('memory-value').innerHTML = data.memory.toFixed(1) + '<span class="stat-unit">%</span>';
                    document.getElementById('memory-bar').style.width = data.memory + '%';
                    
                    document.getElementById('disk-value').innerHTML = data.disk.toFixed(1) + '<span class="stat-unit">%</span>';
                    document.getElementById('disk-bar').style.width = data.disk + '%';
                    
                    let networkSpeed = 0;
                    if (lastNetworkStats) {
                        networkSpeed = ((data.network_sent - lastNetworkStats.sent) + 
                                       (data.network_recv - lastNetworkStats.recv)) / 1024;
                    }
                    lastNetworkStats = {sent: data.network_sent, recv: data.network_recv};
                    
                    document.getElementById('network-value').innerHTML = networkSpeed.toFixed(1) + '<span class="stat-unit">KB/s</span>';
                    
                    document.getElementById('os-info').textContent = data.os;
                    document.getElementById('uptime').textContent = data.uptime;
                    document.getElementById('local-ip').textContent = data.ip;
                    
                    updateDesktopStatus(data.desktop_running);
                })
                .catch(error => console.error('Error:', error));
        }
        
        function updateDesktopStatus(running) {
            const statusDot = document.getElementById('status-dot');
            const startBtn = document.getElementById('start-btn');
            const stopBtn = document.getElementById('stop-btn');
            const desktopStatus = document.getElementById('desktop-status');
            const desktopLink = document.getElementById('desktop-link');
            const desktopUrl = document.getElementById('desktop-url');
            
            if (running) {
                statusDot.className = 'status-indicator status-online';
                startBtn.disabled = true;
                stopBtn.disabled = false;
                desktopStatus.textContent = '运行中';
                desktopLink.style.display = 'block';
                desktopUrl.href = 'http://' + document.getElementById('local-ip').textContent + ':6080/vnc.html';
            } else {
                statusDot.className = 'status-indicator status-offline';
                startBtn.disabled = false;
                stopBtn.disabled = true;
                desktopStatus.textContent = '未运行';
                desktopLink.style.display = 'none';
            }
        }
        
        function startDesktop() {
            fetch('/api/desktop/start', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('桌面启动中，请稍候...');
                    } else {
                        alert('启动失败: ' + data.error);
                    }
                })
                .catch(error => {
                    alert('请求失败: ' + error);
                });
        }
        
        function stopDesktop() {
            fetch('/api/desktop/stop', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('桌面已停止');
                    } else {
                        alert('停止失败: ' + data.error);
                    }
                })
                .catch(error => {
                    alert('请求失败: ' + error);
                });
        }
        
        setInterval(updateStats, 2000);
        updateStats();
    </script>
</body>
</html>
"""


def get_system_stats() -> Dict:
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    network = psutil.net_io_counters()
    
    uptime = time.time() - psutil.boot_time()
    uptime_hours = int(uptime // 3600)
    uptime_minutes = int((uptime % 3600) // 60)
    
    os_info = 'Unknown'
    if os.path.exists('/etc/alpine-release'):
        os_info = 'Alpine Linux'
    elif os.path.exists('/etc/debian_version'):
        os_info = 'Debian'
    elif os.path.exists('/etc/lsb-release'):
        os_info = 'Ubuntu'
    
    local_ip = '127.0.0.1'
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    
    return {
        'cpu': cpu_percent,
        'memory': memory.percent,
        'disk': disk.percent,
        'network_sent': network.bytes_sent,
        'network_recv': network.bytes_recv,
        'os': os_info,
        'uptime': f'{uptime_hours}h {uptime_minutes}m',
        'ip': local_ip,
        'desktop_running': desktop_running
    }


def run_desktop():
    global desktop_running, desktop_manager
    desktop_running = True
    try:
        desktop_manager = DesktopManager()
        desktop_manager.start()
    except Exception as e:
        print(f'桌面运行错误: {e}')
    finally:
        desktop_running = False


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/stats')
def stats():
    return jsonify(get_system_stats())


@app.route('/api/desktop/start', methods=['POST'])
def start_desktop():
    global desktop_thread, desktop_running
    
    if desktop_running:
        return jsonify({'success': False, 'error': '桌面已在运行中'})
    
    try:
        desktop_thread = threading.Thread(target=run_desktop, daemon=True)
        desktop_thread.start()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/desktop/stop', methods=['POST'])
def stop_desktop():
    global desktop_manager, desktop_running
    
    if not desktop_running or not desktop_manager:
        return jsonify({'success': False, 'error': '桌面未在运行'})
    
    try:
        desktop_manager.stop()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def main():
    host = '0.0.0.0'
    port = 5000
    
    print('=' * 50)
    print('  DashLens Web 面板')
    print(f'  访问地址: http://{get_system_stats()["ip"]}:{port}')
    print('=' * 50)
    
    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    main()
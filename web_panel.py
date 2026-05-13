#!/usr/bin/env python3
import os
import sys
import json
import time
import threading
import socket
import subprocess
import select
import fcntl
import termios
import struct
import re
from datetime import datetime
from typing import Dict, Optional, Any
from flask import Flask, render_template_string, jsonify, request, send_file
from flask_socketio import SocketIO, emit, join_room, leave_room
import psutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desktop_manager import DesktopManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dashlens_secret_key'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')

desktop_manager: Optional[DesktopManager] = None
desktop_thread: Optional[threading.Thread] = None
desktop_running = False

class TerminalSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.process = None
        self.thread = None
        self.running = False
        self.pid = None
    
    def start(self):
        try:
            self.process = subprocess.Popen(
                ['/bin/sh', '-i'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
                universal_newlines=False,
                bufsize=0
            )
            self.pid = self.process.pid
            self.running = True
            
            self.thread = threading.Thread(target=self._read_output, daemon=True)
            self.thread.start()
            
            socketio.emit('terminal_start', {'session_id': self.session_id}, room=self.session_id)
            return True
        except Exception as e:
            print(f'启动终端失败: {e}')
            return False
    
    def _read_output(self):
        while self.running and self.process:
            try:
                ready, _, _ = select.select([self.process.stdout], [], [], 0.1)
                if ready:
                    output = self.process.stdout.read(4096).decode('utf-8', errors='replace')
                    if output:
                        socketio.emit('terminal_output', {
                            'session_id': self.session_id,
                            'output': output
                        }, room=self.session_id)
                
                if self.process.poll() is not None:
                    break
            except Exception as e:
                print(f'读取终端输出失败: {e}')
                break
        
        self.running = False
    
    def send_command(self, command: str):
        if self.process and self.running:
            try:
                self.process.stdin.write(command.encode('utf-8'))
                self.process.stdin.flush()
                return True
            except Exception as e:
                print(f'发送命令失败: {e}')
                return False
        return False
    
    def resize(self, rows: int, cols: int):
        if self.process and self.running:
            try:
                winsize = struct.pack('HHHH', rows, cols, 0, 0)
                fcntl.ioctl(self.process.stdout.fileno(), termios.TIOCSWINSZ, winsize)
                return True
            except Exception as e:
                print(f'调整窗口大小失败: {e}')
                return False
        return False
    
    def stop(self):
        self.running = False
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), 9)
            except Exception as e:
                print(f'终止进程失败: {e}')
            self.process = None

terminal_sessions: Dict[str, TerminalSession] = {}


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DashLens - 服务器面板</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.min.css">
    <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
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
            max-width: 1400px;
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
        
        .btn-terminal {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
        }
        
        .btn-terminal:hover {
            transform: scale(1.05);
            box-shadow: 0 5px 20px rgba(79, 172, 254, 0.4);
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
            margin-bottom: 30px;
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
        
        .terminal-panel {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        
        .terminal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .terminal-header h2 {
            color: #333;
        }
        
        .terminal-container {
            border-radius: 10px;
            overflow: hidden;
            border: 2px solid #333;
        }
        
        #terminal {
            height: 400px;
            font-size: 14px;
        }
        
        .terminal-status {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.9em;
            color: #666;
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
            
            #terminal {
                height: 300px;
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
                <button class="btn btn-terminal" id="terminal-btn" onclick="toggleTerminal()">
                    🖥️ 终端
                </button>
            </div>
            <div class="desktop-link" id="desktop-link" style="display: none;">
                <a id="desktop-url" href="#" target="_blank">🚀 打开桌面</a>
            </div>
        </div>
        
        <div class="terminal-panel" id="terminal-panel" style="display: none;">
            <div class="terminal-header">
                <h2>💻 Web 终端</h2>
                <div class="terminal-status">
                    <span class="status-indicator status-offline" id="terminal-status"></span>
                    <span id="terminal-status-text">未连接</span>
                </div>
            </div>
            <div class="terminal-container">
                <div id="terminal"></div>
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
        let term = null;
        let socket = null;
        let terminalConnected = false;
        
        function initTerminal() {
            if (term) return;
            
            term = new Terminal({
                cursorBlink: true,
                fontSize: 14,
                fontFamily: 'Monaco, "Courier New", monospace',
                theme: {
                    background: '#1e1e1e',
                    foreground: '#d4d4d4',
                    cursor: '#aeafad',
                    selection: '#264f78',
                    black: '#0d0d0d',
                    red: '#f14c4c',
                    green: '#6a9955',
                    yellow: '#dcdcaa',
                    blue: '#569cd6',
                    magenta: '#c586c0',
                    cyan: '#4ec9b0',
                    white: '#d4d4d4',
                    brightBlack: '#666666',
                    brightRed: '#f14c4c',
                    brightGreen: '#6a9955',
                    brightYellow: '#dcdcaa',
                    brightBlue: '#569cd6',
                    brightMagenta: '#c586c0',
                    brightCyan: '#4ec9b0',
                    brightWhite: '#ffffff'
                }
            });
            
            const fitAddon = new FitAddon.FitAddon();
            term.loadAddon(fitAddon);
            term.open(document.getElementById('terminal'));
            fitAddon.fit();
            
            window.addEventListener('resize', () => {
                fitAddon.fit();
                resizeTerminal();
            });
            
            term.onData((data) => {
                if (socket && terminalConnected) {
                    socket.emit('command', { data: data });
                }
            });
            
            connectSocket();
        }
        
        function connectSocket() {
            if (socket) {
                socket.disconnect();
            }
            
            socket = io();
            
            socket.on('connect', () => {
                terminalConnected = true;
                updateTerminalStatus(true);
                socket.emit('start_terminal');
            });
            
            socket.on('disconnect', () => {
                terminalConnected = false;
                updateTerminalStatus(false);
            });
            
            socket.on('terminal_output', (data) => {
                if (term) {
                    term.write(data.output);
                }
            });
            
            socket.on('terminal_start', () => {
                if (term) {
                    term.write('欢迎使用 DashLens Web 终端!\r\n');
                }
            });
        }
        
        function resizeTerminal() {
            if (term && terminalConnected) {
                const size = term.proposeGeometry();
                if (size && socket) {
                    socket.emit('resize', { rows: size.rows, cols: size.cols });
                }
            }
        }
        
        function updateTerminalStatus(connected) {
            const statusDot = document.getElementById('terminal-status');
            const statusText = document.getElementById('terminal-status-text');
            
            if (connected) {
                statusDot.className = 'status-indicator status-online';
                statusText.textContent = '已连接';
            } else {
                statusDot.className = 'status-indicator status-offline';
                statusText.textContent = '未连接';
            }
        }
        
        function toggleTerminal() {
            const panel = document.getElementById('terminal-panel');
            const btn = document.getElementById('terminal-btn');
            
            if (panel.style.display === 'none') {
                panel.style.display = 'block';
                btn.textContent = '✕ 关闭终端';
                setTimeout(() => {
                    initTerminal();
                }, 100);
            } else {
                panel.style.display = 'none';
                btn.textContent = '🖥️ 终端';
                if (socket) {
                    socket.disconnect();
                    socket = null;
                }
            }
        }
        
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


def get_cpu_temperature() -> float:
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                for entry in entries:
                    if entry.current > 0:
                        return entry.current
        return 0.0
    except Exception:
        return 0.0

def get_cpu_info() -> str:
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('model name'):
                    return line.split(':')[1].strip()
        return 'Unknown'
    except Exception:
        return 'Unknown'

def get_kernel_version() -> str:
    try:
        with open('/proc/version', 'r') as f:
            line = f.readline()
            parts = line.split()
            if len(parts) >= 3:
                return parts[2]
        return 'Unknown'
    except Exception:
        return 'Unknown'

def get_fastfetch_info() -> Dict:
    info = {}
    try:
        result = subprocess.run(['fastfetch', '--json'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    for key, value in data.items():
                        info[key.lower()] = value
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            if 'type' in item and 'value' in item:
                                info[item['type'].lower()] = item['value']
                            elif 'key' in item and 'value' in item:
                                info[item['key'].lower()] = item['value']
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return info

def parse_disk_from_fastfetch(disk_used: int, disk_total: int, fastfetch_info: Dict) -> float:
    disk_percent = round((disk_used / disk_total) * 100, 1) if disk_total > 0 else 0.0
    if 'disk' in fastfetch_info:
        disk_str = str(fastfetch_info['disk'])
        match = re.search(r'\((\d+)%\)', disk_str)
        if match:
            disk_percent = float(match.group(1))
    return disk_percent

def get_hostname() -> str:
    try:
        with open('/etc/hostname', 'r') as f:
            return f.read().strip()
    except Exception:
        return 'Unknown'

def get_gpu_info() -> str:
    try:
        result = subprocess.run(['lspci', '-nnk'], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'VGA' in line or '3D controller' in line:
                    parts = line.split(':')
                    if len(parts) >= 3:
                        return parts[2].strip()
        return 'Unknown'
    except FileNotFoundError:
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if 'Hardware' in line:
                        return line.split(':')[1].strip()
        except Exception:
            pass
        return 'Unknown'

def get_system_stats() -> Dict:
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    try:
        network = psutil.net_io_counters()
        network_sent = network.bytes_sent
        network_recv = network.bytes_recv
    except PermissionError:
        network_sent = 0
        network_recv = 0
    
    uptime = time.time() - psutil.boot_time()
    uptime_hours = int(uptime // 3600)
    uptime_minutes = int((uptime % 3600) // 60)
    
    os_info = 'Unknown'
    if os.path.exists('/etc/alpine-release'):
        with open('/etc/alpine-release', 'r') as f:
            os_info = f'Alpine Linux {f.read().strip()}'
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
    
    cpu_temp = get_cpu_temperature()
    cpu_name = get_cpu_info()
    kernel = get_kernel_version()
    hostname = get_hostname()
    gpu_info = get_gpu_info()
    
    swap = psutil.swap_memory()
    
    fastfetch_info = get_fastfetch_info()
    
    if 'os' in fastfetch_info and fastfetch_info['os']:
        os_info = fastfetch_info['os']
    if 'kernel' in fastfetch_info and fastfetch_info['kernel']:
        kernel = fastfetch_info['kernel']
    if 'host' in fastfetch_info and fastfetch_info['host']:
        hostname = fastfetch_info['host']
    if 'gpu' in fastfetch_info and fastfetch_info['gpu']:
        gpu_info = fastfetch_info['gpu']
    if 'cpu' in fastfetch_info and fastfetch_info['cpu']:
        cpu_name = fastfetch_info['cpu']
    
    disk_percent = parse_disk_from_fastfetch(disk.used, disk.total, fastfetch_info)
    
    return {
        'cpu': cpu_percent,
        'memory': memory.percent,
        'disk': disk.percent,
        'network_sent': network_sent,
        'network_recv': network_recv,
        'os': os_info,
        'uptime': f'{uptime_hours}h {uptime_minutes}m',
        'ip': local_ip,
        'desktop_running': desktop_running,
        'cpu_usage': cpu_percent,
        'memory_used': memory.used,
        'memory_total': memory.total,
        'disk_used': disk.used,
        'disk_total': disk.total,
        'disk_percent': disk_percent,
        'internal_ip': local_ip,
        'cpu_temp': cpu_temp,
        'cpu_name': cpu_name,
        'kernel': kernel,
        'swap_used': swap.used,
        'swap_total': swap.total,
        'swap_percent': swap.percent,
        'hostname': hostname,
        'gpu': gpu_info
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


@socketio.on('connect')
def handle_connect():
    print(f'客户端连接: {request.sid}')


@socketio.on('disconnect')
def handle_disconnect():
    session_id = request.sid
    if session_id in terminal_sessions:
        terminal_sessions[session_id].stop()
        del terminal_sessions[session_id]
    print(f'客户端断开: {session_id}')


@socketio.on('start_terminal')
def handle_start_terminal():
    session_id = request.sid
    if session_id not in terminal_sessions:
        terminal_sessions[session_id] = TerminalSession(session_id)
        terminal_sessions[session_id].start()
        join_room(session_id)


@socketio.on('command')
def handle_command(data):
    session_id = request.sid
    if session_id in terminal_sessions:
        terminal_sessions[session_id].send_command(data.get('data', ''))


@socketio.on('resize')
def handle_resize(data):
    session_id = request.sid
    if session_id in terminal_sessions:
        terminal_sessions[session_id].resize(
            data.get('rows', 24),
            data.get('cols', 80)
        )


@app.route('/style.css')
def style_css():
    return send_file('style.css')

@app.route('/script.js')
def script_js():
    return send_file('script.js')

@app.route('/')
def index():
    return send_file('index.html')


@app.route('/api/stats')
def stats():
    return jsonify(get_system_stats())


@app.route('/api/status')
def status():
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
    
    socketio.run(app, host=host, port=port, debug=False)


if __name__ == '__main__':
    main()
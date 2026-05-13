#!/usr/bin/env python3
import os
import sys
import subprocess
import signal
import time
import logging
import socket
import psutil
from pathlib import Path
from typing import Optional, Dict, List

class DesktopManager:
    def __init__(self, config: Dict = None):
        self.config = config or self.get_default_config()
        self.processes: Dict[str, subprocess.Popen] = {}
        self.logger = self.setup_logging()
        self.running = False
        
    def get_default_config(self) -> Dict:
        return {
            'log_file': os.path.expanduser('~/desktop.log'),
            'novnc_path': '/opt/novnc',
            'vnc_pass': '/etc/x11vnc.pass',
            'idle_timeout': 30,
            'display_num': 1,
            'resolution': '1280x720x16',
            'vnc_port': 5901,
            'websockify_port': 6080,
            'phone_ip': self.get_local_ip(),
            'check_interval': 5
        }
    
    def setup_logging(self) -> logging.Logger:
        logger = logging.getLogger('DesktopManager')
        logger.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        file_handler = logging.FileHandler(self.config['log_file'])
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return '127.0.0.1'
    
    def detect_os(self) -> str:
        if os.path.exists('/etc/alpine-release'):
            return 'alpine'
        elif os.path.exists('/etc/debian_version'):
            return 'debian'
        elif os.path.exists('/etc/lsb-release'):
            return 'ubuntu'
        return 'unknown'
    
    def cleanup(self):
        self.logger.info('开始回收资源...')
        
        kill_patterns = [
            f"Xvfb :{self.config['display_num']}",
            f"x11vnc.*:{self.config['display_num']}",
            f"websockify.*{self.config['websockify_port']}",
            'xfce4-session',
            'xfwm4',
            'Thunar'
        ]
        
        for pattern in kill_patterns:
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = ' '.join(proc.info['cmdline'] or [])
                        if pattern in cmdline:
                            self.logger.info(f'终止进程: {proc.info["pid"]} - {cmdline[:50]}')
                            proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except Exception as e:
                self.logger.warning(f'清理进程时出错: {e}')
        
        for name, proc in self.processes.items():
            try:
                if proc.poll() is None:
                    proc.terminate()
                    time.sleep(0.5)
                    if proc.poll() is None:
                        proc.kill()
            except Exception as e:
                self.logger.warning(f'终止 {name} 时出错: {e}')
        
        self.processes.clear()
        
        lock_files = [
            f"/tmp/.X{self.config['display_num']}-lock",
            f"/tmp/.X11-unix/X{self.config['display_num']}"
        ]
        
        for lock_file in lock_files:
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                    self.logger.info(f'删除锁文件: {lock_file}')
            except Exception as e:
                self.logger.warning(f'删除锁文件时出错: {e}')
        
        self.logger.info('所有进程已关闭，资源已释放')
    
    def run_command(self, cmd: str, background: bool = False, 
                   env: Dict = None, wait: bool = False) -> Optional[subprocess.Popen]:
        try:
            full_env = os.environ.copy()
            if env:
                full_env.update(env)
            
            self.logger.info(f'执行命令: {cmd}')
            
            if background:
                proc = subprocess.Popen(
                    cmd,
                    shell=True,
                    env=full_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid if sys.platform != 'win32' else None
                )
                return proc
            else:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    env=full_env,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    self.logger.error(f'命令执行失败: {result.stderr}')
                return None
        except Exception as e:
            self.logger.error(f'执行命令时出错: {e}')
            return None
    
    def check_dependencies(self) -> bool:
        required_commands = ['Xvfb', 'x11vnc', 'startxfce4', 'websockify']
        missing = []
        
        for cmd in required_commands:
            try:
                subprocess.run(['which', cmd], capture_output=True, check=True)
            except subprocess.CalledProcessError:
                missing.append(cmd)
        
        if missing:
            self.logger.error(f'缺少依赖: {", ".join(missing)}')
            return False
        
        return True
    
    def setup_vnc_password(self):
        if not os.path.exists(self.config['vnc_pass']):
            self.logger.info('首次运行，需要设置 VNC 密码')
            try:
                subprocess.run(
                    ['x11vnc', '-storepasswd', self.config['vnc_pass']],
                    check=True
                )
                self.logger.info('VNC 密码已保存')
            except subprocess.CalledProcessError as e:
                self.logger.error(f'设置 VNC 密码失败: {e}')
                raise
    
    def start_xvfb(self) -> bool:
        display = f":{self.config['display_num']}"
        cmd = f"Xvfb {display} -screen 0 {self.config['resolution']} -nolisten tcp"
        
        proc = self.run_command(cmd, background=True)
        if not proc:
            return False
        
        self.processes['xvfb'] = proc
        time.sleep(2)
        
        if proc.poll() is None:
            self.logger.info(f'Xvfb 已启动 (PID: {proc.pid})')
            return True
        else:
            self.logger.error('Xvfb 启动失败')
            return False
    
    def start_dbus(self) -> bool:
        os_type = self.detect_os()
        
        try:
            os.makedirs('/run/dbus', exist_ok=True)
            
            if os_type == 'alpine':
                self.run_command('dbus-daemon --system --fork')
            else:
                result = subprocess.run(['dbus-launch', '--sh-syntax', '--exit-with-session'],
                                      capture_output=True, text=True, check=True)
                for line in result.stdout.split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
            
            self.logger.info('D-Bus 已启动')
            return True
        except Exception as e:
            self.logger.warning(f'D-Bus 启动警告: {e}')
            return True
    
    def start_xfce(self) -> bool:
        display = f":{self.config['display_num']}"
        env = {'DISPLAY': display}
        
        cmd = 'startxfce4'
        proc = self.run_command(cmd, background=True, env=env)
        if not proc:
            return False
        
        self.processes['xfce'] = proc
        time.sleep(5)
        
        try:
            subprocess.run(['pgrep', '-f', 'xfce4-session'], check=True, capture_output=True)
            self.logger.info('Xfce 会话已启动')
            return True
        except subprocess.CalledProcessError:
            self.logger.warning('Xfce 会话可能未成功启动，但继续尝试...')
            return True
    
    def start_x11vnc(self) -> bool:
        display = f":{self.config['display_num']}"
        cmd = (f"x11vnc -display {display} -forever -shared "
               f"-rfbauth {self.config['vnc_pass']} "
               f"-rfbport {self.config['vnc_port']} -xkb")
        
        env = {'DISPLAY': display}
        proc = self.run_command(cmd, background=True, env=env)
        if not proc:
            return False
        
        self.processes['x11vnc'] = proc
        time.sleep(3)
        
        if proc.poll() is None:
            self.logger.info(f'x11vnc 已启动 (PID: {proc.pid}), 端口 {self.config["vnc_port"]}')
            return True
        else:
            self.logger.error('x11vnc 启动失败')
            return False
    
    def start_websockify(self) -> bool:
        cmd = (f"websockify --web={self.config['novnc_path']} "
               f"{self.config['websockify_port']} "
               f"localhost:{self.config['vnc_port']}")
        
        proc = self.run_command(cmd, background=True)
        if not proc:
            return False
        
        self.processes['websockify'] = proc
        time.sleep(2)
        
        if proc.poll() is None:
            self.logger.info(f'noVNC 代理已启动 (PID: {proc.pid}), 端口 {self.config["websockify_port"]}')
            return True
        else:
            self.logger.error('noVNC 代理启动失败')
            return False
    
    def check_active_connections(self) -> bool:
        try:
            result = subprocess.run(
                ['ss', '-Htn', 'state', 'established'],
                capture_output=True,
                text=True
            )
            
            ports = [self.config['vnc_port'], self.config['websockify_port']]
            for port in ports:
                if f':{port}' in result.stdout:
                    return True
            return False
        except Exception as e:
            self.logger.warning(f'检查连接时出错: {e}')
            return False
    
    def monitor_idle(self):
        self.logger.info('开始监控连接状态...')
        count = 0
        timeout = self.config['idle_timeout']
        interval = self.config['check_interval']
        
        while self.running and count < timeout:
            time.sleep(interval)
            
            if self.check_active_connections():
                if count != 0:
                    self.logger.info('检测到活动连接，重置空闲计数器')
                count = 0
            else:
                count += interval
                print(f'\r  空闲中: {count}/{timeout} 秒...', end='', flush=True)
        
        print()
    
    def start(self):
        self.running = True
        
        self.logger.info('=' * 50)
        self.logger.info('  按需桌面启动脚本')
        self.logger.info(f'  操作系统: {self.detect_os()}')
        self.logger.info(f'  手机IP: {self.config["phone_ip"]}')
        self.logger.info('=' * 50)
        
        if not self.check_dependencies():
            self.logger.error('依赖检查失败，请安装必要的软件包')
            return False
        
        self.cleanup()
        
        try:
            self.setup_vnc_password()
            
            steps = [
                ('启动虚拟 X 服务器 (Xvfb)', self.start_xvfb),
                ('启动 D-Bus', self.start_dbus),
                ('启动 Xfce 桌面', self.start_xfce),
                ('启动 x11vnc 服务器', self.start_x11vnc),
                ('启动 noVNC 代理', self.start_websockify)
            ]
            
            for i, (desc, func) in enumerate(steps, 1):
                self.logger.info(f'[{i}/{len(steps)}] {desc}...')
                if not func():
                    self.logger.error(f'{desc} 失败')
                    self.cleanup()
                    return False
            
            self.logger.info('')
            self.logger.info('=' * 50)
            self.logger.info('  ✅ 桌面已成功启动！')
            self.logger.info(f'  访问地址: http://{self.config["phone_ip"]}:{self.config["websockify_port"]}/vnc.html')
            self.logger.info(f'  空闲超时: {self.config["idle_timeout"]} 秒')
            self.logger.info('=' * 50)
            self.logger.info('')
            
            self.monitor_idle()
            
            if self.running:
                self.cleanup()
            
            return True
            
        except KeyboardInterrupt:
            self.logger.info('收到中断信号，正在清理...')
            self.cleanup()
            return True
        except Exception as e:
            self.logger.error(f'启动失败: {e}')
            self.cleanup()
            return False
    
    def stop(self):
        self.running = False
        self.cleanup()


if __name__ == '__main__':
    manager = DesktopManager()
    manager.start()
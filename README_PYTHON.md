# DashLens - Python 实现的桌面管理器

## 📋 概述

这是用 Python 重写的桌面启动脚本，完全替代原来的 shell 脚本，具有更好的跨平台兼容性和错误处理能力。

## 🎯 主要特性

- ✅ **跨平台兼容**：自动检测并适配 Alpine、Debian、Ubuntu
- ✅ **智能进程管理**：使用 psutil 进行精确的进程控制
- ✅ **完善的错误处理**：详细的日志记录和异常处理
- ✅ **Web 控制面板**：实时系统监控 + 一键启停桌面
- ✅ **Web 终端**：浏览器中直接执行命令，无需 SSH
- ✅ **空闲自动清理**：无连接时自动释放资源
- ✅ **配置文件支持**：可自定义各项参数

## 📁 文件说明

- `desktop_manager.py` - 核心桌面管理器（替代 start-desktop.sh）
- `web_panel.py` - Web 控制面板（替代 panel-server.py）
- `dashlens.py` - 统一入口脚本
- `config.json` - 配置文件
- `requirements.txt` - Python 依赖

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动 Web 面板（推荐）

```bash
python3 dashlens.py web
```

然后在浏览器访问 `http://手机IP:5000`

### 3. 直接启动桌面

```bash
python3 dashlens.py
```

## ⚙️ 配置说明

编辑 `config.json` 来自定义配置：

```json
{
    "log_file": "~/desktop.log",        // 日志文件路径
    "novnc_path": "/opt/novnc",         // noVNC 安装路径
    "vnc_pass": "/etc/x11vnc.pass",     // VNC 密码文件
    "idle_timeout": 30,                 // 空闲超时（秒）
    "display_num": 1,                   // 显示编号
    "resolution": "1280x720x16",        // 分辨率
    "vnc_port": 5901,                   // VNC 端口
    "websockify_port": 6080,            // Websockify 端口
    "web_panel_port": 5000,             // Web 面板端口
    "check_interval": 5                 // 检查间隔（秒）
}
```

## 🔧 系统依赖

### Alpine Linux

```bash
apk add xvfb x11vnc xfce4 xfce4-terminal dbus-x11 xrdb \
        websockify git python3 py3-pip net-tools iproute2 procps
```

### Debian/Ubuntu

```bash
apt-get install xvfb x11vnc xfce4 xfce4-terminal dbus-x11 xrdb \
        websockify git python3 python3-pip net-tools iproute2 procps
```

## 🌐 使用方式

### 方式一：Web 面板（推荐）

1. 启动 Web 面板：
   ```bash
   python3 dashlens.py web
   ```

2. 浏览器访问：`http://手机IP:5000`

3. 点击"启动桌面"按钮

4. 点击"打开桌面"链接访问 VNC

### 方式二：命令行直接启动

```bash
python3 dashlens.py
```

## 📊 Web 面板功能

- **实时监控**：CPU、内存、磁盘、网络使用率
- **桌面控制**：一键启动/停止桌面
- **Web 终端**：点击"终端"按钮打开命令行，支持所有命令操作
- **系统信息**：操作系统、运行时间、IP 地址
- **自动更新**：每 2 秒刷新数据

## 💻 Web 终端使用说明

Web 终端提供完整的命令行体验，无需 SSH 或密码：

1. 打开 Web 面板后，点击"终端"按钮
2. 等待终端连接（状态显示"已连接"）
3. 即可直接输入命令，支持：
   - `ls`, `cd`, `cat`, `mkdir` 等基础命令
   - `top`, `htop` 等系统监控命令
   - 环境变量和命令历史
   - 窗口大小自动适配

> ⚠️ 注意：Web 终端以运行面板的用户身份执行命令，请谨慎操作。

## 🔍 与 Shell 脚本对比

| 特性 | Shell 脚本 | Python 实现 |
|------|-----------|-----------|
| 跨平台兼容 | ⚠️ 需手动适配 | ✅ 自动检测 |
| 进程管理 | ⚠️ 基础 kill | ✅ psutil 精确控制 |
| 错误处理 | ⚠️ 有限 | ✅ 完善 |
| 日志记录 | ✅ | ✅ 更详细 |
| Web 面板 | ✅ | ✅ 更美观 |
| 配置管理 | ⚠️ 硬编码 | ✅ JSON 配置 |
| 代码可读性 | ⚠️ | ✅ 面向对象 |

## 🐛 常见问题

### 1. ImportError: No module named 'psutil'

```bash
pip install psutil
```

### 2. ImportError: No module named 'flask'

```bash
pip install flask
```

### 3. 权限错误

确保脚本有执行权限：
```bash
chmod +x dashlens.py
```

### 4. 端口被占用

修改 `config.json` 中的端口配置

## 📝 日志查看

```bash
tail -f ~/desktop.log
```

## 🔄 从 Shell 脚本迁移

1. 备份原脚本：
   ```bash
   mv start-desktop.sh start-desktop.sh.bak
   ```

2. 安装 Python 依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 测试新脚本：
   ```bash
   python3 dashlens.py
   ```

4. 确认无误后，可以删除原脚本

## 💡 优化建议

1. **降低分辨率**：如果性能不足，修改 `config.json` 中的 `resolution` 为 `1024x576x16`
2. **调整超时时间**：根据使用习惯调整 `idle_timeout`
3. **使用 systemd**：可以将 Web 面板设为开机自启

## 📄 许可证

MIT License
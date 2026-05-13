# Web终端功能实现计划

## 📋 需求分析

用户希望在DashLens Web面板中添加命令行终端功能，像SSH一样无需密码即可执行命令。

## 🎯 方案选择

选择 **xterm.js + Flask-SocketIO** 方案，理由：
- 完整的交互式终端体验
- 与现有Flask应用无缝集成
- 支持所有终端命令（cd、vi、top等）
- 良好的安全性和扩展性

## 📁 修改文件

### 1. web_panel.py
- 添加Flask-SocketIO支持
- 创建终端会话管理
- 添加WebSocket消息处理

### 2. HTML模板
- 添加xterm.js引用
- 添加终端面板UI
- 添加终端JavaScript逻辑

### 3. requirements.txt
- 添加Flask-SocketIO依赖

## 🚀 实现步骤

### 步骤1：安装依赖
```bash
pip install flask-socketio eventlet
```

### 步骤2：修改web_panel.py
- 引入flask_socketio
- 创建SocketIO实例
- 实现终端会话管理类
- 添加socket事件处理

### 步骤3：更新HTML模板
- 添加xterm.js CDN引用
- 添加终端容器和样式
- 添加终端JavaScript代码

### 步骤4：测试验证
- 启动Web面板
- 测试终端功能

## ⚠️ 风险处理

### 安全风险
- 终端直接暴露系统命令执行
- **解决方案**：
  1. 限制允许执行的命令（可选）
  2. 仅允许本地或内网访问
  3. 添加访问日志记录

### 性能风险
- 多个终端会话可能占用资源
- **解决方案**：
  1. 设置会话超时自动关闭
  2. 限制最大并发会话数

## 📋 任务清单

1. ✅ 分析需求和方案选择
2. 🚧 修改web_panel.py添加SocketIO支持
3. 🚧 更新HTML模板添加终端UI
4. 🚧 更新requirements.txt
5. 🚧 测试验证

## 📝 代码结构

```
web_panel.py
├── TerminalSession类（管理单个终端会话）
├── socketio.on('connect') - 处理新连接
├── socketio.on('disconnect') - 处理断开连接
├── socketio.on('command') - 处理命令输入
└── socketio.on('resize') - 处理窗口大小调整
```

## 📅 预计耗时

约30-45分钟完成实现和测试
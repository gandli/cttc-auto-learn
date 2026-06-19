# 📚 cttc-auto-learn · CDP 版本

烟草网络学院 (mooc.ctt.cn) 自动学习助手 — Chrome DevTools Protocol 版本。

## ✨ 特点

- 🔌 **CDP 连接** — 连接已运行的 Chrome，无需启动新浏览器
- 🔐 **复用登录** — 直接使用 Chrome 已登录的会话
- 📡 **API 优先** — 通过 CDP 执行 fetch 请求获取数据
- 🎯 **四种模式** — 刷任务、刷专题、刷课程、刷学时

## 🚀 使用方法

### 1. 启动 Chrome（开启远程调试）

```bash
# Windows
chrome.exe --remote-debugging-port=9222

# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# Linux
google-chrome --remote-debugging-port=9222
```

### 2. 安装依赖

```bash
pip install websockets
```

### 3. 运行脚本

```bash
python cdp_auto_learn.py
```

### 4. 参数说明

```bash
# 刷学时（默认）
python cdp_auto_learn.py --mode hours --target 50

# 刷任务
python cdp_auto_learn.py --mode tasks

# 刷专题
python cdp_auto_learn.py --mode topics

# 刷课程
python cdp_auto_learn.py --mode courses

# 指定 Chrome 调试端口
python cdp_auto_learn.py --port 9222

# 无头模式（不打开新标签页）
python cdp_auto_learn.py --headless
```

## ⚠️ 注意事项

- 必须先启动 Chrome 并开启 `--remote-debugging-port=9222`
- Chrome 中需要已登录烟草网络学院（或脚本会提示扫码）
- 每次只能播放一个视频（平台限制）
- 不要手动操作脚本正在控制的标签页

## 📄 License

MIT

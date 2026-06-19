# 📚 cttc-auto-learn · CDP 版 (Agent SKILL)

烟草网络学院 (mooc.ctt.cn) 自动学习 — 通过 Agent SKILL 安装，Agent 使用 chrome-devtools MCP 控制你的 Chrome。

## ✨ 特点

- 🔌 **复用 Chrome** — 连接你已打开的 Chrome，不用启动新浏览器
- 🔐 **复用登录** — 直接使用已登录的会话，不用重新扫码
- 🤖 **Agent 驱动** — 安装 SKILL 后，说"帮我刷学时"即可
- 🚫 **零依赖** — 不需要 Playwright、Python 虚拟环境

## 📦 安装

```bash
npx skills add gandli/cttc-auto-learn-cdp
```

## 🚀 使用

安装后对 Agent 说：

```
帮我刷学时
帮我刷专题
帮我刷课程
帮我刷任务
帮我刷班级
```

Agent 会自动：
1. 连接你的 Chrome
2. 检查登录状态（未登录则引导扫码）
3. 获取课程/任务/数据
4. 自动播放视频
5. 监控进度，完成后汇报

## ⚠️ 注意事项

- 需要 chrome-devtools MCP（Hermes 默认已配置）
- Chrome 需要已打开（MCP 会自动启动）
- 每次只能播放一个视频（平台限制）
- 不要手动操作 Agent 正在控制的标签页

## 📄 License

MIT

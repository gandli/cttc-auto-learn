# 烟草网络学院 防挂机刷课机制 完整分析

> 逆向自 study.js (805KB)

---

## 一、机制总览

| # | 机制 | 触发条件 | 后果 | 应对 |
|---|------|---------|------|------|
| 1 | 鼠标停留检测 | 无鼠标移动超过 N 分钟 | 暂停播放 | 定时触发鼠标事件 |
| 2 | 窗口焦点检测 | 窗口失去焦点 | 暂停播放 | 保持窗口焦点 |
| 3 | 多客户端检测 | 同账号多设备同时学习 | 踢掉旧连接/跳转错误页 | 单实例运行 |
| 4 | WebSocket 心跳 | 连接断开 | 进度不计入 | 保持 WS 连接 |
| 5 | 同时学习冲突 | API 返回 40909 | 停止当前学习 | 单实例运行 |
| 6 | 倍速检测 | 使用倍速播放 | 首次弹提示（不影响学时） | 正常速度 |
| 7 | 视频水印 | 视频播放时 | 显示用户名水印 | 不影响 |
| 8 | 页面关闭 | 关闭/刷新页面 | 提交最终进度 | 正常关闭 |
| 9 | 进度防刷 | 提交间隔 < 3 分钟 | 忽略提交 | 保持 3 分钟间隔 |

---

## 二、详细分析

### 2.1 鼠标停留检测（checkMouseStayTime）

**触发条件**：`pauseTime` 分钟内无鼠标移动（默认 30 分钟）

**源码逻辑**：
```javascript
checkMouseStayTime: function() {
    var t = 3600000;  // 默认 1 小时
    if (rule.enableAuti !== 1) return;  // 未启用则跳过
    t = 60 * parseInt(rule.pauseTime) * 1000;  // 转为毫秒

    // 监听 mousemove，每次移动重置计时器
    $(document).on("mousemove", function() {
        clearTimeout(timer);
        timer = setTimeout(function() {
            // 超时 → 暂停播放
            $(document).off("mousemove");
            player.pause();
            // 显示弹窗，用户操作后恢复
            showAlert(function() {
                player.play();
                $(document).on("mousemove", timer);
            });
        }, t);
    });
}
```

**应对**：
```python
# 定时触发鼠标移动事件（每 N-5 分钟）
await page.evaluate("""() => {
    document.dispatchEvent(new MouseEvent('mousemove', {
        clientX: Math.random() * 800 + 100,
        clientY: Math.random() * 400 + 100
    }));
}""")
```

---

### 2.2 窗口焦点检测（blur/focus）

**触发条件**：浏览器窗口失去焦点

**源码逻辑**：
```javascript
$(window).on("blur", function() { player.pause(); });
$(window).on("focus", function() { player.play(); });
```

**效果**：切换到其他窗口时自动暂停，切回时自动播放

**应对**：
- 使用 headless 模式（无焦点概念）
- 或保持 Playwright 窗口在前台：`await page.bring_to_front()`

---

### 2.3 多客户端检测（WebSocket + enableUnique）

**触发条件**：同账号在多个设备/浏览器同时学习

**源码逻辑**：
```javascript
// 进入课程时检查
if (rule.enableUnique === 1) {
    WS.connect(courseId);  // 建立 WebSocket 连接
}

// 收到 "multipleClientStudy" 消息时
multipleClientStudy: function(sectionId) {
    WS.closeConnection();
    window.location.href = "#/study/errors/" + sectionId;
}

// 收到 "otherClientStudy" 消息时
otherClientStudy: function() {
    showMessage("您已打开新的课程页面进行学习，旧页面将为您暂停播放！");
}
```

**WebSocket 地址**：`wss://mooc.ctt.cn/ws/api`

**应对**：确保只运行一个实例（`kill_other_chrome_processes()`）

---

### 2.4 WebSocket 心跳机制

**源码逻辑**：
```javascript
startHeartBeat: function() {
    this.heartBeat = setInterval(function() {
        var now = Date.now();
        var elapsed = now - this.lastTime;
        if (!this.isActive()) {
            this.stopHeartBeat();
            return;
        }
        // 发送心跳
        this.send({ courseId: this.courseId });
        this.lastTime = now;
    }, interval);
}

onClose: function(e) {
    // 1013 或 1006 时自动重连
    if (e.code === 1013 || e.code === 1006) {
        this.connect();
    }
}
```

**应对**：Playwright 自动处理 WebSocket，无需额外操作

---

### 2.5 同时学习冲突（40909 错误码）

**触发条件**：服务端检测到同账号同时学习多个课程

**源码逻辑**：
```javascript
// video-progress API 返回 40909
.catch(function(e) {
    if (e[0].responseText) {
        var n = JSON.parse(e[0].responseText);
        if (40909 === n.errorCode) {
            // 清空当前章节，显示"同时学习"弹窗
            playerState.data.sectionId = "";
            module.regions["study-same-time"].show(...);
        }
    }
});
```

**应对**：确保每次只学习一个课程，不要并行

---

### 2.6 倍速检测（ratechange）

**触发条件**：使用 1.5x 或 2x 倍速

**源码逻辑**：
```javascript
ratechange: function() {
    var userId = currentUser.id;
    var stored = JSON.parse(localStorage.getItem(userId)) || {};
    if (!stored.speed) {
        localStorage.setItem(userId, JSON.stringify({speed: true}));
        // 首次弹提示
        regions["speed-remind"].show(items["speed-remind"]);
    }
}
```

**关键发现**：页面显示"切换倍速不影响学习时长统计"

**结论**：倍速只弹一次提示，**不影响学时计入**。可以使用倍速！

---

### 2.7 视频水印

**源码逻辑**：
```javascript
watermark: {
    type: watermarkContent === 1 ? "text" : "image",
    content: text,           // "mooc.ctt.cn"
    opacity: (100 - opacity) / 100,  // 0.8 → 0.2
}
```

**配置**：`COURSE_WATERMAKING = {watermarkState: "1", text: "mooc.ctt.cn", opacity: "80"}`

**结论**：纯视觉效果，**不影响学习**

---

### 2.8 页面关闭检测（beforeunload）

**源码逻辑**：
```javascript
window.onbeforeunload = function() {
    // 提交最终进度
    commitProgress({end: true, flush: true});
}
```

**结论**：正常关闭会提交进度，无需特殊处理

---

### 2.9 进度提交间隔

**配置**：`submitProgressIntervals: 180000`（3 分钟）

**源码逻辑**：
```javascript
// 每 3 分钟提交一次
setInterval(function() {
    commitProgress({flush: false});
}, submitProgressIntervals);
```

**服务端验证**：提交间隔过短会被忽略

**应对**：保持 3 分钟提交间隔

---

## 三、防刷课配置详解

**API**: `GET /api/v1/system/rule-config/key?key=ANTI_BRUSH_COURSE_MECHANISM`

```json
{
  "enableAuti": "1",    // 启用反作弊
  "enableUnique": "1",  // 唯一性检测（单设备）
  "pauseTime": "30"     // 鼠标停留超时（分钟）
}
```

---

## 四、应对策略总结

| 机制 | 应对方案 | 优先级 |
|------|---------|--------|
| 鼠标停留 | 每 25 分钟触发 mousemove | ⭐⭐⭐ |
| 窗口焦点 | headless 模式 或 bring_to_front | ⭐⭐ |
| 多客户端 | 单实例运行 + kill_other_chrome | ⭐⭐⭐ |
| 心跳断开 | Playwright 自动处理 WS | ⭐ |
| 40909 冲突 | 不并行学习多课程 | ⭐⭐ |
| 倍速 | **可以倍速**，只弹一次提示 | ✅ |
| 水印 | 不影响 | ✅ |
| 提交间隔 | 保持 3 分钟 | ⭐⭐ |

---

## 五、关键结论

1. **可以倍速播放** — 页面明确说"切换倍速不影响学习时长统计"
2. **鼠标检测是最大威胁** — 默认 30 分钟无操作就暂停
3. **单实例是必须的** — 多设备会踢掉旧连接
4. **headless 模式可行** — 焦点检测在 headless 下无效（无窗口概念）
5. **API 提交间隔 3 分钟** — 过于频繁会被忽略

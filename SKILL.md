---
name: cttc-auto-learn-cdp
description: |
  烟草网络学院 (mooc.ctt.cn) CDP 自动学习 SKILL。
  Agent 通过 chrome-devtools MCP 连接用户已打开的 Chrome，复用登录会话，自动刷学时/专题/课程/任务/班级。
  触发词：刷学时、刷专题、刷课程、刷任务、刷班级、自动学习。
  无需 Playwright，无需额外浏览器，直接用用户当前 Chrome。
tags: [cdp, chrome-devtools, automation, china-tobacco, video]
version: 0.1.0
author: gandli
license: MIT
metadata:
  hermes:
    tags: [automation, browser, cdp, china-tobacco]
    related_skills: [chrome-devtools, cttc-auto-learn]
---

# 烟草网络学院 CDP 自动学习

> Agent 通过 chrome-devtools MCP 连接用户已打开的 Chrome，复用登录态，自动完成学习任务。

## 适用场景

- 用户已打开 Chrome 并登录了 mooc.ctt.cn
- 不想启动额外浏览器（Playwright）
- 想让 agent 直接在当前浏览器中操作
- 轻量级：无需 Python 依赖，agent 自带 MCP 工具

## 前置条件

1. **chrome-devtools MCP 已配置**（Hermes 默认已配置）
2. **Chrome 已打开**（MCP 会自动启动，或用户已手动打开）
3. **mooc.ctt.cn 已登录**（或 agent 会引导扫码登录）

## Agent 执行流程

### Step 1: 连接 Chrome，打开 mooc.ctt.cn

```
1. 用 navigate_page 打开 https://mooc.ctt.cn
2. 用 wait_for 等待页面加载
3. 用 take_snapshot 检查页面状态
```

### Step 2: 检查登录状态

```
1. 用 evaluate_script 执行：
   (() => {
     const text = document.body?.innerText || '';
     const token = localStorage.getItem('token') || '';
     return {
       loggedIn: !!token && text.includes('退出'),
       hasToken: !!token,
     };
   })()

2. 如果已登录 → 进入 Step 3
3. 如果未登录 → 进入 Step 2.1（扫码登录）
```

### Step 2.1: 扫码登录

```
1. 用 navigate_page 打开 https://mooc.ctt.cn/#/login
2. 用 evaluate_script 获取微信二维码 UUID：
   (async () => {
     const uuid = crypto.randomUUID();
     const resp = await fetch('/oauth/api/v1/createQRCode?uuid=' + uuid, {method:'POST'});
     const data = await resp.json();
     return data.uuid || uuid;
   })()

3. 构造二维码 URL：
   https://wx.zhixueyun.com/mswx/wechat/tobaccoQR/login/{uuid}/v5/online

4. 通过 send_message 发送二维码给用户（用 api.qrserver.com 生成图片）

5. 轮询检测扫码状态（每 3 秒，共 75 秒）：
   evaluate_script: (async () => {
     const resp = await fetch('/oauth/api/v1/checkUUIDStatus?uuid=' + uuid, {method:'POST'});
     const data = await resp.json();
     return data?.status === true;
   })()

6. 扫码成功 → 刷新页面 → 进入 Step 3
7. 超时 → 重新生成二维码，重复步骤
```

### Step 3: 获取学习数据

通过 `evaluate_script` 执行 fetch 请求（自动携带 token/cookie）：

```javascript
// 获取 token
const token = JSON.parse(localStorage.getItem('token') || '{}').access_token || '';
const headers = {
  'Authorization': 'Bearer__' + token,
  'X-Requested-With': 'XMLHttpRequest'
};

// 获取课程
const courses = await fetch('/api/v1/course-study/course-study-progress/personCourse-list?businessType=0&findStudy=0&studyTimeOrder=desc&page=1&pageSize=50', {headers}).then(r=>r.json());

// 获取任务
const tasks = await fetch('/api/v1/human/task/findMyTaskRemind', {headers}).then(r=>r.json());

// 获取学时统计
const stats = await fetch('/api/v1/system/credit/detail-hour-member', {headers}).then(r=>r.json());

// 获取专题
const topics = await fetch('/api/v1/human/special-topic/findMySpecialTopicPage?page=1&pageSize=50', {headers}).then(r=>r.json());

// 获取班级（v0.1.0 新增）
const classes = await fetch('/api/v1/human/class/findMyClassPage?page=1&pageSize=50', {headers}).then(r=>r.json());
```

**数据结构：**

| 数据 | 关键字段 | 状态映射 |
|------|---------|---------|
| 课程 | `items[].courseId`, `courseInfo.name`, `finishStatus` | 0=未开始, 1=学习中, 2=已完成 |
| 任务 | `taskName`, `statusName`, `businessId` | - |
| 专题 | `name`, `status`, `courseCount` | - |
| 班级 | `name`, `status`, `courseCount` | - |
| 学时 | `creditHour`, `requireCourseHour` | - |

### Step 4: 自动学习（按模式执行）

#### 4.1 刷学时模式 (`--mode hours`)

```
循环：
  1. 获取当前学时 (stats.creditHour)
  2. 如果 >= 目标(50h) → 完成，通知用户
  3. 获取未完成课程列表
  4. 对每门课程：
     a. navigate_page 打开课程页面
     b. wait_for 等待视频加载
     c. evaluate_script 播放视频：
        const v = document.querySelector('video');
        if (v && v.paused) v.play();
     d. evaluate_script 设置普清：
        document.querySelectorAll('.vjs-menu-item').forEach(el => {
          if (el.textContent.includes('普清')) el.click();
        });
     e. 循环等待视频完成（每 10 秒检查）：
        - 检查 video.ended / video.currentTime / video.duration
        - 进度 > 70% 且 video 消失 → 认为完成
        - 定时触发鼠标移动（防挂机）
     f. 视频完成后 → 下一门课程
  5. 所有课程播放完 → 重新获取课程列表（可能有新课程）
```

#### 4.2 刷任务模式 (`--mode tasks`)

```
1. 获取任务列表
2. 对每个未完成任务：
   a. 打开 businessId 对应的课程页面
   b. 播放视频，等待完成
3. 所有任务完成 → 通知用户
```

#### 4.3 刷专题模式 (`--mode topics`)

```
1. 获取专题列表
2. 对每个未完成专题：
   a. 获取专题详情（课程列表）
   b. 对专题内每门课程：播放视频，等待完成
3. 所有专题完成 → 通知用户
```

#### 4.4 刷课程模式 (`--mode courses`)

```
1. 获取所有未完成课程
2. 逐个播放，等待完成
3. 所有课程完成 → 通知用户
```

#### 4.5 刷班级模式 (`--mode classes`)

```
1. 获取班级列表
2. 对每个未完成班级：
   a. 获取班级详情（课程列表）
   b. 对班级内每门课程：播放视频，等待完成
3. 所有班级完成 → 通知用户
```

### Step 5: 视频播放子流程

每个视频的播放流程：

```
1. navigate_page 打开课程 URL
2. wait_for 等待 <video> 元素出现（最多 20 秒）
3. evaluate_script 播放：
   const v = document.querySelector('video');
   if (v) { v.play(); return {duration: v.duration, paused: v.paused}; }

4. 如果 play() 失败，尝试点击播放按钮：
   take_snapshot 找到播放按钮 → click

5. evaluate_script 设置普清画质

6. 循环监控（每 10 秒）：
   evaluate_script: (() => {
     const v = document.querySelector('video');
     if (!v) return {found: false};
     return {
       found: true,
       currentTime: v.currentTime,
       duration: v.duration,
       paused: v.paused,
       ended: v.ended,
       progress: v.duration > 0 ? (v.currentTime / v.duration * 100) : 0
     };
   })()

7. 防挂机（每 5 分钟）：
   evaluate_script: document.dispatchEvent(new MouseEvent('mousemove', {
     clientX: Math.random() * 800 + 100,
     clientY: Math.random() * 400 + 100,
     bubbles: true
   }));

8. 完成条件（任一满足）：
   - video.ended === true
   - progress >= 100%
   - video 元素消失且 progress > 70%

9. 恢复暂停：
   if (status.paused && status.currentTime > 0) {
     document.querySelector('video')?.play();
   }
```

### Step 6: 进度汇报

每完成一个视频，通过 send_message 向用户汇报：

```
📊 学习进度：
- 当前课程：《xxx》已完成
- 总进度：12/50 门课程
- 学时：23.5/50 小时 (47%)
- 状态：🟢 继续学习中...
```

## API 参考

| 接口 | 用途 | 方法 |
|------|------|------|
| `/api/v1/course-study/course-study-progress/personCourse-list` | 课程列表 | GET |
| `/api/v1/course-study/course-front/video-progress` | 视频进度上报 | POST |
| `/api/v1/human/task/findMyTaskRemind` | 任务提醒 | GET |
| `/api/v1/human/special-topic/findMySpecialTopicPage` | 专题列表 | GET |
| `/api/v1/human/special-topic/findMySpecialTopicDetail` | 专题详情 | GET |
| `/api/v1/human/class/findMyClassPage` | 班级列表 | GET |
| `/api/v1/system/credit/detail-hour-member` | 学时统计 | GET |
| `/api/v1/system/cadre-education/detail-hour-member` | 干部教育学时 | GET |
| `/api/v1/system/home-config/organization` | 组织信息 | GET |
| `/oauth/api/v1/createQRCode` | 创建微信二维码 | POST |
| `/oauth/api/v1/checkUUIDStatus` | 检查扫码状态 | POST |

**⚠️ Authorization 格式是 `Bearer__`（双下划线），不是 `Bearer `（空格）**

## 常见 Pitfall

1. **Token 格式** — `localStorage.getItem('token')` 可能是纯字符串（非 JSON），先尝试 JSON.parse，失败则直接用作 token
2. **SPA 页面** — mooc.ctt.cn 是 SPA，navigate 后需要 wait_for 等待内容加载
3. **视频元素消失** — 进度 > 70% 时网站会移除 `<video>` 元素，这是正常现象
4. **防挂机** — 每 5 分钟触发一次 mousemove 事件
5. **单实例** — 每次只能播放一个视频，不要同时打开多个课程页面
6. **画质设置** — 自动选择普清，减少带宽消耗
7. **Authorization 格式** — `Bearer__`（双下划线），不是标准的 `Bearer `（空格）
8. **acw_tc 过期** — WAF cookie 约 30 分钟过期，定期访问页面可自动续期

## 与 Playwright 版的区别

| 方面 | CDP 版 (本 SKILL) | Playwright 版 |
|------|-------------------|--------------|
| 浏览器 | 用户已打开的 Chrome | 新启动的 Chromium |
| 登录态 | 复用已有会话 | 需要扫码保存凭证 |
| 依赖 | chrome-devtools MCP (内置) | Python + Playwright |
| 资源占用 | 低（不启动新进程） | 高（额外浏览器进程） |
| 扩展 | 用户的扩展继续生效 | 无扩展 |
| 适用场景 | 日常使用、快速操作 | CI/CD、服务器、headless |

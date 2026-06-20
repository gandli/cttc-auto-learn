# 烟草网络学院 (mooc.ctt.cn) 网络请求逆向分析文档

> 逆向时间：2026-06-17
> 分析工具：Playwright CDP + Python PyCryptodome
> 目标：自动学习系统，50 学时网络自学

---

## 一、系统架构概述

网站采用 SPA 单页应用架构，前端通过 XHR 与后端 API 通信。

- **前端框架**：自研框架 drizzlejs（类似 Backbone.js）
- **视频播放器**：Video.js
- **视频流**：HLS (m3u8 + ts 分片)
- **通信协议**：REST API (HTTPS) + WebSocket (wss)
- **加密方式**：AES-128-ECB（仅 video-progress 参数）

---

## 二、加密方案

### 2.1 AES 加密

| 项目 | 值 |
|------|-----|
| 算法 | AES-128 |
| 模式 | ECB |
| 填充 | PKCS7 |
| 密钥 | `d8cg8gVakEq9Agup` |
| 库 | CryptoJS (前端) / PyCryptodome (Python) |

### 2.2 加密范围

**仅 `video-progress` API 的请求参数值被加密**，其他所有 API 均为明文传输。

加密逻辑（前端源码）：
```javascript
// main.js 中的 ajax 拦截器
t.options.security && (r.data = p.reduce(r.data, function(e, t, n) {
    return a[n] = h.encrypt(t), a
}, {}))
```

每个参数值单独加密，参数名明文。

### 2.3 Python 加解密

```python
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64, urllib.parse

KEY = b'd8cg8gVakEq9Agup'
cipher = AES.new(KEY, AES.MODE_ECB)

# 加密
def encrypt(plaintext: str) -> str:
    padded = pad(plaintext.encode('utf-8'), AES.block_size)
    encrypted = cipher.encrypt(padded)
    return urllib.parse.quote(base64.b64encode(encrypted).decode())

# 解密
def decrypt(ciphertext: str) -> str:
    decoded = base64.b64decode(urllib.parse.unquote(ciphertext))
    return unpad(cipher.decrypt(decoded), AES.block_size).decode('utf-8')
```

### 2.4 singleMark / logId

- `singleMark`：UUID v4，明文传输，由 `./app/util/uuid` 模块生成
- `logId`：UUID v4，明文传输

UUID 生成算法（前端源码）：
```javascript
n.uuid = function() {
    var e = Date.now();
    "undefined" != typeof performance && "function" == typeof performance.now && (e += performance.now());
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function(t) {
        var n = (e + 16 * Math.random()) % 16 | 0;
        return e = Math.floor(e / 16), ("x" === t ? n : 3 & n | 8).toString(16)
    })
}
```

---

## 三、核心 API 清单

### 3.1 视频进度 API

#### `POST /api/v1/course-study/course-front/video-progress`

**用途**：提交视频播放进度，每 3 分钟自动调用一次

**请求**：`Content-Type: application/x-www-form-urlencoded`

| 参数 | 加密? | 说明 | 示例明文 |
|------|-------|------|---------|
| `logId` | 明文 | UUID | `5b40e7e4-336d-4357-a211-8a789644c9f6` |
| `lessonLocation` | **AES** | 当前播放秒数 | `539` |
| `studyTime` | **AES** | 本轮学习秒数 | `539` |
| `resourceTotalTime` | **AES** | 视频总时长秒 | `1940` |
| `organizationId` | **AES** | 机构ID | `1` |
| `flush` | **AES** | 是否刷新 | `false` |
| `singleMark` | 明文 | UUID v4 | `duW1HM0Qj6q3eoiJqj9rX3rF01Wd` |

**响应**（JSON）：
```json
{
  "completedRate": 30,              // 完成百分比 (0-100)
  "finishStatus": 1,                // 1=进行中, 2=已完成
  "lessonLocation": "539",          // 当前秒数 (字符串)
  "remainingTime": 1401,            // 剩余秒数 (整数)
  "studyTotalTime": 539,            // 已学总秒数
  "studyPcTotalTime": 539,          // PC端学习秒数
  "studyAppTotalTime": 0,           // APP端学习秒数
  "sectionId": "d1c02cbc-...",      // 章节ID
  "courseId": "03071cef-...",        // 课程ID
  "resourceId": "a4b4f62a-...",     // 资源ID
  "memberId": "707e08fe-...",       // 用户ID
  "sectionName": "习近平总书记关于...（中）",
  "sectionType": 6,                 // 6=视频
  "beginTime": 1781686154000,       // 开始时间戳
  "lastAccessTime": 1781686694728,  // 最后访问时间戳
  "noChange": false,                // 是否无变化
  "changeStatus": false             // 状态是否改变
}
```

**触发条件**：
- `submitProgressIntervals`: 180000ms (3分钟)
- 配置来源: `COURSE_STUDY_TIME_STATISTICS_RULE`

---

#### `POST /api/v1/course-study/course-front/course-section-progress`

**用途**：获取课程各章节的学习进度

**请求**：`Content-Type: application/x-www-form-urlencoded`（明文）

| 参数 | 说明 | 示例 |
|------|------|------|
| `resourceIds` | 资源ID列表（逗号分隔） | `ead10be6-...,a4b4f62a-...` |
| `courseId` | 课程ID | `03071cef-...` |

**响应**（JSON Array）：每个元素结构同 `video-progress` 响应

---

#### `GET /api/v1/course-study/course-front/start-progress/{sectionId}`

**用途**：获取章节初始进度（进入课程时调用）

**响应**：
```json
{
  "id": "a91d3b7e-...",
  "remainingTime": 2149    // 剩余秒数
}
```

---

### 3.2 课程信息 API

#### `POST /api/v1/course-study/course-front/registerStudy`

**用途**：注册学习（进入课程时调用，记录学习开始）

**请求**（明文）：
```
courseId=03071cef-...&type=6&isRequired=1
```

| 参数 | 说明 |
|------|------|
| `courseId` | 课程ID |
| `type` | 6=视频 |
| `isRequired` | 1=必修 |

**响应**：
```json
{
  "id": "aacf0e0c-...",
  "currentResourceId": "79ad4b74-...",
  "currentSectionId": "c756d58d-...",
  "finishStatus": 1,
  "type": 6
}
```

---

#### `GET /api/v1/course-study/course-front/info/{courseId}`

**用途**：获取课程详情（章节列表、课程信息）

**响应**（关键字段）：
```json
{
  "id": "03071cef-...",
  "name": "习近平总书记关于...",
  "avgScore": 99,
  "businessType": 0,
  "category": {
    "id": "a5d02292-...",
    "name": "习近平新时代中国特色社会主义思想",
    "fullName": "网络党校-->理论教育-->习近平新时代..."
  },
  "courseChapters": [{
    "id": "8a3081e0-...",
    "name": "第一章",
    "courseChapterSections": [{
      "sectionId": "c756d58d-...",
      "resourceId": "79ad4b74-...",
      "sectionName": "习近平总书记关于...（下）",
      "sectionType": 6,
      "courseHour": 0.5,
      "isRequired": 1,
      "sequence": 3
    }]
  }]
}
```

**注意**：有时返回 422（课程资源不存在时）

---

#### `GET /api/v1/course-study/file/info-auth/{resourceId}`

**用途**：获取视频文件信息（含加密路径）

**响应**：
```json
{
  "filename": "习近平总书记关于...（下）.mp4",
  "items": [
    {"def": 0, "name": "原图", "path": "RrHwv/sc++Vk...", "size": 266075164},
    {"def": 1, "name": "普清", "path": "RrHwv/sc++Vk...", "size": 71063611},
    {"def": 2, "name": "高清", "path": "RrHwv/sc++Vk...", "size": 158444308}
  ]
}
```

视频路径经过加密，前端用 AES 解密后拼接为 HLS 流地址。

---

#### `GET /api/v1/course-study/course-front/getBranchIdByCourseId`

**用途**：获取课程分支ID

**请求参数**：`id={courseId}&type=0`

**响应**：
```json
{
  "branchId": "a6a8dd0d-...",
  "type": 4
}
```

---

### 3.3 学时统计 API

#### `GET /api/v1/system/credit/detail-hour-member`

**用途**：获取学时统计（主接口）

**响应**：
```json
{
  "courseHourResult": {
    "totalHour": 28.1,      // 网络自学已完成小时
    "maxHour": null
  },
  "totalClassHour": 26.0,    // 集中培训已完成小时
  "requireCourseHour": 50.0, // 网络自学目标
  "requireClassHour": 90.0,  // 集中培训目标
  "totalScore": 48.5         // 总学分
}
```

---

#### `GET /api/v1/system/cadre-education/detail-hour-member`

**用途**：干部教育学时（备用接口）

**响应**：
```json
{
  "hourSelf": 28.1,          // 网络自学
  "hourTrain": 26.0,         // 集中培训
  "requireCourseHour": 50.0,
  "requireClassHour": 90.0
}
```

---

#### `GET /api/v1/course-study/course-study-progress/history-and-now-duration`

**用途**：获取历史学习时长

**响应**：
```json
{
  "studyTime": {
    "0": 356580,    // 总学习秒数 (~99.05 小时)
    "1": 6,         // 未知
    "2": 356586     // 总计秒数
  }
}
```

---

### 3.4 系统配置 API

#### `GET /api/v1/system/rule-config/key?key={KEY}`

**用途**：获取系统配置项

| Key | 含义 | 值 |
|-----|------|-----|
| `VIDEO_PALY_THRESHOLD` | 视频完成标准 | `100` (必须播放100%) |
| `VIDEO_PROCESS_THRESHOLD` | 进度完成标准 | `0` |
| `ANTI_BRUSH_COURSE_MECHANISM` | 防刷课机制 | `{"enableAuti":"1","enableUnique":"1","pauseTime":"30"}` |
| `COURSE_STUDY_TIME_STATISTICS_RULE` | 学时统计规则 | `{"courseCompletionRules":"10","maximumLengthAvailable":"10","maximumCumulativeLearningDuration":"24","submitProgressIntervals":"180000"}` |
| `COURSE_WATERMAKING` | 水印配置 | `{"watermarkState":"1","text":"mooc.ctt.cn"}` |
| `SHARE_CONFIG` | 分享配置 | `{"switchOpen":1}` |
| `RESOURCE_STUDY_CONFIG` | 资源配置 | `{"platform":"3","apikey":"7baf8b...","secret":"8ada46..."}` |

**防刷课机制解读**：
- `enableAuti: 1` — 启用反作弊
- `enableUnique: 1` — 唯一性检测（同账号不能多设备同时学习）
- `pauseTime: 30` — 暂停超过 30 秒触发检测

**学时统计规则解读**：
- `submitProgressIntervals: 180000` — 每 3 分钟提交一次进度
- `maximumCumulativeLearningDuration: 24` — 最大连续学习 24 小时
- `courseCompletionRules: 10` — 课程完成规则（10%）
- `maximumLengthAvailable: 10` — 最大可用时长（10小时？）

---

### 3.5 视频流 API

#### HLS 流

```
https://mooc9cdnpro.zhixueyun.com/hls/{uuid}                    # HLS playlist
https://mooc9cdnpro.zhixueyun.com/{path}/index.m3u8              # 多码率索引
https://mooc9cdnpro.zhixueyun.com/{path}/index20.ts              # 视频分片
```

视频路径通过 `file/info-auth` API 获取（加密），前端 AES 解密后拼接为完整 URL。

---

### 3.6 WebSocket

**地址**：`wss://mooc.ctt.cn/ws/api`

**用途**：
- 防刷课检测
- 多客户端同时学习检测
- 实时通知

**前端代码**：
```javascript
a = function(e, t) {
    var n = "http:" === window.location.protocol ? "ws://" : "wss://",
        a = window.filterXSS(window.location.pathname);
    n += window.location.host + a;
    this.app = e;
    this.prefix = e.options.urlRoot + "/" + t;
    this.url = n + this.prefix + "/ws/api";
    this.connect()
}
```

---

### 3.7 其他辅助 API

| API | 方法 | 用途 |
|-----|------|------|
| `/api/v1/system/setting` | GET | 系统设置 |
| `/api/v1/system/home-config/organization` | GET | 首页配置 |
| `/api/v1/system/home-config/config` | GET | 配置详情 |
| `/api/v1/system/home-nav` | GET | 导航菜单 |
| `/api/v1/system/home-footer` | GET | 页脚信息 |
| `/api/v1/system/msg-count` | GET | 消息计数 |
| `/api/v1/system/message-notice/getCount` | GET | 通知计数 |
| `/api/v1/system/message-at-me/get-count` | GET | @我计数 |
| `/api/v1/system/collect` | GET | 收藏状态 |
| `/api/v1/system/comment/front` | GET | 评论列表 |
| `/api/v1/system/topic/hot-all` | GET | 热门专题 |
| `/api/v1/system/topic/ids` | GET | 专题列表 |
| `/api/v1/system/skin-config/skin` | GET | 皮肤配置 |
| `/api/v1/system/integral-result/grade` | GET | 积分等级 |
| `/api/v1/system/operation/announcement/person-list-all` | GET | 公告列表 |
| `/api/v1/human/task/findMyTaskRemind` | GET | 任务提醒 |
| `/api/v1/human/task/findMyTaskCalendar` | GET | 任务日历 |
| `/api/v1/course-study/course-info/related` | GET | 相关课程 |
| `/api/v1/course-study/score/{courseId}` | GET | 课程评分 |
| `/api/v1/system/company-sync/get-company-by-id` | GET | 公司信息 |
| `/api/v1/system/home-footer/getLoginSumCount` | GET | 登录统计 |
| `/api/v1/system/rule-config/getkey?key=...` | GET | 配置项 |
| `/api/v1/system/rule-config/key-not-login?...` | GET | 公开配置 |
| `/api/v1/zxy-log/online/get-online-count-cache` | GET | 在线人数 |

---

## 四、完整学习流程

```
┌─────────────────────────────────────────────────────────┐
│ 1. 进入课程页面                                          │
│    POST registerStudy (courseId, type=6, isRequired=1)  │
│    → 获取 currentSectionId, currentResourceId            │
├─────────────────────────────────────────────────────────┤
│ 2. 获取章节进度                                          │
│    GET start-progress/{sectionId}                        │
│    → 获取 remainingTime                                  │
├─────────────────────────────────────────────────────────┤
│ 3. 获取视频文件                                          │
│    GET file/info-auth/{resourceId}                       │
│    → 获取加密路径，AES 解密后拼接 HLS URL                 │
├─────────────────────────────────────────────────────────┤
│ 4. 播放视频                                              │
│    Video.js 播放 HLS 流 (m3u8 + ts)                      │
│    设置画质为普清                                         │
├─────────────────────────────────────────────────────────┤
│ 5. 定时提交进度 (每 3 分钟)                               │
│    POST video-progress                                   │
│    参数: logId, lessonLocation(AES), studyTime(AES),     │
│          resourceTotalTime(AES), organizationId(AES),    │
│          flush(AES), singleMark                          │
│    → 获取 completedRate, remainingTime, finishStatus     │
├─────────────────────────────────────────────────────────┤
│ 6. 判断完成                                              │
│    completedRate >= 100 或 finishStatus == 2             │
│    → 进入下一个视频                                       │
└─────────────────────────────────────────────────────────┘
```

---

## 五、关键数据字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `completedRate` | int | 完成百分比 (0-100) |
| `finishStatus` | int | 1=进行中, 2=已完成 |
| `lessonLocation` | string | 当前播放位置（秒） |
| `remainingTime` | int | 剩余时间（秒） |
| `studyTotalTime` | int | 已学习总时长（秒） |
| `studyPcTotalTime` | int | PC端学习时长（秒） |
| `studyAppTotalTime` | int | APP端学习时长（秒） |
| `sectionType` | int | 6=视频, 其他=文档等 |
| `isRequired` | int | 1=必修, 0=选修 |
| `noChange` | bool | 进度是否有变化 |

---

## 六、注意事项

1. **防刷课**：`pauseTime=30`，暂停超过 30 秒会触发检测
2. **提交间隔**：每 3 分钟提交一次，过于频繁可能被检测
3. **学时计入**：`studyTotalTime` 是服务端累计值，每次提交会累加
4. **多客户端**：WebSocket 检测多设备同时学习，会踢掉旧连接
5. **视频完成**：必须 `completedRate=100` 才算完成，中间退出不计
6. **资源失效**：部分课程返回 422，表示资源已不存在

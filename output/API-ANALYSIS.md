# 烟草网络学院 API 完整逆向分析

## 1. 核心进度 API

### 1.1 POST `/api/v1/course-study/course-front/video-progress`
**视频播放进度提交（每 3 分钟一次）**

**加密方式**: AES-128-ECB, PKCS7, Key=`d8cg8gVakEq9Agup`

**请求参数** (form-urlencoded, AES 加密每个值):
| 参数 | 明文含义 | 示例 |
|------|---------|------|
| `logId` | UUID（明文） | `5b40e7e4-336d-...` |
| `lessonLocation` | 当前播放秒数 | `539` → AES → `Ismtq...` |
| `studyTime` | 已学时长秒数 | `539` → AES → `Ismtq...` |
| `resourceTotalTime` | 视频总时长秒 | `1940` → AES → `Hb8He...` |
| `organizationId` | 机构ID | `1` → AES → `N8XxZ...` |
| `flush` | 是否刷新 | `false` → AES → `jZTbq...` |
| `singleMark` | UUID v4（明文） | `duW1HM0Qj6q3...` |

**响应** (JSON):
```json
{
  "completedRate": 15,        // 完成率 %
  "finishStatus": 1,          // 1=进行中, 2=已完成
  "lessonLocation": "539",    // 当前秒
  "remainingTime": 1401,      // 剩余秒数
  "studyTotalTime": 539,      // 已学总秒
  "studyPcTotalTime": 539,    // PC端学习秒
  "sectionId": "d1c02cbc-...",
  "courseId": "03071cef-...",
  "sectionName": "习近平总书记关于...（中）",
  "sectionType": 6,           // 6=视频
  "beginTime": 1781686154000,
  "lastAccessTime": 1781686694728,
  "noChange": false
}
```

---

### 1.2 POST `/api/v1/course-study/course-front/course-section-progress`
**获取课程各章节进度**

**请求参数** (form-urlencoded, 明文):
```
resourceIds=ead10be6-...,a4b4f62a-...,79ad4b74-...
courseId=03071cef-...
```

**响应** (JSON Array):
```json
[{
  "completedRate": 15,
  "finishStatus": 1,
  "lessonLocation": "539",
  "remainingTime": 1401,
  "studyTotalTime": 539,
  "sectionId": "d1c02cbc-...",
  "sectionName": "习近平总书记关于...（中）",
  "sectionType": 6
}]
```

---

### 1.3 GET `/api/v1/course-study/course-front/start-progress/{sectionId}`
**获取章节初始进度**

**响应**:
```json
{
  "id": "a91d3b7e-...",
  "remainingTime": 2149     // 剩余秒数
}
```

---

### 1.4 GET `/api/v1/course-study/course-study-progress/history-and-now-duration`
**获取学习历史时长**

**响应**:
```json
{
  "studyTime": {
    "0": 356580,   // 总学习秒数 (~99小时)
    "1": 6,        // ?
    "2": 356586    // 总计秒数
  }
}
```

---

## 2. 课程信息 API

### 2.1 GET `/api/v1/course-study/course-front/info/{courseId}`
**获取课程详情**

**响应** (关键字段):
```json
{
  "id": "03071cef-...",
  "name": "习近平总书记关于...",
  "courseChapters": [{
    "courseChapterSections": [{
      "sectionId": "c756d58d-...",
      "resourceId": "79ad4b74-...",
      "sectionName": "习近平总书记关于...（下）",
      "sectionType": 6,        // 6=视频
      "courseHour": 0.5,
      "isRequired": 1          // 1=必修
    }]
  }]
}
```

---

### 2.2 GET `/api/v1/course-study/file/info-auth/{resourceId}`
**获取视频文件信息（含加密路径）**

**响应**:
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

---

### 2.3 POST `/api/v1/course-study/course-front/registerStudy`
**注册学习（进入课程时调用）**

**请求参数** (form-urlencoded, 明文):
```
courseId=03071cef-...&type=6&isRequired=1
```

**响应**:
```json
{
  "currentResourceId": "79ad4b74-...",
  "currentSectionId": "c756d58d-...",
  "finishStatus": 1,
  "id": "aacf0e0c-...",
  "type": 6
}
```

---

## 3. 学时统计 API

### 3.1 GET `/api/v1/system/credit/detail-hour-member`
**学时统计（主接口）**

**响应**:
```json
{
  "courseHourResult": {"totalHour": 28.1},  // 网络自学
  "totalClassHour": 26.0,                    // 集中培训
  "requireCourseHour": 50.0,                 // 自学目标
  "requireClassHour": 90.0,                  // 培训目标
  "totalScore": 48.5                         // 总学分
}
```

### 3.2 GET `/api/v1/system/cadre-education/detail-hour-member`
**干部教育学时（备用接口）**

**响应**:
```json
{
  "hourSelf": 28.1,
  "hourTrain": 26.0,
  "requireCourseHour": 50.0,
  "requireClassHour": 90.0
}
```

---

## 4. 系统配置 API

### 4.1 GET `/api/v1/system/rule-config/key?key={KEY}`
**获取系统配置**

| Key | 含义 | 值 |
|-----|------|-----|
| `VIDEO_PALY_THRESHOLD` | 视频完成标准 | `100` (100%) |
| `VIDEO_PROCESS_THRESHOLD` | 进度完成标准 | `0` |
| `ANTI_BRUSH_COURSE_MECHANISM` | 防刷课 | `enableAuti:1, pauseTime:30` |
| `COURSE_STUDY_TIME_STATISTICS_RULE` | 学时规则 | `submitProgressIntervals:180000` (3分钟) |
| `COURSE_WATERMAKING` | 水印 | `watermarkState:1` |
| `SHARE_CONFIG` | 分享配置 | `switchOpen:1` |

---

## 5. 视频流

### 5.1 HLS 流
```
https://mooc9cdnpro.zhixueyun.com/hls/{uuid}           # HLS playlist
https://mooc9cdnpro.zhixueyun.com/.../index.m3u8       # 多码率索引
https://mooc9cdnpro.zhixueyun.com/.../index20.ts       # 视频分片
```

视频路径通过 `file/info-auth` API 获取（加密），在浏览器端用 AES 解密后拼接。

---

## 6. 关键流程

```
1. registerStudy → 注册学习，获取 currentSectionId
2. start-progress/{sectionId} → 获取 remainingTime
3. file/info-auth/{resourceId} → 获取视频路径
4. 播放视频 (HLS)
5. 每 3 分钟 → video-progress (AES 加密提交)
6. 完成 → completedRate=100, finishStatus=2
```

---

## 7. WebSocket

发现 WebSocket 连接: `wss://mooc.ctt.cn/ws/api` (防刷课、多客户端检测)
本次捕获未触发 WS 事件（单客户端）。

---

## 8. 加密方案总结

| 组件 | 值 |
|------|-----|
| 算法 | AES-128-ECB |
| 填充 | PKCS7 |
| 密钥 | `d8cg8gVakEq9Agup` |
| 库 | CryptoJS (browser) / PyCryptodome (Python) |
| 加密范围 | 仅 `video-progress` 的参数值 |
| 其他 API | 明文 form-urlencoded |

# mooc.ctt.cn 全站 API 爬取报告

**爬取时间**: 2026-06-20 11:50
**耗时**: ~8 分钟
**页面**: 136 页
**API 端点**: 34 个
**API 请求**: 4802 条（含重复）

---

## 📡 API 端点分类

### 1. 课程学习 (`/api/v1/course-study/`)

| 方法 | 路径 | 说明 | 响应字段 |
|------|------|------|----------|
| GET | `/course-study/course-study-progress/history-and-now-duration` | 学习进度 | `studyTime` |
| GET | `/course-study/course-info/front/recommend` | 推荐课程 | - |
| GET | `/course-study/course-info/home/front/find-by-ids` | 批量查询课程 | - |
| GET | `/course-study/course-front/companyLecturerCourseRank` | 讲师课程排名 | - |
| GET | `/course-study/course-total/course-finish-count` | 课程完成数 | - |
| GET | `/course-study/course-total/findCityRankValue` | 城市排名 | - |

### 2. 任务管理 (`/api/v1/human/`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/human/task/findMyTaskCalendar` | 任务日历 |
| GET | `/human/task/findMyTaskRemind` | 任务提醒 |

### 3. 系统配置 (`/api/v1/system/`)

| 方法 | 路径 | 说明 | 响应字段 |
|------|------|------|----------|
| GET | `/system/setting` | 系统设置 | `redirectUri`, `currentUser`, `organization`, `roleLength` |
| GET | `/system/home-config/config` | 首页配置 | `id`, `name`, `organizationId`, `type` |
| GET | `/system/home-config/organization` | 组织配置 | - |
| GET | `/system/home-config/personHomeConfig` | 个人首页配置 | `activityName`, `moduleConfigList` |
| GET | `/system/home-nav` | 导航菜单 | - |
| GET | `/system/home-module` | 首页模块 | - |
| GET | `/system/home-content` | 首页内容 | - |
| GET | `/system/home-news` | 首页资讯 | - |
| GET | `/system/home-footer` | 页脚配置 | `clientType`, `configId`, `content` |
| GET | `/system/home-footer/getLoginSumCount` | 登录总数 | - |
| GET | `/system/home-advertisement` | 广告 | - |
| GET | `/system/home-content/companyFooterMemberCount` | 公司成员统计 | `companyPcLoginCount`, `companyAppLoginCount` |
| GET | `/system/company-sync/get-company-by-id` | 公司信息 | `id`, `liveSupply`, `name` |
| GET | `/system/cadre-education/detail-hour-member` | 干部教育学时 | `hourSelf`, `hourTrain`, `requireClassHour`, `requireCourseHour` |
| GET | `/system/credit/detail-hour-member` | 学分详情 | `courseHourResult`, `maxScore`, `totalClassHour`, `totalScore` |
| GET | `/system/integral-result/grade` | 积分等级 | `integralGrade`, `totalScore`, `memberName` |
| GET | `/system/msg-count` | 消息计数 | `atCount`, `count`, `todoCount` |
| GET | `/system/message-notice/getCount` | 通知计数 | - |
| GET | `/system/message-at-me/get-count` | @我的计数 | `num` |
| GET | `/system/operation/announcement/person-list-all` | 公告列表 | - |
| GET | `/system/topic/hot-all` | 热门专题 | - |
| GET | `/system/skin-config/skin` | 皮肤配置 | - |
| GET | `/system/rule-config/key` | 规则配置 | `key`, `value`, `desc` |
| GET | `/system/rule-config/getkey` | 获取规则值 | `key`, `value`, `companyName` |
| GET | `/system/rule-config/key-not-login` | 未登录规则 | `key`, `value` |

### 4. 培训 (`/api/v1/training/`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/training/home-lecturer` | 首页讲师 |

### 5. OAuth

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/oauth/authorize` | OAuth 授权 |

---

## 🔑 关键发现

### 学时相关 API
- `/api/v1/system/cadre-education/detail-hour-member` - 干部教育学时（`hourSelf`, `hourTrain`）
- `/api/v1/system/credit/detail-hour-member` - 学分详情（`totalClassHour`, `totalScore`）
- `/api/v1/course-study/course-study-progress/history-and-now-duration` - 学习进度（`studyTime`）

### 课程相关 API
- `/api/v1/course-study/course-info/front/recommend` - 推荐课程
- `/api/v1/course-study/course-info/home/front/find-by-ids` - 批量查询课程（需传 `ids` 参数）

### 任务相关 API
- `/api/v1/human/task/findMyTaskCalendar` - 任务日历
- `/api/v1/human/task/findMyTaskRemind` - 任务提醒

### 消息相关 API
- `/api/v1/system/msg-count` - 消息计数（`atCount`, `todoCount`）
- `/api/v1/system/message-at-me/get-count` - @我的计数

---

## ⚠️ 限制

1. **"系统繁忙" 问题** - `/center/*` 等页面返回 "系统繁忙"，可能是：
   - 请求频率过高
   - 需要特定 Referer/Origin
   - 需要特定 Cookie 或 Token

2. **未发现 POST API** - 可能的原因：
   - 未触发提交操作
   - POST 请求被拦截
   - 需要特定交互才能触发

3. **未发现视频进度 API** - 可能需要：
   - 导航到具体课程页面
   - 播放视频才会触发

---

## 📁 输出文件

- `api-catalog.json` - API 端点目录
- `api-requests.json` - API 请求日志（前 2000 条）
- `pages.json` - 页面列表
- `sitemap.txt` - URL 列表
- `report.md` - 本报告

---

## 🔧 建议

1. **降低请求频率** - 增加页面间延迟到 2-3 秒
2. **模拟真实浏览** - 添加随机滚动、鼠标移动
3. **使用 Referer** - 确保每个请求都有正确的 Referer
4. **触发视频播放** - 导航到课程页面并播放视频以触发进度 API
5. **检查 JS Bundle** - 分析前端代码发现隐藏 API

# mooc.ctt.cn 全站爬取完整报告

> 爬取时间: 2026-06-20
> 工具: Playwright + Python

---

## 📊 概览

| 项目 | 数量 |
|------|------|
| API 端点 | 34 |
| 分院/专区 | 13 |
| 专题 | 52 |

---

## 🏛️ 分院/专区结构

### 分院（9 个）

| # | 名称 | configId | 导航项 |
|---|------|----------|--------|
| 1 | 网络学院（总院） | `81b0c456-c6a8-4e25-9416-25f7cf5f6c06` | 9 项 |
| 2 | 专卖分院 | `03e2ef50-92fe-4ad4-9391-6289127ab901` | 6 项 |
| 3 | 安全生产分院 | `eb691412-0bbe-4405-922d-be20f18b5afd` | 6 项 |
| 4 | 精益管理分院 | `4bba3cc7-900d-4641-9704-94d255c4df42` | 6 项 |
| 5 | 网信分院 | `69ea081e-f533-49f8-ac33-79dde8275ea5` | 6 项 |
| 6 | 物流分院 | `2ed3163d-d990-4ed8-9538-9860b01aad63` | 6 项 |
| 7 | 营销分院 | `0334f9d7-4cdc-46d6-97a7-6c403690edc7` | 6 项 |
| 8 | 农业分院 | `56f4b71e-c869-427a-aa77-eee1336cd361` | 6 项 |
| 9 | 烟机设备分院 | `95cdfef5-6c6c-498e-a999-6b78bf16e623` | 6 项 |

### 专区（4 个）

| # | 名称 | configId |
|---|------|----------|
| 1 | 法律法规学习专区 | `c1fe8977-efcc-420e-9512-9d1f61fd055d` |
| 2 | 组织人事学习专区 | `d0c9afaf-ebd9-424d-935a-48b05842a8cd` |
| 3 | 卷烟工艺质量学习专区 | `246abad2-d4d8-4b0d-bdca-260b0c70d356` |
| 4 | 财务与审计学习专区 | `ffa07f0e-6ad5-4b89-b4ce-f28ad202867c` |

---

## 🗂️ 标准导航菜单

### 网络学院（总院）- 9 项

| 导航项 | URL 路径 |
|--------|----------|
| 首页 | `home` |
| 课程 | `study/course/index` |
| 专题 | `study/subject/index` |
| 活动 | `activity/index` |
| 纷享 | `ask/index` |
| 知识 | `knowledge/index` |
| 商城 | `integral-mall/home` |
| 赛事活动 | `microclass/index` |
| 发现 | `discover/index` |

### 分院/专区 - 6 项标准导航

| 导航项 | URL 路径 | 说明 |
|--------|----------|------|
| 首页 | `homeBranch` | 分院首页 |
| XX动态 | `news-dynamic/index` | 新闻资讯 |
| 学习资源 | `study/branch/index` | 课程列表 |
| 政策法规 | `policy-statute/index` | 政策文件 |
| 阅读空间 | `reading-space/index` | 文章阅读 |
| 专家专区 | `expert-zone/index` | 专家介绍 |

---

## 🔌 API 端点目录

### 课程学习 `/api/v1/course-study/`

| 方法 | 路径 | 说明 | 响应字段 |
|------|------|------|----------|
| GET | `/course-study/course-study-progress/history-and-now-duration` | 学习进度 | `studyTime` |
| GET | `/course-study/course-info/front/recommend` | 推荐课程 | - |
| GET | `/course-study/course-info/home/front/find-by-ids` | 批量查询课程 | - |
| GET | `/course-study/course-front/companyLecturerCourseRank` | 讲师课程排名 | - |
| GET | `/course-study/course-total/course-finish-count` | 课程完成数 | - |
| GET | `/course-study/course-total/findCityRankValue` | 城市排名 | - |

### 任务管理 `/api/v1/human/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/human/task/findMyTaskCalendar` | 任务日历 |
| GET | `/human/task/findMyTaskRemind` | 任务提醒 |

### 系统配置 `/api/v1/system/`

| 方法 | 路径 | 说明 | 响应字段 |
|------|------|------|----------|
| GET | `/system/setting` | 系统设置 | `currentUser`, `organization`, `redirectUri` |
| GET | `/system/home-config/config` | 首页配置 | `id`, `name`, `organizationId` |
| GET | `/system/home-config/organization` | 组织列表 | - |
| GET | `/system/home-config/personHomeConfig` | 个人首页配置 | `moduleConfigList` |
| GET | `/system/home-nav` | 导航菜单 | - |
| GET | `/system/home-module` | 首页模块 | - |
| GET | `/system/home-content` | 首页内容 | - |
| GET | `/system/home-news` | 首页资讯 | - |
| GET | `/system/home-footer` | 页脚配置 | `content` |
| GET | `/system/home-footer/getLoginSumCount` | 登录总数 | - |
| GET | `/system/home-advertisement` | 广告 | - |
| GET | `/system/home-content/companyFooterMemberCount` | 公司成员统计 | `companyPcLoginCount`, `companyAppLoginCount` |
| GET | `/system/company-sync/get-company-by-id` | 公司信息 | `id`, `liveSupply`, `name` |
| GET | `/system/cadre-education/detail-hour-member` | 干部教育学时 | `hourSelf`, `hourTrain`, `requireClassHour` |
| GET | `/system/credit/detail-hour-member` | 学分详情 | `totalClassHour`, `totalScore`, `maxScore` |
| GET | `/system/integral-result/grade` | 积分等级 | `integralGrade`, `totalScore` |
| GET | `/system/msg-count` | 消息计数 | `atCount`, `todoCount`, `count` |
| GET | `/system/message-notice/getCount` | 通知计数 | - |
| GET | `/system/message-at-me/get-count` | @我的计数 | `num` |
| GET | `/system/operation/announcement/person-list-all` | 公告列表 | - |
| GET | `/system/topic/hot-all` | 热门专题 | - |
| GET | `/system/skin-config/skin` | 皮肤配置 | - |
| GET | `/system/rule-config/key` | 规则配置 | `key`, `value`, `desc` |
| GET | `/system/rule-config/getkey` | 获取规则值 | `key`, `value`, `companyName` |
| GET | `/system/rule-config/key-not-login` | 未登录规则 | `key`, `value` |

### 培训 `/api/v1/training/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/training/home-lecturer` | 首页讲师 |

### OAuth

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/oauth/authorize` | OAuth 授权 |

---

## 🔑 关键 API 速查

### 📊 学时/学分

```
GET /api/v1/system/cadre-education/detail-hour-member
  → hourSelf, hourTrain, requireClassHour, requireCourseHour

GET /api/v1/system/credit/detail-hour-member
  → totalClassHour, totalScore, maxScore, courseHourResult

GET /api/v1/course-study/course-study-progress/history-and-now-duration
  → studyTime
```

### 📚 课程

```
GET /api/v1/course-study/course-info/front/recommend?memberId=...
GET /api/v1/course-study/course-info/home/front/find-by-ids?ids=...
GET /api/v1/course-study/course-total/course-finish-count
GET /api/v1/course-study/course-total/findCityRankValue
```

### 📋 任务/专题

```
GET /api/v1/human/task/findMyTaskCalendar
GET /api/v1/human/task/findMyTaskRemind
GET /api/v1/system/topic/hot-all?limit=6&organizationId=1
```

### 🔔 消息/通知

```
GET /api/v1/system/msg-count → atCount, todoCount, count
GET /api/v1/system/message-at-me/get-count → num
GET /api/v1/system/message-notice/getCount
GET /api/v1/system/operation/announcement/person-list-all
```

### ⚙️ 系统配置

```
GET /api/v1/system/setting → currentUser, organization, redirectUri
GET /api/v1/system/home-config/personHomeConfig → moduleConfigList
GET /api/v1/system/home-config/config?configId=...
GET /api/v1/system/rule-config/getkey?key=...
GET /api/v1/system/skin-config/skin?organizationId=1&clientType=1
```

### 🏛️ 分院/专区

```
GET /api/v1/system/home-config/organization
  → 获取所有分院/专区列表

GET /api/v1/system/home-nav?homeConfigId={configId}
  → 获取指定分院的导航菜单

GET /api/v1/system/home-module?homeConfigId={configId}
  → 获取指定分院的内容模块

GET /api/v1/system/home-content?moduleHomeConfigId={moduleId}
  → 获取指定分院的首页内容

GET /api/v1/system/home-footer?homeConfigId={configId}
  → 获取指定分院的页脚
```

---

## 📁 输出文件

```
output/crawl/
├── API-FULL-CATALOG.md          # API 完整目录
├── BRANCHES-AND-ZONES.md        # 分院与专区目录
├── FINAL-REPORT.md              # 最终报告
├── api-catalog.json             # API 端点目录
├── api-deep-explore.json        # API 深度探索
├── api-requests.json            # API 请求日志
├── branches-zones.json          # 分院/专区数据
├── pages.json                   # 页面列表
├── sitemap.txt                  # URL 列表
└── branches/                    # 分院详细数据
    ├── REPORT.md                # 分院爬取报告
    ├── summary.json             # 汇总数据
    ├── all-subjects.json        # 所有专题
    ├── api-catalog.json         # 分院 API 目录
    ├── 网络学院.json
    ├── 专卖分院.json
    ├── 安全生产分院.json
    ├── 精益管理分院.json
    ├── 网信分院.json
    ├── 物流分院.json
    ├── 营销分院.json
    ├── 农业分院.json
    ├── 烟机设备分院.json
    ├── 法律法规学习专区.json
    ├── 组织人事学习专区.json
    ├── 卷烟工艺质量学习专区.json
    └── 财务与审计学习专区.json
```

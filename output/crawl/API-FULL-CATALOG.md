# mooc.ctt.cn 全站 API 完整目录

> 爬取时间: 2026-06-20 | 端点数: 34 | 请求样本: 101

---

## /api/v1/course-study

| # | 方法 | 路径 | 调用 | 响应字段 |
|---|------|------|------|----------|
| 1 | GET | `/api/v1/course-study/course-front/companyLecturerCourseRank` | 2 | - |
| 2 | GET | `/api/v1/course-study/course-info/front/recommend` | 2 | - |
| 3 | GET | `/api/v1/course-study/course-info/home/front/find-by-ids` | 6 | - |
| 4 | GET | `/api/v1/course-study/course-study-progress/history-and-now-duration` | 1 | `studyTime` |
| 5 | GET | `/api/v1/course-study/course-total/course-finish-count` | 2 | - |
| 6 | GET | `/api/v1/course-study/course-total/findCityRankValue` | 2 | - |

## /api/v1/human

| # | 方法 | 路径 | 调用 | 响应字段 |
|---|------|------|------|----------|
| 1 | GET | `/api/v1/human/task/findMyTaskCalendar` | 2 | - |
| 2 | GET | `/api/v1/human/task/findMyTaskRemind` | 2 | - |

## /api/v1/system

| # | 方法 | 路径 | 调用 | 响应字段 |
|---|------|------|------|----------|
| 1 | GET | `/api/v1/system/cadre-education/detail-hour-member` | 2 | `hourSelf`, `hourTrain`, `id`, `requireClassHour`, `requireCourseHour` |
| 2 | GET | `/api/v1/system/company-sync/get-company-by-id` | 2 | `id`, `liveSupply`, `name` |
| 3 | GET | `/api/v1/system/credit/detail-hour-member` | 2 | `courseHourResult`, `id`, `maxScore`, `requireClassHour`, `requireCourseHour`, `totalClassHour`, `totalScore` |
| 4 | GET | `/api/v1/system/home-advertisement` | 2 | - |
| 5 | GET | `/api/v1/system/home-config/config` | 10 | `createTime`, `deleteFlag`, `description`, `enableHomeBrowse`, `enableNav`, `enableTime`, `haschild`, `id` (+16) |
| 6 | GET | `/api/v1/system/home-config/organization` | 8 | - |
| 7 | GET | `/api/v1/system/home-config/personHomeConfig` | 2 | `activityName`, `createMemberId`, `createMemberName`, `createTime`, `deleteFlag`, `description`, `enableHomeBrowse`, `enableNav` (+26) |
| 8 | GET | `/api/v1/system/home-content` | 10 | - |
| 9 | GET | `/api/v1/system/home-content/companyFooterMemberCount` | 2 | `companyPcLoginCount`, `companyAppLoginCount`, `companyHomeCurYearCount`, `companySumLoginCount`, `companyHomeRegCount`, `companyHomeCurMonthCount` |
| 10 | GET | `/api/v1/system/home-footer` | 2 | `clientType`, `configId`, `content`, `createTime`, `id` |
| 11 | GET | `/api/v1/system/home-footer/getLoginSumCount` | 2 | - |
| 12 | GET | `/api/v1/system/home-module` | 2 | - |
| 13 | GET | `/api/v1/system/home-nav` | 2 | - |
| 14 | GET | `/api/v1/system/home-news` | 2 | - |
| 15 | GET | `/api/v1/system/integral-result/grade` | 2 | `createTime`, `headPortrait`, `id`, `integralGrade`, `maxScore`, `memberId`, `memberName`, `orgPath` (+3) |
| 16 | GET | `/api/v1/system/message-at-me/get-count` | 2 | `num` |
| 17 | GET | `/api/v1/system/message-notice/getCount` | 2 | - |
| 18 | GET | `/api/v1/system/msg-count` | 2 | `atCount`, `count`, `createTime`, `id`, `innerCount`, `memberId`, `todoCount` |
| 19 | GET | `/api/v1/system/operation/announcement/person-list-all` | 2 | - |
| 20 | GET | `/api/v1/system/rule-config/getkey` | 10 | `companyName`, `desc`, `id`, `key`, `organizationId`, `status`, `type`, `value` |
| 21 | GET | `/api/v1/system/rule-config/key` | 2 | `desc`, `id`, `key`, `organizationId`, `status`, `type`, `value` |
| 22 | GET | `/api/v1/system/rule-config/key-not-login` | 2 | `desc`, `id`, `key`, `organizationId`, `status`, `type`, `value` |
| 23 | GET | `/api/v1/system/setting` | 2 | `redirectUri`, `shareTemplate`, `resourceConfigs`, `cdnPreviewAddress`, `menuLengthThreshold`, `currentUser`, `courseToolSwitch`, `courseScormFileUrl` (+6) |
| 24 | GET | `/api/v1/system/skin-config/skin` | 2 | - |
| 25 | GET | `/api/v1/system/topic/hot-all` | 2 | - |

## /api/v1/training

| # | 方法 | 路径 | 调用 | 响应字段 |
|---|------|------|------|----------|
| 1 | GET | `/api/v1/training/home-lecturer` | 2 | - |

---

## 分院与专区

### 组织结构

- **[1]** 全行业

### 专区（业务分类）

- **烟叶生产** → `/#/staticConfigNew/40288177515b351601515b`
- **卷烟销售** → `/#/staticConfigNew/40288177515b351601515b`
- **专卖管理** → `/#/staticConfigNew/40288177515b351601515b`
- **烟草物流** → `/#/staticConfigNew/40288177515b351601515b`
- **技能鉴定** → `/#/staticConfigNew/40288177515b351601515b`
- **综合管理** → `/#/staticConfigNew/40288177515b351601515b`

### 专题列表

- **习近平总书记的重要讲话精神** → `/#/study/subject/detail/813d5d89-bea9-4e6`
- **深入学习贯彻习近平总书记论述摘编** → `/#/study/subject/detail/6a3153f5-9e94-4d2`
- **马列主义经典著作导读** → `/#/study/subject/detail/faad900d-93a6-476`
- **壮大战略性新兴产业，培育经济新动能** → `/#/study/subject/detail/a66f4509-e869-4a9`
- **加强国有企业管理，筑牢合法合规防线** → `/#/study/subject/detail/0dac0b1b-12bd-45d`
- **壮国有企...先进技术应用** → `/#/study/subject/detail/8e930e92-8984-43b`
- **数字时代风险与内控体系设计** → `/#/study/subject/detail/edd3de94-7323-4cd`
- **深入学习贯彻...党性修养** → `/#/study/subject/detail/e6bb8f5c-1a32-448`

---

## 关键 API 速查

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


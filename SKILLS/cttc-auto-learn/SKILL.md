---
name: cttc-auto-learn
description: |
  烟草网络学院 (mooc.ctt.cn) 自动学习脚本。支持刷学时、刷专题、刷课程、刷任务四种模式。
  触发词：烟草、网络学院、mooc、自动学习、学时、cttc、刷专题、刷课程、刷任务。
  安装：`npx skills add gandli/cttc-auto-learn`
  用户只需说"帮我刷学时"，Agent 自动完成全部流程。
tags: [playwright, automation, china-tobacco, video, agent-workflow]
project_url: https://github.com/gandli/cttc-auto-learn
---

# 烟草网络学院自动学习

> 用户只需安装此 SKILL，说"帮我刷学时"即可。Agent 自动完成环境搭建、登录、学习。

## Agent 执行流程（按顺序执行）

### Step 1: 安装 SKILL（如果还没有）

```bash
npx skills add gandli/cttc-auto-learn
```

### Step 2: 克隆项目

```bash
# 检查项目是否存在
if [ ! -d ~/Desktop/cttc-auto-learn ]; then
  git clone https://github.com/gandli/cttc-auto-learn.git ~/Desktop/cttc-auto-learn
fi
cd ~/Desktop/cttc-auto-learn
```

### Step 3: 安装依赖

```bash
cd ~/Desktop/cttc-auto-learn
uv sync
```

### Step 4: 清理环境

```bash
# 清除 Python 缓存
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
```

**注意：** 不要使用 `taskkill //F //IM chrome.exe`，这会误杀 Hermes Agent 的浏览器进程。脚本会自动清理自己的 Chrome 进程。

### Step 5: 首次登录（需要用户扫码）

检查凭证文件是否存在且有效：

```bash
ls output/auth-state.json 2>/dev/null
```

**如果不存在或已过期**，需要用户扫码登录：

```bash
cd ~/Desktop/cttc-auto-learn
uv run python main.py
```

**登录流程特性：**
- **事件驱动**：监听页面跳转 (`framenavigated`)，扫码后立即检测成功
- **双二维码**：同时提供 APP 和微信两种扫码方式
- **自动刷新**：二维码过期时自动刷新并重新保存图片
- **即时响应**：无需轮询，登录成功后立即开始学习

**二维码图片位置：**
- `output/qrcode-app.png` — APP 扫码
- `output/qrcode-wechat.png` — 微信扫码

### Step 6: 运行自动学习

登录成功后，根据用户需求运行对应模式：

```bash
cd ~/Desktop/cttc-auto-learn

# 刷学时（默认）
uv run python main.py --mode hours --target 50 --headless

# 刷专题
uv run python main.py --mode topics --headless

# 刷课程
uv run python main.py --mode courses --headless

# 刷任务
uv run python main.py --mode tasks --headless
```

**参数说明：**
- `--mode` — 运行模式（hours/topics/courses/tasks）
- `--target` — 目标学时（默认 50）
- `--headless` — 无头模式（推荐，不显示浏览器窗口）

## 支持模式

| 模式 | 命令 | 说明 |
|------|------|------|
| 刷学时 | `uv run python main.py --mode hours` | 播放视频累计学时（默认） |
| 刷专题 | `uv run python main.py --mode topics` | 完成专题课程 |
| 刷课程 | `uv run python main.py --mode courses` | 完成所有未完成课程 |
| 刷任务 | `uv run python main.py --mode tasks` | 完成指定任务 |

**触发词对应模式：**
- "帮我刷学时" / "累计学时" → `--mode hours`
- "帮我刷专题" / "完成专题" → `--mode topics`
- "帮我刷课程" / "完成课程" → `--mode courses`
- "帮我刷任务" / "完成任务" → `--mode tasks`

## DataManager（v1.1.0 新增）

登录后自动获取全部数据，保存到 `data/` 目录：

| 文件 | 内容 | API |
|------|------|-----|
| `data/courses.json` | 我的课程 | `personCourse-list` |
| `data/topics.json` | 我的专题 | DOM 托底 |
| `data/tasks.json` | 我的任务 | `/api/v1/human/task` |
| `data/study_stats.json` | 学时统计 | `credit/detail-hour-member` |

**查看数据报告：**

```bash
uv run python scripts/list_courses.py
```

## 监控运行

### 检查脚本是否在运行

```bash
# Windows
tasklist | findstr python

# 或检查进程
ps aux | grep main.py
```

### 读取实时状态（推荐）

脚本运行时会自动更新 `output/status.json`：

```bash
cat output/status.json
```

**status.json 字段说明：**

| 字段 | 说明 |
|------|------|
| `status` | 当前状态：playing / idle / error |
| `current_video` | 正在播放的视频名称 |
| `video_progress` | 视频播放进度（百分比） |
| `study_hours_current` | 当前学时 |
| `study_hours_target` | 目标学时 |
| `courses_completed` | 已完成课程数 |
| `courses_pending` | 待学习课程数 |
| `errors_count` | 错误次数 |

### Agent 主动汇报模板

Agent 可以定期读取 status.json 并向用户汇报：

```
📊 学习进度汇报：
- 学时：33/50 小时 (66%)
- 当前视频：《资本论》导读 (22.4%)
- 已完成：261 门
- 待学习：75 门
- 状态：🟢 正常运行
```

## 运行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--mode` | hours | 运行模式 |
| `--target` | 50.0 | 目标学时 |
| `--headless` | False | 无头模式 |

## 常见问题

### 1. 40909 错误（多开限制）
**现象：** 日志出现 `40909`
**原因：** 多个脚本实例或浏览器会话同时访问同一课程
**解决：** 等待 30 秒自动重试，或关闭其他浏览器窗口

### 2. 40904 错误（studyTime 错误）
**现象：** 日志出现 `40904`
**原因：** studyTime 必须是增量值（≤30秒），不能等于 lessonLocation
**解决：** 脚本已自动处理，无需干预

### 3. 浏览器崩溃
**现象：** 日志出现浏览器相关错误
**解决：** 脚本会自动恢复（最多 5 次），如持续崩溃请重启脚本

### 4. 学时不增长
**现象：** status.json 中 study_hours_current 不变
**原因：** 可能是视频未完全播放完成
**解决：** 检查 video_progress 是否达到 100%

### 5. 二维码过期
**现象：** 扫码后无反应
**解决：** 脚本会自动刷新二维码，重新扫码即可

## 技术细节（供参考）

- **加密方式：** AES-128-ECB
- **上报频率：** 每 ~3 分钟
- **完成标志：** `finishStatus=2`, `completedRate=100%`
- **防挂机：** 每 5 分钟模拟鼠标移动
- **单实例：** 文件锁防止多开
- **标签页管理：** 严格单标签，自动关闭多余标签页
- **数据获取：** API 优先，DOM 托底

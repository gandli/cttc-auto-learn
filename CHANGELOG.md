# Changelog

## v0.0.1 (2026-06-20)

- 599ca90 docs: README 增加人类使用说明（克隆、安装依赖、运行）
- 5b59d7c docs: 支持 pip + venv 原生安装方式
- b19f80e docs: add development roadmap to README
- 1ddf71f ci: fix changelog workflow — use git log instead of requarks action

## v0.0.2 (2026-06-20)

### Roadmap
- 新增「刷班级」模式开发计划 (`--mode classes`)
- 油猴脚本版 (tampermonkey 分支) v0.1.0
- CDP 版本 (cdp 分支) v0.1.0

### CI/CD
- 修复 GitHub Actions changelog workflow（requarks → Python 脚本）
- 去重逻辑：匹配已有 commit hash，避免重复条目

## v0.0.1 (2026-06-20)

### Features
- QR 扫码登录（APP + 微信双通道）
- v22 快速登录：headless Chrome + HTTP 并行轮询
- 四种运行模式：hours / topics / courses / tasks
- 视频自动播放与进度监控
- 学时统计与目标驱动自动停止
- DataManager API 数据获取
- StudyPlanner 智能学习规划
- 组织/分院 API

### Tests
- 168 tests passed
- 覆盖登录、播放、进度、监控、模式调度

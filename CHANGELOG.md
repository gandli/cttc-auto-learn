# Changelog

本项目所有重要更改都记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。


## [0.0.3] - 2026-06-20

### 新增
- 添加 MIT 开源许可证 (`LICENSE`)
- 添加贡献指南 (`CONTRIBUTING.md`)，中英文双语
- 添加 `cttc/py.typed` 标记文件支持 PEP 561 类型检查
- `pyproject.toml` 声明 `license = "MIT"`
- 新增 `test_planner.py` (15 个测试) 和 `test_ui.py` (16 个测试)

### 变更
- 拆分 `main.py` (900+ 行) 为模块化结构：`main.py` (160 行) + `cttc/ui.py` (200 行) + `cttc/modes.py` (550 行)
- 所有公共函数添加类型提示 (type hints)
- 所有公共函数添加文档字符串 (docstrings)
- 探索脚本移至 `scripts/explore/`，分析文档移至 `docs/`
- `qr-gen` 日志移至 `logs/` 目录
- CI CHANGELOG 工作流改为 Keep a Changelog 规范

### 测试
- 测试覆盖率从 53% 提升至 63%
- `planner.py` 覆盖率: 0% → 97%
- `ui.py` 覆盖率: 4% → 90%
- 总测试数: 168 → 199 tests passed

## [0.0.2] - 2026-06-20

### 新增
- 登录后展示数据看板（学时进度条、课程/专题/任务统计）
- 交互式目标选择（智能推荐：优先显示未达标项、进行中任务）
- `--mode` 参数改为可选，默认交互式选择

### 变更
- 二维码路径统一改为相对路径
- fetch_qr_codes 返回相对路径
- 日志和回调统一使用相对路径
- 更新测试适配新流程

### 修复
- 移除集中培训学时选项（线下进行，脚本不支持）

## [0.0.1] - 2026-06-20

### 新增
- QR 扫码登录（APP + 微信双通道）
- 快速登录：headless Chrome + HTTP 并行轮询
- 四种运行模式：hours / topics / courses / tasks
- 视频自动播放与进度监控
- 学时统计与目标驱动自动停止
- DataManager API 数据获取
- StudyPlanner 智能学习规划
- 组织/分院 API

### 测试
- 168 tests passed
- 覆盖登录、播放、进度、监控、模式调度

[0.0.3]: https://github.com/gandli/cttc-auto-learn/compare/v0.0.2...v0.0.3
[0.0.2]: https://github.com/gandli/cttc-auto-learn/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/gandli/cttc-auto-learn/releases/tag/v0.0.1

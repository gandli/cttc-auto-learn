# Contributing to cttc-auto-learn

[English](#how-to-contribute) | [中文](#如何贡献)

---

## How to Contribute

### Prerequisites

- Python 3.11+
- Git
- Windows 10/11

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/gandli/cttc-auto-learn.git
cd cttc-auto-learn

# Install with dev dependencies
uv sync --all-extras
# or
pip install -e ".[test]"

# Install Playwright browsers
playwright install chromium
```

### Code Quality Standards

| Requirement | Standard |
|-------------|----------|
| Function length | ≤ 50 lines |
| Type hints | Required for all functions |
| Docstrings | Required for all public functions |
| Tests | Required for new features |
| Coverage | Maintain ≥ 60% |

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=cttc --cov-report=term-missing

# Run specific test file
pytest tests/test_player.py -v
```

### Code Style

- Follow PEP 8
- Use `ruff` for linting (if configured)
- Use `black` for formatting (if configured)
- All strings in Chinese for user-facing messages

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new feature
fix: fix a bug
docs: update documentation
test: add tests
refactor: refactor code
chore: maintenance tasks
```

### Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest`)
6. Commit your changes (`git commit -m 'feat: add my feature'`)
7. Push to the branch (`git push origin feat/my-feature`)
8. Open a Pull Request

### Reporting Issues

When reporting issues, please include:

- Python version
- Playwright version
- Error message and stack trace
- Steps to reproduce

---

## 如何贡献

### 前置条件

- Python 3.11+
- Git
- Windows 10/11

### 搭建开发环境

```bash
# 克隆仓库
git clone https://github.com/gandli/cttc-auto-learn.git
cd cttc-auto-learn

# 安装依赖（含开发依赖）
uv sync --all-extras
# 或
pip install -e ".[test]"

# 安装 Playwright 浏览器
playwright install chromium
```

### 代码质量标准

| 要求 | 标准 |
|------|------|
| 函数长度 | ≤ 50 行 |
| 类型提示 | 所有函数必须添加 |
| 文档字符串 | 所有公共函数必须添加 |
| 测试 | 新功能必须附带测试 |
| 覆盖率 | 维持 ≥ 60% |

### 运行测试

```bash
# 运行所有测试
pytest

# 运行并查看覆盖率
pytest --cov=cttc --cov-report=term-missing

# 运行特定测试文件
pytest tests/test_player.py -v
```

### 代码风格

- 遵循 PEP 8
- 使用 `ruff` 进行代码检查（如已配置）
- 使用 `black` 进行代码格式化（如已配置）
- 所有用户可见的字符串使用中文

### 提交信息规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
feat: 添加新功能
fix: 修复 bug
docs: 更新文档
test: 添加测试
refactor: 重构代码
chore: 维护任务
```

### Pull Request 流程

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feat/my-feature`)
3. 进行修改
4. 为新功能添加测试
5. 确保所有测试通过 (`pytest`)
6. 提交修改 (`git commit -m 'feat: 添加我的功能'`)
7. 推送分支 (`git push origin feat/my-feature`)
8. 发起 Pull Request

### 报告问题

报告问题时，请提供：

- Python 版本
- Playwright 版本
- 错误信息和堆栈跟踪
- 复现步骤

---

感谢你的贡献！🙏

"""共享测试 fixtures"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cttc.config import Config
from cttc.logger import Logger


@pytest.fixture
def tmp_dir(tmp_path):
    """临时目录，用于隔离测试文件"""
    return tmp_path


@pytest.fixture
def config(tmp_dir):
    """测试用 Config 实例"""
    # 创建必要的目录
    (tmp_dir / "output").mkdir(parents=True, exist_ok=True)
    (tmp_dir / "output" / "screenshots").mkdir(parents=True, exist_ok=True)
    (tmp_dir / "data").mkdir(parents=True, exist_ok=True)
    (tmp_dir / "logs").mkdir(parents=True, exist_ok=True)

    return Config(
        output_dir=str(tmp_dir / "output"),
        screenshot_dir=str(tmp_dir / "output" / "screenshots"),
        progress_file=str(tmp_dir / "data" / "progress.json"),
        courses_file=str(tmp_dir / "data" / "courses.json"),
        study_time_file=str(tmp_dir / "data" / "study_time.json"),
        log_file=str(tmp_dir / "logs" / "cttc.log"),
    )


@pytest.fixture
def log(tmp_dir):
    """测试用 Logger 实例"""
    return Logger(str(tmp_dir / "test.log"))


@pytest.fixture
def mock_page():
    """模拟 Playwright Page"""
    page = AsyncMock()
    page.evaluate = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.screenshot = AsyncMock()
    page.reload = AsyncMock()
    page.go_back = AsyncMock()
    return page


@pytest.fixture
def mock_context():
    """模拟 Playwright BrowserContext"""
    ctx = AsyncMock()
    ctx.storage_state = AsyncMock(return_value={
        "cookies": [],
        "origins": []
    })
    return ctx


@pytest.fixture
def mock_browser():
    """模拟 Playwright Browser"""
    browser = AsyncMock()
    return browser


@pytest.fixture
def sample_state():
    """示例浏览器状态数据"""
    return {
        "cookies": [
            {
                "name": "session",
                "value": "abc123",
                "domain": "mooc.ctt.cn",
                "path": "/"
            }
        ],
        "origins": [
            {
                "origin": "https://mooc.ctt.cn",
                "localStorage": [
                    {"name": "token", "value": "test_token"}
                ],
                "sessionStorage": [
                    {"name": "user", "value": "test_user"}
                ]
            }
        ]
    }


@pytest.fixture
def sample_progress():
    """示例进度数据"""
    return {
        "courses": {
            "course-1": {"title": "测试课程1", "status": "completed"},
            "course-2": {"title": "测试课程2", "status": "in_progress"}
        },
        "last_updated": "2026-06-17T10:00:00"
    }


@pytest.fixture
def sample_study_time():
    """示例学时数据"""
    return {
        "records": [
            {"timestamp": "2026-06-17T10:00:00", "total_hours": 5.0, "delta": 0.5}
        ],
        "current_total": 5.0,
        "last_increase": "2026-06-17T10:00:00",
        "stale_since": None
    }

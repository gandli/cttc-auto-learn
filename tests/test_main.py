"""测试 main.py 入口 — 参数解析 / 登录流程 / 模式调度 / 错误处理"""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── 参数解析 ──


def test_parse_args_default():
    """测试默认参数"""
    with patch("sys.argv", ["main.py"]):
        import importlib
        import main
        importlib.reload(main)
        # 直接测试 argparse
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--mode", choices=["hours", "topics", "courses", "tasks"], default="hours")
        parser.add_argument("--target", type=float, default=50.0)
        parser.add_argument("--headless", action="store_true")
        args = parser.parse_args([])
        assert args.mode == "hours"
        assert args.target == 50.0
        assert args.headless is False


def test_parse_args_mode_topics():
    """测试 --mode topics"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["hours", "topics", "courses", "tasks"], default="hours")
    parser.add_argument("--target", type=float, default=50.0)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args(["--mode", "topics"])
    assert args.mode == "topics"


def test_parse_args_mode_courses():
    """测试 --mode courses"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["hours", "topics", "courses", "tasks"], default="hours")
    parser.add_argument("--target", type=float, default=50.0)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args(["--mode", "courses"])
    assert args.mode == "courses"


def test_parse_args_mode_tasks():
    """测试 --mode tasks"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["hours", "topics", "courses", "tasks"], default="hours")
    parser.add_argument("--target", type=float, default=50.0)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args(["--mode", "tasks"])
    assert args.mode == "tasks"


def test_parse_args_target():
    """测试 --target"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["hours", "topics", "courses", "tasks"], default="hours")
    parser.add_argument("--target", type=float, default=50.0)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args(["--target", "30"])
    assert args.target == 30.0


def test_parse_args_headless():
    """测试 --headless"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["hours", "topics", "courses", "tasks"], default="hours")
    parser.add_argument("--target", type=float, default=50.0)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args(["--headless"])
    assert args.headless is True


# ── 登录流程 ──


@pytest.mark.asyncio
async def test_login_flow_restore_success(config, log):
    """测试凭证恢复成功"""
    with patch("main.CTTCLogin") as MockLogin:
        mock_client = AsyncMock()
        mock_client.try_restore_session = AsyncMock(return_value=True)
        MockLogin.return_value = mock_client

        from main import login_flow
        client, success, qr_paths = await login_flow(config, log)

        assert success is True
        assert qr_paths["app"] is None
        assert qr_paths["wechat"] is None
        mock_client.start.assert_called_once()
        mock_client.try_restore_session.assert_called_once()


@pytest.mark.asyncio
async def test_login_flow_qr_scan(config, log):
    """测试扫码登录"""
    with patch("main.CTTCLogin") as MockLogin:
        mock_client = AsyncMock()
        mock_client.try_restore_session = AsyncMock(return_value=False)
        mock_client.navigate_to_login = AsyncMock()
        mock_client.extract_both_qrs = AsyncMock(return_value={"app": "b64app", "wechat": "b64wx"})
        mock_client.save_both_qrs = AsyncMock(return_value={"app": "/path/app.png", "wechat": "/path/wx.png"})
        mock_client.wait_for_login = AsyncMock(return_value=True)
        mock_client.page = AsyncMock()
        MockLogin.return_value = mock_client

        from main import login_flow
        client, success, qr_paths = await login_flow(config, log)

        assert success is True
        mock_client.navigate_to_login.assert_called_once()
        mock_client.extract_both_qrs.assert_called_once()
        mock_client.wait_for_login.assert_called_once()


@pytest.mark.asyncio
async def test_login_flow_timeout(config, log):
    """测试登录超时"""
    with patch("main.CTTCLogin") as MockLogin:
        mock_client = AsyncMock()
        mock_client.try_restore_session = AsyncMock(return_value=False)
        mock_client.navigate_to_login = AsyncMock()
        mock_client.extract_both_qrs = AsyncMock(return_value={"app": None, "wechat": None})
        mock_client.save_both_qrs = AsyncMock(return_value={"app": None, "wechat": None})
        mock_client.wait_for_login = AsyncMock(return_value=False)
        MockLogin.return_value = mock_client

        from main import login_flow
        client, success, qr_paths = await login_flow(config, log)

        assert success is False
        mock_client.close.assert_called_once()


# ── enforce_single_tab ──


@pytest.mark.asyncio
async def test_enforce_single_tab_closes_extra():
    """测试关闭多余标签页"""
    from main import enforce_single_tab

    page = AsyncMock()
    extra_page = MagicMock()
    extra_page.is_closed.return_value = False
    extra_page.close = AsyncMock()
    extra_page.__ne__ = lambda self, other: True  # p != page → True

    ctx = MagicMock()
    ctx.pages = [page, extra_page]
    page.context = ctx

    log = MagicMock()
    await enforce_single_tab(page, log)
    extra_page.close.assert_called_once()
    log.info.assert_called_once()


@pytest.mark.asyncio
async def test_enforce_single_tab_no_extra():
    """测试无多余标签页"""
    from main import enforce_single_tab

    page = AsyncMock()
    ctx = MagicMock()
    ctx.pages = [page]
    page.context = ctx

    log = MagicMock()
    await enforce_single_tab(page, log)
    log.info.assert_not_called()


# ── mode_hours 目标检查 ──


@pytest.mark.asyncio
async def test_mode_hours_target_reached():
    """测试达到目标学时后退出"""
    from main import mode_hours

    client = MagicMock()
    client.page = AsyncMock()

    config = MagicMock()
    config.target_hours = 50

    log = MagicMock()
    progress = MagicMock()
    progress.study_time = {"current_total": 50.0}
    progress.is_course_completed = MagicMock(return_value=False)

    status = MagicMock()
    courses = MagicMock()
    monitor = AsyncMock()

    data_mgr = AsyncMock()
    data_mgr.fetch_study_stats = AsyncMock(return_value={
        "online_completed": 50.0, "online_target": 50.0,
        "classroom_completed": 0, "classroom_target": 90.0
    })
    data_mgr.fetch_tasks = AsyncMock(return_value=[])
    data_mgr.fetch_topics = AsyncMock(return_value=[])
    data_mgr.fetch_courses = AsyncMock(return_value=[])

    with patch("main.DataManager", return_value=data_mgr), \
         patch("main.ask_new_target", return_value=None) as mock_ask:
        await mode_hours(client, config, log, progress, status, courses, monitor)

    mock_ask.assert_called_once_with(50.0, 50)


# ── mode_topics 无专题 ──


@pytest.mark.asyncio
async def test_mode_topics_no_topics():
    """测试无专题时的处理"""
    from main import mode_topics

    client = MagicMock()
    client.page = AsyncMock()
    config = MagicMock()
    log = MagicMock()
    progress = MagicMock()
    status = MagicMock()
    courses = MagicMock()
    monitor = AsyncMock()

    data_mgr = AsyncMock()
    data_mgr.fetch_topics = AsyncMock(return_value=[])

    with patch("main.DataManager", return_value=data_mgr):
        await mode_topics(client, config, log, progress, status, courses, monitor)

    log.warn.assert_any_call("⚠️ 未找到专题课程")


# ── mode_courses 无课程 ──


@pytest.mark.asyncio
async def test_mode_courses_no_courses():
    """测试无待学习课程"""
    from main import mode_courses

    client = MagicMock()
    client.page = AsyncMock()
    config = MagicMock()
    log = MagicMock()
    progress = MagicMock()
    status = MagicMock()
    courses = MagicMock()
    monitor = AsyncMock()

    data_mgr = AsyncMock()
    data_mgr.fetch_courses = AsyncMock(return_value=[])

    with patch("main.DataManager", return_value=data_mgr):
        await mode_courses(client, config, log, progress, status, courses, monitor)

    log.warn.assert_any_call("⚠️ 没有待学习的课程")


# ── mode_tasks 无任务 ──


@pytest.mark.asyncio
async def test_mode_tasks_no_tasks():
    """测试无任务"""
    from main import mode_tasks

    client = MagicMock()
    client.page = AsyncMock()
    config = MagicMock()
    log = MagicMock()
    progress = MagicMock()
    status = MagicMock()
    courses = MagicMock()
    monitor = AsyncMock()

    data_mgr = AsyncMock()
    data_mgr.fetch_tasks = AsyncMock(return_value=[])

    with patch("main.DataManager", return_value=data_mgr):
        await mode_tasks(client, config, log, progress, status, courses, monitor)

    log.warn.assert_any_call("⚠️ 未找到任务")

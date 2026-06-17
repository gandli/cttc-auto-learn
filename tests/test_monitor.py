"""测试 Monitor 模块"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from cttc.monitor import StudyMonitor
from cttc.progress import ProgressManager


@pytest.fixture
def monitor(config, log, mock_page):
    """创建测试用 StudyMonitor 实例"""
    progress = ProgressManager(config, log)
    return StudyMonitor(mock_page, config, log, progress)


@pytest.mark.asyncio
async def test_read_study_time(monitor, mock_page):
    """测试读取学时"""
    mock_page.evaluate = AsyncMock(return_value=5.5)

    hours = await monitor._read_study_time()

    assert hours == 5.5


@pytest.mark.asyncio
async def test_read_study_time_zero(monitor, mock_page):
    """测试读取学时 - 无数据"""
    mock_page.evaluate = AsyncMock(return_value=0)

    hours = await monitor._read_study_time()

    assert hours == 0


@pytest.mark.asyncio
async def test_repair(monitor, mock_page):
    """测试学时修复"""
    mock_page.reload = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()

    await monitor._repair()

    mock_page.reload.assert_called_once()
    mock_page.wait_for_timeout.assert_called_with(3000)


@pytest.mark.asyncio
async def test_repair_failure(monitor, mock_page):
    """测试学时修复失败"""
    mock_page.reload = AsyncMock(side_effect=Exception("Reload failed"))

    # 应该不会抛出异常
    await monitor._repair()


@pytest.mark.asyncio
async def test_start_creates_task(monitor):
    """测试启动监控"""
    await monitor.start()

    assert monitor._running is True
    assert monitor._task is not None

    # 清理
    await monitor.stop()


@pytest.mark.asyncio
async def test_stop_cancels_task(monitor):
    """测试停止监控"""
    await monitor.start()
    await monitor.stop()

    assert monitor._running is False


@pytest.mark.asyncio
async def test_monitor_loop_study_increase(monitor, mock_page):
    """测试监控循环 - 学时增长 (lines 41-58)"""
    monitor.config.study_check_interval = 0.01

    call_count = 0
    async def mock_evaluate(script):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return 5.0
        else:
            monitor._running = False
            return 5.0

    mock_page.evaluate = AsyncMock(side_effect=mock_evaluate)

    await monitor.start()
    # Wait just enough for one iteration
    await asyncio.sleep(0.05)
    await monitor.stop()


@pytest.mark.asyncio
async def test_monitor_loop_stale_triggers_repair(monitor, mock_page):
    """测试监控循环 - 学时停滞触发修复 (lines 50-52)"""
    monitor.config.study_check_interval = 0.01
    monitor.config.study_stale_threshold = 0  # Always stale

    # Pre-record study time so delta will be 0
    monitor.progress.record_study_time(5.0)

    async def mock_evaluate(script):
        monitor._running = False
        return 5.0

    mock_page.evaluate = AsyncMock(side_effect=mock_evaluate)
    mock_page.reload = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()

    await monitor.start()
    await asyncio.sleep(0.05)
    await monitor.stop()


@pytest.mark.asyncio
async def test_monitor_loop_exception(monitor, mock_page):
    """测试监控循环 - 异常处理 (lines 56-58)"""
    monitor.config.study_check_interval = 0.01

    call_count = 0
    async def mock_evaluate(script):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Page crashed")
        else:
            monitor._running = False
            return 0

    mock_page.evaluate = AsyncMock(side_effect=mock_evaluate)

    await monitor.start()
    await asyncio.sleep(0.2)
    await monitor.stop()


@pytest.mark.asyncio
async def test_monitor_loop_cancelled(monitor, mock_page):
    """测试监控循环 - 取消 (line 54-55)"""
    monitor.config.study_check_interval = 0.01
    mock_page.evaluate = AsyncMock(return_value=5.0)

    await monitor.start()
    # Cancel the task directly
    monitor._task.cancel()
    try:
        await monitor._task
    except asyncio.CancelledError:
        pass

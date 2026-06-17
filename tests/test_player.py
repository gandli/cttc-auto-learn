"""player 模块测试"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cttc.player import VideoPlayer


@pytest.fixture
def player():
    page = AsyncMock()
    page.evaluate = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.reload = AsyncMock()
    page.on = MagicMock()

    config = MagicMock()
    config.page_timeout = 15000

    log = MagicMock()
    progress = MagicMock()

    p = VideoPlayer(page, config, log, progress)
    return p


# ── setup ──

def test_setup_registers_response_handler(player):
    player.setup()
    # 需要 await
    loop = asyncio.new_event_loop()
    loop.run_until_complete(player.setup())
    loop.close()
    player.page.on.assert_called()


# ── _find_and_play ──

@pytest.mark.asyncio
async def test_find_and_play_plays_video(player):
    # has_video=True, video.play()=True, 3s后确认is_playing=True
    player.page.evaluate = AsyncMock(side_effect=[True, True, True])
    result = await player._find_and_play()
    assert result is True


@pytest.mark.asyncio
async def test_find_and_play_clicks_button(player):
    # 20个False(无video) → 跳过策略1 → 按钮返回'vjs-big-play-button' → 确认is_playing=True
    player.page.evaluate = AsyncMock(side_effect=[False] * 20 + ['vjs-big-play-button', True])
    result = await player._find_and_play()
    assert result is True


@pytest.mark.asyncio
async def test_find_and_play_nothing_found(player):
    # 20个False(无video) → 按钮返回None → 无控件 → False
    player.page.evaluate = AsyncMock(side_effect=[False] * 20 + [None])
    result = await player._find_and_play()
    assert result is False


# ── _set_quality_standard ──

@pytest.mark.asyncio
async def test_set_quality_found(player):
    player.page.evaluate = AsyncMock(return_value="ok")
    await player._set_quality_standard()
    player.log.info.assert_called()


@pytest.mark.asyncio
async def test_set_quality_not_found(player):
    player.page.evaluate = AsyncMock(return_value=None)
    await player._set_quality_standard()
    player.log.info.assert_called()


# ── _read_video_status ──

@pytest.mark.asyncio
async def test_read_video_status_from_video(player):
    player.page.evaluate = AsyncMock(return_value={
        "found": True,
        "currentTime": 100,
        "duration": 300,
        "paused": False,
        "ended": False,
        "progress": 33.3,
        "source": "video"
    })
    status = await player._read_video_status()
    assert status["found"] is True
    assert status["currentTime"] == 100


@pytest.mark.asyncio
async def test_read_video_status_not_found(player):
    player.page.evaluate = AsyncMock(return_value={"found": False})
    player._api_progress = None
    status = await player._read_video_status()
    assert status["found"] is False


@pytest.mark.asyncio
async def test_read_video_status_from_api(player):
    player.page.evaluate = AsyncMock(return_value={"found": False})
    player._api_progress = {
        "lessonLocation": "200",
        "remainingTime": 100,
        "finishStatus": 1,
    }
    player._api_progress_time = 9999999999
    import time
    player._api_progress_time = time.time()
    status = await player._read_video_status()
    assert status["found"] is True
    assert status["currentTime"] == 200
    assert status["duration"] == 300


# ── _handle_popups ──

@pytest.mark.asyncio
async def test_handle_popups_found(player):
    player.page.evaluate = AsyncMock(return_value=["button: 确定", "DIV[class*=\"close\"] class=\"modal-close\" text=\"×\""])
    await player._handle_popups()
    player.log.info.assert_called()


@pytest.mark.asyncio
async def test_handle_popups_none(player):
    player.page.evaluate = AsyncMock(return_value=[])
    await player._handle_popups()
    # 不应该打印日志


# ── _wait_for_complete ──

@pytest.mark.asyncio
async def test_wait_for_complete_ends(player):
    """视频正常结束"""
    player.page.evaluate = AsyncMock(side_effect=[
        # _maybe_move_mouse (不需要)
        None,
    ])
    player._read_video_status = AsyncMock(side_effect=[
        {"found": True, "currentTime": 100, "duration": 300, "paused": False, "ended": False, "progress": 33, "source": "vjs"},
        {"found": True, "currentTime": 300, "duration": 300, "paused": False, "ended": True, "progress": 100, "source": "vjs"},
    ])
    player._maybe_move_mouse = AsyncMock()
    result = await player._wait_for_complete(timeout=60)
    assert result is True


@pytest.mark.asyncio
async def test_wait_for_complete_target_closed(player):
    """页面崩溃"""
    player._read_video_status = AsyncMock(side_effect=Exception("Target closed"))
    player._maybe_move_mouse = AsyncMock()
    result = await player._wait_for_complete(timeout=60)
    assert result is False


@pytest.mark.asyncio
async def test_wait_for_complete_not_found_over_90(player):
    """进度 > 90% 后元素消失，等待 API 确认后完成"""
    player._read_video_status = AsyncMock(side_effect=[
        {"found": True, "currentTime": 280, "duration": 300, "paused": False, "ended": False, "progress": 93, "source": "vjs"},
        {"found": False},
    ])
    player._maybe_move_mouse = AsyncMock()
    player._wait_for_api_completion = AsyncMock(return_value=True)
    result = await player._wait_for_complete(timeout=60)
    assert result is True


@pytest.mark.asyncio
async def test_wait_for_complete_paused_auto_resume(player):
    """暂停自动恢复"""
    call_count = 0
    async def mock_read():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return {"found": True, "currentTime": 100, "duration": 300, "paused": True, "ended": False, "progress": 33, "source": "vjs"}
        return {"found": True, "currentTime": 300, "duration": 300, "paused": False, "ended": True, "progress": 100, "source": "vjs"}

    player._read_video_status = mock_read
    player._maybe_move_mouse = AsyncMock()
    player.page.evaluate = AsyncMock()
    result = await player._wait_for_complete(timeout=60)
    assert result is True


@pytest.mark.asyncio
async def test_wait_for_complete_timeout(player):
    """超时"""
    player._read_video_status = AsyncMock(return_value={
        "found": True, "currentTime": 100, "duration": 300,
        "paused": False, "ended": False, "progress": 33, "source": "vjs"
    })
    player._maybe_move_mouse = AsyncMock()
    result = await player._wait_for_complete(timeout=1)
    assert result is False


# ── _repair_stalled ──

@pytest.mark.asyncio
async def test_repair_stalled(player):
    player.page.reload = AsyncMock()
    player._find_and_play = AsyncMock(return_value=True)
    player._set_quality_standard = AsyncMock()
    await player._repair_stalled()
    player.page.reload.assert_called()


@pytest.mark.asyncio
async def test_repair_stalled_exception(player):
    player.page.reload = AsyncMock(side_effect=Exception("fail"))
    await player._repair_stalled()
    player.log.warn.assert_called()


# ── _maybe_move_mouse ──

@pytest.mark.asyncio
async def test_move_mouse(player):
    import time
    player._last_mouse_move = time.time() - 26 * 60  # 26 分钟前
    player.page.evaluate = AsyncMock()
    await player._maybe_move_mouse()
    player.page.evaluate.assert_called()


@pytest.mark.asyncio
async def test_move_mouse_not_yet(player):
    import time
    player._last_mouse_move = time.time() - 10  # 10 秒前
    player.page.evaluate = AsyncMock()
    await player._maybe_move_mouse()
    player.page.evaluate.assert_not_called()


# ── _wait_for_api_completion ──

@pytest.mark.asyncio
async def test_wait_for_api_completion_finish_status_2(player):
    """API 返回 finishStatus=2 应立即返回 True"""
    player._api_progress = {"finishStatus": 2, "completedRate": 100, "lessonLocation": 600}
    import time as _time
    player._api_progress_time = _time.time()
    player.page.wait_for_timeout = AsyncMock()
    result = await player._wait_for_api_completion(timeout=10)
    assert result is True


@pytest.mark.asyncio
async def test_wait_for_api_completion_completed_rate_100(player):
    """API 返回 completedRate=100 应返回 True"""
    player._api_progress = {"finishStatus": 1, "completedRate": 100, "lessonLocation": 600}
    import time as _time
    player._api_progress_time = _time.time()
    player.page.wait_for_timeout = AsyncMock()
    result = await player._wait_for_api_completion(timeout=10)
    assert result is True


@pytest.mark.asyncio
async def test_wait_for_api_completion_timeout(player):
    """API 一直没确认应超时返回 False"""
    player._api_progress = {"finishStatus": 1, "completedRate": 95, "remainingTime": 30}
    import time as _time
    player._api_progress_time = _time.time() - 100  # 过期数据
    player.page.wait_for_timeout = AsyncMock()
    result = await player._wait_for_api_completion(timeout=1)
    assert result is False

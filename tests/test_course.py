"""测试 Course 模块"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from cttc.course import CourseManager
from cttc.progress import ProgressManager


@pytest.fixture
def course_manager(config, log, mock_page):
    """创建测试用 CourseManager 实例"""
    progress = ProgressManager(config, log)
    return CourseManager(mock_page, config, log, progress)


@pytest.mark.asyncio
async def test_get_study_time(course_manager, mock_page):
    """测试获取学时"""
    mock_page.evaluate = AsyncMock(return_value={"online": 28.1, "online_target": 50.0, "classroom": 26.0, "classroom_target": 90.0})
    hours = await course_manager.get_study_time()
    assert hours == 28.1


@pytest.mark.asyncio
async def test_get_study_time_zero(course_manager, mock_page):
    """测试获取学时 - 无数据"""
    mock_page.evaluate = AsyncMock(return_value=None)
    hours = await course_manager.get_study_time()
    assert hours == 0


@pytest.mark.asyncio
async def test_get_study_time_from_interceptor(course_manager):
    """测试从 API 拦截器获取学时 (line 23)"""
    course_manager._study_stats = {"online_completed": 42.5, "online_target": 50}
    hours = await course_manager.get_study_time()
    assert hours == 42.5


@pytest.mark.asyncio
async def test_get_study_time_from_interceptor_default(course_manager):
    """测试从 API 拦截器获取学时 - 无 online_completed key (line 23)"""
    course_manager._study_stats = {"other_key": 99}
    hours = await course_manager.get_study_time()
    assert hours == 0


@pytest.mark.asyncio
async def test_get_study_stats_from_interceptor(course_manager):
    """测试从 API 拦截器获取完整统计 (lines 44-45)"""
    stats = {"online_completed": 30, "online_target": 50, "classroom_completed": 20, "classroom_target": 90}
    course_manager._study_stats = stats
    result = await course_manager.get_study_stats()
    assert result == stats


@pytest.mark.asyncio
async def test_get_study_stats_dom_fallback(course_manager, mock_page):
    """测试 get_study_stats DOM 降级 (lines 44-64)"""
    dom_stats = {"online_target": 50.0, "online_completed": 28.0, "classroom_target": 90.0, "classroom_completed": 26.0}
    mock_page.evaluate = AsyncMock(return_value=dom_stats)

    result = await course_manager.get_study_stats()
    assert result == dom_stats


@pytest.mark.asyncio
async def test_get_study_stats_dom_fallback_empty(course_manager, mock_page):
    """测试 get_study_stats DOM 降级返回空 (line 64)"""
    mock_page.evaluate = AsyncMock(return_value=None)

    result = await course_manager.get_study_stats()
    assert result == {}


def test_setup_api_interceptor(course_manager, mock_page):
    """测试 API 拦截器设置 (lines 68-94)"""
    # Track listeners registered
    listeners = {}
    def on_event(event, callback):
        listeners[event] = callback
    mock_page.on = MagicMock(side_effect=on_event)

    course_manager.setup_api_interceptor()

    assert course_manager._study_stats == {}
    assert "response" in listeners
    mock_page.on.assert_called_with("response", listeners["response"])


@pytest.mark.asyncio
async def test_api_interceptor_courseHourResult(course_manager, mock_page):
    """测试 API 拦截器 - courseHourResult 格式 (lines 70-82)"""
    listeners = {}
    def on_event(event, callback):
        listeners[event] = callback
    mock_page.on = MagicMock(side_effect=on_event)

    course_manager.setup_api_interceptor()
    on_response = listeners["response"]

    # Simulate response with courseHourResult
    mock_response = AsyncMock()
    mock_response.url = "https://api.example.com/credit/detail-hour-member"
    mock_response.json = AsyncMock(return_value={
        "courseHourResult": {"totalHour": 25.5},
        "requireCourseHour": 50,
        "totalClassHour": 20,
        "requireClassHour": 90,
        "totalScore": 85,
    })

    await on_response(mock_response)

    assert course_manager._study_stats["online_completed"] == 25.5
    assert course_manager._study_stats["online_target"] == 50
    assert course_manager._study_stats["classroom_completed"] == 20
    assert course_manager._study_stats["classroom_target"] == 90
    assert course_manager._study_stats["total_score"] == 85


@pytest.mark.asyncio
async def test_api_interceptor_hourSelf(course_manager, mock_page):
    """测试 API 拦截器 - hourSelf 格式 (lines 83-90)"""
    listeners = {}
    def on_event(event, callback):
        listeners[event] = callback
    mock_page.on = MagicMock(side_effect=on_event)

    course_manager.setup_api_interceptor()
    on_response = listeners["response"]

    mock_response = AsyncMock()
    mock_response.url = "https://api.example.com/cadre-education/detail-hour-member"
    mock_response.json = AsyncMock(return_value={
        "hourSelf": 15.0,
        "requireCourseHour": 50,
        "hourTrain": 10.0,
        "requireClassHour": 90,
    })

    await on_response(mock_response)

    assert course_manager._study_stats["online_completed"] == 15.0
    assert course_manager._study_stats["online_target"] == 50
    assert course_manager._study_stats["classroom_completed"] == 10.0
    assert course_manager._study_stats["classroom_target"] == 90
    assert course_manager._study_stats["total_score"] == 0


@pytest.mark.asyncio
async def test_api_interceptor_ignores_other_urls(course_manager, mock_page):
    """测试 API 拦截器忽略无关 URL"""
    listeners = {}
    def on_event(event, callback):
        listeners[event] = callback
    mock_page.on = MagicMock(side_effect=on_event)

    course_manager.setup_api_interceptor()
    on_response = listeners["response"]

    mock_response = AsyncMock()
    mock_response.url = "https://api.example.com/other/endpoint"
    mock_response.json = AsyncMock(return_value={"something": "else"})

    await on_response(mock_response)
    assert course_manager._study_stats == {}


@pytest.mark.asyncio
async def test_api_interceptor_json_error(course_manager, mock_page):
    """测试 API 拦截器 JSON 解析失败 (line 91-92)"""
    listeners = {}
    def on_event(event, callback):
        listeners[event] = callback
    mock_page.on = MagicMock(side_effect=on_event)

    course_manager.setup_api_interceptor()
    on_response = listeners["response"]

    mock_response = AsyncMock()
    mock_response.url = "https://api.example.com/credit/detail-hour-member"
    mock_response.json = AsyncMock(side_effect=Exception("JSON parse error"))

    # Should not raise
    await on_response(mock_response)
    assert course_manager._study_stats == {}


@pytest.mark.asyncio
async def test_navigate_to_learning_center(course_manager, mock_page):
    """测试进入学习中心"""
    mock_page.goto = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value=None)
    mock_page.wait_for_timeout = AsyncMock()
    mock_page.locator = MagicMock(return_value=MagicMock(count=AsyncMock(return_value=0)))

    await course_manager.navigate_to_learning_center()

    mock_page.goto.assert_called_once()
    assert mock_page.wait_for_timeout.call_count >= 2


@pytest.mark.asyncio
async def test_get_special_topics(course_manager, mock_page):
    """测试获取专题课程列表"""
    mock_topics = [
        {"title": "专题1", "href": "https://example.com/1", "id": "1"},
        {"title": "专题2", "href": "https://example.com/2", "id": "2"},
    ]
    mock_page.evaluate = AsyncMock(return_value=mock_topics)

    topics = await course_manager.get_special_topics()

    assert len(topics) == 2
    assert topics[0]["title"] == "专题1"


@pytest.mark.asyncio
async def test_get_special_topics_empty(course_manager, mock_page):
    """测试获取专题课程列表 - 空列表"""
    mock_page.evaluate = AsyncMock(return_value=[])

    topics = await course_manager.get_special_topics()

    assert len(topics) == 0


@pytest.mark.asyncio
async def test_get_subject_courses(course_manager, mock_page):
    """测试获取课程列表"""
    mock_courses = [
        {"title": "课程1", "action": "continue", "status": "in_progress"},
        {"title": "课程2", "action": "review", "status": "completed"},
    ]
    mock_page.evaluate = AsyncMock(return_value=mock_courses)

    courses = await course_manager.get_subject_courses()

    assert len(courses) == 2
    assert courses[0]["action"] == "continue"
    assert courses[1]["action"] == "review"


@pytest.mark.asyncio
async def test_enter_course(course_manager, mock_page):
    """测试进入课程"""
    mock_page.goto = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()

    result = await course_manager.enter_course("https://example.com/course")

    assert result is True
    mock_page.goto.assert_called_once()


@pytest.mark.asyncio
async def test_enter_course_failure(course_manager, mock_page):
    """测试进入课程失败"""
    mock_page.goto = AsyncMock(side_effect=Exception("Navigation failed"))

    result = await course_manager.enter_course("https://example.com/course")

    assert result is False


@pytest.mark.asyncio
async def test_enter_course_invalid_href_empty(course_manager, mock_page):
    """测试进入课程 - 空链接 (line 192-194)"""
    result = await course_manager.enter_course("")
    assert result is False


@pytest.mark.asyncio
async def test_enter_course_invalid_href_javascript(course_manager, mock_page):
    """测试进入课程 - javascript: 链接 (line 192-194)"""
    result = await course_manager.enter_course("javascript:void(0)")
    assert result is False


@pytest.mark.asyncio
async def test_enter_course_invalid_href_no_http(course_manager, mock_page):
    """测试进入课程 - 非 http 链接 (line 192-194)"""
    result = await course_manager.enter_course("ftp://example.com")
    assert result is False


@pytest.mark.asyncio
async def test_click_course_action_found_with_popup(course_manager, mock_page, mock_context):
    """测试点击课程操作按钮 - 新窗口弹出 (lines 210-266)"""
    mock_page.context = mock_context

    # Simulate page.evaluate returning found
    mock_page.evaluate = AsyncMock(return_value={"found": True, "action": "继续学习"})
    mock_page.wait_for_timeout = AsyncMock()

    # Simulate new page opening after a few wait_for_timeout calls
    new_page = AsyncMock()
    new_page.url = "https://example.com/course/123"
    new_page.wait_for_load_state = AsyncMock()

    call_count = 0
    def on_page_event(event, callback):
        if event == "page":
            # Simulate popup after delay
            async def trigger():
                await callback(new_page)
            asyncio.get_event_loop().create_task(trigger())
    mock_context.on = MagicMock(side_effect=on_page_event)
    mock_context.remove_listener = MagicMock()

    result = await course_manager.click_course_action("测试课程名称")

    assert result is not None
    mock_page.evaluate.assert_called_once()
    mock_context.on.assert_called()
    mock_context.remove_listener.assert_called()


@pytest.mark.asyncio
async def test_click_course_action_found_no_popup(course_manager, mock_page, mock_context):
    """测试点击课程操作按钮 - 无新窗口 (lines 260-262)"""
    mock_page.context = mock_context
    mock_page.evaluate = AsyncMock(return_value={"found": True, "action": "继续学习"})
    mock_page.wait_for_timeout = AsyncMock()

    mock_context.on = MagicMock()  # No popup triggered
    mock_context.remove_listener = MagicMock()

    result = await course_manager.click_course_action("测试课程")

    # No new page, returns current page
    assert result is mock_page
    mock_context.remove_listener.assert_called()


@pytest.mark.asyncio
async def test_click_course_action_not_found(course_manager, mock_page, mock_context):
    """测试点击课程操作按钮 - 未找到 (lines 264-266)"""
    mock_page.context = mock_context
    mock_page.evaluate = AsyncMock(return_value={"found": False})
    mock_page.wait_for_timeout = AsyncMock()

    mock_context.on = MagicMock()
    mock_context.remove_listener = MagicMock()

    result = await course_manager.click_course_action("不存在的课程")

    assert result is None
    mock_context.remove_listener.assert_called()


@pytest.mark.asyncio
async def test_click_course_action_new_page_load_state_timeout(course_manager, mock_page, mock_context):
    """测试点击课程 - 新页面加载超时 (lines 254-259)"""
    mock_page.context = mock_context
    mock_page.evaluate = AsyncMock(return_value={"found": True, "action": "继续学习"})

    new_page = AsyncMock()
    new_page.url = "https://example.com/course/123"
    new_page.wait_for_load_state = AsyncMock(side_effect=Exception("Timeout"))

    # Fire the popup callback during the wait_for_timeout loop
    call_count = 0
    popup_fired = False
    captured_callback = None

    def on_page_event(event, callback):
        nonlocal captured_callback
        if event == "page":
            captured_callback = callback
    mock_context.on = MagicMock(side_effect=on_page_event)
    mock_context.remove_listener = MagicMock()

    async def wait_side_effect(ms):
        nonlocal call_count, popup_fired
        call_count += 1
        if call_count == 1 and captured_callback and not popup_fired:
            popup_fired = True
            await captured_callback(new_page)

    mock_page.wait_for_timeout = AsyncMock(side_effect=wait_side_effect)

    result = await course_manager.click_course_action("测试课程")

    assert result is new_page
    new_page.wait_for_load_state.assert_called_once()
    mock_context.remove_listener.assert_called()

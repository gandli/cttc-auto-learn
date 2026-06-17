"""学时增长验证测试

测试层次：
  1. 单元测试 — 验证 monitor/player 模块在视频完成后能检测到学时变化
  2. 集成测试 — 真实登录 + 播放一个短视频 + 验证 API 学时是否增长
"""

import asyncio
import json
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cttc.config import Config
from cttc.logger import Logger
from cttc.monitor import StudyMonitor
from cttc.player import VideoPlayer
from cttc.progress import ProgressManager


# ═══════════════════════════════════════════════
# 第 1 层：单元测试 — 模块逻辑验证
# ═══════════════════════════════════════════════

class TestStudyTimeDetection:
    """验证 monitor 能正确检测学时增长"""

    @pytest.mark.asyncio
    async def test_monitor_detects_increase_from_api(self, config, log, mock_page):
        """API 拦截器返回的学时增长应该被记录"""
        progress = ProgressManager(config, log)
        monitor = StudyMonitor(mock_page, config, log, progress)

        # 先记录初始学时
        progress.record_study_time(28.1)

        # 模拟 API 返回学时 28.5（从 28.1 增长到 28.5）
        monitor._api_study_hours = 28.5

        hours = await monitor._read_study_time()
        assert hours == 28.5

        # 记录后应该有增量
        delta = progress.record_study_time(hours)
        assert delta == pytest.approx(0.4, abs=0.01)
        assert progress.study_time["current_total"] == 28.5

    @pytest.mark.asyncio
    async def test_monitor_detects_increase_from_dom(self, config, log, mock_page):
        """DOM 解析的学时增长应该被记录"""
        progress = ProgressManager(config, log)
        monitor = StudyMonitor(mock_page, config, log, progress)

        # 先记录初始学时
        progress.record_study_time(28.1)

        # DOM 返回新学时
        mock_page.evaluate = AsyncMock(return_value=28.3)
        monitor._api_study_hours = 0  # 无 API 数据

        hours = await monitor._read_study_time()
        assert hours == 28.3

        delta = progress.record_study_time(hours)
        assert delta == pytest.approx(0.2, abs=0.01)

    @pytest.mark.asyncio
    async def test_monitor_api_interceptor_parses_credit_response(self, config, log, mock_page):
        """验证 credit/detail-hour-member 响应能正确解析"""
        progress = ProgressManager(config, log)
        monitor = StudyMonitor(mock_page, config, log, progress)
        monitor.setup_api_interceptor()

        # 模拟 API 响应
        mock_response = AsyncMock()
        mock_response.url = "https://mooc.ctt.cn/api/v1/system/credit/detail-hour-member?_=123"
        mock_response.json = AsyncMock(return_value={
            "courseHourResult": {"totalHour": 28.5},
            "totalClassHour": 26.0,
        })

        # 触发 response handler
        handler = mock_page.on.call_args[0][1]
        await handler(mock_response)

        assert monitor._api_study_hours == 28.5

    @pytest.mark.asyncio
    async def test_monitor_api_interceptor_parses_cadre_response(self, config, log, mock_page):
        """验证 cadre-education/detail-hour-member 响应能正确解析"""
        progress = ProgressManager(config, log)
        monitor = StudyMonitor(mock_page, config, log, progress)
        monitor.setup_api_interceptor()

        mock_response = AsyncMock()
        mock_response.url = "https://mooc.ctt.cn/api/v1/system/cadre-education/detail-hour-member?_=456"
        mock_response.json = AsyncMock(return_value={
            "hourSelf": 29.0,
            "hourTrain": 26.0,
        })

        handler = mock_page.on.call_args[0][1]
        await handler(mock_response)

        assert monitor._api_study_hours == 29.0


class TestVideoCompletionFlow:
    """验证视频播放完成后，进度数据能正确传递"""

    @pytest.mark.asyncio
    async def test_play_and_wait_reports_progress(self, config, log):
        """play_and_wait 完成后，应有 API 进度数据"""
        page = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.context = MagicMock()
        page.context._cttc_study_time_fix_installed = False
        page.context.route = AsyncMock()

        progress = ProgressManager(config, log)
        player = VideoPlayer(page, config, log, progress)

        # 模拟 API 进度拦截
        player._api_progress = {
            "lessonLocation": 600,
            "studyTotalTime": 600,
            "remainingTime": 0,
            "finishStatus": 2,
            "completedRate": 100,
        }
        player._api_progress_time = time.time()

        # 直接模拟 DOM 返回 found:false，让它回退到 API
        page.evaluate = AsyncMock(return_value={"found": False})

        # _read_video_status 应该能从 API 回退读到完成状态
        status = await player._read_video_status()
        assert status["found"] is True
        assert status["ended"] is True
        assert status["progress"] == pytest.approx(100.0, abs=0.1)

    @pytest.mark.asyncio
    async def test_video_finish_triggers_completed_status(self, config, log):
        """视频 finishStatus=2 应该被识别为已完成"""
        page = AsyncMock()
        page.evaluate = AsyncMock(return_value={"found": False})
        page.context = MagicMock()

        progress = ProgressManager(config, log)
        player = VideoPlayer(page, config, log, progress)

        player._api_progress = {
            "lessonLocation": 1094,
            "remainingTime": 0,
            "finishStatus": 2,
        }
        player._api_progress_time = time.time()

        status = await player._read_video_status()
        assert status["found"] is True
        assert status["ended"] is True

    @pytest.mark.asyncio
    async def test_progress_recorded_after_video_complete(self, config, log):
        """视频完成后，课程状态应更新为 completed"""
        progress = ProgressManager(config, log)

        # 模拟 main.py 中的完成逻辑
        course_id = "test-course-001"
        progress.update_course(course_id, {
            "title": "测试课程",
            "status": "completed"
        })

        assert progress.is_course_completed(course_id) is True
        assert progress.get_course(course_id)["title"] == "测试课程"


class TestStudyTimeRecording:
    """验证学时记录逻辑"""

    def test_record_study_time_increments(self, config, log):
        """学时从 28.1 增长到 28.5，delta 应该是 0.4"""
        progress = ProgressManager(config, log)

        delta1 = progress.record_study_time(28.1)
        assert delta1 == 28.1  # 首次记录

        delta2 = progress.record_study_time(28.5)
        assert delta2 == pytest.approx(0.4, abs=0.01)

        delta3 = progress.record_study_time(28.5)
        assert delta3 == 0.0  # 无变化

    def test_record_study_time_tracks_increase_time(self, config, log):
        """学时增长时应更新 last_increase 时间"""
        progress = ProgressManager(config, log)

        progress.record_study_time(28.1)
        last1 = progress.study_time["last_increase"]

        time.sleep(0.01)
        progress.record_study_time(28.3)
        last2 = progress.study_time["last_increase"]

        assert last2 > last1

    def test_stale_detection(self, config, log):
        """学时长时间不增长应被检测为停滞"""
        progress = ProgressManager(config, log)

        progress.record_study_time(28.1)
        # 手动设置 last_increase 为很久以前
        progress.study_time["last_increase"] = "2020-01-01T00:00:00"
        progress.save_study_time()

        stale = progress.get_stale_seconds()
        assert stale > 86400 * 365  # 超过一年 = 肯定停滞了


# ═══════════════════════════════════════════════
# 第 2 层：集成测试 — 真实环境验证
# ═══════════════════════════════════════════════

@pytest.mark.integration
class TestRealStudyTimeIncrease:
    """真实登录后验证学时是否增长

    这些测试需要：
    - output/auth-state.json 存在（有效登录凭证）
    - 网络可达 mooc.ctt.cn
    - 有至少一门未完成的课程

    运行: uv run pytest tests/test_study_time_increase.py -v -m integration
    """

    @pytest.fixture
    def auth_state_path(self):
        from pathlib import Path
        p = Path("output/auth-state.json")
        if not p.exists():
            pytest.skip("auth-state.json 不存在，跳过集成测试")
        return str(p)

    @pytest.fixture
    def study_time_api_response(self):
        """存储 API 学时响应的容器"""
        return {"hours": None, "raw": None}

    @pytest.mark.asyncio
    async def test_read_current_study_hours(self, auth_state_path, study_time_api_response):
        """验证能通过 API 读取当前学时"""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(storage_state=auth_state_path)
            page = await context.new_page()

            # 拦截学时 API
            async def on_response(response):
                url = response.url
                if "credit/detail-hour-member" in url or "cadre-education/detail-hour-member" in url:
                    try:
                        data = await response.json()
                        study_time_api_response["raw"] = data
                        if "courseHourResult" in data:
                            study_time_api_response["hours"] = data["courseHourResult"]["totalHour"]
                        elif "hourSelf" in data:
                            study_time_api_response["hours"] = data["hourSelf"]
                    except Exception:
                        pass

            page.on("response", on_response)

            # 导航到学习中心触发学时 API
            await page.goto("https://mooc.ctt.cn/#/center/index", wait_until="domcontentloaded")
            await page.wait_for_timeout(8000)

            await browser.close()

        assert study_time_api_response["hours"] is not None, "未能获取学时数据"
        assert study_time_api_response["hours"] > 0, "学时为 0"
        print(f"\n📊 当前学时: {study_time_api_response['hours']}h")
        print(f"📊 API 原始数据: {json.dumps(study_time_api_response['raw'], ensure_ascii=False, indent=2)}")

    @pytest.mark.asyncio
    async def test_play_short_video_and_check_hours_increase(self, auth_state_path):
        """播放一个短视频后验证学时是否增长

        流程：
        1. 读取当前学时（API 拦截）
        2. 获取一门未完成的课程
        3. 导航到课程页并播放视频
        4. 等待视频播放一段时间（30秒）
        5. 再次读取学时
        6. 对比学时是否增长
        """
        from playwright.async_api import async_playwright

        hours_before = {"value": None}
        hours_after = {"value": None}
        video_responses = []  # 收集 video-progress 响应

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False, slow_mo=50)
            context = await browser.new_context(storage_state=auth_state_path)
            page = await context.new_page()

            # ── 拦截器 ──
            async def on_response(response):
                url = response.url
                # 学时 API
                if "credit/detail-hour-member" in url or "cadre-education/detail-hour-member" in url:
                    try:
                        data = await response.json()
                        if "courseHourResult" in data:
                            h = data["courseHourResult"]["totalHour"]
                        elif "hourSelf" in data:
                            h = data["hourSelf"]
                        else:
                            return
                        if hours_before["value"] is None:
                            hours_before["value"] = h
                        else:
                            hours_after["value"] = h
                    except Exception:
                        pass
                # video-progress API
                if "video-progress" in url and response.request.method == "POST":
                    try:
                        body = await response.json()
                        video_responses.append({
                            "timestamp": datetime.now().isoformat(),
                            "lessonLocation": body.get("lessonLocation"),
                            "studyTotalTime": body.get("studyTotalTime"),
                            "completedRate": body.get("completedRate"),
                            "finishStatus": body.get("finishStatus"),
                            "errorCode": body.get("errorCode"),
                        })
                    except Exception:
                        pass

            page.on("response", on_response)

            # ── 步骤 1: 读取当前学时 ──
            print("\n📍 步骤 1: 读取当前学时...")
            await page.goto("https://mooc.ctt.cn/#/center/index", wait_until="domcontentloaded")
            await page.wait_for_timeout(8000)
            assert hours_before["value"] is not None, "无法获取初始学时"
            print(f"   当前学时: {hours_before['value']}h")

            # ── 步骤 2: 获取课程列表 ──
            print("\n📖 步骤 2: 获取课程列表...")
            token_str = await page.evaluate("() => localStorage.getItem('token') || ''")
            token_data = json.loads(token_str) if token_str else {}
            access_token = token_data.get("access_token", "")

            courses_data = await page.evaluate(f"""async () => {{
                const resp = await fetch('/api/v1/course-study/course-study-progress/personCourse-list?businessType=0&findStudy=0&studyTimeOrder=desc&page=1&pageSize=50', {{
                    headers: {{
                        'Authorization': 'Bearer__{access_token}',
                        'X-Requested-With': 'XMLHttpRequest'
                    }}
                }});
                return await resp.json();
            }}""")

            items = courses_data.get("items", [])
            # 找一门学习中的课程
            target = None
            for item in items:
                if item.get("finishStatus") == 1:  # 学习中
                    target = item
                    break
            if not target:
                for item in items:
                    if item.get("finishStatus") == 0:  # 未开始
                        target = item
                        break
            if not target:
                pytest.skip("没有可学习的课程")

            course_name = target.get("courseInfo", {}).get("name", "?")
            course_id = target.get("courseId", "")
            print(f"   目标课程: {course_name[:50]}")
            print(f"   课程 ID: {course_id}")

            # ── 步骤 3: 导航到课程页 ──
            print(f"\n🔗 步骤 3: 导航到课程页...")
            course_url = f"https://mooc.ctt.cn/#/study/course/detail/13&{course_id}"
            await page.goto(course_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)

            # ── 步骤 4: 播放视频并等待 ──
            print("\n▶️ 步骤 4: 播放视频...")
            played = await page.evaluate("""() => {
                const v = document.querySelector('video');
                if (v && v.paused) {
                    v.play().catch(() => {});
                    return true;
                }
                return !!v;
            }""")
            if not played:
                # 尝试点击播放按钮
                await page.evaluate("""() => {
                    const btns = document.querySelectorAll(
                        '.vjs-big-play-button, .prism-big-play-btn, [class*="play"]'
                    );
                    for (const b of btns) {
                        if (b.offsetParent !== null) { b.click(); break; }
                    }
                }""")
            await page.wait_for_timeout(3000)

            # 设置普清
            await page.evaluate("""() => {
                const items = document.querySelectorAll(
                    '.vjs-def-box .vjs-menu-item, .vjs-subs-caps-button .vjs-menu-item'
                );
                for (const item of items) {
                    if ((item.textContent || '').trim().includes('普清')) {
                        item.click();
                        return;
                    }
                }
            }""")

            # 播放 60 秒
            print("   等待 60 秒观察进度提交...")
            for i in range(6):
                await page.wait_for_timeout(10000)
                status = await page.evaluate("""() => {
                    const v = document.querySelector('video');
                    if (!v) return 'no video';
                    return `${v.currentTime.toFixed(0)}/${v.duration.toFixed(0)} ${v.paused ? 'paused' : 'playing'}`;
                }""")
                print(f"   [{(i+1)*10}s] 视频状态: {status}")

            # ── 步骤 5: 再次读取学时 ──
            print("\n📊 步骤 5: 重新读取学时...")
            await page.goto("https://mooc.ctt.cn/#/center/index", wait_until="domcontentloaded")
            await page.wait_for_timeout(8000)

            await browser.close()

        # ── 步骤 6: 对比结果 ──
        print(f"\n{'='*50}")
        print(f"📊 学时变化测试结果:")
        print(f"   播放前: {hours_before['value']}h")
        print(f"   播放后: {hours_after['value'] or '?'}h")

        if video_responses:
            print(f"\n📤 video-progress 提交记录 ({len(video_responses)} 次):")
            for r in video_responses[-5:]:  # 最近 5 条
                print(f"   loc={r['lessonLocation']}s, study={r['studyTotalTime']}s, "
                      f"completed={r['completedRate']}%, finish={r['finishStatus']}, "
                      f"error={r['errorCode']}")
        else:
            print("\n⚠️ 未捕获到 video-progress 请求")

        if hours_after["value"] is not None:
            delta = hours_after["value"] - hours_before["value"]
            print(f"\n   学时增量: {delta:+.2f}h")
            if delta > 0:
                print("   ✅ 学时增长确认！")
            else:
                print("   ❌ 学时未增长（可能需要完成整个课程才计入）")
                print("   💡 提示：检查视频是否完整播放、是否有 40909/40904 错误")
        else:
            print("   ⚠️ 未能读取播放后学时")

        # 不强制断言 — 先用作诊断工具
        # 如果确认学时增长机制后，可以加 assert delta > 0


@pytest.mark.integration
class TestStudyTimeAfterFullCourse:
    """完整播放一门短课程后验证学时

    运行: uv run pytest tests/test_study_time_increase.py::TestStudyTimeAfterFullCourse -v -m integration
    """

    @pytest.fixture
    def auth_state_path(self):
        from pathlib import Path
        p = Path("output/auth-state.json")
        if not p.exists():
            pytest.skip("auth-state.json 不存在，跳过集成测试")
        return str(p)

    @pytest.mark.asyncio
    async def test_complete_one_course_check_hours(self, auth_state_path):
        """完整播放一门课程，验证学时变化

        选一门时长最短的未完成课程，完整播放后检查学时。
        超时上限 30 分钟。
        """
        from playwright.async_api import async_playwright

        hours_before = {"value": None}
        hours_after = {"value": None}
        video_progress_log = []
        course_completed = {"value": False}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(storage_state=auth_state_path)
            page = await context.new_page()

            # 清除旧会话
            token_str = await page.goto("https://mooc.ctt.cn").then(
                lambda _: page.evaluate("() => localStorage.getItem('token') || ''")
            )

            # ── 拦截器 ──
            async def on_response(response):
                url = response.url
                if "credit/detail-hour-member" in url or "cadre-education/detail-hour-member" in url:
                    try:
                        data = await response.json()
                        if "courseHourResult" in data:
                            h = data["courseHourResult"]["totalHour"]
                        elif "hourSelf" in data:
                            h = data["hourSelf"]
                        else:
                            return
                        if hours_before["value"] is None:
                            hours_before["value"] = h
                        else:
                            hours_after["value"] = h
                    except Exception:
                        pass
                if "video-progress" in url and response.request.method == "POST":
                    try:
                        body = await response.json()
                        video_progress_log.append(body)
                        if body.get("finishStatus") == 2:
                            course_completed["value"] = True
                    except Exception:
                        pass

            page.on("response", on_response)

            # ── 1. 读取初始学时 ──
            await page.goto("https://mooc.ctt.cn/#/center/index", wait_until="domcontentloaded")
            await page.wait_for_timeout(8000)
            print(f"\n📊 初始学时: {hours_before['value']}h")

            # ── 2. 找最短的未完成课程 ──
            token_str = await page.evaluate("() => localStorage.getItem('token') || ''")
            token_data = json.loads(token_str) if token_str else {}
            access_token = token_data.get("access_token", "")

            courses_data = await page.evaluate(f"""async () => {{
                const resp = await fetch('/api/v1/course-study/course-study-progress/personCourse-list?businessType=0&findStudy=0&studyTimeOrder=asc&page=1&pageSize=50', {{
                    headers: {{
                        'Authorization': 'Bearer__{access_token}',
                        'X-Requested-With': 'XMLHttpRequest'
                    }}
                }});
                return await resp.json();
            }}""")

            items = courses_data.get("items", [])
            # 按 studyTotalTime 排序，找最短的未完成课程
            pending = [i for i in items if i.get("finishStatus") != 2]
            if not pending:
                pytest.skip("所有课程已完成")

            target = pending[0]
            course_name = target.get("courseInfo", {}).get("name", "?")
            course_id = target.get("courseId", "")
            total_time = target.get("courseInfo", {}).get("totalTime", 0)
            print(f"📖 目标课程: {course_name}")
            print(f"   时长: {total_time}s ({total_time//60}分{total_time%60}秒)")

            # ── 3. 播放 ──
            course_url = f"https://mooc.ctt.cn/#/study/course/detail/13&{course_id}"
            await page.goto(course_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)

            # 播放
            await page.evaluate("""() => {
                const v = document.querySelector('video');
                if (v && v.paused) { v.play().catch(() => {}); }
            }""")

            # 等待完成（最多 30 分钟）
            max_wait = min(total_time + 120, 1800)  # 视频时长 + 2 分钟缓冲，最多 30 分钟
            print(f"⏳ 等待播放完成（最多 {max_wait}s）...")

            for i in range(max_wait // 10):
                await page.wait_for_timeout(10000)
                status = await page.evaluate("""() => {
                    const v = document.querySelector('video');
                    if (!v) return null;
                    return {
                        current: v.currentTime,
                        duration: v.duration,
                        paused: v.paused,
                        ended: v.ended
                    };
                }""")

                if status:
                    pct = status["current"] / status["duration"] * 100 if status["duration"] > 0 else 0
                    if (i + 1) % 6 == 0:  # 每分钟打印
                        print(f"   [{(i+1)*10}s] {pct:.1f}% ({int(status['current'])}/{int(status['duration'])}s)")
                    if status.get("ended") or pct > 98:
                        print(f"   ✅ 视频播放完成 ({pct:.1f}%)")
                        break
                elif course_completed["value"]:
                    print("   ✅ 服务端确认完成")
                    break
                else:
                    # video 元素消失
                    last = video_progress_log[-1] if video_progress_log else {}
                    if last.get("completedRate", 0) > 90:
                        print(f"   ✅ 视频元素消失，进度 {last.get('completedRate')}%")
                        break

            # ── 4. 等待学时更新 ──
            print("\n⏳ 等待 15 秒让服务端处理学时...")
            await page.wait_for_timeout(15000)

            # ── 5. 重新读取学时 ──
            await page.goto("https://mooc.ctt.cn/#/center/index", wait_until="domcontentloaded")
            await page.wait_for_timeout(8000)

            await browser.close()

        # ── 结果 ──
        print(f"\n{'='*50}")
        print(f"📊 完整课程播放测试结果:")
        print(f"   课程: {course_name[:50]}")
        print(f"   视频时长: {total_time}s")
        print(f"   progress 提交: {len(video_progress_log)} 次")

        if video_progress_log:
            last = video_progress_log[-1]
            print(f"   最终状态: completed={last.get('completedRate')}%, finish={last.get('finishStatus')}")
            errors = [r for r in video_progress_log if r.get("errorCode")]
            if errors:
                print(f"   ⚠️ 错误: {set(r['errorCode'] for r in errors)}")

        print(f"\n   学时: {hours_before['value']}h → {hours_after['value'] or '?'}h")
        if hours_after["value"] and hours_before["value"]:
            delta = hours_after["value"] - hours_before["value"]
            print(f"   增量: {delta:+.2f}h")
            if delta > 0:
                print("   ✅ 学时增长确认！")
            else:
                print("   ❌ 学时未增长")
                print("   💡 可能原因:")
                print("      - 服务器延迟（等待更久）")
                print("      - 需要完成整个专题而非单门课程")
                print("      - studyTime 提交值有问题（检查 video-progress 日志）")

"""截图脚本：使用项目凭证访问视频播放页面并截图"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

OUTPUT_DIR = Path("output")
SCREENSHOT_DIR = Path("docs/screenshots")
AUTH_STATE = Path("output/auth-state.json")
BASE_URL = "https://mooc.ctt.cn"


async def check_logged_in(page) -> bool:
    """检查是否已登录（与 cttc/login.py 一致）"""
    return await page.evaluate("""() => {
        const text = document.body?.innerText || '';
        const url = window.location.href;
        const has_token = !!localStorage.getItem('token');
        if (has_token) return true;
        const has_logout = text.includes('退出') || text.includes('注销');
        const not_login_page = !url.includes('/login') && !url.includes('/oauth/');
        const has_user_info = !!document.querySelector('.user-avatar, .avatar, [class*="user-info"]');
        return (has_logout || has_user_info) && not_login_page;
    }""")


async def main():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--disable-software-rasterizer", "--no-sandbox"],
        )
        context = await browser.new_context(
            storage_state=str(AUTH_STATE),
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        # 1. 首页 — 等待足够时间让 SPA 加载并恢复 token
        print("[1/5] 访问首页...")
        await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(8000)  # 与 try_restore_session 一致

        logged_in = await check_logged_in(page)
        print(f"  登录状态: {'✅ 已登录' if logged_in else '❌ 未登录'}")

        if not logged_in:
            print("  ⚠️ 凭证可能过期，尝试直接用 token 注入...")
            # 从 auth-state.json 读取 token 并注入
            state = json.loads(AUTH_STATE.read_text())
            for origin in state.get("origins", []):
                for item in origin.get("localStorage", []):
                    if item.get("name") == "token":
                        token_val = item["value"]
                        # 转义单引号
                        escaped = token_val.replace("'", "\\'")
                        await page.evaluate("() => { localStorage.setItem('token', '" + escaped + "'); }")
                        print("  📝 Token 已注入")
                        break

            # 刷新页面让 token 生效
            await page.reload(wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(8000)
            logged_in = await check_logged_in(page)
            print(f"  登录状态: {'✅ 已登录' if logged_in else '❌ 未登录'}")

        await page.screenshot(path=str(SCREENSHOT_DIR / "01-homepage.png"), full_page=False)
        print(f"  ✅ 首页截图保存")

        if not logged_in:
            print("\n❌ 凭证已完全过期，需要重新扫码登录")
            await browser.close()
            return

        # 2. 学习中心
        print("[2/5] 访问学习中心...")
        await page.goto(f"{BASE_URL}/#/center/index", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "02-learning-center.png"), full_page=False)
        print(f"  ✅ 学习中心截图保存")

        # 3. 获取课程
        print("[3/5] 获取课程列表...")
        token_raw = await page.evaluate("() => localStorage.getItem('token') || ''")
        try:
            token_data = json.loads(token_raw) if token_raw else {}
            token = token_data.get("access_token", token_raw)
        except (json.JSONDecodeError, AttributeError):
            token = token_raw

        courses = []
        if token:
            try:
                courses_data = await page.evaluate(f"""async () => {{
                    const r = await fetch("/api/v1/human/personCourse/list?page=1&pageSize=50&studyStatus=1", {{
                        headers: {{"Authorization": "Bearer__{token}"}}
                    }});
                    if (!r.ok) return {{}};
                    return r.json();
                }}""")
                courses = courses_data.get("data", {}).get("records", [])
                print(f"  📚 找到 {len(courses)} 门进行中的课程")
            except Exception as e:
                print(f"  ⚠️ API 请求失败: {e}")

        if not courses:
            print("  ⚠️ 未找到进行中的课程，尝试获取所有课程...")
            try:
                courses_data = await page.evaluate(f"""async () => {{
                    const r = await fetch("/api/v1/human/personCourse/list?page=1&pageSize=10", {{
                        headers: {{"Authorization": "Bearer__{token}"}}
                    }});
                    if (!r.ok) return {{}};
                    return r.json();
                }}""")
                courses = courses_data.get("data", {}).get("records", [])
                print(f"  📚 找到 {len(courses)} 门课程")
            except Exception:
                pass

        if courses:
            course = courses[0]
            course_id = course.get("courseId") or course.get("id")
            course_name = course.get("courseName") or course.get("name", "未知课程")
            print(f"  📚 目标课程: {course_name} (ID: {course_id})")

            # 4. 课程详情页
            print("[4/5] 访问课程详情页...")
            course_url = f"{BASE_URL}/#/study/course/detail/{course_id}"
            await page.goto(course_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(5000)
            await page.screenshot(path=str(SCREENSHOT_DIR / "03-course-detail.png"), full_page=False)
            print(f"  ✅ 课程详情截图保存")

            # 5. 视频播放页
            print("[5/5] 尝试进入视频播放页...")
            # 查找课时链接并点击
            lesson = await page.query_selector('.lesson-item a, .chapter-item a, [class*="lesson"] a, [class*="video"] a')
            if lesson:
                await lesson.click()
                await page.wait_for_timeout(6000)
            else:
                # 尝试点击播放按钮
                play_btn = await page.query_selector('.play-btn, [class*="play"], button:has-text("播放")')
                if play_btn:
                    await play_btn.click()
                    await page.wait_for_timeout(6000)

            await page.screenshot(path=str(SCREENSHOT_DIR / "04-video-player.png"), full_page=False)
            print(f"  ✅ 视频播放页截图保存")
        else:
            print("  ⚠️ 无法获取课程列表")
            # 截取课程页面
            await page.goto(f"{BASE_URL}/#/study/course", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            await page.screenshot(path=str(SCREENSHOT_DIR / "03-course-list.png"), full_page=False)
            print(f"  ✅ 课程页面截图保存")

        # 6. 数据看板
        print("[额外] 截取个人中心...")
        await page.goto(f"{BASE_URL}/#/personal/info", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "05-personal-center.png"), full_page=False)
        print(f"  ✅ 个人中心截图保存")

        await browser.close()

    print("\n📸 截图完成！文件列表:")
    for f in sorted(SCREENSHOT_DIR.glob("*.png")):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    asyncio.run(main())

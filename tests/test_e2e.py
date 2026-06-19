"""
端到端测试 — 测试实际用户流程

需要真实浏览器环境，标记为 @pytest.mark.e2e。
运行方式: pytest tests/test_e2e.py -m e2e -v
"""

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e]


@pytest.fixture
def auth_state_path():
    """凭证文件路径（字符串）"""
    return str(Path("output/auth-state.json").resolve())


@pytest.fixture
def has_auth(auth_state_path):
    """检查是否有保存的凭证"""
    p = Path(auth_state_path)
    return p.exists() and p.stat().st_size > 10


@pytest.fixture
async def page_and_context(has_auth, auth_state_path):
    """创建浏览器页面和上下文"""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--disable-software-rasterizer", "--no-sandbox"],
        )

        ctx_opts = {
            "viewport": {"width": 1280, "height": 800},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        if has_auth:
            ctx_opts["storage_state"] = auth_state_path

        ctx = await browser.new_context(**ctx_opts)
        page = await ctx.new_page()
        page.on("dialog", lambda d: d.dismiss())

        yield page, ctx

        await browser.close()


# ═══════════════════════════════════════════
# 首页
# ═══════════════════════════════════════════


class TestHomepage:
    async def test_loads(self, page_and_context):
        page, _ = page_and_context
        await page.goto("https://mooc.ctt.cn", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        title = await page.title()
        assert title
        text = await page.evaluate("() => document.body?.innerText || ''")
        assert any(kw in text for kw in ["中国烟草", "网络学院", "登录"])

    async def test_has_login_button(self, page_and_context):
        page, _ = page_and_context
        await page.goto("https://mooc.ctt.cn", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        found = await page.evaluate("""() => {
            for (const el of document.querySelectorAll('a, button')) {
                if (el.textContent.trim().includes('登录')) return true;
            }
            return false;
        }""")
        assert found


# ═══════════════════════════════════════════
# 登录页
# ═══════════════════════════════════════════


class TestLoginPage:
    async def _goto_login(self, page):
        await page.goto("https://mooc.ctt.cn", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        await page.evaluate("""() => {
            for (const el of document.querySelectorAll('a, button')) {
                if (el.textContent.trim().includes('登录')) { el.click(); return; }
            }
        }""")
        await page.wait_for_timeout(5000)

    async def test_login_page_loads(self, page_and_context):
        page, _ = page_and_context
        await self._goto_login(page)
        url = page.url
        text = await page.evaluate("() => document.body?.innerText || ''")
        assert "/login" in url or "/oauth/" in url or "扫码" in text or "账号" in text

    async def test_has_qr_code(self, page_and_context):
        page, _ = page_and_context
        await self._goto_login(page)
        has = await page.evaluate("""() => {
            for (const img of document.querySelectorAll('img')) {
                if (img.src?.startsWith('data:image')) return true;
            }
            if (document.querySelectorAll('canvas').length) return true;
            return (document.body?.innerText || '').includes('扫码');
        }""")
        assert has

    async def test_has_account_form(self, page_and_context):
        page, _ = page_and_context
        await self._goto_login(page)
        has = await page.evaluate("""() => {
            const inputs = document.querySelectorAll('input');
            return Array.from(inputs).some(i =>
                i.placeholder?.includes('账号') || i.placeholder?.includes('手机号') || i.type === 'password'
            );
        }""")
        assert has


# ═══════════════════════════════════════════
# 学习中心（需要凭证）
# ═══════════════════════════════════════════


async def _get_token(page):
    """从页面提取 access_token"""
    return await page.evaluate("""() => {
        try { return JSON.parse(localStorage.getItem('token') || '{}').access_token || ''; }
        catch { return ''; }
    }""")


class TestLearningCenter:
    async def test_loads(self, page_and_context, has_auth):
        if not has_auth:
            pytest.skip("需要凭证")
        page, _ = page_and_context
        await page.goto("https://mooc.ctt.cn/#/center/index", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)
        text = await page.evaluate("() => document.body?.innerText || ''")
        assert any(kw in text for kw in ["退出", "学习中心", "我的学习"])

    async def test_courses_api(self, page_and_context, has_auth):
        if not has_auth:
            pytest.skip("需要凭证")
        page, _ = page_and_context
        await page.goto("https://mooc.ctt.cn", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        token = await _get_token(page)
        if not token:
            pytest.skip("无 token")
        result = await page.evaluate(f"""async () => {{
            const r = await fetch('/api/v1/course-study/course-study-progress/personCourse-list?businessType=0&findStudy=0&page=1&pageSize=5', {{
                headers: {{ 'Authorization': 'Bearer__{token}', 'X-Requested-With': 'XMLHttpRequest' }}
            }});
            return r.ok ? await r.json() : null;
        }}""")
        assert result is not None

    async def test_study_stats_api(self, page_and_context, has_auth):
        if not has_auth:
            pytest.skip("需要凭证")
        page, _ = page_and_context
        await page.goto("https://mooc.ctt.cn", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        token = await _get_token(page)
        if not token:
            pytest.skip("无 token")
        result = await page.evaluate(f"""async () => {{
            const r = await fetch('/api/v1/system/credit/detail-hour-member', {{
                headers: {{ 'Authorization': 'Bearer__{token}', 'X-Requested-With': 'XMLHttpRequest' }}
            }});
            return r.ok ? await r.json() : null;
        }}""")
        assert result is not None


# ═══════════════════════════════════════════
# 凭证
# ═══════════════════════════════════════════


class TestCredentials:
    async def test_auth_state_valid(self, has_auth, auth_state_path):
        if not has_auth:
            pytest.skip("无凭证")
        data = json.loads(Path(auth_state_path).read_text(encoding="utf-8"))
        assert "cookies" in data or "origins" in data

    async def test_token_validity(self, page_and_context, has_auth):
        if not has_auth:
            pytest.skip("需要凭证")
        page, _ = page_and_context
        await page.goto("https://mooc.ctt.cn", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        token = await _get_token(page)
        if not token:
            pytest.skip("无 token")
        result = await page.evaluate(f"""async () => {{
            const r = await fetch('/api/v1/human/task?page=1&pageSize=1', {{
                headers: {{ 'Authorization': 'Bearer__{token}', 'X-Requested-With': 'XMLHttpRequest' }}
            }});
            return {{ status: r.status }};
        }}""")
        assert result["status"] in [200, 401]

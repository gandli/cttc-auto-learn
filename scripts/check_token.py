"""验证 token 是否有效，尝试刷新凭证"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

AUTH_STATE = Path("output/auth-state.json")
BASE_URL = "https://mooc.ctt.cn"


async def main():
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

        # 1. 访问首页
        print("[1] 访问首页...")
        await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)

        # 2. 检查页面状态
        url = page.url
        print(f"  当前 URL: {url}")

        # 3. 检查 localStorage
        token_raw = await page.evaluate("() => localStorage.getItem('token') || ''")
        print(f"  Token 存在: {bool(token_raw)}")
        if token_raw:
            try:
                token_obj = json.loads(token_raw)
                token = token_obj.get("access_token", "")
                print(f"  access_token: {token[:20]}...")
            except (json.JSONDecodeError, AttributeError):
                token = token_raw
                print(f"  Token (raw): {token[:20]}...")

        # 4. 尝试调用 API
        print("\n[2] 测试 API...")
        api_result = await page.evaluate("""async () => {
            try {
                const token = localStorage.getItem('token') || '';
                let access_token = '';
                try {
                    access_token = JSON.parse(token).access_token || '';
                } catch(e) {
                    access_token = token;
                }
                
                const r = await fetch('/api/v1/system/credit/detail-hour-member', {
                    headers: {'Authorization': 'Bearer__' + access_token}
                });
                const status = r.status;
                const text = await r.text();
                return {status: status, body: text.substring(0, 500)};
            } catch(e) {
                return {error: e.message};
            }
        }""")
        print(f"  API 结果: {json.dumps(api_result, ensure_ascii=False, indent=2)}")

        # 5. 检查页面内容
        print("\n[3] 页面内容检查...")
        page_info = await page.evaluate("""() => {
            const text = document.body?.innerText || '';
            return {
                has_login: text.includes('登录'),
                has_logout: text.includes('退出'),
                has_study: text.includes('学习中心'),
                title: document.title,
                url: window.location.href
            };
        }""")
        print(f"  {json.dumps(page_info, ensure_ascii=False, indent=2)}")

        # 6. 截图当前状态
        await page.screenshot(path="docs/screenshots/debug-token-check.png", full_page=False)
        print("\n  📸 调试截图已保存")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

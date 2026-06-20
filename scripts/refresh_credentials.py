"""刷新 acw_tc WAF cookie 并保存更新后的凭证"""
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

        # 访问首页，触发 WAF 设置新 cookie
        print("[1] 访问首页刷新 acw_tc cookie...")
        await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)

        # 检查是否已登录
        logged_in = await page.evaluate("""() => {
            const has_token = !!localStorage.getItem('token');
            if (has_token) return 'token_ok';
            const text = document.body?.innerText || '';
            if (text.includes('退出') || text.includes('学习中心')) return 'page_ok';
            return 'not_logged_in';
        }""")
        print(f"  登录状态: {logged_in}")

        if logged_in == "not_logged_in":
            # 尝试注入 token
            print("[2] 注入 token...")
            state = json.loads(AUTH_STATE.read_text())
            for origin in state.get("origins", []):
                for item in origin.get("localStorage", []):
                    if item.get("name") == "token":
                        token_val = item["value"]
                        escaped = token_val.replace("'", "\\'")
                        await page.evaluate("() => { localStorage.setItem('token', '" + escaped + "'); }")
                        print("  Token 已注入")
                        break

            await page.reload(wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(5000)

            logged_in = await page.evaluate("""() => {
                return !!localStorage.getItem('token') ? 'token_ok' : 'not_logged_in';
            }""")
            print(f"  注入后状态: {logged_in}")

        # 保存更新后的凭证
        print("[3] 保存更新后的凭证...")
        new_state = await context.storage_state()
        AUTH_STATE.write_text(json.dumps(new_state, ensure_ascii=False, indent=2))
        print(f"  已保存: {AUTH_STATE}")

        # 列出 cookies
        print("\n=== 更新后的 Cookies ===")
        for c in new_state.get("cookies", []):
            print(f"  {c['name']}: {c['value'][:30]}...")

        await browser.close()
    print("\n✅ 凭证刷新完成！")


if __name__ == "__main__":
    asyncio.run(main())

"""从 chrome-profile 恢复凭证并保存 auth-state.json"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

PROFILE_DIR = Path("output/chrome-profile")
AUTH_STATE = Path("output/auth-state.json")
BASE_URL = "https://mooc.ctt.cn"


async def main():
    async with async_playwright() as p:
        # 使用持久化上下文，复用 chrome-profile 的会话
        context = await p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=True,
            args=["--disable-gpu", "--disable-software-rasterizer", "--no-sandbox"],
            viewport={"width": 1280, "height": 800},
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        print("[1] 访问首页...")
        await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)
        
        # 检查登录状态
        logged_in = await page.evaluate("""() => {
            const has_token = !!localStorage.getItem('token');
            if (has_token) return 'token_ok';
            const text = document.body?.innerText || '';
            if (text.includes('退出') || text.includes('学习中心')) return 'page_ok';
            return 'not_logged_in';
        }""")
        print(f"  登录状态: {logged_in}")
        
        if logged_in != 'not_logged_in':
            print("[2] 保存凭证...")
            state = await context.storage_state()
            AUTH_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
            print(f"  ✅ 凭证已保存: {AUTH_STATE}")
            
            # 验证 token
            token = await page.evaluate("() => localStorage.getItem('token') || ''")
            if token:
                print(f"  Token: {token[:30]}...")
        else:
            print("  ❌ 未登录，需要重新扫码")
        
        await context.close()
    
    print("\n✅ 完成！")


if __name__ == "__main__":
    asyncio.run(main())

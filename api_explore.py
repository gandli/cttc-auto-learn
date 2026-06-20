"""API 深度探索 - 直接调用已知端点，发现更多 API"""
import asyncio, json, time, sys
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "https://mooc.ctt.cn"
AUTH = "output/auth-state.json"
OUT = Path("output/crawl")

async def main():
    print("🔍 API 深度探索...", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-gpu", "--no-sandbox"])
        auth = Path(AUTH)
        if auth.exists():
            ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, storage_state=str(auth))
            print("✅ 已加载凭证", flush=True)
        else:
            ctx = await browser.new_context(viewport={"width": 1280, "height": 800})

        page = await ctx.new_page()

        # 收集所有 API 请求
        api_requests = []

        async def on_resp(resp):
            url = resp.url
            if "/api/" not in url and "/oauth/" not in url:
                return
            entry = {
                "url": url,
                "method": resp.request.method,
                "status": resp.status,
                "timestamp": time.time(),
            }
            # 获取请求体
            try:
                pd = resp.request.post_data
                if pd:
                    try: entry["request_body"] = json.loads(pd)
                    except: entry["request_body"] = pd[:500]
            except: pass
            # 获取响应体
            try:
                ct = resp.headers.get("content-type", "")
                if "json" in ct:
                    body = await resp.json()
                    entry["response"] = body
                    if isinstance(body, dict):
                        entry["response_keys"] = list(body.keys())
            except: pass
            api_requests.append(entry)
            print(f"  [{entry['method']}] {url[:80]} -> {entry['status']}", flush=True)

        page.on("response", on_resp)

        # 1. 加载首页
        print("\n📍 加载首页...", flush=True)
        await page.goto(BASE, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)

        # 2. 导航到各个页面
        pages_to_visit = [
            "/center/index",
            "/center/study",
            "/center/plan",
            "/center/task",
            "/center/topic",
            "/center/course",
        ]

        for route in pages_to_visit:
            url = f"{BASE}{route}"
            print(f"\n📍 访问: {route}", flush=True)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
            except Exception as e:
                print(f"  ❌ {str(e)[:100]}", flush=True)

        # 3. 尝试触发更多 API（点击、滚动等）
        print("\n📍 触发交互...", flush=True)
        try:
            # 回到首页
            await page.goto(BASE, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            # 点击各种按钮
            buttons = await page.query_selector_all("button, .btn, [role='button']")
            for i, btn in enumerate(buttons[:5]):
                try:
                    text = await btn.text_content()
                    if text and len(text.strip()) < 20:
                        print(f"  点击: {text.strip()}", flush=True)
                        await btn.click()
                        await page.wait_for_timeout(1000)
                except:
                    pass

            # 滚动页面
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(2000)

        except Exception as e:
            print(f"  ❌ 交互失败: {str(e)[:100]}", flush=True)

        await browser.close()

    # 保存结果
    print(f"\n💾 保存 {len(api_requests)} 条 API 请求...", flush=True)

    with open(OUT / "api-deep-explore.json", "w", encoding="utf-8") as f:
        json.dump(api_requests, f, ensure_ascii=False, indent=2)

    # 统计
    methods = {}
    endpoints = {}
    for req in api_requests:
        m = req["method"]
        methods[m] = methods.get(m, 0) + 1
        url = req["url"].split("?")[0]
        if url not in endpoints:
            endpoints[url] = {"method": m, "count": 0, "keys": req.get("response_keys", [])}
        endpoints[url]["count"] += 1

    print(f"\n📊 统计:", flush=True)
    print(f"  总请求: {len(api_requests)}", flush=True)
    for m, c in sorted(methods.items()):
        print(f"  {m}: {c}", flush=True)
    print(f"  端点: {len(endpoints)}", flush=True)

    # 打印端点
    print(f"\n📡 API 端点:", flush=True)
    for url in sorted(endpoints.keys()):
        info = endpoints[url]
        print(f"  {info['method']:6} {url} [{info['count']}次]", flush=True)
        if info["keys"]:
            print(f"         Keys: {info['keys'][:10]}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())

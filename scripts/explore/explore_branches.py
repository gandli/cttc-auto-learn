"""探索分院和专区 - 获取所有组织/分院结构"""
import asyncio, json, time, sys
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "https://mooc.ctt.cn"
AUTH = "output/auth-state.json"
OUT = Path("output/crawl")

async def main():
    print("🏛️ 探索分院和专区...", flush=True)
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

        # 收集 API 响应
        api_responses = {}

        async def on_resp(resp):
            url = resp.url
            if "/api/" not in url:
                return
            try:
                ct = resp.headers.get("content-type", "")
                if "json" in ct:
                    body = await resp.json()
                    key = url.split("?")[0]
                    if key not in api_responses:
                        api_responses[key] = []
                    api_responses[key].append({"url": url, "data": body})
            except:
                pass

        page.on("response", on_resp)

        # 1. 加载首页获取组织信息
        print("\n📍 加载首页获取组织信息...", flush=True)
        await page.goto(BASE, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)

        # 2. 获取组织列表
        print("\n📍 获取组织列表...", flush=True)
        org_data = None
        for key in api_responses:
            if "organization" in key and "home-config" in key:
                org_data = api_responses[key]
                break

        if org_data:
            print(f"  ✅ 找到 {len(org_data)} 条组织数据", flush=True)
            for item in org_data[:3]:
                print(f"    URL: {item['url'][:80]}", flush=True)
                if isinstance(item['data'], list):
                    print(f"    列表: {len(item['data'])} 项", flush=True)
                elif isinstance(item['data'], dict):
                    print(f"    字段: {list(item['data'].keys())[:10]}", flush=True)

        # 3. 获取公司信息
        print("\n📍 获取公司信息...", flush=True)
        company_data = None
        for key in api_responses:
            if "company-sync" in key:
                company_data = api_responses[key]
                break

        if company_data:
            print(f"  ✅ 找到 {len(company_data)} 条公司数据", flush=True)
            for item in company_data:
                print(f"    {item['data']}", flush=True)

        # 4. 尝试不同 organizationId
        print("\n📍 尝试不同 organizationId...", flush=True)
        org_results = {}

        for org_id in range(1, 20):
            url = f"{BASE}/api/v1/system/company-sync/get-company-by-id?id={org_id}"
            try:
                resp = await page.evaluate(f"""async () => {{
                    const r = await fetch('{url}');
                    return await r.json();
                }}""")
                if resp and resp.get('name'):
                    org_results[org_id] = resp
                    print(f"  [{org_id}] {resp.get('name', 'N/A')}", flush=True)
            except:
                pass
            await asyncio.sleep(0.2)

        # 5. 探索导航菜单中的分院/专区链接
        print("\n📍 探索导航菜单...", flush=True)
        nav_links = await page.evaluate("""() => {
            const links = [];
            document.querySelectorAll('a[href]').forEach(a => {
                const text = a.textContent?.trim() || '';
                const href = a.href || '';
                if (text && href) {
                    links.push({text: text.substring(0, 50), href: href});
                }
            });
            return links;
        }""")

        # 过滤分院/专区相关链接
        branch_keywords = ['分院', '专区', '学院', '中心', '频道', '基地', 'branch', 'zone', 'area']
        branch_links = [l for l in nav_links if any(k in l['text'] for k in branch_keywords)]

        if branch_links:
            print(f"  ✅ 找到 {len(branch_links)} 个分院/专区链接:", flush=True)
            for link in branch_links[:20]:
                print(f"    {link['text']}: {link['href']}", flush=True)
        else:
            print("  ⚠️ 未找到分院/专区链接", flush=True)
            # 显示所有导航链接
            print(f"  所有导航链接 ({len(nav_links)} 个):", flush=True)
            for link in nav_links[:30]:
                print(f"    {link['text'][:30]}: {link['href'][:60]}", flush=True)

        # 6. 探索专题列表
        print("\n📍 探索专题列表...", flush=True)
        topic_data = None
        for key in api_responses:
            if "topic/hot-all" in key:
                topic_data = api_responses[key]
                break

        if topic_data:
            print(f"  ✅ 找到 {len(topic_data)} 条专题数据", flush=True)
            for item in topic_data:
                data = item['data']
                if isinstance(data, list):
                    print(f"    热门专题: {len(data)} 个", flush=True)
                    for topic in data[:5]:
                        print(f"      - {topic.get('title', topic.get('name', 'N/A'))}", flush=True)

        await browser.close()

    # 保存结果
    results = {
        "organizations": org_results,
        "branch_links": branch_links if branch_links else [],
        "all_nav_links": nav_links,
        "api_responses_summary": {k: len(v) for k, v in api_responses.items()},
    }

    with open(OUT / "branches-zones.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 统计
    print(f"\n{'='*60}", flush=True)
    print(f"📊 结果汇总:", flush=True)
    print(f"  组织/分院: {len(org_results)}", flush=True)
    print(f"  分院链接: {len(branch_links)}", flush=True)
    print(f"  API 响应: {len(api_responses)}", flush=True)
    print(f"  保存到: output/crawl/branches-zones.json", flush=True)

if __name__ == "__main__":
    asyncio.run(main())

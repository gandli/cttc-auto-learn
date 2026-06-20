"""mooc.ctt.cn 全站爬虫 v3 - 简化版"""
import asyncio, json, time, sys
from pathlib import Path
from urllib.parse import urlparse
from collections import defaultdict
from playwright.async_api import async_playwright

BASE = "https://mooc.ctt.cn"
AUTH = "output/auth-state.json"
OUT = Path("output/crawl")
MAX = 300
DELAY = 0.5

# 已知路由
ROUTES = [
    "/", "/center/index", "/center/study", "/center/plan", "/center/task",
    "/center/topic", "/center/course", "/center/exam", "/center/survey",
    "/center/live", "/center/certificate", "/center/message", "/center/favorite",
    "/center/note", "/center/credit", "/center/integral", "/center/rank",
    "/center/help", "/center/profile", "/center/settings",
    "/course/list", "/course/recommend", "/course/category",
    "/topic/list", "/exam/list", "/live/list", "/activity/list",
    "/news/list", "/lecturer/list", "/search",
]

visited = set()
pages = []
api_calls = []
api_summary = {}
errors = []
start = time.time()

def log(msg):
    print(msg, flush=True)

def classify(url):
    import re
    p = urlparse(url).path
    p = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "{uuid}", p)
    p = re.sub(r"/\d+", "/{id}", p)
    return p

async def main():
    log("🚀 启动爬虫 v3...")
    OUT.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-gpu", "--no-sandbox"])
        auth = Path(AUTH)
        if auth.exists():
            ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, storage_state=str(auth))
            log("✅ 已加载凭证")
        else:
            ctx = await browser.new_context(viewport={"width": 1280, "height": 800})

        page = await ctx.new_page()

        # 网络拦截
        cur_url = [""]

        async def on_resp(resp):
            url = resp.url
            if "/api/" not in url and "/oauth/" not in url:
                return
            entry = {"url": url, "method": resp.request.method, "status": resp.status, "page": cur_url[0]}
            try:
                pd = resp.request.post_data
                if pd:
                    try: entry["body"] = json.loads(pd)
                    except: entry["body"] = pd[:300]
            except: pass
            try:
                ct = resp.headers.get("content-type", "")
                if "json" in ct:
                    body = await resp.json()
                    entry["resp"] = body
                    if isinstance(body, dict): entry["keys"] = list(body.keys())
            except: pass
            api_calls.append(entry)

            pat = classify(url)
            if pat not in api_summary:
                api_summary[pat] = {"methods": set(), "count": 0, "statuses": set(), "params": None, "keys": None, "pages": set()}
            s = api_summary[pat]
            s["methods"].add(resp.request.method)
            s["count"] += 1
            s["statuses"].add(resp.status)
            s["pages"].add(cur_url[0])
            if entry.get("body") and not s["params"]: s["params"] = entry["body"]
            if entry.get("keys") and not s["keys"]: s["keys"] = entry["keys"]

        page.on("response", on_resp)

        # 构建路由队列
        queue = [f"{BASE}{r}" for r in ROUTES]

        # 首页加载后提取更多链接
        log(f"\n📍 加载首页...")
        cur_url[0] = BASE
        await page.goto(BASE, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)

        nav_links = await page.evaluate("""() => {
            const links = new Set();
            document.querySelectorAll('a[href]').forEach(a => {
                if (a.href && a.href.startsWith(location.origin)) links.add(a.href);
            });
            document.querySelectorAll('[to]').forEach(el => {
                const to = el.getAttribute('to');
                if (to && to.startsWith('/')) links.add(new URL(to, location.origin).href);
            });
            return [...links];
        }""")
        for link in nav_links:
            if link not in queue:
                queue.append(link)
        log(f"   发现 {len(nav_links)} 个链接，队列: {len(queue)}")

        # 爬取队列
        count = 0
        for url in queue:
            if count >= MAX: break
            if url in visited: continue

            from urllib.parse import urldefrag
            url, _ = urldefrag(url)
            if not url.startswith(BASE): continue

            visited.add(url)
            cur_url[0] = url
            count += 1

            log(f"[{count}/{len(queue)}] {url.replace(BASE, '')[:60]}")

            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

                title = await page.title()

                # 提取新链接
                new_links = await page.evaluate("""() => {
                    const links = new Set();
                    document.querySelectorAll('a[href]').forEach(a => {
                        if (a.href && a.href.startsWith(location.origin)) links.add(a.href);
                    });
                    document.querySelectorAll('[to]').forEach(el => {
                        const to = el.getAttribute('to');
                        if (to && to.startsWith('/')) links.add(new URL(to, location.origin).href);
                    });
                    return [...links];
                }""")
                for link in new_links:
                    if link not in visited and link not in queue:
                        queue.append(link)

                pages.append({"url": url, "title": title, "status": resp.status if resp else None, "apis": len([a for a in api_calls if a["page"] == url])})

            except Exception as e:
                log(f"  ❌ {str(e)[:100]}")
                errors.append({"url": url, "error": str(e)[:200]})

            await asyncio.sleep(DELAY)

        await browser.close()

    # 保存结果
    log(f"\n💾 保存结果...")

    with open(OUT / "pages.json", "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)

    catalog = {}
    for pat, info in api_summary.items():
        catalog[pat] = {"methods": list(info["methods"]), "count": info["count"], "statuses": list(info["statuses"]), "pages": list(info["pages"]), "params": info["params"], "keys": info["keys"]}
    with open(OUT / "api-catalog.json", "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    with open(OUT / "api-requests.json", "w", encoding="utf-8") as f:
        json.dump(api_calls[:2000], f, ensure_ascii=False, indent=2)

    with open(OUT / "sitemap.txt", "w", encoding="utf-8") as f:
        for u in sorted(visited): f.write(u + "\n")

    # Markdown 报告
    lines = ["# mooc.ctt.cn 全站爬取报告\n\n"]
    lines.append(f"**时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}  \n")
    lines.append(f"**耗时**: {time.time()-start:.0f}s  \n")
    lines.append(f"**页面**: {len(pages)}  \n")
    lines.append(f"**API**: {len(api_summary)}  \n")
    lines.append(f"**请求**: {len(api_calls)}  \n\n")
    lines.append("## API 端点\n\n")
    lines.append("| 方法 | 路径 | 次数 | 状态 |\n|------|------|------|------|\n")
    for pat in sorted(api_summary):
        info = api_summary[pat]
        lines.append(f"| {','.join(info['methods'])} | `{pat}` | {info['count']} | {','.join(str(s) for s in info['statuses'])} |\n")
    lines.append("\n## 页面\n\n")
    lines.append("| URL | 标题 | API |\n|-----|------|-----|\n")
    for p in pages:
        lines.append(f"| `{p['url'].replace(BASE,'')}` | {(p.get('title') or '')[:40]} | {p.get('apis',0)} |\n")
    with open(OUT / "report.md", "w", encoding="utf-8") as f:
        f.writelines(lines)

    # 摘要
    elapsed = time.time() - start
    log(f"\n{'='*60}")
    log(f"🏁 完成！ {elapsed:.0f}s")
    log(f"📄 {len(pages)} 页 | 🔌 {len(api_summary)} API | 📡 {len(api_calls)} 请求 | ❌ {len(errors)} 错误")
    log(f"{'='*60}")

    # API 分类
    prefix_groups = defaultdict(list)
    for pat in sorted(api_summary):
        parts = pat.split("/")
        prefix = "/".join(parts[:4]) if len(parts) > 4 else pat
        prefix_groups[prefix].append(pat)

    for prefix in sorted(prefix_groups):
        pats = prefix_groups[prefix]
        total = sum(api_summary[p]["count"] for p in pats)
        log(f"\n  📁 {prefix}/ ({total}次)")
        for p in sorted(pats):
            info = api_summary[p]
            log(f"     {','.join(info['methods']):6} {p} [{info['count']}次]")

if __name__ == "__main__":
    asyncio.run(main())

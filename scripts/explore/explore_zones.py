"""深度爬取专区和专题内容"""
import asyncio, json, time, re
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "https://mooc.ctt.cn"
AUTH = "output/auth-state.json"
OUT = Path("output/crawl")

# 从之前爬取结果中提取的专区和专题 URL
ZONES = [
    "/#/staticConfigNew/40288177515b351601515b",  # 烟叶生产
]

SUBJECTS = [
    "/#/study/subject/detail/0dac0b1b-12bd-45d",
    "/#/study/subject/detail/8e930e92-8984-43b",
    "/#/study/subject/detail/a66f4509-e869-4a9",
    "/#/study/subject/detail/edd3de94-7323-4cd",
    "/#/study/subject/detail/e6bb8f5c-1a32-448",
    "/#/study/subject/detail/813d5d89-bea9-4e6",
    "/#/study/subject/detail/6a3153f5-9e94-4d2",
    "/#/study/subject/detail/faad900d-93a6-476",
]

async def main():
    print("🔍 深度爬取专区和专题...", flush=True)
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

        # 收集 API
        api_calls = []

        async def on_resp(resp):
            url = resp.url
            if "/api/" not in url:
                return
            entry = {"url": url, "method": resp.request.method, "status": resp.status}
            try:
                ct = resp.headers.get("content-type", "")
                if "json" in ct:
                    body = await resp.json()
                    entry["response"] = body
                    if isinstance(body, dict):
                        entry["keys"] = list(body.keys())
                    elif isinstance(body, list):
                        entry["count"] = len(body)
            except:
                pass
            api_calls.append(entry)

        page.on("response", on_resp)

        results = {"zones": {}, "subjects": {}, "courses": []}

        # 1. 爬取专区
        print("\n📍 爬取专区...", flush=True)
        for i, zone_path in enumerate(ZONES, 1):
            url = f"{BASE}/{zone_path}" if zone_path.startswith("#") else f"{BASE}{zone_path}"
            print(f"  [{i}/{len(ZONES)}] {zone_path[:50]}", flush=True)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

                # 提取页面内容
                title = await page.title()
                content = await page.evaluate("""() => {
                    const links = [];
                    document.querySelectorAll('a[href]').forEach(a => {
                        const text = a.textContent?.trim() || '';
                        const href = a.href || '';
                        if (text && href && href.includes('#')) {
                            links.push({text: text.substring(0, 100), href: href});
                        }
                    });
                    return {links: links, title: document.title};
                }""")

                results["zones"][zone_path] = {
                    "title": title,
                    "links": content["links"][:50],
                }
                print(f"    标题: {title}", flush=True)
                print(f"    链接: {len(content['links'])} 个", flush=True)

            except Exception as e:
                print(f"    ❌ {str(e)[:100]}", flush=True)

            await asyncio.sleep(1)

        # 2. 爬取专题
        print("\n📍 爬取专题...", flush=True)
        for i, subject_path in enumerate(SUBJECTS, 1):
            url = f"{BASE}/{subject_path}" if subject_path.startswith("#") else f"{BASE}{subject_path}"
            print(f"  [{i}/{len(SUBJECTS)}] {subject_path[:50]}", flush=True)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

                title = await page.title()
                content = await page.evaluate("""() => {
                    const courses = [];
                    document.querySelectorAll('a[href*="course"]').forEach(a => {
                        const text = a.textContent?.trim() || '';
                        const href = a.href || '';
                        if (text && href) {
                            courses.push({text: text.substring(0, 100), href: href});
                        }
                    });
                    return {courses: courses, title: document.title};
                }""")

                results["subjects"][subject_path] = {
                    "title": title,
                    "courses": content["courses"][:20],
                }
                print(f"    标题: {title}", flush=True)
                print(f"    课程: {len(content['courses'])} 个", flush=True)

                # 收集课程 URL
                for course in content["courses"]:
                    if course["href"] not in [c["href"] for c in results["courses"]]:
                        results["courses"].append(course)

            except Exception as e:
                print(f"    ❌ {str(e)[:100]}", flush=True)

            await asyncio.sleep(1)

        await browser.close()

    # 保存结果
    with open(OUT / "zones-subjects.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open(OUT / "zone-api-calls.json", "w", encoding="utf-8") as f:
        json.dump(api_calls, f, ensure_ascii=False, indent=2)

    # 统计
    print(f"\n{'='*60}", flush=True)
    print(f"📊 结果汇总:", flush=True)
    print(f"  专区: {len(results['zones'])}", flush=True)
    print(f"  专题: {len(results['subjects'])}", flush=True)
    print(f"  课程: {len(results['courses'])}", flush=True)
    print(f"  API 调用: {len(api_calls)}", flush=True)

    # 打印发现的课程
    if results["courses"]:
        print(f"\n📚 发现的课程:", flush=True)
        for course in results["courses"][:20]:
            print(f"  {course['text'][:50]}: {course['href'][:60]}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())

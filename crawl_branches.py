"""深度爬取所有分院和专区 - 使用 Playwright"""
import asyncio, json, time, re
from pathlib import Path
from urllib.parse import urlparse
from collections import defaultdict
from playwright.async_api import async_playwright

BASE = "https://mooc.ctt.cn"
AUTH = "output/auth-state.json"
OUT = Path("output/crawl/branches")

# 所有分院/专区配置
BRANCHES = [
    {"name": "网络学院", "configId": "81b0c456-c6a8-4e25-9416-25f7cf5f6c06", "type": "总院"},
    {"name": "专卖分院", "configId": "03e2ef50-92fe-4ad4-9391-6289127ab901", "type": "分院"},
    {"name": "安全生产分院", "configId": "eb691412-0bbe-4405-922d-be20f18b5afd", "type": "分院"},
    {"name": "精益管理分院", "configId": "4bba3cc7-900d-4641-9704-94d255c4df42", "type": "分院"},
    {"name": "网信分院", "configId": "69ea081e-f533-49f8-ac33-79dde8275ea5", "type": "分院"},
    {"name": "物流分院", "configId": "2ed3163d-d990-4ed8-9538-9860b01aad63", "type": "分院"},
    {"name": "营销分院", "configId": "0334f9d7-4cdc-46d6-97a7-6c403690edc7", "type": "分院"},
    {"name": "农业分院", "configId": "56f4b71e-c869-427a-aa77-eee1336cd361", "type": "分院"},
    {"name": "烟机设备分院", "configId": "95cdfef5-6c6c-498e-a999-6b78bf16e623", "type": "分院"},
    {"name": "法律法规学习专区", "configId": "c1fe8977-efcc-420e-9512-9d1f61fd055d", "type": "专区"},
    {"name": "组织人事学习专区", "configId": "d0c9afaf-ebd9-424d-935a-48b05842a8cd", "type": "专区"},
    {"name": "卷烟工艺质量学习专区", "configId": "246abad2-d4d8-4b0d-bdca-260b0c70d356", "type": "专区"},
    {"name": "财务与审计学习专区", "configId": "ffa07f0e-6ad5-4b89-b4ce-f28ad202867c", "type": "专区"},
]

# 标准导航路径
NAV_PATHS = [
    "home",
    "homeBranch",
    "news-dynamic/index",
    "study/branch/index",
    "study/course/index",
    "study/subject/index",
    "policy-statute/index",
    "reading-space/index",
    "expert-zone/index",
    "activity/index",
    "ask/index",
    "knowledge/index",
]

def log(msg):
    print(msg, flush=True)

def classify_api(url):
    path = urlparse(url).path
    path = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "{uuid}", path)
    path = re.sub(r"/\d+", "/{id}", path)
    return path

async def crawl_branch(page, branch, api_calls, page_data):
    """爬取单个分院/专区"""
    name = branch["name"]
    config_id = branch["configId"]
    branch_type = branch["type"]
    
    log(f"\n{'='*60}")
    log(f"🏛️ 爬取: {name} ({branch_type})")
    log(f"   configId: {config_id}")
    log(f"{'='*60}")
    
    branch_results = {
        "name": name,
        "configId": config_id,
        "type": branch_type,
        "pages": [],
        "api_calls": [],
        "courses": [],
        "subjects": [],
        "articles": [],
    }
    
    # 设置当前分院标识
    current_branch = [name]
    
    # 爬取每个导航页面
    for nav_path in NAV_PATHS:
        url = f"{BASE}/#/{nav_path}?configId={config_id}"
        log(f"\n  📍 {nav_path}")
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
            
            # 提取页面信息
            page_info = await page.evaluate("""() => {
                const title = document.title;
                const text = document.body?.innerText?.substring(0, 500) || '';
                
                // 提取链接
                const links = [];
                document.querySelectorAll('a[href]').forEach(a => {
                    const t = a.textContent?.trim() || '';
                    const h = a.href || '';
                    if (t && h && h.includes('#')) {
                        links.push({text: t.substring(0, 100), href: h});
                    }
                });
                
                // 提取课程卡片
                const courses = [];
                document.querySelectorAll('[class*="course"], [class*="item"], .card').forEach(el => {
                    const title = el.querySelector('h3, h4, .title, [class*="title"]');
                    const link = el.querySelector('a');
                    if (title) {
                        courses.push({
                            title: title.textContent?.trim()?.substring(0, 100) || '',
                            href: link?.href || '',
                        });
                    }
                });
                
                return {title, text, links: links.slice(0, 100), courses: courses.slice(0, 50)};
            }""")
            
            branch_results["pages"].append({
                "url": nav_path,
                "title": page_info["title"],
                "links_count": len(page_info["links"]),
                "courses_count": len(page_info["courses"]),
            })
            
            # 收集课程
            for course in page_info["courses"]:
                if course["title"] and course["href"]:
                    branch_results["courses"].append(course)
            
            # 收集链接中的专题
            for link in page_info["links"]:
                if "subject" in link["href"]:
                    branch_results["subjects"].append(link)
                elif "news" in link["href"] or "article" in link["href"]:
                    branch_results["articles"].append(link)
            
            log(f"    标题: {page_info['title'][:50]}")
            log(f"    链接: {len(page_info['links'])} | 课程: {len(page_info['courses'])}")
            
            # 如果是学习资源页面，滚动加载更多
            if "study/branch" in nav_path or "course" in nav_path:
                for scroll in range(3):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(1500)
                    
                    # 提取更多课程
                    more_courses = await page.evaluate("""() => {
                        const courses = [];
                        document.querySelectorAll('[class*="course"], [class*="item"], .card').forEach(el => {
                            const title = el.querySelector('h3, h4, .title, [class*="title"]');
                            const link = el.querySelector('a');
                            if (title) {
                                courses.push({
                                    title: title.textContent?.trim()?.substring(0, 100) || '',
                                    href: link?.href || '',
                                });
                            }
                        });
                        return courses;
                    }""")
                    
                    for course in more_courses:
                        if course["title"] and course["href"]:
                            if course not in branch_results["courses"]:
                                branch_results["courses"].append(course)
                    
                    log(f"    滚动 {scroll+1}/3 → 累计课程: {len(branch_results['courses'])}")
            
        except Exception as e:
            log(f"    ❌ 错误: {str(e)[:100]}")
            branch_results["pages"].append({
                "url": nav_path,
                "error": str(e)[:200],
            })
        
        await asyncio.sleep(0.5)
    
    # 去重课程
    seen = set()
    unique_courses = []
    for c in branch_results["courses"]:
        key = c["href"]
        if key not in seen:
            seen.add(key)
            unique_courses.append(c)
    branch_results["courses"] = unique_courses
    
    # 去重专题
    seen = set()
    unique_subjects = []
    for s in branch_results["subjects"]:
        key = s["href"]
        if key not in seen:
            seen.add(key)
            unique_subjects.append(s)
    branch_results["subjects"] = unique_subjects
    
    log(f"\n  📊 {name} 汇总:")
    log(f"     页面: {len(branch_results['pages'])}")
    log(f"     课程: {len(branch_results['courses'])}")
    log(f"     专题: {len(branch_results['subjects'])}")
    log(f"     文章: {len(branch_results['articles'])}")
    
    return branch_results

async def main():
    log("🚀 启动分院/专区深度爬虫...")
    OUT.mkdir(parents=True, exist_ok=True)
    
    all_results = []
    all_api_calls = []
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--disable-software-rasterizer", "--no-sandbox"]
        )
        
        auth = Path(AUTH)
        if auth.exists():
            ctx = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                storage_state=str(auth),
            )
            log("✅ 已加载凭证")
        else:
            ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
            log("⚠️ 无凭证")
        
        page = await ctx.new_page()
        
        # API 拦截
        async def on_resp(resp):
            url = resp.url
            if "/api/" not in url:
                return
            entry = {
                "url": url,
                "method": resp.request.method,
                "status": resp.status,
                "timestamp": time.time(),
            }
            try:
                ct = resp.headers.get("content-type", "")
                if "json" in ct:
                    body = await resp.json()
                    if isinstance(body, dict):
                        entry["keys"] = list(body.keys())
                    elif isinstance(body, list):
                        entry["count"] = len(body)
            except:
                pass
            all_api_calls.append(entry)
        
        page.on("response", on_resp)
        
        # 先加载首页建立会话
        log("\n📍 加载首页建立会话...")
        await page.goto(BASE, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        
        # 爬取每个分院
        for i, branch in enumerate(BRANCHES, 1):
            log(f"\n{'#'*60}")
            log(f"# [{i}/{len(BRANCHES)}] {branch['name']}")
            log(f"{'#'*60}")
            
            result = await crawl_branch(page, branch, all_api_calls, [])
            all_results.append(result)
            
            # 保存单个分院结果
            filename = branch["name"].replace("/", "-") + ".json"
            with open(OUT / filename, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            await asyncio.sleep(1)
        
        await browser.close()
    
    # 保存汇总
    log("\n💾 保存汇总数据...")
    
    # 分院汇总
    summary = []
    for r in all_results:
        summary.append({
            "name": r["name"],
            "type": r["type"],
            "configId": r["configId"],
            "pages": len(r["pages"]),
            "courses": len(r["courses"]),
            "subjects": len(r["subjects"]),
            "articles": len(r["articles"]),
        })
    
    with open(OUT / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    # 所有课程
    all_courses = []
    for r in all_results:
        for c in r["courses"]:
            all_courses.append({
                "branch": r["name"],
                "title": c["title"],
                "href": c["href"],
            })
    
    with open(OUT / "all-courses.json", "w", encoding="utf-8") as f:
        json.dump(all_courses, f, ensure_ascii=False, indent=2)
    
    # 所有专题
    all_subjects = []
    for r in all_results:
        for s in r["subjects"]:
            all_subjects.append({
                "branch": r["name"],
                "text": s["text"],
                "href": s["href"],
            })
    
    with open(OUT / "all-subjects.json", "w", encoding="utf-8") as f:
        json.dump(all_subjects, f, ensure_ascii=False, indent=2)
    
    # API 调用汇总
    api_summary = defaultdict(lambda: {"count": 0, "methods": set()})
    for call in all_api_calls:
        pat = classify_api(call["url"])
        api_summary[pat]["count"] += 1
        api_summary[pat]["methods"].add(call["method"])
    
    api_catalog = {k: {"count": v["count"], "methods": list(v["methods"])} for k, v in api_summary.items()}
    with open(OUT / "api-catalog.json", "w", encoding="utf-8") as f:
        json.dump(api_catalog, f, ensure_ascii=False, indent=2)
    
    with open(OUT / "api-requests.json", "w", encoding="utf-8") as f:
        json.dump(all_api_calls[:5000], f, ensure_ascii=False, indent=2)
    
    # 生成 Markdown 报告
    generate_report(all_results, all_courses, all_subjects, api_catalog)
    
    # 打印汇总
    log(f"\n{'='*60}")
    log(f"🏁 全部完成！")
    log(f"{'='*60}")
    log(f"📊 分院/专区: {len(all_results)}")
    log(f"📚 课程总数: {len(all_courses)}")
    log(f"📖 专题总数: {len(all_subjects)}")
    log(f"🔌 API 端点: {len(api_catalog)}")
    log(f"📡 API 请求: {len(all_api_calls)}")
    
    log(f"\n📁 各分院详情:")
    for s in summary:
        log(f"  {s['name']:12} | 课程: {s['courses']:3} | 专题: {s['subjects']:2} | 文章: {s['articles']:3}")

def generate_report(results, courses, subjects, api_catalog):
    lines = ["# mooc.ctt.cn 分院/专区深度爬取报告\n\n"]
    lines.append(f"> 爬取时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    
    lines.append("## 📊 汇总\n\n")
    lines.append("| 分院/专区 | 类型 | 课程 | 专题 | 文章 |\n")
    lines.append("|-----------|------|------|------|------|\n")
    for r in results:
        lines.append(f"| {r['name']} | {r['type']} | {len(r['courses'])} | {len(r['subjects'])} | {len(r['articles'])} |\n")
    lines.append(f"| **总计** | - | **{len(courses)}** | **{len(subjects)}** | - |\n\n")
    
    lines.append("## 📚 课程列表\n\n")
    lines.append("| 分院 | 课程名称 |\n")
    lines.append("|------|----------|\n")
    for c in courses[:100]:
        lines.append(f"| {c['branch']} | {c['title'][:60]} |\n")
    if len(courses) > 100:
        lines.append(f"| ... | 共 {len(courses)} 门课程 |\n")
    
    lines.append("\n## 📖 专题列表\n\n")
    lines.append("| 分院 | 专题名称 |\n")
    lines.append("|------|----------|\n")
    for s in subjects[:50]:
        lines.append(f"| {s['branch']} | {s['text'][:60]} |\n")
    
    lines.append("\n## 🔌 API 端点\n\n")
    lines.append("| 路径 | 方法 | 调用次数 |\n")
    lines.append("|------|------|----------|\n")
    for pat in sorted(api_catalog.keys()):
        info = api_catalog[pat]
        methods = ", ".join(info["methods"])
        lines.append(f"| `{pat}` | {methods} | {info['count']} |\n")
    
    with open(OUT / "REPORT.md", "w", encoding="utf-8") as f:
        f.writelines(lines)

if __name__ == "__main__":
    asyncio.run(main())

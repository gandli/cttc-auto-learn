"""
cdp_login_analyzer.py — CDP 深度分析登录流程
1. 启动 Chrome（非 headless）连接 CDP
2. 拦截所有网络请求/响应
3. 监控 DOM 变化
4. 等待用户操作（扫码、切换二维码等）
5. 记录完整流程日志
"""
import asyncio
import json
import time
from pathlib import Path
from datetime import datetime

OUTPUT = Path("output/cdp_analysis")
OUTPUT.mkdir(parents=True, exist_ok=True)

# 日志收集
network_log = []
dom_log = []
console_log = []


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def log(category, msg, data=None):
    entry = {"ts": ts(), "cat": category, "msg": msg}
    if data:
        entry["data"] = data
    print(f"[{ts()}] [{category}] {msg}", flush=True)
    return entry


async def main():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        # 启动 Chrome（使用已安装的 Chrome）
        log("SYS", "启动 Chrome...")
        browser = await p.chromium.launch(
            headless=False,
            executable_path=r"C:\Users\user\scoop\apps\googlechrome\current\chrome.exe",
            args=["--disable-gpu", "--no-sandbox", "--window-size=1280,800"]
        )
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await ctx.new_page()

        # === 网络请求拦截 ===
        async def on_request(request):
            entry = log("REQ", f"{request.method} {request.url[:120]}")
            try:
                if request.post_data:
                    entry["post_data"] = request.post_data[:500]
            except:
                pass
            network_log.append(entry)

        async def on_response(response):
            body_preview = ""
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct or "text" in ct:
                    text = await response.text()
                    body_preview = text[:500]
            except:
                body_preview = "<无法读取>"

            entry = log("RESP", f"{response.status} {response.url[:120]}", {"body": body_preview})
            network_log.append(entry)

        page.on("request", on_request)
        page.on("response", on_response)

        # === Console 拦截 ===
        page.on("console", lambda msg: console_log.append(
            log("CONSOLE", f"[{msg.type}] {msg.text[:200]}")
        ))

        # === DOM 变化监控 ===
        await page.evaluate("""() => {
            window.__domChanges = [];
            const observer = new MutationObserver((mutations) => {
                for (const m of mutations) {
                    const target = m.target;
                    const desc = target.tagName + (target.id ? '#' + target.id : '') + 
                                 (target.className ? '.' + String(target.className).split(' ').slice(0,2).join('.') : '');
                    let detail = '';
                    if (m.type === 'childList') {
                        const added = m.addedNodes.length;
                        const removed = m.removedNodes.length;
                        detail = `children: +${added}/-${removed}`;
                        // 记录新增节点的文本
                        for (const node of m.addedNodes) {
                            if (node.textContent && node.textContent.trim().length < 100) {
                                detail += ` text:"${node.textContent.trim().substring(0, 50)}"`;
                            }
                        }
                    } else if (m.type === 'attributes') {
                        detail = `attr[${m.attributeName}]=${target.getAttribute(m.attributeName)?.substring(0, 50)}`;
                    }
                    window.__domChanges.push({
                        time: new Date().toISOString(),
                        target: desc,
                        type: m.type,
                        detail: detail
                    });
                }
            });
            observer.observe(document.body, {childList: true, subtree: true, attributes: true, attributeFilter: ['src', 'href', 'class', 'style', 'display']});
            console.log('[CDP] DOM Observer 已启动');
        }""")

        # 先清除登录状态，确保看到登录页
        await page.goto("https://mooc.ctt.cn/", wait_until="domcontentloaded", timeout=30000)
        await page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
        await ctx.clear_cookies()
        log("SYS", "已清除 localStorage + cookies")

        # 重新打开首页，应该会跳转到登录页
        log("SYS", "打开首页...")
        await page.goto("https://mooc.ctt.cn/", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
        log("SYS", f"当前 URL: {page.url}")

        # 如果没有跳转到登录页，点击登录按钮
        if "/oauth/" not in page.url and "/login" not in page.url.lower():
            log("SYS", "未跳转到登录页，尝试点击登录按钮...")
            try:
                login_btn = page.locator('a:has-text("登录"), button:has-text("登录")').first
                if await login_btn.count() > 0:
                    await login_btn.click(timeout=5000)
                    await page.wait_for_timeout(3000)
                    log("SYS", f"点击登录后 URL: {page.url}")
            except Exception as e:
                log("SYS", f"点击登录失败: {e}")

        await page.wait_for_timeout(3000)

        # === 截取初始状态 ===
        log("SYS", "页面加载完成，记录初始状态...")
        await page.screenshot(path=str(OUTPUT / "01_initial.png"))

        # 获取页面结构
        structure = await page.evaluate("""() => {
            function getTree(el, depth = 0) {
                if (depth > 5) return '';
                let result = '  '.repeat(depth) + el.tagName;
                if (el.id) result += '#' + el.id;
                if (el.className && typeof el.className === 'string') 
                    result += '.' + el.className.split(' ').filter(Boolean).join('.');
                if (el.src) result += ' src=' + el.src.substring(0, 60);
                if (el.href) result += ' href=' + el.href.substring(0, 60);
                result += '\\n';
                for (const child of el.children) {
                    result += getTree(child, depth + 1);
                }
                return result;
            }
            return getTree(document.body);
        }""")
        (OUTPUT / "01_dom_tree.txt").write_text(structure, encoding="utf-8")
        log("SYS", f"DOM 树已保存 ({len(structure)} chars)")

        # 获取所有图片
        imgs = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('img')).map(img => ({
                src: img.src?.substring(0, 100),
                alt: img.alt,
                width: img.getBoundingClientRect().width,
                height: img.getBoundingClientRect().height,
                parent: img.parentElement?.tagName + (img.parentElement?.id ? '#' + img.parentElement.id : '')
            }));
        }""")
        log("SYS", f"页面图片: {len(imgs)} 个")
        for img in imgs:
            log("IMG", f"  {img['parent']} {img['width']}x{img['height']} alt={img['alt']} src={img['src'][:60]}")

        # 获取所有可点击元素
        clickables = await page.evaluate("""() => {
            const els = document.querySelectorAll('a, button, [onclick], [role="button"], .clickable, [class*="tab"], [class*="step"]');
            return Array.from(els).map(el => ({
                tag: el.tagName,
                id: el.id,
                text: el.textContent?.trim().substring(0, 50),
                class: el.className?.toString().substring(0, 60),
                rect: el.getBoundingClientRect()
            }));
        }""")
        log("SYS", f"可点击元素: {len(clickables)} 个")
        for c in clickables:
            if c['text']:
                log("CLICK", f"  {c['tag']}#{c['id']}.{c['class'][:30]} text=\"{c['text']}\"")

        # === 记录当前网络请求摘要 ===
        log("SYS", f"初始网络请求: {len(network_log)} 个")
        for entry in network_log:
            log("NET_INIT", f"  {entry['msg']}")

        # === 等待用户操作 ===
        log("WAIT", "="*50)
        log("WAIT", "请在浏览器中操作：")
        log("WAIT", "1. 观察 APP 二维码（左侧）")
        log("WAIT", "2. 点击 '微信登录' 标签")
        log("WAIT", "3. 等二维码过期")
        log("WAIT", "4. 点击刷新二维码")
        log("WAIT", "5. 用微信扫码")
        log("WAIT", "="*50)
        log("WAIT", "脚本每 5 秒记录一次状态变化，Ctrl+C 结束")

        # 持续监控循环
        last_net_count = len(network_log)
        last_dom_count = 0
        tick = 0

        try:
            while True:
                await page.wait_for_timeout(5000)
                tick += 1

                # 检查新网络请求
                new_requests = network_log[last_net_count:]
                if new_requests:
                    log("NET_NEW", f"+{len(new_requests)} 新请求")
                    last_net_count = len(network_log)

                # 检查 DOM 变化
                dom_changes = await page.evaluate("() => { const c = window.__domChanges || []; window.__domChanges = []; return c; }")
                if dom_changes:
                    log("DOM_CHANGE", f"+{len(dom_changes)} DOM 变化")
                    for dc in dom_changes[:10]:  # 最多打印 10 个
                        dom_log.append(dc)
                        log("DOM", f"  {dc['target']} [{dc['type']}] {dc['detail'][:100]}")
                    if len(dom_changes) > 10:
                        log("DOM", f"  ... 还有 {len(dom_changes)-10} 个变化")

                # 检查 URL 变化
                current_url = page.url
                if "/login" not in current_url.lower() and "/oauth/" not in current_url.lower():
                    log("NAV", f"页面已跳转: {current_url}")
                    await page.screenshot(path=str(OUTPUT / f"02_redirect_{tick}.png"))
                    break

                # 检查是否出现"退出"
                has_logout = await page.evaluate("() => (document.body?.innerText || '').includes('退出')")
                if has_logout:
                    log("LOGIN", "检测到'退出'文字 — 登录成功！")
                    await page.screenshot(path=str(OUTPUT / f"03_login_success_{tick}.png"))
                    break

                # 每 30 秒截图一次
                if tick % 6 == 0:
                    await page.screenshot(path=str(OUTPUT / f"tick_{tick:04d}.png"))
                    log("TICK", f"第 {tick} 次检查 (已过 {tick*5}s)")

        except KeyboardInterrupt:
            log("SYS", "用户中断")

        # === 保存完整分析 ===
        log("SYS", "保存分析结果...")

        # 网络请求
        (OUTPUT / "network_log.json").write_text(
            json.dumps(network_log, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # DOM 变化
        (OUTPUT / "dom_changes.json").write_text(
            json.dumps(dom_log, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Console
        (OUTPUT / "console_log.json").write_text(
            json.dumps(console_log, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 最终 DOM 树
        final_structure = await page.evaluate("""() => {
            function getTree(el, depth = 0) {
                if (depth > 5) return '';
                let result = '  '.repeat(depth) + el.tagName;
                if (el.id) result += '#' + el.id;
                if (el.className && typeof el.className === 'string') 
                    result += '.' + el.className.split(' ').filter(Boolean).join('.');
                result += '\\n';
                for (const child of el.children) {
                    result += getTree(child, depth + 1);
                }
                return result;
            }
            return getTree(document.body);
        }""")
        (OUTPUT / "final_dom_tree.txt").write_text(final_structure, encoding="utf-8")

        # 最终 cookies
        cookies = await ctx.cookies()
        (OUTPUT / "cookies.json").write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # localStorage
        storage = await page.evaluate("""() => {
            const result = {};
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                result[key] = localStorage.getItem(key)?.substring(0, 200);
            }
            return result;
        }""")
        (OUTPUT / "localStorage.json").write_text(
            json.dumps(storage, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        log("SYS", f"分析完成！结果保存在 {OUTPUT}")
        log("SYS", f"网络请求: {len(network_log)} 个")
        log("SYS", f"DOM 变化: {len(dom_log)} 个")
        log("SYS", f"Console: {len(console_log)} 条")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

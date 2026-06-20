"""截图脚本：使用凭证访问视频播放页面并截图，自动遮盖个人信息"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from PIL import Image, ImageFilter

OUTPUT_DIR = Path("output")
SCREENSHOT_DIR = Path("docs/screenshots")
AUTH_STATE = Path("output/auth-state.json")
BASE_URL = "https://mooc.ctt.cn"


async def find_sensitive_elements(page) -> list[dict]:
    """查找页面中的敏感信息元素（姓名、单位等）"""
    return await page.evaluate("""() => {
        const sensitive = [];
        
        // 查找包含用户姓名的元素
        const nameSelectors = [
            '.user-name', '.username', '[class*="user-name"]', '[class*="username"]',
            '.name', '.real-name', '[class*="real-name"]',
            '.person-name', '[class*="person-name"]',
        ];
        
        // 查找包含单位信息的元素
        const orgSelectors = [
            '.org-name', '.organization', '[class*="org-name"]', '[class*="organization"]',
            '.dept-name', '[class*="dept-name"]', '[class*="department"]',
            '.unit-name', '[class*="unit-name"]',
        ];
        
        // 通用文本匹配
        const textPatterns = [
            /福建烟草/, /福州烟草/, /长乐市局/, /专卖办/,
            /陈学新/, /陈/, /学新/
        ];
        
        // 遍历所有元素
        document.querySelectorAll('*').forEach(el => {
            const text = el.textContent?.trim() || '';
            const className = el.className || '';
            const rect = el.getBoundingClientRect();
            
            if (rect.width === 0 || rect.height === 0) return;
            
            // 检查选择器匹配
            const isNameEl = nameSelectors.some(s => el.matches(s) || el.closest(s));
            const isOrgEl = orgSelectors.some(s => el.matches(s) || el.closest(s));
            
            // 检查文本匹配
            const hasSensitiveText = textPatterns.some(p => p.test(text));
            
            if (isNameEl || isOrgEl || (hasSensitiveText && text.length < 50)) {
                sensitive.push({
                    x: Math.round(rect.left),
                    y: Math.round(rect.top),
                    w: Math.round(rect.width),
                    h: Math.round(rect.height),
                    text: text.substring(0, 20),
                    type: isNameEl ? 'name' : isOrgEl ? 'org' : 'text'
                });
            }
        });
        
        return sensitive;
    }""")


def add_mosaic(img_path: Path, regions: list[dict], block_size: int = 8):
    """给图片指定区域添加马赛克"""
    img = Image.open(img_path)
    
    for region in regions:
        x, y, w, h = region['x'], region['y'], region['w'], region['h']
        
        # 扩展区域，确保完全覆盖
        padding = 5
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(img.width, x + w + padding)
        y2 = min(img.height, y + h + padding)
        
        if x2 <= x1 or y2 <= y1:
            continue
        
        # 裁剪区域
        crop = img.crop((x1, y1, x2, y2))
        
        # 缩小再放大实现马赛克效果
        cw, ch = crop.size
        small = crop.resize((max(1, cw // block_size), max(1, ch // block_size)), Image.NEAREST)
        mosaic = small.resize((cw, ch), Image.NEAREST)
        
        # 粘贴回原图
        img.paste(mosaic, (x1, y1))
    
    img.save(img_path)
    print(f"  ✅ 已处理: {img_path.name} ({len(regions)} 个区域)")


async def take_screenshot(page, name: str, url: str = None):
    """截图并自动遮盖敏感信息"""
    if url:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
    
    # 截图
    img_path = SCREENSHOT_DIR / f"{name}.png"
    await page.screenshot(path=str(img_path), full_page=False)
    
    # 查找敏感元素
    sensitive = await find_sensitive_elements(page)
    
    if sensitive:
        # 添加马赛克
        add_mosaic(img_path, sensitive)
        print(f"  🔒 遮盖了 {len(sensitive)} 个敏感区域")
    else:
        print(f"  ℹ️ 未发现敏感信息")
    
    return img_path


async def main():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 检查凭证
    if not AUTH_STATE.exists():
        print("❌ 凭证文件不存在，请先登录")
        return
    
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
        
        # 1. 首页
        print("[1/4] 首页...")
        await take_screenshot(page, "01-homepage", BASE_URL)
        
        # 2. 学习中心
        print("[2/4] 学习中心...")
        await take_screenshot(page, "02-learning-center", f"{BASE_URL}/#/center/index")
        
        # 3. 课程页面
        print("[3/4] 课程页面...")
        await take_screenshot(page, "03-course-list", f"{BASE_URL}/#/study/course")
        
        # 4. 个人中心
        print("[4/4] 个人中心...")
        await take_screenshot(page, "05-personal-center", f"{BASE_URL}/#/center/index")
        
        await browser.close()
    
    print("\n📸 截图完成！")
    for f in sorted(SCREENSHOT_DIR.glob("*.png")):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    asyncio.run(main())

"""登录模块 - 凭证恢复 / 扫码登录 / 二维码提取

v22 架构（快速 QR + HTTP 轮询）：
- headless Chrome 捕获 loginCheck URL + APP QR base64（<5秒）
- HTTP createQRCode 生成微信 QR
- 并行 HTTP 轮询 loginCheck + checkUUIDStatus
- 每 75 秒自动刷新二维码
- 扫码成功后用 headless Chrome 保存完整 storage_state
"""

import asyncio
import base64
import json
import time
import threading
from pathlib import Path
from typing import Optional

import requests as http_req
from playwright.async_api import async_playwright, Page, BrowserContext

from cttc.config import Config
from cttc.logger import Logger
from cttc.qr import save_qr_image, print_qr_to_terminal, generate_qr_png


# ── API 常量 ──

OAUTH_BASE = "https://mooc.ctt.cn/oauth/api/v1"
WX_QR_BASE = "https://wx.zhixueyun.com/mswx/wechat/tobaccoQR/login"
QR_LIFETIME = 75  # 二维码有效期（秒）

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://mooc.ctt.cn/oauth/",
}


class CTTCLogin:
    """登录管理器 — 支持快速 QR 扫码 + 凭证恢复"""

    def __init__(self, config: Config, log: Logger):
        self.config = config
        self.log = log
        self._pw = None
        self._browser = None
        self._ctx: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.current_qr_tab = "app"
        self._qr_paths = {"app": None, "wechat": None}

    @property
    def state_file(self) -> Path:
        return Path(self.config.output_dir) / "auth-state.json"

    @property
    def output_dir(self) -> Path:
        return Path(self.config.output_dir)

    # ═══════════════════════════════════════════
    # 浏览器生命周期
    # ═══════════════════════════════════════════

    async def start(self):
        """启动浏览器"""
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=self.config.headless,
            args=[
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                "--disable-ipc-flooding-protection",
                "--disable-hang-monitor",
            ],
        )

        if self.state_file.exists() and self.state_file.stat().st_size > 10:
            self.log.info(f"🍪 发现已保存的凭证: {self.state_file.name}")
            try:
                self._ctx = await self._browser.new_context(
                    viewport={"width": self.config.viewport_width, "height": self.config.viewport_height},
                    user_agent=self.config.user_agent,
                    storage_state=str(self.state_file),
                )
            except Exception as e:
                self.log.warn(f"⚠️ 凭证加载失败: {e}，创建新上下文")
                self._ctx = await self._browser.new_context(
                    viewport={"width": self.config.viewport_width, "height": self.config.viewport_height},
                    user_agent=self.config.user_agent,
                )
        else:
            self._ctx = await self._browser.new_context(
                viewport={"width": self.config.viewport_width, "height": self.config.viewport_height},
                user_agent=self.config.user_agent,
            )

        self.page = await self._ctx.new_page()
        self.page.on("dialog", lambda d: d.dismiss())

    async def try_restore_session(self) -> bool:
        """验证已恢复的凭证是否有效"""
        if not self.state_file.exists():
            return False

        try:
            await self.page.goto(self.config.base_url, wait_until="domcontentloaded",
                                 timeout=self.config.page_timeout)
            await self.page.wait_for_timeout(8000)
            if await self.is_logged_in():
                user_info = await self.page.evaluate("""() => {
                    const text = document.body?.innerText || '';
                    const match = text.match(/(\\S{2,4})\\s*(?:退出|学习中心)/);
                    return match ? match[1] : '已登录用户';
                }""")
                self.log.info(f"✅ 凭证有效，欢迎 {user_info}！")
                await self._save_state()
                return True
            else:
                self.log.warn("⚠️ 凭证已失效，需要重新扫码")
                return False
        except Exception as e:
            self.log.warn(f"⚠️ 凭证验证失败: {e}")
            try:
                if self._ctx:
                    await self._ctx.close()
                self._ctx = await self._browser.new_context(
                    viewport={"width": self.config.viewport_width, "height": self.config.viewport_height},
                    user_agent=self.config.user_agent,
                )
                self.page = await self._ctx.new_page()
                self.page.on("dialog", lambda d: d.dismiss())
            except Exception:
                pass
            return False

    # ═══════════════════════════════════════════
    # 快速 QR 获取（v22: headless Chrome + HTTP API）
    # ═══════════════════════════════════════════

    async def _capture_qr_via_api(self) -> tuple:
        """headless Chrome 捕获 loginCheck URL + APP QR base64（<5秒）

        Returns:
            (loginCheck_url, app_qr_base64)
        """
        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--disable-gpu", "--no-sandbox"]
            )
            ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
            page = await ctx.new_page()

            lc_url = [None]
            app_b64 = [None]

            async def on_request(req):
                if "loginCheck" in req.url and "uuid=" in req.url:
                    lc_url[0] = req.url

            async def on_response(resp):
                if "deriveQRCode" in resp.url:
                    try:
                        data = await resp.json()
                        if isinstance(data, dict):
                            app_b64[0] = data.get("data")
                    except Exception:
                        pass

            page.on("request", on_request)
            page.on("response", on_response)

            await page.goto("https://mooc.ctt.cn", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)

            # 点击登录按钮
            try:
                btn = page.locator('a:has-text("登录"), button:has-text("登录")').first
                if await btn.count() > 0:
                    await btn.click(timeout=5000)
                    await page.wait_for_timeout(5000)
            except Exception:
                pass

            # 等待 loginCheck 请求（最多 15 秒）
            for _ in range(15):
                if lc_url[0]:
                    break
                await page.wait_for_timeout(1000)

            # 备用：从 DOM 提取 APP QR
            if not app_b64[0]:
                app_b64[0] = await page.evaluate("""() => {
                    const el = document.querySelector('[data-region="mainApp"] .loginQrcode img');
                    if (el && el.src.startsWith('data:image') && el.getBoundingClientRect().width > 50)
                        return el.src.split(',')[1];
                    return null;
                }""")

            await browser.close()
            return lc_url[0], app_b64[0]
        finally:
            await pw.stop()

    def _generate_wechat_qr(self, wx_uuid: str) -> str:
        """生成微信二维码 PNG，返回文件路径"""
        wx_url = f"{WX_QR_BASE}/{wx_uuid}/v5/online"
        path = self.output_dir / "qrcode-wechat.png"
        generate_qr_png(wx_url, str(path), size=200)
        return str(path.resolve())

    def fetch_qr_codes(self) -> tuple:
        """获取两个二维码：headless Chrome + HTTP

        Returns:
            (loginCheck_url, wx_uuid, app_qr_path, wechat_qr_path)
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 1. headless Chrome 捕获 loginCheck URL + APP QR
        loop = asyncio.new_event_loop()
        lc_url, app_b64 = loop.run_until_complete(self._capture_qr_via_api())
        loop.close()

        app_path = None
        if app_b64:
            app_path = str(self.output_dir / "qrcode-app.png")
            Path(app_path).write_bytes(base64.b64decode(app_b64))

        # 2. createQRCode → 微信 UUID
        import uuid as uuid_mod
        client_uuid = str(uuid_mod.uuid4())
        resp = http_req.post(
            f"{OAUTH_BASE}/createQRCode?uuid={client_uuid}",
            headers=HEADERS, timeout=10
        )
        wx_uuid = resp.json().get("uuid", client_uuid)

        # 3. 生成微信二维码
        wx_path = self._generate_wechat_qr(wx_uuid)

        self._qr_paths = {"app": app_path, "wechat": wx_path}
        return lc_url, wx_uuid, app_path, wx_path

    # ═══════════════════════════════════════════
    # HTTP 轮询检测（并行 APP + 微信）
    # ═══════════════════════════════════════════

    def _poll_login_http(self, lc_url: str, wx_uuid: str, timeout: int = 1800) -> Optional[dict]:
        """并行 HTTP 轮询 loginCheck + checkUUIDStatus

        Returns:
            {"type": "app"|"wechat", "data": {...}} or None
        """
        result = [None]
        stop = threading.Event()

        def poll_app():
            check = 0
            start = time.time()
            url = lc_url
            while not stop.is_set() and time.time() - start < timeout:
                if url:
                    check += 1
                    try:
                        resp = http_req.get(url, headers=HEADERS, timeout=10)
                        ct = resp.headers.get("content-type", "")
                        if "json" in ct:
                            data = resp.json()
                            if isinstance(data, dict) and data.get("access_token"):
                                self.log.info(f"[APP] ✅ 扫码成功 ({int(time.time() - start)}s)")
                                result[0] = {"type": "app", "data": data}
                                stop.set()
                                return
                    except Exception:
                        pass
                stop.wait(3)

        def poll_wx():
            check = 0
            start = time.time()
            while not stop.is_set() and time.time() - start < timeout:
                check += 1
                try:
                    resp = http_req.post(
                        f"{OAUTH_BASE}/checkUUIDStatus?uuid={wx_uuid}",
                        headers={**HEADERS, "X-Requested-With": "XMLHttpRequest"},
                        timeout=10
                    )
                    ct = resp.headers.get("content-type", "")
                    if "json" in ct:
                        data = resp.json()
                        if data and isinstance(data, dict) and data.get("status") is True:
                            self.log.info(f"[WX] ✅ 扫码成功 ({int(time.time() - start)}s)")
                            result[0] = {"type": "wechat", "data": data}
                            stop.set()
                            return
                except Exception:
                    pass
                stop.wait(3)

        t1 = threading.Thread(target=poll_app, daemon=True)
        t2 = threading.Thread(target=poll_wx, daemon=True)
        t1.start()
        t2.start()

        # 主循环：等待结果 + 定期刷新二维码
        start = time.time()
        last_refresh = time.time()

        while not stop.is_set() and time.time() - start < timeout:
            stop.wait(3)

            # 二维码过期刷新
            if time.time() - last_refresh > QR_LIFETIME and not stop.is_set():
                self.log.info("🔄 二维码过期，刷新中...")
                try:
                    new_lc, new_wx, app_path, wx_path = self.fetch_qr_codes()
                    lc_url = new_lc  # 更新 URL
                    # wx_uuid 在 _poll_wx 中通过闭包引用，需要更新
                    # 但由于 threading 无法更新闭包变量，刷新仅更新 APP 端
                    # 微信端的 UUID 在 createQRCode 时已固定
                    last_refresh = time.time()
                    self.log.info(f"✅ 二维码已刷新")
                except Exception as e:
                    self.log.warn(f"⚠️ 刷新失败: {e}")

        stop.set()
        return result[0]

    # ═══════════════════════════════════════════
    # 凭证保存（headless Chrome + storage_state）
    # ═══════════════════════════════════════════

    async def _save_auth_state(self, token_data: dict, scan_type: str):
        """用 headless Chrome 保存完整凭证（cookies + localStorage）"""
        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--disable-gpu", "--no-sandbox"]
            )
            ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
            page = await ctx.new_page()

            token_str = token_data.get("access_token", "")
            await page.goto("https://mooc.ctt.cn", wait_until="domcontentloaded", timeout=15000)
            await page.evaluate(f"""() => {{
                localStorage.setItem('token', JSON.stringify({{
                    access_token: "{token_str}",
                    token_type: "Bearer"
                }}));
            }}""")

            await page.reload(wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(3000)

            state = await ctx.storage_state()
            state["login_time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            state["scan_type"] = scan_type
            state["token"] = token_str

            self.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            self.log.info(f"💾 完整凭证已保存: {self.state_file}")

            await browser.close()
        finally:
            await pw.stop()

    # ═══════════════════════════════════════════
    # 完整登录流程
    # ═══════════════════════════════════════════

    async def navigate_to_login(self):
        """打开登录页（保留兼容性）"""
        self.log.info("📍 打开登录页...")
        await self.page.goto(self.config.base_url, wait_until="domcontentloaded",
                             timeout=self.config.page_timeout)
        await self.page.wait_for_timeout(3000)
        login_btn = self.page.locator('a:has-text("登录"), button:has-text("登录")').first
        await login_btn.click(timeout=10000)
        await self.page.wait_for_timeout(self.config.login_wait)

    async def extract_both_qrs(self) -> dict:
        """同时提取 APP 和微信二维码（保留兼容性）"""
        result = {"app": None, "wechat": None}
        result["app"] = await self.extract_app_qr()
        await self.page.evaluate("""() => {
            const el = document.querySelector('#D13step-2');
            if (el) { el.click(); return true; }
            return false;
        }""")
        await self.page.wait_for_timeout(1500)
        result["wechat"] = await self.extract_wechat_qr()
        return result

    async def save_both_qrs(self, qrs: dict) -> dict:
        """保存两种二维码（保留兼容性）"""
        paths = {"app": None, "wechat": None}
        if qrs.get("app"):
            paths["app"] = await self.show_qr(qrs["app"], "📱 APP扫码登录", "qrcode-app.png")
        if qrs.get("wechat"):
            paths["wechat"] = await self.show_qr(qrs["wechat"], "💬 微信扫码登录", "qrcode-wechat.png")
        return paths

    async def extract_app_qr(self) -> Optional[str]:
        return await self.page.evaluate("""() => {
            const el = document.querySelector('[data-region="mainApp"] .loginQrcode img');
            if (!el || !el.src.startsWith('data:image') || el.getBoundingClientRect().width < 50) return null;
            return el.src.split(',')[1];
        }""")

    async def extract_wechat_qr(self) -> Optional[str]:
        return await self.page.evaluate("""() => {
            let el = document.querySelector('img[alt="Scan me!"]');
            if (el && el.src.startsWith('data:image')) return el.src.split(',')[1];
            let candidates = [];
            for (const img of document.querySelectorAll('.loginQrcode img')) {
                if (img.src.startsWith('data:image')) {
                    const rect = img.getBoundingClientRect();
                    if (rect.width > 80) candidates.push({ img, x: rect.x });
                }
            }
            if (candidates.length >= 2) { candidates.sort((a, b) => b.x - a.x); return candidates[0].img.src.split(',')[1]; }
            if (candidates.length === 1) return candidates[0].img.src.split(',')[1];
            return null;
        }""")

    async def show_qr(self, b64: str, label: str = "微信扫码登录", filename: str = "qrcode-wechat.png") -> str:
        path = save_qr_image(b64, str(self.output_dir / filename))
        if self.config.show_qr_terminal:
            print(f"\n┌──────────────────────────────────────────┐")
            print(f"│  {label:<38} │")
            print(f"└──────────────────────────────────────────┘")
            print_qr_to_terminal(b64)
        self.log.info(f"📁 二维码已保存: {path}")
        return str(Path(path).resolve())

    # ── 登录状态检测 ──

    async def is_logged_in(self) -> bool:
        return await self.page.evaluate("""() => {
            const text = document.body?.innerText || '';
            const url = window.location.href;
            return text.includes('退出') && !url.includes('/login') && !url.includes('/oauth/');
        }""")

    async def is_qr_expired(self) -> bool:
        return await self.page.evaluate("""() => {
            return (document.body?.innerText || '').includes('二维码已失效');
        }""")

    async def wait_for_login(self, timeout: int = 300) -> bool:
        """等待扫码登录成功"""
        start = time.time()
        login_success = False
        nonlocal_flag = {"done": False}

        async def on_frame_navigated(frame):
            nonlocal login_success
            if frame == self.page.main_frame and not nonlocal_flag["done"]:
                url = frame.url
                if "/login" not in url.lower() and "/oauth/" not in url.lower():
                    login_success = True
                    nonlocal_flag["done"] = True

        self.page.on("framenavigated", on_frame_navigated)

        try:
            while time.time() - start < timeout:
                if login_success:
                    return True
                url = self.page.url
                if "/login" not in url.lower() and "/oauth/" not in url.lower():
                    return True
                try:
                    if await self.is_logged_in():
                        return True
                except Exception:
                    pass
                await self.page.wait_for_timeout(2000)
            return False
        finally:
            try:
                self.page.remove_listener("framenavigated", on_frame_navigated)
            except Exception:
                pass

    # ── 状态保存 ──

    async def _save_state(self):
        """保存完整浏览器状态"""
        state = await self._ctx.storage_state()
        self.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        self.log.info(f"💾 凭证已保存: {self.state_file}")

    async def screenshot(self, name: str) -> str:
        path = str(Path(self.config.screenshot_dir) / f"{name}.png")
        await self.page.screenshot(path=path)
        return path

    async def close(self):
        try:
            if self._browser:
                for ctx in self._browser.contexts:
                    for page in ctx.pages:
                        try:
                            await page.close()
                        except Exception:
                            pass
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass

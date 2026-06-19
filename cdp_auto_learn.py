"""
烟草网络学院自动学习助手 — CDP (Chrome DevTools Protocol) 版本

连接已运行的 Chrome 浏览器，复用登录会话，通过 CDP 控制页面。

用法:
    1. chrome.exe --remote-debugging-port=9222
    2. python cdp_auto_learn.py --mode hours --target 50
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import websockets
except ImportError:
    print("❌ 缺少依赖: pip install websockets")
    sys.exit(1)

try:
    import requests
except ImportError:
    import urllib.request
    import urllib.error

    # 简单的 requests 替代
    class _Requests:
        @staticmethod
        def get(url, headers=None, timeout=10):
            req = urllib.request.Request(url, headers=headers or {})
            try:
                resp = urllib.request.urlopen(req, timeout=timeout)
                return _Response(resp)
            except urllib.error.URLError as e:
                raise ConnectionError(str(e))

        @staticmethod
        def post(url, headers=None, json=None, timeout=10):
            data = json.dumps(json).encode() if json else None
            req = urllib.request.Request(url, data=data, headers=headers or {}, method='POST')
            try:
                resp = urllib.request.urlopen(req, timeout=timeout)
                return _Response(resp)
            except urllib.error.URLError as e:
                raise ConnectionError(str(e))

    class _Response:
        def __init__(self, resp):
            self.status_code = resp.status
            self.headers = dict(resp.headers)
            self._data = resp.read()

        def json(self):
            return json.loads(self._data)

        @property
        def text(self):
            return self._data.decode()

    requests = _Requests()


# ═══════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════

API_BASE = "https://mooc.ctt.cn"
OAUTH_BASE = "https://mooc.ctt.cn/oauth/api/v1"
WX_QR_BASE = "https://wx.zhixueyun.com/mswx/wechat/tobaccoQR/login"

API = {
    "courses": "/api/v1/course-study/course-study-progress/personCourse-list",
    "video_progress": "/api/v1/course-study/course-front/video-progress",
    "tasks": "/api/v1/human/task",
    "task_remind": "/api/v1/human/task/findMyTaskRemind",
    "study_stats": "/api/v1/system/credit/detail-hour-member",
    "cadre_stats": "/api/v1/system/cadre-education/detail-hour-member",
    "organization": "/api/v1/system/home-config/organization",
    "topics": "/api/v1/human/special-topic/findMySpecialTopicPage",
    "topic_detail": "/api/v1/human/special-topic/findMySpecialTopicDetail",
}


# ═══════════════════════════════════════════
# 数据类
# ═══════════════════════════════════════════

@dataclass
class Course:
    title: str
    course_id: str
    status: str  # 未开始/学习中/已完成
    required: str  # 必修/选修
    study_min: int = 0
    total_min: int = 0
    pct: str = "0%"
    url: str = ""


@dataclass
class Task:
    id: str
    title: str
    status: str
    deadline: str = ""
    business_id: str = ""
    business_type: str = ""


@dataclass
class Topic:
    id: str
    title: str
    status: str
    course_count: int = 0
    completed_count: int = 0


@dataclass
class AppData:
    courses: list = field(default_factory=list)
    tasks: list = field(default_factory=list)
    topics: list = field(default_factory=list)
    study_stats: dict = field(default_factory=dict)
    organization: dict = field(default_factory=dict)


# ═══════════════════════════════════════════
# CDP 客户端
# ═══════════════════════════════════════════

class CDPClient:
    """Chrome DevTools Protocol 客户端"""

    def __init__(self, port: int = 9222):
        self.port = port
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._msg_id = 0
        self._target_id: Optional[str] = None
        self._page_url: str = ""

    async def connect(self) -> bool:
        """连接到 Chrome CDP"""
        try:
            # 获取可用的调试目标（标签页）
            resp = requests.get(f"http://localhost:{self.port}/json", timeout=5)
            targets = resp.json()

            # 找到 mooc.ctt.cn 的标签页，或使用第一个页面
            page_target = None
            for t in targets:
                if t.get("type") == "page":
                    url = t.get("url", "")
                    if "mooc.ctt.cn" in url:
                        page_target = t
                        break
                    if not page_target:
                        page_target = t

            if not page_target:
                print("❌ 未找到可用的 Chrome 标签页")
                return False

            ws_url = page_target["webSocketDebuggerUrl"]
            self._target_id = page_target.get("id")
            self._page_url = page_target.get("url", "")

            print(f"🔌 连接: {page_target.get('title', '未知页面')}")
            print(f"   URL: {self._page_url}")

            self.ws = await websockets.connect(ws_url, max_size=10 * 1024 * 1024)
            # 启用必要的域
            await self.send("Runtime.enable")
            await self.send("Network.enable")
            return True

        except Exception as e:
            print(f"❌ 连接失败: {e}")
            print(f"   请确保 Chrome 已启动: chrome --remote-debugging-port={self.port}")
            return False

    async def disconnect(self):
        """断开连接"""
        if self.ws:
            await self.ws.close()
            self.ws = None

    async def send(self, method: str, params: dict = None) -> dict:
        """发送 CDP 命令"""
        self._msg_id += 1
        msg = {"id": self._msg_id, "method": method}
        if params:
            msg["params"] = params

        await self.ws.send(json.dumps(msg))

        # 等待对应的响应
        while True:
            resp = json.loads(await self.ws.recv())
            if resp.get("id") == self._msg_id:
                return resp.get("result", {})
            # 忽略事件消息

    async def evaluate(self, expression: str) -> any:
        """执行 JavaScript 表达式"""
        result = await self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        if result.get("exceptionDetails"):
            raise Exception(result["exceptionDetails"].get("text", "JS 执行错误"))
        return result.get("result", {}).get("value")

    async def navigate(self, url: str):
        """导航到 URL"""
        await self.send("Page.navigate", {"url": url})
        await asyncio.sleep(3)

    async def reload(self):
        """刷新页面"""
        await self.send("Page.reload")
        await asyncio.sleep(3)

    async def fetch_via_js(self, url: str, method: str = "GET", headers: dict = None, body: dict = None) -> any:
        """通过页面的 fetch API 发送请求（复用页面的 cookie/token）"""
        js_headers = json.dumps(headers or {})
        js_body = json.dumps(body) if body else "null"

        expression = f"""
        (async () => {{
            const resp = await fetch('{url}', {{
                method: '{method}',
                headers: {js_headers},
                body: {js_body},
            }});
            if (!resp.ok) return null;
            const ct = resp.headers.get('content-type') || '';
            if (!ct.includes('json')) return null;
            return await resp.json();
        }})()
        """
        return await self.evaluate(expression)


# ═══════════════════════════════════════════
# 主逻辑
# ═══════════════════════════════════════════

class CTTCApp:
    """烟草网络学院自动学习应用"""

    def __init__(self, cdp: CDPClient, args):
        self.cdp = cdp
        self.args = args
        self.data = AppData()
        self.is_running = False
        self.stop_requested = False

    # ── 日志 ──

    def log(self, msg: str, level: str = "info"):
        ts = time.strftime("%H:%M:%S")
        prefix = {"info": "ℹ️", "warn": "⚠️", "error": "❌", "success": "✅"}.get(level, "")
        print(f"[{ts}] {prefix} {msg}")

    # ── 登录检查 ──

    async def check_login(self) -> bool:
        """检查是否已登录"""
        self.log("检查登录状态...")
        result = await self.cdp.evaluate("""(() => {
            const text = document.body?.innerText || '';
            const token = localStorage.getItem('token') || '';
            return {
                hasToken: !!token,
                hasLogout: text.includes('退出'),
                url: location.href,
            };
        })()""")

        if not result:
            return False

        has_token = result.get("hasToken", False)
        has_logout = result.get("hasLogout", False)
        url = result.get("url", "")
        is_login_page = "/login" in url or "/oauth/" in url

        if has_token and has_logout and not is_login_page:
            self.log("✅ 已登录", "success")
            return True

        self.log("❌ 未登录", "warn")
        return False

    async def show_qr_login(self):
        """显示微信扫码登录"""
        self.log("📱 获取微信扫码二维码...")

        # 导航到登录页
        await self.cdp.navigate(f"{API_BASE}/#/login")
        await asyncio.sleep(3)

        # 创建微信二维码 UUID
        import uuid
        client_uuid = str(uuid.uuid4())

        try:
            resp = requests.post(
                f"{OAUTH_BASE}/createQRCode?uuid={client_uuid}",
                headers={"Referer": "https://mooc.ctt.cn/oauth/"},
                timeout=10,
            )
            data = resp.json()
            wx_uuid = data.get("uuid", client_uuid)
        except Exception as e:
            self.log(f"❌ 获取二维码失败: {e}", "error")
            return False

        qr_url = f"{WX_QR_BASE}/{wx_uuid}/v5/online"
        print(f"\n┌──────────────────────────────────────────┐")
        print(f"│  📱 微信扫码登录                           │")
        print(f"└──────────────────────────────────────────┘")
        print(f"🔗 二维码链接: {qr_url}")
        print(f"📱 请使用微信扫描上方链接\n")

        # 轮询扫码状态
        self.log("⏳ 等待扫码... (75秒超时)")
        start = time.time()
        while time.time() - start < 75:
            try:
                resp = requests.post(
                    f"{OAUTH_BASE}/checkUUIDStatus?uuid={wx_uuid}",
                    headers={
                        "Referer": "https://mooc.ctt.cn/oauth/",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    timeout=10,
                )
                data = resp.json()
                if data and data.get("status") is True:
                    self.log("✅ 扫码成功！", "success")
                    # 保存 token
                    if data.get("access_token"):
                        await self.cdp.evaluate(f"""(() => {{
                            localStorage.setItem('token', JSON.stringify({{
                                access_token: "{data['access_token']}",
                                token_type: "Bearer"
                            }}));
                        }})()""")
                    await self.cdp.reload()
                    return True
            except Exception:
                pass
            await asyncio.sleep(3)

        self.log("⏰ 二维码过期", "warn")
        return False

    # ── 数据获取 ──

    async def fetch_all_data(self):
        """获取所有数据"""
        self.log("📡 获取数据...")

        # 并行获取
        courses_task = asyncio.create_task(self.fetch_courses())
        tasks_task = asyncio.create_task(self.fetch_tasks())
        topics_task = asyncio.create_task(self.fetch_topics())
        stats_task = asyncio.create_task(self.fetch_study_stats())

        self.data.courses = await courses_task
        self.data.tasks = await tasks_task
        self.data.topics = await topics_task
        self.data.study_stats = await stats_task

        completed = sum(1 for c in self.data.courses if c.status == "已完成")
        in_progress = sum(1 for c in self.data.courses if c.status == "学习中")
        not_started = sum(1 for c in self.data.courses if c.status == "未开始")

        self.log(f"📊 课程: {len(self.data.courses)}门 (✅{completed} 🔄{in_progress} ⏳{not_started})")
        self.log(f"📋 任务: {len(self.data.tasks)}个")
        self.log(f"📖 专题: {len(self.data.topics)}个")

        stats = self.data.study_stats
        credit = stats.get("creditHour", 0) if stats else 0
        self.log(f"⏱️ 学时: {credit:.1f}h / 50h")

    async def fetch_courses(self) -> list:
        """获取课程列表"""
        courses = []
        for page in range(1, 21):
            data = await self.cdp.fetch_via_js(
                f"{API_BASE}{API['courses']}?businessType=0&findStudy=0&studyTimeOrder=desc&page={page}&pageSize=50",
                headers={
                    "Authorization": f"Bearer__{await self._get_token()}",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            if not data:
                break
            items = data.get("items", [])
            for item in items:
                ci = item.get("courseInfo", {})
                fs = item.get("finishStatus", 0)
                status_map = {0: "未开始", 1: "学习中", 2: "已完成"}
                courses.append(Course(
                    title=ci.get("name", ""),
                    course_id=item.get("courseId", ""),
                    status=status_map.get(fs, "未知"),
                    required="必修" if item.get("isRequired") == 1 else "选修",
                    study_min=round(item.get("studyTotalTime", 0) / 60),
                    total_min=round(ci.get("totalTime", 0) / 60),
                    pct=f"{item.get('studyTotalTime', 0) / ci.get('totalTime', 1) * 100:.1f}%" if ci.get("totalTime") else "0%",
                    url=f"{API_BASE}/#/course/info/{item.get('courseId', '')}",
                ))
            if len(items) < 50:
                break
        return courses

    async def fetch_tasks(self) -> list:
        """获取任务列表"""
        data = await self.cdp.fetch_via_js(
            f"{API_BASE}{API['task_remind']}",
            headers={
                "Authorization": f"Bearer__{await self._get_token()}",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        if not data or not isinstance(data, list):
            return []
        return [Task(
            id=t.get("id", ""),
            title=t.get("taskName", t.get("title", "")),
            status=t.get("statusName", t.get("status", "")),
            deadline=t.get("endTime", ""),
            business_id=t.get("businessId", ""),
            business_type=t.get("businessType", ""),
        ) for t in data]

    async def fetch_topics(self) -> list:
        """获取专题列表"""
        data = await self.cdp.fetch_via_js(
            f"{API_BASE}{API['topics']}?page=1&pageSize=50",
            headers={
                "Authorization": f"Bearer__{await self._get_token()}",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        if not data:
            return []
        items = data.get("items", data.get("records", []))
        return [Topic(
            id=t.get("id", ""),
            title=t.get("name", t.get("title", "")),
            status=t.get("statusName", t.get("status", "")),
            course_count=t.get("courseCount", 0),
            completed_count=t.get("completedCount", 0),
        ) for t in items]

    async def fetch_study_stats(self) -> dict:
        """获取学时统计"""
        data = await self.cdp.fetch_via_js(
            f"{API_BASE}{API['study_stats']}",
            headers={
                "Authorization": f"Bearer__{await self._get_token()}",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        return data or {}

    async def _get_token(self) -> str:
        """获取 auth token"""
        result = await self.cdp.evaluate("""(() => {
            try {
                const raw = localStorage.getItem('token') || '';
                const data = JSON.parse(raw);
                return data.access_token || '';
            } catch { return ''; }
        })()""")
        return result or ""

    # ── 自动学习 ──

    async def auto_tasks(self):
        """刷任务"""
        if self.is_running:
            self.log("⚠️ 已有任务在运行", "warn")
            return
        self.is_running = True
        self.stop_requested = False

        tasks = [t for t in self.data.tasks if t.status != "已完成"]
        self.log(f"📋 开始刷任务 ({len(tasks)}个)...")

        for i, t in enumerate(tasks):
            if self.stop_requested:
                break
            self.log(f"📋 [{i+1}/{len(tasks)}] {t.title}")
            if t.business_id:
                url = f"{API_BASE}/#/course/info/{t.business_id}"
                await self.play_course(url)
            await asyncio.sleep(2)

        self.is_running = False
        self.log("⏹️ 已停止" if self.stop_requested else "✅ 任务完成")

    async def auto_topics(self):
        """刷专题"""
        if self.is_running:
            self.log("⚠️ 已有任务在运行", "warn")
            return
        self.is_running = True
        self.stop_requested = False

        topics = [t for t in self.data.topics if t.status != "已完成"]
        self.log(f"📖 开始刷专题 ({len(topics)}个)...")

        for i, t in enumerate(topics):
            if self.stop_requested:
                break
            self.log(f"📖 [{i+1}/{len(topics)}] {t.title}")
            # 获取专题详情
            detail = await self.cdp.fetch_via_js(
                f"{API_BASE}{API['topic_detail']}?id={t.id}",
                headers={
                    "Authorization": f"Bearer__{await self._get_token()}",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            if detail:
                courses = detail.get("courses", detail.get("items", []))
                for c in courses:
                    if self.stop_requested:
                        break
                    cid = c.get("courseId", c.get("id", ""))
                    self.log(f"  ▶️ {c.get('name', c.get('title', cid))}")
                    await self.play_course(f"{API_BASE}/#/course/info/{cid}")
                    await asyncio.sleep(2)
            await asyncio.sleep(2)

        self.is_running = False
        self.log("⏹️ 已停止" if self.stop_requested else "✅ 专题完成")

    async def auto_courses(self):
        """刷课程"""
        if self.is_running:
            self.log("⚠️ 已有任务在运行", "warn")
            return
        self.is_running = True
        self.stop_requested = False

        courses = [c for c in self.data.courses if c.status != "已完成"]
        self.log(f"🎓 开始刷课程 ({len(courses)}门)...")

        for i, c in enumerate(courses):
            if self.stop_requested:
                break
            self.log(f"🎓 [{i+1}/{len(courses)}] {c.title} ({c.pct})")
            await self.play_course(c.url)
            await asyncio.sleep(3)

        self.is_running = False
        self.log("⏹️ 已停止" if self.stop_requested else "✅ 课程完成")

    async def auto_hours(self, target: float = 50):
        """刷学时"""
        if self.is_running:
            self.log("⚠️ 已有任务在运行", "warn")
            return
        self.is_running = True
        self.stop_requested = False

        self.log(f"⏱️ 开始刷学时 (目标: {target}h)...")

        round_num = 0
        while not self.stop_requested:
            round_num += 1
            stats = await self.fetch_study_stats()
            current = stats.get("creditHour", 0) if stats else 0
            self.log(f"⏱️ 第{round_num}轮 | 当前: {current:.1f}h / {target}h")

            if current >= target:
                self.log("🎉 已达到目标学时！", "success")
                break

            # 刷新课程列表
            self.data.courses = await self.fetch_courses()
            not_done = [c for c in self.data.courses if c.status != "已完成"]
            if not not_done:
                self.log("⚠️ 没有未完成的课程", "warn")
                break

            for c in not_done:
                if self.stop_requested:
                    break
                self.log(f"▶️ {c.title} ({c.pct})")
                await self.play_course(c.url)
                await asyncio.sleep(2)

            await asyncio.sleep(5)

        self.is_running = False
        self.log("⏹️ 已停止" if self.stop_requested else "✅ 学时任务完成")

    async def play_course(self, url: str):
        """播放单个课程"""
        self.log(f"🔗 打开: {url}")
        await self.cdp.navigate(url)
        await asyncio.sleep(5)

        # 查找并播放视频
        found = await self.cdp.evaluate("""(() => {
            const v = document.querySelector('video');
            return !!v;
        })()""")

        if not found:
            self.log("⚠️ 未找到视频", "warn")
            return False

        # 播放
        played = await self.cdp.evaluate("""(() => {
            const v = document.querySelector('video');
            if (!v) return false;
            if (v.paused) {
                v.play().catch(() => {});
                return true;
            }
            return true;
        })()""")

        if not played:
            # 尝试点击播放按钮
            await self.cdp.evaluate("""(() => {
                const btn = document.querySelector('.vjs-big-play-button');
                if (btn) btn.click();
            })()""")
            await asyncio.sleep(2)

        self.log("▶️ 视频开始播放")

        # 设置普清
        await self.cdp.evaluate("""(() => {
            const items = document.querySelectorAll('.vjs-def-box .vjs-menu-item, .vjs-subs-caps-button .vjs-menu-item');
            for (const item of items) {
                if ((item.textContent || '').includes('普清')) {
                    item.click();
                    return;
                }
            }
        })()""")

        # 等待播放完成
        return await self._wait_for_complete()

    async def _wait_for_complete(self, timeout: int = 7200) -> bool:
        """等待视频播放完成"""
        start = time.time()
        last_progress = 0
        stall_count = 0

        while time.time() - start < timeout:
            if self.stop_requested:
                return False

            # 防挂机
            if int(time.time()) % 25 == 0:
                await self.cdp.evaluate("""(() => {
                    document.dispatchEvent(new MouseEvent('mousemove', {
                        clientX: Math.random() * 800 + 100,
                        clientY: Math.random() * 400 + 100,
                        bubbles: true,
                    }));
                })()""")

            status = await self.cdp.evaluate("""(() => {
                const v = document.querySelector('video');
                if (!v) return { found: false };
                return {
                    found: true,
                    currentTime: v.currentTime,
                    duration: v.duration,
                    paused: v.paused,
                    ended: v.ended,
                    progress: v.duration > 0 ? (v.currentTime / v.duration * 100) : 0,
                };
            })()""")

            if not status or not status.get("found"):
                if last_progress > 70:
                    self.log("✅ 视频播放完成（元素消失）", "success")
                    return True
                self.log("⚠️ 视频元素消失", "warn")
                return False

            if status.get("ended"):
                self.log("✅ 视频播放完成", "success")
                return True

            # 恢复暂停
            if status.get("paused") and status.get("currentTime", 0) > 0:
                await self.cdp.evaluate("document.querySelector('video')?.play()")

            progress = status.get("progress", 0)

            # 检测停滞
            if abs(progress - last_progress) < 0.5:
                stall_count += 1
                if stall_count > 60:
                    self.log("⚠️ 视频进度停滞", "warn")
                    await self.cdp.evaluate("document.querySelector('video')?.play()")
                    stall_count = 0
            else:
                stall_count = 0
            last_progress = progress

            # 打印进度
            if int(time.time()) % 30 == 0:
                cur_min = int(status.get("currentTime", 0)) // 60
                dur_min = int(status.get("duration", 0)) // 60
                self.log(f"⏱️ {progress:.1f}% ({cur_min}/{dur_min}分钟)")

            await asyncio.sleep(5)

        self.log("⚠️ 视频播放超时", "warn")
        return False

    # ── 交互 ──

    def print_menu(self):
        """打印菜单"""
        print("\n" + "=" * 50)
        print("📚 烟草网络学院 · CDP 自动学习助手")
        print("=" * 50)
        print("1. 📋 刷任务")
        print("2. 📖 刷专题")
        print("3. 🎓 刷课程")
        print("4. ⏱️  刷学时")
        print("5. 🔄 刷新数据")
        print("6. 📊 查看统计")
        print("0. 退出")
        print("=" * 50)

    def print_stats(self):
        """打印统计"""
        stats = self.data.study_stats
        credit = stats.get("creditHour", 0) if stats else 0
        completed = sum(1 for c in self.data.courses if c.status == "已完成")
        in_progress = sum(1 for c in self.data.courses if c.status == "学习中")
        not_started = sum(1 for c in self.data.courses if c.status == "未开始")
        tasks_pending = sum(1 for t in self.data.tasks if t.status != "已完成")
        topics_pending = sum(1 for t in self.data.topics if t.status != "已完成")

        print(f"\n📊 学习统计:")
        print(f"   ⏱️  学时: {credit:.1f}h / 50h")
        print(f"   🎓 课程: ✅{completed} 🔄{in_progress} ⏳{not_started}")
        print(f"   📋 任务: {tasks_pending}个待完成")
        print(f"   📖 专题: {topics_pending}个待完成")

    async def interactive_loop(self):
        """交互循环"""
        while True:
            self.print_menu()
            try:
                choice = input("\n请选择 (0-6): ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if choice == "0":
                self.stop_requested = True
                break
            elif choice == "1":
                await self.auto_tasks()
            elif choice == "2":
                await self.auto_topics()
            elif choice == "3":
                await self.auto_courses()
            elif choice == "4":
                try:
                    target = float(input("目标学时 (默认50): ").strip() or "50")
                except ValueError:
                    target = 50
                await self.auto_hours(target)
            elif choice == "5":
                await self.fetch_all_data()
            elif choice == "6":
                self.print_stats()
            else:
                print("⚠️ 无效选择")


# ═══════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(description="烟草网络学院 CDP 自动学习助手")
    parser.add_argument("--port", type=int, default=9222, help="Chrome 调试端口 (默认 9222)")
    parser.add_argument("--mode", choices=["tasks", "topics", "courses", "hours", "interactive"],
                        default="interactive", help="运行模式")
    parser.add_argument("--target", type=float, default=50, help="目标学时 (默认 50)")
    args = parser.parse_args()

    print("📚 烟草网络学院 · CDP 自动学习助手")
    print(f"🔌 连接 Chrome (端口: {args.port})...")

    cdp = CDPClient(port=args.port)
    if not await cdp.connect():
        return

    app = CTTCApp(cdp, args)

    try:
        # 检查登录
        if not await app.check_login():
            if not await app.show_qr_login():
                print("❌ 登录失败")
                return

        # 获取数据
        await app.fetch_all_data()

        # 运行模式
        if args.mode == "interactive":
            await app.interactive_loop()
        elif args.mode == "tasks":
            await app.auto_tasks()
        elif args.mode == "topics":
            await app.auto_topics()
        elif args.mode == "courses":
            await app.auto_courses()
        elif args.mode == "hours":
            await app.auto_hours(args.target)

    finally:
        await cdp.disconnect()
        print("\n👋 已断开连接")


if __name__ == "__main__":
    asyncio.run(main())

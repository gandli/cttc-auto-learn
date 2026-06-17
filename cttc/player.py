"""播放模块 - 视频自动播放与进度监控

正常播放模式：不突破限制，不倍速，不刷课
- 通过 DOM 读取 Video.js 控制栏时间
- 通过 API 响应获取精确进度
- 定时触发鼠标事件防止挂机检测
- 自动恢复暂停
"""

import asyncio
import time
from typing import Optional
from playwright.async_api import Page, Response

from cttc.config import Config
from cttc.logger import Logger
from cttc.progress import ProgressManager


class VideoPlayer:
    """视频自动播放与进度监控"""

    # 防挂机鼠标触发间隔（秒），默认 25 分钟
    MOUSE_MOVE_INTERVAL = 25 * 60

    def __init__(self, page: Page, config: Config, log: Logger, progress: ProgressManager, status=None):
        self.page = page
        self.config = config
        self.log = log
        self.progress = progress
        self.status = status  # StatusReporter（可选）

        # API 进度数据（从 video-progress 响应中拦截）
        self._api_progress: Optional[dict] = None
        self._api_progress_time: float = 0
        self._last_progress_error = None

        # 鼠标移动计时
        self._last_mouse_move: float = time.time()

    # ──────────────────────────────────────────
    # 公共方法
    # ──────────────────────────────────────────

    async def setup(self):
        """初始化：设置 API 拦截器"""
        # 先移除旧的 response 监听器
        if hasattr(self.page, '_cttc_response_handler') and self.page._cttc_response_handler:
            try:
                self.page.remove_listener("response", self.page._cttc_response_handler)
            except Exception:
                pass
        # 创建 bound method 一次，用同一个引用注册和存储（关键！）
        handler = self._on_response
        self.page._cttc_response_handler = handler
        self.page.on("response", handler)

    def teardown(self):
        """清理：移除 response 监听器，防止累积"""
        if hasattr(self.page, '_cttc_response_handler') and self.page._cttc_response_handler:
            try:
                self.page.remove_listener("response", self.page._cttc_response_handler)
            except Exception:
                pass
            self.page._cttc_response_handler = None

    async def play_and_wait(self) -> bool:
        """播放视频并等待完成，返回是否成功"""
        # 1. 处理弹窗
        await self._handle_popups()

        # 2. 找到并播放视频
        if not await self._find_and_play():
            self.log.warn("⚠️ 未找到视频或播放按钮")
            return False

        # 3. 设置普清
        await self._set_quality_standard()

        # 4. 等待播放完成（网站原生 JS 自动上报进度，无需干预）
        return await self._wait_for_complete()



    # ──────────────────────────────────────────
    # 视频查找与播放
    # ──────────────────────────────────────────

    async def _find_and_play(self) -> bool:
        """找到视频并开始播放"""
        # 等待视频元素出现（最多 20 秒）
        video_found = False
        for i in range(20):
            has_video = await self.page.evaluate(
                "() => document.querySelectorAll('video').length > 0"
            )
            if has_video:
                video_found = True
                break
            await self.page.wait_for_timeout(1000)

        if not video_found:
            self.log.warn("⚠️ 20秒内未找到 <video> 元素")

        # 策略 1: 直接播放 <video>（需要有 video 元素）
        if video_found:
            played = await self.page.evaluate("""() => {
                const videos = document.querySelectorAll('video');
                for (const v of videos) {
                    if (v.paused && !v.ended) {
                        v.play().catch(() => {});
                        return true;
                    }
                }
                return false;
            }""")
            if played:
                self.log.info("▶️ 视频开始播放")
                # 等待确认视频确实在播放
                await self.page.wait_for_timeout(3000)
                is_playing = await self.page.evaluate("""() => {
                    const v = document.querySelector('video');
                    return v && !v.paused && v.currentTime > 0;
                }""")
                if is_playing:
                    return True
                self.log.warn("⚠️ play() 调用成功但视频未实际播放，尝试按钮方式")

        # 策略 2: 点击播放按钮
        clicked = await self.page.evaluate("""() => {
            // 优先点击 Video.js 大播放按钮
            const bigBtn = document.querySelector('.vjs-big-play-button');
            if (bigBtn && bigBtn.offsetParent !== null) {
                bigBtn.click();
                return 'vjs-big-play-button';
            }
            // 再点击播放控制按钮
            const playCtrl = document.querySelector('.vjs-play-control');
            if (playCtrl && playCtrl.offsetParent !== null) {
                playCtrl.click();
                return 'vjs-play-control';
            }
            // 最后点击视频区域
            const video = document.querySelector('video');
            if (video) { video.click(); return 'video-element'; }
            return null;
        }""")
        if clicked:
            self.log.info(f"▶️ 点击播放按钮 ({clicked})")
            # 等待视频开始播放
            for _ in range(5):
                await self.page.wait_for_timeout(2000)
                is_playing = await self.page.evaluate("""() => {
                    const v = document.querySelector('video');
                    return v && !v.paused && v.currentTime > 0;
                }""")
                if is_playing:
                    self.log.info("✅ 视频确认播放中")
                    return True
                # 再次尝试播放
                await self.page.evaluate("""() => {
                    const v = document.querySelector('video');
                    if (v && v.paused) v.play().catch(() => {});
                }""")
            self.log.warn("⚠️ 点击播放按钮后视频未开始播放")
            return False

        self.log.warn("⚠️ 未找到任何播放控件")
        return False

    async def _set_quality_standard(self):
        """设置画质为普清"""
        try:
            result = await self.page.evaluate("""() => {
                const items = document.querySelectorAll(
                    '.vjs-def-box .vjs-menu-item, .vjs-subs-caps-button .vjs-menu-item'
                );
                for (const item of items) {
                    const t = (item.textContent || '').trim();
                    if (t === '普清' || t.includes('普清')) {
                        const box = item.closest('.vjs-def-box') || item.closest('.vjs-menu');
                        if (box && box.offsetHeight === 0) {
                            const btn = document.querySelector('.vjs-subs-caps-button');
                            if (btn) btn.click();
                        }
                        item.click();
                        return 'ok';
                    }
                }
                return null;
            }""")
            if result:
                self.log.info("🎨 画质: 普清")
            else:
                self.log.info("🎨 画质: 默认")
        except Exception as e:
            self.log.debug(f"设置画质失败: {e}")

    # ──────────────────────────────────────────
    # 进度监控
    # ──────────────────────────────────────────

    async def _on_response(self, response: Response):
        """拦截 video-progress API 响应"""
        if "video-progress" not in response.url or response.request.method != "POST":
            return
        try:
            body = await response.json()

            # 检查错误响应（Internal Error, errorCode 等）
            error_code = body.get("errorCode")
            message = body.get("message", "")
            if error_code or message == "Internal Error":
                # Invalid input 是网站原生 JS 偶尔被拒，无害，降级为 DEBUG
                if "Invalid input" in (message or ""):
                    self.log.debug(f"📤 进度提交被拒（无害）: {message}")
                else:
                    self.log.warn(f"⚠️ 进度提交失败: {message or f'errorCode={error_code}'}")
                self._last_progress_error = error_code or message
                return  # 不存储错误响应为进度数据

            self._api_progress = body
            self._api_progress_time = time.time()
            self._last_progress_error = None
            loc = body.get("lessonLocation", 0)
            study_time = body.get("studyTotalTime", body.get("studyTime", 0))
            remaining = body.get("remainingTime", 0)
            finish = body.get("finishStatus", 0)
            completed = body.get("completedRate", 0)
            self.log.info(f"📤 进度: loc={loc}s, study_total={study_time}s, remain={remaining}s, completed={completed}%, finish={finish}")
            if self.status:
                self.status.update_api_progress(loc, study_time, remaining, completed, finish)
        except Exception:
            pass

    def _get_progress_from_video(self) -> Optional[dict]:
        """同步方法：从已缓存的 API 响应获取进度"""
        if self._api_progress and time.time() - self._api_progress_time < 30:
            return self._api_progress
        return None

    async def _wait_for_api_completion(self, timeout: int = 120) -> bool:
        """等待 API 确认视频完成（finishStatus=2）

        视频元素在 ~90% 时被网站移除，但剩余进度仍由 JS 提交。
        完成标志：finishStatus=2 或 completedRate=100 或 remainingTime=None

        Returns:
            True 如果 API 确认完成，False 如果超时
        """
        start = time.time()
        while time.time() - start < timeout:
            if self._api_progress and time.time() - self._api_progress_time < 15:
                finish = self._api_progress.get("finishStatus", 0)
                completed = self._api_progress.get("completedRate", 0)
                remaining = self._api_progress.get("remainingTime")

                if finish == 2:
                    return True
                if completed and completed >= 100:
                    return True
                if remaining is None and self._api_progress.get("lessonLocation", 0) > 0:
                    # remaining=None 且有进度 = 完成
                    return True

                self.log.debug(f"📊 等待完成: finish={finish}, completed={completed}%, remain={remaining}")

            await self.page.wait_for_timeout(5000)

        if self._api_progress:
            finish = self._api_progress.get("finishStatus", 0)
            completed = self._api_progress.get("completedRate", 0)
            self.log.warn(f"⚠️ 等待 API 确认超时: finish={finish}, completed={completed}%")
        return False

    async def _read_video_status(self) -> dict:
        """读取当前视频状态（DOM + API）"""
        # 优先从 DOM 读取 Video.js 控制栏
        dom_status = await self.page.evaluate("""() => {
            // 策略 1: <video> 元素
            const v = document.querySelector('video');
            if (v && v.duration > 0) {
                return {
                    found: true,
                    currentTime: v.currentTime,
                    duration: v.duration,
                    paused: v.paused,
                    ended: v.ended,
                    progress: (v.currentTime / v.duration * 100),
                    source: 'video'
                };
            }

            // 策略 2: Video.js 控制栏
            const curEl = document.querySelector('.vjs-current-time-display');
            const durEl = document.querySelector('.vjs-duration-display');
            if (curEl && durEl) {
                const parse = (s) => {
                    const m = s.match(/(\\d+):(\\d+)(?::(\\d+))?/);
                    if (!m) return 0;
                    return m[3] ? +m[1]*3600 + +m[2]*60 + +m[3] : +m[1]*60 + +m[2];
                };
                const cur = parse(curEl.textContent.trim());
                const dur = parse(durEl.textContent.trim());
                if (dur > 0) {
                    return {
                        found: true,
                        currentTime: cur,
                        duration: dur,
                        paused: false,
                        ended: false,
                        progress: (cur / dur * 100),
                        source: 'vjs'
                    };
                }
            }

            return {found: false};
        }""")

        # 如果 DOM 读取成功，直接返回
        if dom_status.get("found"):
            return dom_status

        # 回退：从 API 响应读取
        api = self._get_progress_from_video()
        if api:
            loc = int(api.get("lessonLocation", 0))
            total_time = loc + int(api.get("remainingTime", 0))
            if total_time > 0:
                return {
                    "found": True,
                    "currentTime": loc,
                    "duration": total_time,
                    "paused": False,
                    "ended": api.get("finishStatus") == 2,
                    "progress": loc / total_time * 100,
                    "source": "api",
                }

        return {"found": False}

    async def _wait_for_complete(self, timeout: int = 7200) -> bool:
        """等待视频播放完成

        Args:
            timeout: 最大等待秒数（默认 2 小时）
        """
        start = time.time()
        last_progress = 0
        stall_count = 0
        not_found_count = 0
        tick_count = 0

        while time.time() - start < timeout:
            # 防挂机：定时触发鼠标移动
            await self._maybe_move_mouse()
            # 每 5 分钟处理一次弹窗
            if tick_count > 0 and tick_count % 30 == 0:
                await self._handle_popups()

            try:
                status = await self._read_video_status()
            except Exception as e:
                if "Target closed" in str(e) or "Target crashed" in str(e):
                    self.log.warn("⚠️ 页面崩溃")
                    return False
                raise

            if not status.get("found"):
                not_found_count += 1
                # 进度 > 70% 时视频可能被网站移除（正常现象），等待 API 确认完成
                if last_progress > 70:
                    confirmed = await self._wait_for_api_completion(timeout=120)
                    if confirmed:
                        self.log.info(f"✅ 视频播放完成（API 确认 finishStatus=2）")
                    else:
                        self.log.info(f"✅ 视频播放完成（进度 {last_progress:.1f}% 后元素消失）")
                    return True
                if not_found_count > 10:
                    # 尝试恢复：点击页面触发视频重新加载
                    self.log.info(f"🔄 视频消失（进度 {last_progress:.1f}%），尝试恢复...")
                    recovered = await self._try_recover_video()
                    if recovered:
                        not_found_count = 0
                        continue
                    self.log.warn("⚠️ 恢复失败，放弃此视频")
                    return False
                await self.page.wait_for_timeout(3000)
                continue
            not_found_count = 0

            # 视频已结束
            if status.get("ended"):
                self.log.info("✅ 视频播放完成")
                return True

            # 检查进度提交错误（40909 = 多客户端冲突）
            if self._last_progress_error == 40909:
                self.log.error("❌ 检测到多客户端冲突(40909)，停止播放")
                return False

            progress = status.get("progress", 0)
            source = status.get("source", "?")

            # 检测进度停滞
            # 优先用 API 进度判断（更精确），DOM 进度取整会导致假停滞
            api_progress = None
            if self._api_progress and time.time() - self._api_progress_time < 60:
                api_loc = int(self._api_progress.get("lessonLocation", 0))
                api_remain = self._api_progress.get("remainingTime", 0) or 0
                api_total = api_loc + int(api_remain)
                if api_total > 0:
                    api_progress = api_loc / api_total * 100

            effective_progress = api_progress if api_progress is not None else progress
            if abs(effective_progress - last_progress) < 0.5:
                stall_count += 1
                if stall_count > 50:  # 50 * 10s = 500s 无变化才判定停滞
                    self.log.warn("⚠️ 视频进度停滞，尝试修复...")
                    if self.status:
                        self.status.set_status("stalled")
                    await self._repair_stalled()
                    stall_count = 0
            else:
                stall_count = 0
            last_progress = effective_progress

            # 自动恢复暂停
            if status.get("paused") and status.get("currentTime", 0) > 0:
                self.log.info("▶️ 视频暂停，自动恢复...")
                try:
                    await self.page.evaluate("document.querySelector('video')?.play()")
                except Exception:
                    pass

            # 每 30 秒打印进度
            tick_count += 1
            if tick_count % 3 == 0:
                cur_min = int(status.get("currentTime", 0)) // 60
                dur_min = int(status.get("duration", 0)) // 60
                self.log.info(f"⏱️ 进度: {progress:.1f}% ({cur_min}/{dur_min}分钟) [{source}]")
                if self.status:
                    self.status.update_video_progress(
                        status.get("currentTime", 0), status.get("duration", 0)
                    )

            await self.page.wait_for_timeout(10000)

        self.log.warn("⚠️ 视频播放超时")
        return False

    # ──────────────────────────────────────────
    # 防挂机
    # ──────────────────────────────────────────

    async def _maybe_move_mouse(self):
        """定时触发鼠标移动，防止挂机检测"""
        now = time.time()
        if now - self._last_mouse_move < self.MOUSE_MOVE_INTERVAL:
            return

        try:
            await self.page.evaluate("""() => {
                document.dispatchEvent(new MouseEvent('mousemove', {
                    clientX: Math.floor(Math.random() * 800 + 100),
                    clientY: Math.floor(Math.random() * 400 + 100),
                    bubbles: true
                }));
            }""")
            self._last_mouse_move = now
            self.log.debug("🖱️ 触发鼠标移动（防挂机）")
        except Exception:
            pass

    # ──────────────────────────────────────────
    # 弹窗处理
    # ──────────────────────────────────────────

    async def _handle_popups(self):
        """处理弹窗（排除视频播放器区域）"""
        try:
            result = await self.page.evaluate("""() => {
                let clicked = [];
                const inPlayer = (el) => el.closest('.video-js') || el.closest('.vjs-text-track-display') || el.closest('[class*="player"]');
                const isVisible = (el) => {
                    const s = window.getComputedStyle(el);
                    return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0' && el.offsetParent !== null;
                };

                // 关闭按钮（排除播放器内的）
                document.querySelectorAll(
                    '[class*="close"], [class*="Close"], [aria-label="close"]'
                ).forEach(el => {
                    if (inPlayer(el)) return;
                    if (!isVisible(el)) return;
                    const tag = el.tagName;
                    const cls = el.className || '';
                    const txt = (el.textContent || '').trim().slice(0, 30);
                    // 跳过输入框、表单元素
                    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
                    clicked.push(`${tag}[class*="close"] class="${cls}" text="${txt}"`);
                    el.click();
                });
                // 确认按钮
                document.querySelectorAll(
                    '[class*="confirm"], [class*="Confirm"]'
                ).forEach(el => {
                    if (inPlayer(el)) return;
                    if (!isVisible(el)) return;
                    const t = (el.textContent || '').trim();
                    if (t.includes('确定') || t.includes('确认')) {
                        clicked.push(`confirm: "${t}"`);
                        el.click();
                    }
                });
                // 知道了按钮
                document.querySelectorAll('button, [role="button"]').forEach(el => {
                    if (inPlayer(el)) return;
                    if (!isVisible(el)) return;
                    const t = (el.textContent || '').trim();
                    if (t.includes('我知道了') || t.includes('知道了')) {
                        clicked.push(`button: "${t}"`);
                        el.click();
                    }
                });
                return clicked;
            }""")
            if result:
                self.log.info(f"🔔 处理了 {len(result)} 个弹窗: {result}")
        except Exception:
            pass

    # ──────────────────────────────────────────
    # 修复
    # ──────────────────────────────────────────

    async def _repair_stalled(self):
        """修复停滞的视频（先检查暂停状态，不轻易刷新页面）"""
        self.log.info("🔧 尝试修复停滞视频...")
        try:
            # 先检查是否只是暂停了
            is_paused = await self.page.evaluate(
                "() => { const v = document.querySelector('video'); return v ? v.paused : null; }"
            )
            if is_paused is True:
                await self.page.evaluate("document.querySelector('video')?.play()")
                self.log.info("🔧 视频只是暂停了，已恢复播放")
                if self.status:
                    self.status.record_stall_repair()
                return
            if is_paused is None:
                self.log.info("🔧 视频元素不存在，刷新页面...")
            else:
                self.log.info("🔧 视频确实在播放但进度不动，刷新页面...")
            if self.status:
                self.status.record_stall_repair()
            await self.page.reload(
                wait_until="domcontentloaded",
                timeout=self.config.page_timeout
            )
            await self.page.wait_for_timeout(3000)
            await self._find_and_play()
            await self._set_quality_standard()
        except Exception as e:
            self.log.warn(f"⚠️ 修复失败: {e}")

    async def _try_recover_video(self) -> bool:
        """尝试恢复消失的视频（刷新页面重新加载播放器）"""
        try:
            # 刷新页面
            await self.page.reload(
                wait_until="domcontentloaded",
                timeout=self.config.page_timeout
            )
            await self.page.wait_for_timeout(5000)

            # 处理弹窗
            await self._handle_popups()

            # 找到并播放视频
            if not await self._find_and_play():
                return False

            # 设置普清
            await self._set_quality_standard()

            self.log.info("✅ 视频已恢复")
            return True
        except Exception as e:
            self.log.warn(f"⚠️ 恢复失败: {e}")
            return False

"""监控模块 - 学时统计监控与自动修复"""

import asyncio
from typing import Optional
from playwright.async_api import Page

from cttc.config import Config
from cttc.logger import Logger
from cttc.progress import ProgressManager


class StudyMonitor:
    """学时监控与自动修复"""

    def __init__(self, page: Page, config: Config, log: Logger, progress: ProgressManager):
        self.page = page
        self.config = config
        self.log = log
        self.progress = progress
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._api_study_hours: float = 0
        self._video_playing = False  # 视频是否正在播放

    def setup_api_interceptor(self):
        """设置 API 拦截器，从学时统计接口获取精确数据"""
        async def on_response(response):
            url = response.url
            if 'credit/detail-hour-member' in url or 'cadre-education/detail-hour-member' in url:
                try:
                    data = await response.json()
                    if 'courseHourResult' in data:
                        self._api_study_hours = data.get("courseHourResult", {}).get("totalHour", 0)
                    elif 'hourSelf' in data:
                        self._api_study_hours = data.get("hourSelf", 0)
                except:
                    pass
        self.page.on("response", on_response)

    async def start(self):
        """启动后台监控"""
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        self.log.info("📊 学时监控已启动")

    async def stop(self):
        """停止监控"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                await asyncio.sleep(self.config.study_check_interval)

                hours = await self._read_study_time()
                if hours > 0:
                    delta = self.progress.record_study_time(hours)
                    if delta > 0:
                        self.log.info(f"📈 学时增长: +{delta}h (总计 {hours}h)")
                    elif self._video_playing:
                        pass  # 视频播放中，静默跳过
                    elif self.progress.get_stale_seconds() > self.config.study_stale_threshold:
                        stale_min = int(self.progress.get_stale_seconds()) // 60
                        self.log.info(f"📊 学时停滞 {stale_min}分钟，等待课程结束时检查")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.error(f"监控异常: {e}")
                await asyncio.sleep(10)

    async def _read_study_time(self) -> float:
        """读取页面上的学时（支持多种格式）"""
        # 优先从 API 拦截器获取
        if hasattr(self, '_api_study_hours') and self._api_study_hours > 0:
            return self._api_study_hours

        return await self.page.evaluate("""() => {
            const text = document.body?.innerText || '';
            // 格式1: "网络自学 28.1/50 小时"
            const m1 = text.match(/网络自学[\\s:]*(\\d+\\.?\\d*)\\s*\\/\\s*(\\d+\\.?\\d*)/);
            if (m1) return parseFloat(m1[1]);
            // 格式2: "网络学习时长：28.1"
            const m2 = text.match(/网络学习时长[\\s:：]*(\\d+\\.?\\d*)/);
            if (m2) return parseFloat(m2[1]);
            // 格式3: "28.1 小时" 附近有"自学"
            const m3 = text.match(/自学[\\s\\S]{0,20}?(\\d+\\.?\\d*)\\s*小时/);
            if (m3) return parseFloat(m3[1]);
            return 0;
        }""")

    async def _repair(self):
        """学时停滞修复"""
        self.log.info("🔧 执行学时修复...")
        try:
            await self.page.reload(wait_until="domcontentloaded", timeout=self.config.page_timeout)
            await self.page.wait_for_timeout(3000)
        except Exception as e:
            self.log.error(f"修复失败: {e}")

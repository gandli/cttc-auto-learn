"""配置模块"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    # ── 基本设置 ──
    base_url: str = "https://mooc.ctt.cn"
    headless: bool = False
    viewport_width: int = 1280
    viewport_height: int = 800
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0"

    # ── 目标设置 ──
    target_hours: float = 50.0  # 目标学时（None=不限）

    # ── 二维码设置 ──
    qr_refresh_cooldown: int = 15
    show_qr_terminal: bool = True

    # ── 检测间隔 ──
    check_interval: int = 1
    study_check_interval: int = 60

    # ── 超时设置 ──
    page_timeout: int = 30000
    login_wait: int = 2000
    short_wait: int = 2000
    medium_wait: int = 3000
    long_wait: int = 5000

    # ── 学时监控 ──
    study_stale_threshold: int = 300
    max_retry: int = 3
    refresh_interval: int = 1800  # 30 分钟

    # ── 课程类型 ──
    section_type: str = "13"  # 课程类型 ID

    # ── URL 模板 ──
    @property
    def learning_center_url(self) -> str:
        return f"{self.base_url}/#/center/index"

    def course_detail_url(self, course_id: str) -> str:
        return f"{self.base_url}/#/study/course/detail/{self.section_type}&{course_id}"

    def topic_detail_url(self, topic_id: str) -> str:
        return f"{self.base_url}/#/study/subject/detail/{topic_id}"

    # ── 路径（自动填充） ──
    output_dir: str = ""
    screenshot_dir: str = ""
    progress_file: str = ""
    courses_file: str = ""
    study_time_file: str = ""
    log_file: str = ""

    def __post_init__(self):
        base = Path.cwd()
        if not self.output_dir:
            self.output_dir = str(base / "output")
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        if not self.screenshot_dir:
            self.screenshot_dir = str(Path(self.output_dir) / "screenshots")
        Path(self.screenshot_dir).mkdir(parents=True, exist_ok=True)

        data_dir = base / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        logs_dir = base / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        if not self.progress_file:
            self.progress_file = str(data_dir / "progress.json")
        if not self.courses_file:
            self.courses_file = str(data_dir / "courses.json")
        if not self.study_time_file:
            self.study_time_file = str(data_dir / "study_time.json")
        if not self.log_file:
            self.log_file = str(logs_dir / "cttc.log")

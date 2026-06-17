"""状态报告器 — 实时写入 output/status.json 供外部监控"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


class StatusReporter:
    """实时状态报告器

    定期将运行状态写入 output/status.json，供外部脚本或人工监控。
    """

    def __init__(self, output_dir: str = "output"):
        self._status_file = Path(output_dir) / "status.json"
        self._start_time = time.time()
        self._state = {
            "status": "initializing",
            "started_at": datetime.now().isoformat(),
            "uptime_seconds": 0,
            "current_video": None,
            "video_progress": 0,
            "video_duration": 0,
            "video_current_time": 0,
            "api_completed_rate": 0,
            "api_finish_status": 0,
            "api_lesson_location": 0,
            "api_remaining_time": 0,
            "study_hours_current": 0,
            "study_hours_target": 0,
            "courses_completed": 0,
            "courses_total": 0,
            "courses_pending": 0,
            "last_api_time": None,
            "last_error": None,
            "last_error_time": None,
            "errors_count": 0,
            "stall_repairs": 0,
        }

    def set_status(self, status: str):
        self._state["status"] = status
        self._flush()

    def set_video(self, title: str, url: str = ""):
        self._state["current_video"] = title[:80]
        self._state["current_video_url"] = url
        self._flush()

    def update_video_progress(self, current_time: float, duration: float):
        self._state["video_current_time"] = round(current_time, 1)
        self._state["video_duration"] = round(duration, 1)
        self._state["video_progress"] = round(current_time / duration * 100, 1) if duration > 0 else 0
        self._flush()

    def update_api_progress(self, lesson_location, study_total, remaining, completed, finish_status):
        self._state["api_lesson_location"] = lesson_location
        self._state["api_remaining_time"] = remaining
        self._state["api_completed_rate"] = completed
        self._state["api_finish_status"] = finish_status
        self._state["last_api_time"] = datetime.now().isoformat()
        self._flush()

    def set_study_hours(self, current: float, target: float):
        self._state["study_hours_current"] = current
        self._state["study_hours_target"] = target
        self._flush()

    def set_courses(self, completed: int, total: int, pending: int):
        self._state["courses_completed"] = completed
        self._state["courses_total"] = total
        self._state["courses_pending"] = pending
        self._flush()

    def record_error(self, error: str):
        self._state["last_error"] = error[:200]
        self._state["last_error_time"] = datetime.now().isoformat()
        self._state["errors_count"] += 1
        self._flush()

    def record_stall_repair(self):
        self._state["stall_repairs"] += 1
        self._flush()

    def video_completed(self):
        self._state["courses_completed"] += 1
        self._state["courses_pending"] = max(0, self._state["courses_pending"] - 1)
        self._flush()

    def _flush(self):
        self._state["uptime_seconds"] = int(time.time() - self._start_time)
        self._state["updated_at"] = datetime.now().isoformat()
        try:
            self._status_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._status_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._status_file)
        except Exception:
            pass

    @staticmethod
    def read_status(path: str = "output/status.json") -> Optional[dict]:
        """读取当前状态（静态方法，供外部脚本调用）"""
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            return None

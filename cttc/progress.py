"""持久化模块 - 学习进度与学时记录"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from cttc.config import Config
from cttc.logger import Logger


class ProgressManager:
    """管理学习进度的持久化"""

    def __init__(self, config: Config, log: Logger):
        self.config = config
        self.log = log
        self.progress = self._load_json(config.progress_file, {"courses": {}, "last_updated": None})
        self.study_time = self._load_json(config.study_time_file, {
            "records": [], "current_total": 0.0,
            "last_increase": None, "stale_since": None
        })

    # ── JSON 读写 ──

    def _load_json(self, path: str, default: dict) -> dict:
        p = Path(path)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return default

    def _save_json(self, path: str, data: dict):
        """原子写入：先写临时文件再重命名"""
        tmp = Path(path + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    # ── 课程进度 ──

    def save_progress(self):
        self.progress["last_updated"] = datetime.now().isoformat()
        self._save_json(self.config.progress_file, self.progress)

    def get_course(self, course_id: str) -> dict:
        return self.progress.get("courses", {}).get(course_id, {})

    def update_course(self, course_id: str, data: dict):
        if "courses" not in self.progress:
            self.progress["courses"] = {}
        if course_id not in self.progress["courses"]:
            self.progress["courses"][course_id] = {}
        self.progress["courses"][course_id].update(data)
        self.progress["courses"][course_id]["last_study"] = datetime.now().isoformat()
        self.save_progress()

    def is_course_completed(self, course_id: str) -> bool:
        return self.get_course(course_id).get("status") == "completed"

    # ── 学时记录 ──

    def save_study_time(self):
        self._save_json(self.config.study_time_file, self.study_time)

    def record_study_time(self, hours: float) -> float:
        """记录学时，返回增量"""
        prev = self.study_time.get("current_total", 0.0)
        delta = round(hours - prev, 2)

        self.study_time["records"].append({
            "timestamp": datetime.now().isoformat(),
            "total_hours": hours,
            "delta": delta
        })
        self.study_time["current_total"] = hours

        if delta > 0:
            self.study_time["last_increase"] = datetime.now().isoformat()
            self.study_time["stale_since"] = None

        self.save_study_time()
        return delta

    def get_stale_seconds(self) -> float:
        """学时停滞时长（秒）"""
        last = self.study_time.get("last_increase")
        if not last:
            return 0
        return (datetime.now() - datetime.fromisoformat(last)).total_seconds()

    def reset_stale(self):
        """重置停滞计时（视频开始播放时调用）"""
        self.study_time["stale_since"] = None
        self.study_time["last_increase"] = datetime.now().isoformat()
        self.save_study_time()

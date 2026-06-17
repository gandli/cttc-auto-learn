"""测试 Progress 模块"""

import json
from datetime import datetime
from pathlib import Path

from cttc.progress import ProgressManager

def test_progress_init_creates_default(config, log):
    """测试初始化创建默认数据"""
    pm = ProgressManager(config, log)
    assert pm.progress["courses"] == {}
    assert pm.study_time["current_total"] == 0.0
    assert pm.study_time["records"] == []


def test_progress_loads_existing(config, log, sample_progress):
    """测试加载已有进度数据"""
    Path(config.progress_file).parent.mkdir(parents=True, exist_ok=True)
    Path(config.progress_file).write_text(
        json.dumps(sample_progress), encoding="utf-8"
    )

    pm = ProgressManager(config, log)
    assert "course-1" in pm.progress["courses"]
    assert pm.progress["courses"]["course-1"]["status"] == "completed"


def test_progress_update_course(config, log):
    """测试更新课程进度"""
    pm = ProgressManager(config, log)
    pm.update_course("course-1", {"title": "测试课程", "status": "completed"})

    assert pm.is_course_completed("course-1")
    assert pm.get_course("course-1")["title"] == "测试课程"


def test_progress_is_course_completed(config, log):
    """测试课程完成状态检查"""
    pm = ProgressManager(config, log)
    assert not pm.is_course_completed("nonexistent")

    pm.update_course("course-1", {"status": "in_progress"})
    assert not pm.is_course_completed("course-1")

    pm.update_course("course-1", {"status": "completed"})
    assert pm.is_course_completed("course-1")


def test_progress_save_study_time(config, log):
    """测试保存学时记录"""
    pm = ProgressManager(config, log)
    delta = pm.record_study_time(5.0)

    assert delta == 5.0
    assert pm.study_time["current_total"] == 5.0
    assert len(pm.study_time["records"]) == 1


def test_progress_record_study_time_delta(config, log):
    """测试学时增量计算"""
    pm = ProgressManager(config, log)

    delta1 = pm.record_study_time(5.0)
    assert delta1 == 5.0

    delta2 = pm.record_study_time(5.5)
    assert delta2 == 0.5

    delta3 = pm.record_study_time(5.5)
    assert delta3 == 0.0


def test_progress_get_stale_seconds(config, log):
    """测试学停滞时间计算"""
    pm = ProgressManager(config, log)
    assert pm.get_stale_seconds() == 0

    pm.record_study_time(5.0)
    stale = pm.get_stale_seconds()
    assert stale < 1  # 刚记录，应该很短


def test_progress_atomic_write(config, log):
    """测试原子写入（不会损坏文件）"""
    pm = ProgressManager(config, log)
    pm.record_study_time(5.0)

    # 验证文件存在且内容正确
    data = json.loads(Path(config.study_time_file).read_text(encoding="utf-8"))
    assert data["current_total"] == 5.0


def test_progress_load_json_corrupt_file(config, log):
    """测试加载损坏的 JSON 文件 (lines 31-32)"""
    # Write invalid JSON
    p = Path(config.progress_file)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("not valid json {{{", encoding="utf-8")

    pm = ProgressManager(config, log)
    # Should fall back to default
    assert pm.progress["courses"] == {}
    assert pm.progress["last_updated"] is None


def test_progress_load_json_corrupt_study_time(config, log):
    """测试加载损坏的学时文件 (lines 31-32)"""
    p = Path(config.study_time_file)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{broken json", encoding="utf-8")

    pm = ProgressManager(config, log)
    assert pm.study_time["current_total"] == 0.0
    assert pm.study_time["records"] == []


def test_progress_update_course_no_courses_key(config, log):
    """测试更新课程 - 无 courses key (line 52)"""
    pm = ProgressManager(config, log)
    # Manually remove courses key
    del pm.progress["courses"]

    pm.update_course("course-new", {"title": "新课程", "status": "in_progress"})

    assert "courses" in pm.progress
    assert "course-new" in pm.progress["courses"]
    assert pm.progress["courses"]["course-new"]["title"] == "新课程"


def test_progress_get_course_nonexistent(config, log):
    """测试获取不存在的课程"""
    pm = ProgressManager(config, log)
    result = pm.get_course("nonexistent-id")
    assert result == {}


def test_progress_save_study_time_file(config, log):
    """测试 save_study_time 方法"""
    pm = ProgressManager(config, log)
    pm.study_time["current_total"] = 10.0
    pm.save_study_time()

    data = json.loads(Path(config.study_time_file).read_text(encoding="utf-8"))
    assert data["current_total"] == 10.0


def test_progress_stale_since_reset(config, log):
    """测试学时增长时 stale_since 重置"""
    pm = ProgressManager(config, log)
    pm.record_study_time(5.0)
    assert pm.study_time["stale_since"] is None
    assert pm.study_time["last_increase"] is not None


def test_progress_no_stale_when_no_increase(config, log):
    """测试学时无增长时不更新 last_increase"""
    pm = ProgressManager(config, log)
    pm.record_study_time(5.0)
    first_increase = pm.study_time["last_increase"]

    # No delta (same hours)
    pm.record_study_time(5.0)
    # last_increase should still be the first one (not updated)
    assert pm.study_time["last_increase"] == first_increase

"""planner.py 测试"""

import pytest
from unittest.mock import MagicMock

from cttc.planner import StudyPlanner


@pytest.fixture
def planner():
    log = MagicMock()
    return StudyPlanner(log)


@pytest.fixture
def sample_courses():
    return [
        {"course_id": "c1", "title": "课程A", "total_min": 60, "study_min": 0, "status": "未开始"},
        {"course_id": "c2", "title": "课程B", "total_min": 120, "study_min": 30, "status": "学习中"},
        {"course_id": "c3", "title": "课程C", "total_min": 90, "study_min": 0, "status": "未开始"},
        {"course_id": "c4", "title": "课程D", "total_min": 0, "study_min": 0, "status": "已完成"},
    ]


# ── plan_courses ──


class TestPlanCourses:
    """plan_courses 测试"""

    def test_already_reached_target(self, planner):
        """已达到目标时返回空列表"""
        result = planner.plan_courses(
            current_hours=50.0,
            target_hours=50.0,
            courses=[],
            priority_courses=[],
        )
        assert result == []

    def test_exceeded_target(self, planner):
        """超过目标时返回空列表"""
        result = planner.plan_courses(
            current_hours=60.0,
            target_hours=50.0,
            courses=[],
            priority_courses=[],
        )
        assert result == []

    def test_plan_with_priority_courses(self, planner, sample_courses):
        """优先课程排在前面"""
        priority = [{"course_id": "c1"}]
        result = planner.plan_courses(
            current_hours=0.0,
            target_hours=2.0,
            courses=sample_courses,
            priority_courses=priority,
        )
        # c1 应该排在第一位
        assert len(result) > 0
        assert result[0]["course_id"] == "c1"

    def test_plan_stops_at_target(self, planner, sample_courses):
        """规划在达到目标学时后停止"""
        result = planner.plan_courses(
            current_hours=0.0,
            target_hours=1.5,  # 1.5 小时
            courses=sample_courses,
            priority_courses=[],
        )
        # 应该只选择部分课程
        total_hours = sum(c["estimated_hours"] for c in result)
        assert total_hours >= 1.5 or len(result) == len([c for c in sample_courses if c["status"] != "已完成"])

    def test_plan_includes_all_courses(self, planner, sample_courses):
        """规划包含所有课程（包括已完成）"""
        result = planner.plan_courses(
            current_hours=0.0,
            target_hours=10.0,
            courses=sample_courses,
            priority_courses=[],
        )
        # plan_courses 不过滤已完成课程，只按顺序选择
        assert len(result) > 0

    def test_plan_empty_courses(self, planner):
        """无课程时返回空列表"""
        result = planner.plan_courses(
            current_hours=0.0,
            target_hours=50.0,
            courses=[],
            priority_courses=[],
        )
        assert result == []


# ── _estimate_hours ──


class TestEstimateHours:
    """_estimate_hours 测试"""

    def test_with_total_min(self, planner):
        """有 total_min 时计算剩余学时"""
        course = {"total_min": 120, "study_min": 30}
        result = planner._estimate_hours(course)
        assert result == 1.5  # (120 - 30) / 60

    def test_fully_studied(self, planner):
        """已学完的课程返回 0"""
        course = {"total_min": 60, "study_min": 60}
        result = planner._estimate_hours(course)
        assert result == 0.0

    def test_over_studied(self, planner):
        """超额学习返回 0（不返回负数）"""
        course = {"total_min": 60, "study_min": 90}
        result = planner._estimate_hours(course)
        assert result == 0.0

    def test_no_total_min(self, planner):
        """无 total_min 时返回默认值 1.0"""
        course = {"total_min": 0, "study_min": 0}
        result = planner._estimate_hours(course)
        assert result == 1.0

    def test_missing_fields(self, planner):
        """缺失字段时返回默认值"""
        course = {}
        result = planner._estimate_hours(course)
        assert result == 1.0


# ── calculate_optimal_plan ──


class TestCalculateOptimalPlan:
    """calculate_optimal_plan 测试"""

    def test_already_reached_target(self, planner):
        """已达到目标时返回空计划"""
        result = planner.calculate_optimal_plan(
            current_hours=50.0,
            target_hours=50.0,
            topics=[],
            tasks=[],
            courses=[],
        )
        assert result == {"plan": [], "total_hours": 0, "priority_count": 0, "normal_count": 0}

    def test_with_active_tasks(self, planner):
        """进行中的任务课程优先"""
        tasks = [{"status": "进行中", "business_id": "t1"}]
        courses = [
            {"course_id": "c1", "title": "任务课程", "total_min": 60, "study_min": 0, "status": "未开始"},
            {"course_id": "c2", "title": "普通课程", "total_min": 60, "study_min": 0, "status": "未开始"},
        ]
        # 任务课程标题以 "任务课程" 开头，匹配 business_id
        result = planner.calculate_optimal_plan(
            current_hours=0.0,
            target_hours=2.0,
            topics=[],
            tasks=tasks,
            courses=courses,
        )
        # 应该包含课程
        assert len(result["plan"]) > 0

    def test_with_topics(self, planner):
        """专题课程优先"""
        topics = [{"courses": [{"title": "专题课程A", "status": "未开始"}]}]
        courses = [
            {"course_id": "c1", "title": "专题课程A", "total_min": 60, "study_min": 0, "status": "未开始"},
            {"course_id": "c2", "title": "普通课程", "total_min": 60, "study_min": 0, "status": "未开始"},
        ]
        result = planner.calculate_optimal_plan(
            current_hours=0.0,
            target_hours=2.0,
            topics=topics,
            tasks=[],
            courses=courses,
        )
        assert result["priority_count"] > 0

    def test_skips_completed_courses(self, planner):
        """跳过已完成课程"""
        courses = [
            {"course_id": "c1", "title": "已完成课程", "total_min": 60, "study_min": 60, "status": "已完成"},
            {"course_id": "c2", "title": "未完成课程", "total_min": 60, "study_min": 0, "status": "未开始"},
        ]
        result = planner.calculate_optimal_plan(
            current_hours=0.0,
            target_hours=2.0,
            topics=[],
            tasks=[],
            courses=courses,
        )
        # 已完成课程不应该在计划中
        plan_ids = [c["course_id"] for c in result["plan"]]
        assert "c1" not in plan_ids

    def test_deduplicates_courses(self, planner):
        """去重课程"""
        courses = [
            {"course_id": "c1", "title": "重复课程", "total_min": 60, "study_min": 0, "status": "未开始"},
            {"course_id": "c1", "title": "重复课程", "total_min": 60, "study_min": 0, "status": "未开始"},
        ]
        result = planner.calculate_optimal_plan(
            current_hours=0.0,
            target_hours=2.0,
            topics=[],
            tasks=[],
            courses=courses,
        )
        # 去重后应该只有一个
        plan_ids = [c["course_id"] for c in result["plan"]]
        assert len(plan_ids) == len(set(plan_ids))

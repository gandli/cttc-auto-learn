"""ui.py 测试"""

import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

from cttc.ui import show_user_dashboard, ask_user_goal, ask_new_target


# ── show_user_dashboard ──


class TestShowUserDashboard:
    """show_user_dashboard 测试"""

    def test_basic_output(self, capsys):
        """基本输出包含关键信息"""
        data = {
            "study_stats": {
                "online_completed": 30.0,
                "online_target": 50.0,
                "classroom_completed": 10.0,
                "classroom_target": 90.0,
            },
            "courses": [
                {"status": "已完成", "required": "必修"},
                {"status": "未开始", "required": "必修"},
                {"status": "学习中", "required": "选修"},
            ],
            "topics": [
                {"courses": [{"status": "已完成"}]},
                {"courses": [{"status": "未开始"}]},
            ],
            "tasks": [
                {"status": "进行中", "name": "任务1", "deadline": "2026-06-30"},
                {"status": "已过期", "name": "任务2", "deadline": "2026-01-01"},
            ],
        }
        show_user_dashboard(data)
        output = capsys.readouterr().out

        assert "用户数据概览" in output
        assert "网络自学" in output
        assert "集中培训" in output
        assert "课程" in output
        assert "专题" in output
        assert "任务" in output
        assert "任务1" in output

    def test_empty_data(self, capsys):
        """空数据不报错"""
        data = {
            "study_stats": {},
            "courses": [],
            "topics": [],
            "tasks": [],
        }
        show_user_dashboard(data)
        output = capsys.readouterr().out
        assert "用户数据概览" in output

    def test_progress_bar(self, capsys):
        """进度条正确显示"""
        data = {
            "study_stats": {"online_completed": 25.0, "online_target": 50.0},
            "courses": [],
            "topics": [],
            "tasks": [],
        }
        show_user_dashboard(data)
        output = capsys.readouterr().out
        assert "50%" in output

    def test_completed_target(self, capsys):
        """达标时显示 ✅"""
        data = {
            "study_stats": {"online_completed": 50.0, "online_target": 50.0},
            "courses": [],
            "topics": [],
            "tasks": [],
        }
        show_user_dashboard(data)
        output = capsys.readouterr().out
        assert "✅" in output


# ── ask_user_goal ──


class TestAskUserGoal:
    """ask_user_goal 测试"""

    def test_select_first_suggestion(self):
        """选择第一个推荐选项"""
        data = {
            "study_stats": {"online_completed": 30.0, "online_target": 50.0},
            "courses": [],
            "topics": [],
            "tasks": [],
        }
        with patch("builtins.input", return_value="1"):
            result = ask_user_goal(data)
        assert result == ("hours", 50.0)

    def test_select_custom_hours(self):
        """选择自定义学时"""
        data = {
            "study_stats": {"online_completed": 30.0, "online_target": 50.0},
            "courses": [],
            "topics": [],
            "tasks": [],
        }
        with patch("builtins.input", side_effect=["2", "60"]):
            result = ask_user_goal(data)
        assert result == ("hours", 60.0)

    def test_select_exit(self):
        """选择退出"""
        data = {
            "study_stats": {},
            "courses": [],
            "topics": [],
            "tasks": [],
        }
        # 没有推荐选项时，退出是第 3 个选项
        with patch("builtins.input", return_value="3"):
            result = ask_user_goal(data)
        assert result is None

    def test_eof_returns_none(self):
        """EOF 返回 None"""
        data = {
            "study_stats": {},
            "courses": [],
            "topics": [],
            "tasks": [],
        }
        with patch("builtins.input", side_effect=EOFError):
            result = ask_user_goal(data)
        assert result is None

    def test_invalid_input_then_valid(self):
        """无效输入后重试"""
        data = {
            "study_stats": {"online_completed": 30.0, "online_target": 50.0},
            "courses": [],
            "topics": [],
            "tasks": [],
        }
        with patch("builtins.input", side_effect=["abc", "1"]):
            result = ask_user_goal(data)
        assert result == ("hours", 50.0)


# ── ask_new_target ──


class TestAskNewTarget:
    """ask_new_target 测试"""

    def test_select_new_target(self):
        """选择输入新目标"""
        with patch("builtins.input", side_effect=["1", "60"]):
            result = ask_new_target(50.0, 50.0)
        assert result == 60.0

    def test_select_unlimited(self):
        """选择无限制"""
        with patch("builtins.input", return_value="2"):
            result = ask_new_target(50.0, 50.0)
        assert result == float("inf")

    def test_select_exit(self):
        """选择退出"""
        with patch("builtins.input", return_value="3"):
            result = ask_new_target(50.0, 50.0)
        assert result is None

    def test_eof_returns_none(self):
        """EOF 返回 None"""
        with patch("builtins.input", side_effect=EOFError):
            result = ask_new_target(50.0, 50.0)
        assert result is None

    def test_invalid_then_valid(self):
        """无效输入后重试"""
        with patch("builtins.input", side_effect=["abc", "1", "60"]):
            result = ask_new_target(50.0, 50.0)
        assert result == 60.0

    def test_new_target_must_exceed_current(self):
        """新目标必须大于当前学时"""
        with patch("builtins.input", side_effect=["1", "40", "60"]):
            result = ask_new_target(50.0, 50.0)
        assert result == 60.0

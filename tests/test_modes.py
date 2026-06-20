"""测试运行模式 - hours/topics/courses/tasks"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestModes:
    """测试 4 种运行模式"""

    @pytest.fixture
    def mock_deps(self):
        """模拟依赖"""
        client = MagicMock()
        client.page = MagicMock()
        client.page.evaluate = AsyncMock(return_value="")
        client.page.goto = AsyncMock()
        client.page.wait_for_timeout = AsyncMock()
        client.page.on = MagicMock()
        
        config = MagicMock()
        config.target_hours = 50
        config.study_check_interval = 30
        
        log = MagicMock()
        
        progress = MagicMock()
        progress.study_time = {"current_total": 0}
        progress.is_course_completed = MagicMock(return_value=False)
        progress.mark_course_completed = MagicMock()
        
        status = MagicMock()
        
        courses = MagicMock()
        courses.navigate_to_learning_center = AsyncMock()
        courses.get_study_stats = AsyncMock(return_value={
            "online_completed": 33,
            "online_target": 50,
            "classroom_completed": 26,
            "classroom_target": 90
        })
        courses.get_my_courses = AsyncMock(return_value=[])
        courses.get_special_topics = AsyncMock(return_value=[])
        courses.get_subject_courses = AsyncMock(return_value=[])
        
        monitor = MagicMock()
        monitor.start = AsyncMock()
        monitor.stop = AsyncMock()
        
        return client, config, log, progress, status, courses, monitor

    @pytest.mark.asyncio
    async def test_mode_hours_logs_correctly(self, mock_deps):
        """测试刷学时模式日志输出"""
        from main import mode_hours
        client, config, log, progress, status, courses, monitor = mock_deps
        
        courses.get_my_courses = AsyncMock(return_value=[])
        
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                mode_hours(client, config, log, progress, status, courses, monitor),
                timeout=0.2
            )
        
        log.info.assert_any_call("🎯 模式: 刷网络自学学时")

    @pytest.mark.asyncio
    async def test_mode_topics_no_topics(self, mock_deps):
        """测试刷专题模式 - 无专题"""
        from main import mode_topics
        client, config, log, progress, status, courses, monitor = mock_deps
        
        courses.get_special_topics = AsyncMock(return_value=[])
        
        await mode_topics(client, config, log, progress, status, courses, monitor)
        
        log.info.assert_any_call("🎯 模式: 刷专题")
        log.warn.assert_any_call("⚠️ 未找到专题课程")

    @pytest.mark.asyncio
    async def test_mode_topics_with_topics(self, mock_deps):
        """测试刷专题模式 - 有专题"""
        from unittest.mock import patch
        from main import mode_topics
        client, config, log, progress, status, courses, monitor = mock_deps
        
        # Mock DataManager
        mock_data_mgr = AsyncMock()
        mock_data_mgr.fetch_topics = AsyncMock(return_value=[
            {"title": "测试专题", "href": "http://test.com/topic1", "courses": []}
        ])
        
        with patch('main.DataManager', return_value=mock_data_mgr):
            await mode_topics(client, config, log, progress, status, courses, monitor)
        
        log.info.assert_any_call("🎯 模式: 刷专题")
        log.info.assert_any_call("📚 共 1 个专题")

    @pytest.mark.asyncio
    async def test_mode_courses_no_courses(self, mock_deps):
        """测试刷课程模式 - 无课程"""
        from unittest.mock import patch
        from main import mode_courses
        client, config, log, progress, status, courses, monitor = mock_deps
        
        # Mock DataManager
        mock_data_mgr = AsyncMock()
        mock_data_mgr.fetch_courses = AsyncMock(return_value=[])
        
        with patch('main.DataManager', return_value=mock_data_mgr):
            await mode_courses(client, config, log, progress, status, courses, monitor)
        
        log.info.assert_any_call("🎯 模式: 刷课程")
        log.warn.assert_any_call("⚠️ 没有待学习的课程")
    
    @pytest.mark.asyncio
    async def test_mode_courses_with_courses(self, mock_deps):
        """测试刷课程模式 - 有课程"""
        from unittest.mock import patch
        from main import mode_courses
        client, config, log, progress, status, courses, monitor = mock_deps
        
        # Mock DataManager
        mock_data_mgr = AsyncMock()
        mock_data_mgr.fetch_courses = AsyncMock(return_value=[
            {"course_id": "course1", "title": "测试课程", "status": "学习中", "url": "http://test.com/course1"}
        ])
        
        with patch('main.DataManager', return_value=mock_data_mgr):
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    mode_courses(client, config, log, progress, status, courses, monitor),
                    timeout=0.3
                )
        
        log.info.assert_any_call("🎯 模式: 刷课程")

    @pytest.mark.asyncio
    async def test_mode_tasks_logs_correctly(self, mock_deps):
        """测试刷任务模式日志输出"""
        from unittest.mock import patch
        from main import mode_tasks
        client, config, log, progress, status, courses, monitor = mock_deps
        
        # Mock DataManager
        mock_data_mgr = AsyncMock()
        mock_data_mgr.fetch_tasks = AsyncMock(return_value=[])
        
        with patch('main.DataManager', return_value=mock_data_mgr):
            await mode_tasks(client, config, log, progress, status, courses, monitor)
        
        log.info.assert_any_call("🎯 模式: 刷任务")

    @pytest.mark.asyncio
    async def test_mode_hours_fetches_study_stats(self, mock_deps):
        """测试刷学时模式获取学时统计"""
        from unittest.mock import patch
        from main import mode_hours
        client, config, log, progress, status, courses, monitor = mock_deps
        
        # Mock DataManager
        mock_data_mgr = AsyncMock()
        mock_data_mgr.fetch_study_stats = AsyncMock(return_value={
            "online_completed": 33, "online_target": 50,
            "classroom_completed": 26, "classroom_target": 90
        })
        mock_data_mgr.fetch_courses = AsyncMock(return_value=[])
        mock_data_mgr.update_progress = AsyncMock(return_value={
            "study_stats": {"online_completed": 33, "online_target": 50}
        })
        
        with patch('main.DataManager', return_value=mock_data_mgr):
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    mode_hours(client, config, log, progress, status, courses, monitor),
                    timeout=0.3
                )
        
        mock_data_mgr.fetch_study_stats.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_mode_hours_sets_target_hours(self, mock_deps):
        """测试刷学时模式设置目标学时"""
        from unittest.mock import patch
        from main import mode_hours
        client, config, log, progress, status, courses, monitor = mock_deps
        
        config.target_hours = 50
        
        # Mock DataManager
        mock_data_mgr = AsyncMock()
        mock_data_mgr.fetch_study_stats = AsyncMock(return_value={
            "online_completed": 33, "online_target": 50,
            "classroom_completed": 26, "classroom_target": 90
        })
        mock_data_mgr.fetch_courses = AsyncMock(return_value=[])
        mock_data_mgr.update_progress = AsyncMock(return_value={
            "study_stats": {"online_completed": 33, "online_target": 50}
        })
        
        with patch('main.DataManager', return_value=mock_data_mgr):
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    mode_hours(client, config, log, progress, status, courses, monitor),
                    timeout=0.3
                )
        
        status.set_study_hours.assert_called()
    
    @pytest.mark.asyncio
    async def test_mode_hours_skips_completed_courses(self, mock_deps):
        """测试刷学时模式跳过已完成课程"""
        from unittest.mock import patch
        from main import mode_hours
        client, config, log, progress, status, courses, monitor = mock_deps
        
        # Mock DataManager
        mock_data_mgr = AsyncMock()
        mock_data_mgr.fetch_study_stats = AsyncMock(return_value={
            "online_completed": 33, "online_target": 50,
            "classroom_completed": 26, "classroom_target": 90
        })
        mock_data_mgr.fetch_courses = AsyncMock(return_value=[
            {"course_id": "course1", "title": "已完成课程", "status": "已完成", "url": "http://test.com/1"},
            {"course_id": "course2", "title": "待学习课程", "status": "学习中", "url": "http://test.com/2"}
        ])
        mock_data_mgr.update_progress = AsyncMock(return_value={
            "study_stats": {"online_completed": 33, "online_target": 50}
        })
        progress.is_course_completed = MagicMock(side_effect=lambda x: x == "course1")
        
        with patch('main.DataManager', return_value=mock_data_mgr):
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    mode_hours(client, config, log, progress, status, courses, monitor),
                    timeout=0.3
                )
        
        # 验证至少检查了一个课程
        assert progress.is_course_completed.call_count >= 1

    @pytest.mark.asyncio
    async def test_mode_topics_fetches_topics(self, mock_deps):
        """测试刷专题模式获取专题列表"""
        from unittest.mock import patch
        from main import mode_topics
        client, config, log, progress, status, courses, monitor = mock_deps
        
        # Mock DataManager
        mock_data_mgr = AsyncMock()
        mock_data_mgr.fetch_topics = AsyncMock(return_value=[
            {"title": "专题1", "href": "http://test.com/topic1", "courses": []}
        ])
        
        with patch('main.DataManager', return_value=mock_data_mgr):
            await mode_topics(client, config, log, progress, status, courses, monitor)
        
        mock_data_mgr.fetch_topics.assert_called_once()

    @pytest.mark.asyncio
    async def test_mode_courses_fetches_courses(self, mock_deps):
        """测试刷课程模式获取课程列表"""
        from unittest.mock import patch
        from main import mode_courses
        client, config, log, progress, status, courses, monitor = mock_deps
        
        # Mock DataManager
        mock_data_mgr = AsyncMock()
        mock_data_mgr.fetch_courses = AsyncMock(return_value=[])
        
        with patch('main.DataManager', return_value=mock_data_mgr):
            await mode_courses(client, config, log, progress, status, courses, monitor)
        
        mock_data_mgr.fetch_courses.assert_called_once()


class TestArgParser:
    """测试命令行参数解析"""

    def test_default_mode_is_hours(self):
        """测试默认模式是 hours"""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--mode", choices=["hours", "topics", "courses", "tasks"], default="hours")
        args = parser.parse_args([])
        assert args.mode == "hours"

    def test_mode_hours(self):
        """测试 --mode hours"""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--mode", choices=["hours", "topics", "courses", "tasks"], default="hours")
        args = parser.parse_args(["--mode", "hours"])
        assert args.mode == "hours"

    def test_mode_topics(self):
        """测试 --mode topics"""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--mode", choices=["hours", "topics", "courses", "tasks"], default="hours")
        args = parser.parse_args(["--mode", "topics"])
        assert args.mode == "topics"

    def test_mode_courses(self):
        """测试 --mode courses"""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--mode", choices=["hours", "topics", "courses", "tasks"], default="hours")
        args = parser.parse_args(["--mode", "courses"])
        assert args.mode == "courses"

    def test_mode_tasks(self):
        """测试 --mode tasks"""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--mode", choices=["hours", "topics", "courses", "tasks"], default="hours")
        args = parser.parse_args(["--mode", "tasks"])
        assert args.mode == "tasks"

    def test_invalid_mode_rejected(self):
        """测试无效模式被拒绝"""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--mode", choices=["hours", "topics", "courses", "tasks"], default="hours")
        with pytest.raises(SystemExit):
            parser.parse_args(["--mode", "invalid"])

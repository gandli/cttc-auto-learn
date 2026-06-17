"""
学时规划模块 - 智能规划课程学习顺序，精确满足目标学时
"""
from typing import Optional


class StudyPlanner:
    """学时规划器 - 计算最优课程组合"""

    def __init__(self, log):
        self.log = log

    def plan_courses(
        self,
        current_hours: float,
        target_hours: float,
        courses: list[dict],
        priority_courses: list[dict],
    ) -> list[dict]:
        """规划课程学习顺序

        Args:
            current_hours: 当前学时
            target_hours: 目标学时
            courses: 所有待学习课程
            priority_courses: 优先课程（专题/任务）

        Returns:
            规划后的课程列表（按优先级排序，精确满足目标）
        """
        remaining_hours = target_hours - current_hours
        if remaining_hours <= 0:
            self.log.info(f"🎉 已达到目标学时 {target_hours}h (当前 {current_hours:.1f}h)")
            return []

        self.log.info(f"📊 学时规划: 当前 {current_hours:.1f}h, 目标 {target_hours}h, 还需 {remaining_hours:.1f}h")

        # 1. 分离优先课程和普通课程
        priority_ids = {c["course_id"] for c in priority_courses}
        priority = [c for c in courses if c["course_id"] in priority_ids]
        normal = [c for c in courses if c["course_id"] not in priority_ids]

        # 2. 计算每门课程的预计学时（小时）
        for c in priority:
            c["estimated_hours"] = self._estimate_hours(c)
        for c in normal:
            c["estimated_hours"] = self._estimate_hours(c)

        # 3. 贪心算法：优先学习专题/任务课程，然后普通课程
        planned = []
        accumulated_hours = 0.0

        # 先添加优先课程
        for c in priority:
            if accumulated_hours >= remaining_hours:
                break
            planned.append(c)
            accumulated_hours += c["estimated_hours"]

        # 再添加普通课程（直到满足目标）
        for c in normal:
            if accumulated_hours >= remaining_hours:
                break
            planned.append(c)
            accumulated_hours += c["estimated_hours"]

        # 4. 输出规划结果
        self.log.info(f"📋 规划结果:")
        self.log.info(f"  - 优先课程: {len(priority)} 门 (预计 {sum(c['estimated_hours'] for c in priority):.1f}h)")
        self.log.info(f"  - 普通课程: {len([c for c in planned if c not in priority])} 门")
        self.log.info(f"  - 总计: {len(planned)} 门, 预计 {accumulated_hours:.1f}h")
        self.log.info(f"  - 目标: {remaining_hours:.1f}h")

        return planned

    def _estimate_hours(self, course: dict) -> float:
        """估算课程学时

        优先使用 API 返回的 total_min，否则使用默认值
        """
        total_min = course.get("total_min", 0)
        study_min = course.get("study_min", 0)

        if total_min > 0:
            # 剩余时间 = 总时长 - 已学习时长
            remaining_min = max(0, total_min - study_min)
            return remaining_min / 60
        else:
            # 默认估算：每门课程约 1 小时
            return 1.0

    def calculate_optimal_plan(
        self,
        current_hours: float,
        target_hours: float,
        topics: list[dict],
        tasks: list[dict],
        courses: list[dict],
    ) -> dict:
        """计算最优学习计划

        优先从专题/任务中选择课程，精确满足目标学时

        Returns:
            {
                "plan": list[dict],  # 规划的课程列表
                "total_hours": float,  # 预计总学时
                "priority_count": int,  # 优先课程数
                "normal_count": int,  # 普通课程数
            }
        """
        remaining_hours = target_hours - current_hours
        if remaining_hours <= 0:
            return {"plan": [], "total_hours": 0, "priority_count": 0, "normal_count": 0}

        # 1. 收集专题/任务中的课程 ID
        priority_course_ids = set()

        # 从任务中收集
        for task in tasks:
            if task.get("status") == "进行中":
                priority_course_ids.add(task.get("business_id", ""))

        # 从专题中收集
        for topic in topics:
            for tc in topic.get("courses", []):
                if tc.get("status") != "已完成":
                    # 通过标题前 20 字符匹配
                    priority_course_ids.add(tc.get("title", "")[:20])

        # 2. 分类课程
        priority_courses = []
        normal_courses = []
        seen_ids = set()

        for c in courses:
            if c["status"] not in ("学习中", "未开始"):
                continue
            if c["course_id"] in seen_ids:
                continue
            seen_ids.add(c["course_id"])

            # 判断是否为优先课程
            is_priority = False
            for pid in priority_course_ids:
                if pid and c["title"][:20].startswith(pid):
                    is_priority = True
                    break

            if is_priority:
                priority_courses.append(c)
            else:
                normal_courses.append(c)

        # 3. 计算学时
        for c in priority_courses:
            c["estimated_hours"] = self._estimate_hours(c)
        for c in normal_courses:
            c["estimated_hours"] = self._estimate_hours(c)

        # 4. 贪心算法选择课程
        planned = []
        accumulated_hours = 0.0

        # 先添加优先课程
        for c in priority_courses:
            if accumulated_hours >= remaining_hours:
                break
            planned.append(c)
            accumulated_hours += c["estimated_hours"]

        # 再添加普通课程
        for c in normal_courses:
            if accumulated_hours >= remaining_hours:
                break
            planned.append(c)
            accumulated_hours += c["estimated_hours"]

        priority_count = len([c for c in planned if c in priority_courses])
        normal_count = len([c for c in planned if c in normal_courses])

        return {
            "plan": planned,
            "total_hours": accumulated_hours,
            "priority_count": priority_count,
            "normal_count": normal_count,
        }

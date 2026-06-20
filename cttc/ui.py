"""用户交互模块 — 数据看板 & 目标选择"""

from __future__ import annotations

from typing import Any


def show_user_dashboard(data: dict[str, Any]) -> None:
    """展示用户当前数据摘要

    Args:
        data: 包含 study_stats, courses, topics, tasks 的字典
    """
    stats = data.get("study_stats", {})
    courses = data.get("courses", [])
    topics = data.get("topics", [])
    tasks = data.get("tasks", [])

    online = stats.get("online_completed", 0)
    online_target = stats.get("online_target", 0)
    classroom = stats.get("classroom_completed", 0)
    classroom_target = stats.get("classroom_target", 0)

    # 课程统计
    total_courses = len(courses)
    completed_courses = sum(1 for c in courses if c.get("status") == "已完成")
    required_courses = [c for c in courses if c.get("required") == "必修"]
    required_done = sum(1 for c in required_courses if c.get("status") == "已完成")
    pending_courses = sum(1 for c in courses if c.get("status") in ("学习中", "未开始"))

    # 任务统计
    active_tasks = [t for t in tasks if t.get("status") == "进行中"]
    expired_tasks = [t for t in tasks if t.get("status") == "已过期"]

    # 专题统计
    topics_incomplete = 0
    for t in topics:
        tc = t.get("courses", [])
        if any(c.get("status") != "已完成" for c in tc):
            topics_incomplete += 1

    print(f"\n{'='*55}")
    print(f"  📊 用户数据概览")
    print(f"{'='*55}")

    # 学时
    print(f"\n  ⏱️  学时进度:")
    if online_target:
        pct = online / online_target * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        flag = " ✅" if online >= online_target else ""
        print(f"     网络自学: {online:.1f}/{online_target:.0f}h [{bar}] {pct:.0f}%{flag}")
    if classroom_target:
        pct = classroom / classroom_target * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        flag = " ✅" if classroom >= classroom_target else ""
        print(f"     集中培训: {classroom:.1f}/{classroom_target:.0f}h [{bar}] {pct:.0f}%{flag}")

    # 课程
    print(f"\n  📚  课程:")
    print(f"     总计: {total_courses} 门 (已完成 {completed_courses}, 待学 {pending_courses})")
    if required_courses:
        print(f"     必修: {len(required_courses)} 门 (已完成 {required_done})")

    # 专题
    print(f"\n  📖  专题: {len(topics)} 个 (未完成 {topics_incomplete})")

    # 任务
    print(f"\n  📋  任务: {len(tasks)} 个 (进行中 {len(active_tasks)}, 已过期 {len(expired_tasks)})")
    for t in active_tasks[:3]:
        name = t.get("name", "")[:40]
        deadline = t.get("deadline", "")
        print(f"     • {name} (截止: {deadline})")
    if len(active_tasks) > 3:
        print(f"     ... 还有 {len(active_tasks) - 3} 个")

    print(f"\n{'='*55}")


def ask_user_goal(data: dict[str, Any]) -> tuple[str, float] | None:
    """询问用户刷课目标

    Args:
        data: 包含 study_stats, courses, topics, tasks 的字典

    Returns:
        (mode, target_hours) 或 None 表示退出
        mode: "hours" | "topics" | "courses" | "tasks"
    """
    stats = data.get("study_stats", {})
    courses = data.get("courses", [])
    tasks = data.get("tasks", [])
    topics = data.get("topics", [])

    online = stats.get("online_completed", 0)
    online_target = stats.get("online_target", 0)

    pending_courses = sum(1 for c in courses if c.get("status") in ("学习中", "未开始"))
    active_tasks = [t for t in tasks if t.get("status") == "进行中"]

    # 生成推荐（仅线上可刷的目标）
    suggestions: list[tuple[str, float, str]] = []
    if online_target and online < online_target:
        remaining = online_target - online
        suggestions.append(("hours", online_target, f"刷网络自学学时 (还差 {remaining:.1f}h 达标)"))
    if active_tasks:
        suggestions.append(("tasks", 0, f"完成 {len(active_tasks)} 个进行中的任务"))
    if topics:
        topics_incomplete = sum(1 for t in topics
                                if any(c.get("status") != "已完成" for c in t.get("courses", [])))
        if topics_incomplete:
            suggestions.append(("topics", 0, f"完成 {topics_incomplete} 个未完成的专题"))
    if pending_courses:
        suggestions.append(("courses", 0, f"刷完 {pending_courses} 门待学课程"))

    print(f"\n  🎯 请选择刷课目标:\n")

    # 显示推荐选项
    for i, (mode, target, desc) in enumerate(suggestions, 1):
        print(f"     {i}. {desc}")

    # 补充通用选项
    offset = len(suggestions) + 1
    print(f"     {offset}. 刷网络自学学时 (自定义目标)")
    print(f"     {offset+1}. 无限制刷课 (所有课程)")
    print(f"     {offset+2}. 退出程序")

    print()

    while True:
        try:
            choice = input("  请输入选项编号: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None

        try:
            idx = int(choice)
        except ValueError:
            print("  ⚠️ 请输入数字")
            continue

        # 推荐选项
        if 1 <= idx <= len(suggestions):
            mode, target, _ = suggestions[idx - 1]
            return (mode, target)

        # 自定义学时
        if idx == offset:
            default_target = online_target if online_target else 50
            try:
                val = input(f"  请输入目标学时 (默认 {default_target}h): ").strip()
                target = float(val) if val else default_target
            except (ValueError, EOFError, KeyboardInterrupt):
                target = default_target
            return ("hours", target)

        # 无限制
        if idx == offset + 1:
            return ("courses", float("inf"))

        # 退出
        if idx == offset + 2:
            return None

        print("  ⚠️ 无效选项")


def ask_new_target(current_hours: float, old_target: float) -> float | None:
    """达到目标后询问用户是否继续

    Args:
        current_hours: 当前学时
        old_target: 旧目标学时

    Returns:
        新的目标学时，None 表示退出
    """
    print(f"\n{'='*50}")
    print(f"🎉 已达到目标学时 {old_target}h (当前 {current_hours:.1f}h)！")
    print(f"{'='*50}")
    print(f"\n请选择:")
    print(f"  1. 输入新目标继续刷课")
    print(f"  2. 无限制继续刷课")
    print(f"  3. 退出程序")
    print()

    while True:
        try:
            choice = input("请输入选项 (1/2/3): ").strip()
        except (EOFError, KeyboardInterrupt):
            return None

        if choice == "1":
            while True:
                try:
                    new_target = input(f"请输入新目标学时 (当前 {current_hours:.1f}h): ").strip()
                    new_target = float(new_target)
                    if new_target > current_hours:
                        return new_target
                    else:
                        print(f"⚠️ 新目标必须大于当前学时 {current_hours:.1f}h")
                except ValueError:
                    print("⚠️ 请输入有效数字")
                except (EOFError, KeyboardInterrupt):
                    return None
        elif choice == "2":
            return float("inf")  # 无限制
        elif choice == "3":
            return None
        else:
            print("⚠️ 无效选项，请输入 1、2 或 3")

"""烟草网络学院 - 全自动学习系统

支持模式：
  --mode hours     刷学时（默认）
  --mode topics    刷专题
  --mode courses   刷课程
  --mode tasks     刷任务

使用：
  uv run python main.py --mode hours
  uv run python main.py --mode topics
  uv run python main.py --mode courses
  uv run python main.py --mode tasks
"""

import argparse
import asyncio
import sys
from pathlib import Path

from cttc.config import Config
from cttc.logger import Logger
from cttc.login import CTTCLogin
from cttc.course import CourseManager
from cttc.player import VideoPlayer
from cttc.monitor import StudyMonitor
from cttc.progress import ProgressManager
from cttc.process_manager import kill_other_chrome_processes, check_single_instance, release_lock
from cttc.status import StatusReporter
from cttc.data_manager import DataManager
from cttc.planner import StudyPlanner


# ──────────────────────────────────────────────
# 用户交互 — 数据看板 & 目标选择
# ──────────────────────────────────────────────

def show_user_dashboard(data: dict) -> None:
    """展示用户当前数据摘要"""
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


def ask_user_goal(data: dict) -> tuple[str, float] | None:
    """询问用户刷课目标

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
    classroom = stats.get("classroom_completed", 0)
    classroom_target = stats.get("classroom_target", 0)

    pending_courses = sum(1 for c in courses if c.get("status") in ("学习中", "未开始"))
    active_tasks = [t for t in tasks if t.get("status") == "进行中"]

    # 生成推荐（仅线上可刷的目标）
    suggestions = []
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


# ──────────────────────────────────────────────
# 标签页管理 — 严格单标签
# ──────────────────────────────────────────────

async def enforce_single_tab(page, log):
    """关闭所有多余标签页，只保留当前页面"""
    ctx = page.context
    closed = 0
    for p in list(ctx.pages):
        if p != page and not p.is_closed():
            try:
                await p.close()
                closed += 1
            except Exception:
                pass
    if closed > 0:
        log.info(f"🔒 关闭了 {closed} 个多余标签页")


# ──────────────────────────────────────────────
# 登录流程
# ──────────────────────────────────────────────

async def login_flow(config: Config, log: Logger):
    """完整登录流程，返回 (client, success, qr_paths)
    
    浏览器方式：打开登录页 → 提取二维码 → 等待页面跳转
    """
    client = CTTCLogin(config, log)
    await client.start()
    qr_paths = {"app": None, "wechat": None}

    # 1. 尝试 Cookie 恢复
    if await client.try_restore_session():
        return client, True, qr_paths

    # 2. 打开登录页
    await client.navigate_to_login()

    # 3. 提取两种二维码
    qrs = await client.extract_both_qrs()
    qr_paths = await client.save_both_qrs(qrs)

    log.info(f"📱 APP 二维码: {qr_paths.get('app')}")
    log.info(f"📱 微信二维码: {qr_paths.get('wechat')}")
    log.info("⏳ 等待扫码...")

    # 4. 等待登录（浏览器页面跳转检测 + token 检测）
    success = await client.wait_for_login(timeout=300)

    if success:
        log.info("🎉 登录成功！")
        await client.page.wait_for_timeout(2000)
        await client._save_state()
        return client, True, qr_paths
    else:
        log.error("❌ 登录超时")
        await client.close()
        return client, False, qr_paths


# ──────────────────────────────────────────────
# 刷学时模式
# ──────────────────────────────────────────────

async def mode_hours(client, config, log, progress, status, courses, monitor, track="online"):
    """刷学时模式 - 播放视频累计学时

    Args:
        track: "online" (网络自学) 或 "classroom" (集中培训)
    """
    data_mgr = DataManager(client.page, config, log)
    track_label = "网络自学" if track == "online" else "集中培训"
    log.info(f"🎯 模式: 刷{track_label}学时")

    # 使用 API 获取学时统计（无需导航到学习中心）
    current_hours = 0.0
    stats = await data_mgr.fetch_study_stats()
    if stats:
        online = stats.get("online_completed", 0)
        online_target = stats.get("online_target", 0)
        classroom = stats.get("classroom_completed", 0)
        classroom_target = stats.get("classroom_target", 0)
        log.info(f"📊 网络自学: {online}/{online_target} 小时 ({online/online_target*100:.1f}%)" if online_target else f"📊 网络自学: {online} 小时")
        if classroom_target:
            log.info(f"📊 集中培训: {classroom}/{classroom_target} 小时 ({classroom/classroom_target*100:.1f}%)")
        if track == "classroom":
            progress.record_study_time(classroom)
            current_hours = classroom
        else:
            progress.record_study_time(online)
            current_hours = online

    # 目标检查
    target_hours = config.target_hours
    status.set_study_hours(current_hours, target_hours or 0)
    if target_hours:
        remaining = target_hours - current_hours
        if remaining <= 0:
            new_target = ask_new_target(current_hours, target_hours)
            if new_target is None:
                return
            target_hours = new_target
            config.target_hours = target_hours
        log.info(f"🎯 目标: {target_hours}h, 还需: {max(0, target_hours - current_hours):.1f}h")
    else:
        log.info(f"🎯 无目标限制，将学习所有可用课程")

    # 启动学时监控
    await monitor.start()
    status.set_status("running")
    
    # 上次刷新学时的时间
    last_study_hours_refresh = asyncio.get_event_loop().time()

    try:
        while True:
            # 每 30 分钟刷新一次学时和课程数据
            current_time = asyncio.get_event_loop().time()
            if current_time - last_study_hours_refresh > 1800:  # 30 分钟
                try:
                    update_result = await data_mgr.update_progress()
                    stats = update_result.get("study_stats", {})
                    if stats:
                        online = stats.get("online_completed", 0)
                        online_target = stats.get("online_target", 0)
                        classroom = stats.get("classroom_completed", 0)
                        classroom_target = stats.get("classroom_target", 0)
                        log.info(f"📊 刷新学时: 网络自学 {online}/{online_target}h, 集中培训 {classroom}/{classroom_target}h")
                        if track == "classroom":
                            progress.record_study_time(classroom)
                            status.set_study_hours(classroom, target_hours or 0)
                        else:
                            progress.record_study_time(online)
                            status.set_study_hours(online, target_hours or 0)
                    last_study_hours_refresh = current_time
                except Exception as e:
                    log.warn(f"⚠️ 刷新数据失败: {e}")
            
            # 目标检查
            if target_hours:
                current = progress.study_time.get("current_total", 0)
                if current >= target_hours:
                    new_target = ask_new_target(current, target_hours)
                    if new_target is None:
                        break
                    target_hours = new_target
                    config.target_hours = target_hours

            # 获取优先课程（专题/任务中的课程）
            priority_course_ids = set()
            
            # 1. 获取任务中的课程
            try:
                tasks = await data_mgr.fetch_tasks()
                for task in tasks:
                    if task.get("status") == "进行中" and task.get("business_type") == "专题":
                        # 专题任务的 business_id 就是专题 ID
                        priority_course_ids.add(task.get("business_id", ""))
            except Exception as e:
                log.warn(f"⚠️ 获取任务失败: {e}")
            
            # 2. 获取专题中的课程
            try:
                topics = await data_mgr.fetch_topics()
                for topic in topics:
                    for tc in topic.get("courses", []):
                        if tc.get("status") != "已完成":
                            # 专题课程没有 course_id，需要通过标题匹配
                            priority_course_ids.add(tc.get("title", "")[:20])
            except Exception as e:
                log.warn(f"⚠️ 获取专题失败: {e}")
            
            # 3. 获取所有课程
            my_courses = await data_mgr.fetch_courses(status_filter="all")
            
            # 4. 分类：优先课程 vs 普通课程
            priority_courses = []
            normal_courses = []
            seen_ids = set()
            
            for c in my_courses:
                if c["status"] not in ("学习中", "未开始"):
                    continue
                if c["course_id"] in seen_ids:
                    continue
                seen_ids.add(c["course_id"])
                
                # 判断是否为优先课程（通过标题前缀匹配）
                is_priority = False
                for pid in priority_course_ids:
                    if pid and c["title"][:20].startswith(pid):
                        is_priority = True
                        break
                
                if is_priority:
                    priority_courses.append(c)
                else:
                    normal_courses.append(c)
            
            # 5. 合并：优先课程在前
            pending = priority_courses + normal_courses
            
            if priority_courses:
                log.info(f"🎯 优先课程: {len(priority_courses)} 门（专题/任务）")

            if not pending:
                log.warn("⚠️ 没有待学习的课程，等待 10 分钟后重试...")
                status.set_status("idle - no courses")
                await asyncio.sleep(600)
                continue

            log.info(f"📚 共 {len(pending)} 门待学习课程")
            status.set_courses(0, len(my_courses), len(pending))

            for course in pending:
                # 目标检查
                if target_hours:
                    current = progress.study_time.get("current_total", 0)
                    if current >= target_hours:
                        new_target = ask_new_target(current, target_hours)
                        if new_target is None:
                            break
                        target_hours = new_target
                        config.target_hours = target_hours

                course_id = course["course_id"]
                if progress.is_course_completed(course_id):
                    continue

                log.info(f"📖 学习: {course['title'][:50]}")
                video_url = course["url"]
                status.set_video(course["title"], video_url)
                status.set_status("playing")

                # 关闭多余标签页（严格单标签）
                await enforce_single_tab(client.page, log)
                await asyncio.sleep(0.5)

                # 导航到课程页
                log.info(f"  🔗 {video_url[:100]}")
                try:
                    await client.page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
                except Exception as e:
                    err = str(e)
                    if "Target" in err or "closed" in err.lower():
                        log.warn(f"  ⚠️ 浏览器已关闭，跳出课程循环让外层重试")
                        raise
                    log.warn(f"  ⚠️ 导航失败: {e}")
                    continue
                try:
                    await client.page.wait_for_timeout(5000)
                except Exception as e:
                    if "Target" in str(e) or "closed" in str(e).lower():
                        log.warn(f"  ⚠️ 浏览器已关闭，跳出课程循环")
                        raise
                    raise

                # 再次关闭多余标签页
                await enforce_single_tab(client.page, log)

                # 播放视频
                player = VideoPlayer(client.page, config, log, progress, status)
                await player.setup()

                try:
                    monitor._video_playing = True
                    progress.reset_stale()
                    success = await player.play_and_wait()
                    monitor._video_playing = False

                    # 40909 重试
                    if not success and player._last_progress_error == 40909:
                        log.warn("⚠️ 40909 冲突，等待 30 秒后重试...")
                        await asyncio.sleep(30)
                        try:
                            await enforce_single_tab(client.page, log)
                            await client.page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
                            await client.page.wait_for_timeout(5000)
                            await enforce_single_tab(client.page, log)
                            player = VideoPlayer(client.page, config, log, progress, status)
                            await player.setup()
                            monitor._video_playing = True
                            progress.reset_stale()
                            success = await player.play_and_wait()
                            monitor._video_playing = False
                        except Exception as retry_err:
                            log.warn(f"  ⚠️ 重试失败: {retry_err}")
                    
                    if success:
                        progress.mark_course_completed(course_id)
                        log.info(f"  ✅ 完成: {course['title'][:50]}")
                    else:
                        log.warn(f"  ❌ 失败: {course['title'][:50]}")
                        
                except Exception as e:
                    monitor._video_playing = False
                    log.error(f"  ❌ 播放异常: {e}")
                    
                await asyncio.sleep(2)

    finally:
        await monitor.stop()


# ──────────────────────────────────────────────
# 刷专题模式
# ──────────────────────────────────────────────

async def mode_topics(client, config, log, progress, status, courses, monitor):
    """刷专题模式 - 完成专题课程"""
    data_mgr = DataManager(client.page, config, log)
    log.info("🎯 模式: 刷专题")
    status.set_status("scanning topics")
    
    # 获取专题列表（从缓存或重新获取）
    topics = await data_mgr.fetch_topics()
    
    if not topics:
        log.warn("⚠️ 未找到专题课程")
        return
    
    log.info(f"📚 共 {len(topics)} 个专题")
    
    completed_topics = 0
    for i, topic in enumerate(topics, 1):
        log.info(f"\n📖 专题 {i}/{len(topics)}: {topic['title'][:60]}")
        status.set_status(f"topic {i}/{len(topics)}")
        
        try:
            # 使用 DataManager 已获取的专题内课程（如果有）
            subject_courses = topic.get("courses", [])
            
            # 如果没有缓存的课程，则从页面获取
            if not subject_courses:
                await client.page.goto(topic["href"], wait_until="domcontentloaded", timeout=30000)
                await client.page.wait_for_timeout(3000)
                subject_courses = await courses.get_subject_courses()
            
            if not subject_courses:
                log.info(f"  ⚠️ 专题内无课程")
                continue
            
            log.info(f"  📚 专题内 {len(subject_courses)} 门课程")
            
            # 播放专题内的课程
            for j, course in enumerate(subject_courses, 1):
                course_id = course.get("resource_id", "")
                if progress.is_course_completed(course_id):
                    log.info(f"  ✅ 已完成: {course['title'][:40]}")
                    continue
                
                log.info(f"  🎬 {j}/{len(subject_courses)}: {course['title'][:40]}")
                status.set_video(course["title"], course.get("url", ""))
                status.set_status(f"topic {i}/{len(topics)} - course {j}/{len(subject_courses)}")
                
                # 播放视频
                try:
                    await client.page.goto(course["url"], wait_until="domcontentloaded", timeout=30000)
                    await client.page.wait_for_timeout(5000)
                    await enforce_single_tab(client.page, log)
                    
                    player = VideoPlayer(client.page, config, log, progress, status)
                    await player.setup()
                    monitor._video_playing = True
                    success = await player.play_and_wait()
                    monitor._video_playing = False
                    
                    if success:
                        progress.mark_course_completed(course_id)
                        log.info(f"  ✅ 完成")
                    
                except Exception as e:
                    monitor._video_playing = False
                    log.warn(f"  ❌ 失败: {e}")
                
                await asyncio.sleep(2)
            
            completed_topics += 1
            log.info(f"  ✅ 专题完成")
            
        except Exception as e:
            log.warn(f"  ❌ 专题处理失败: {e}")
        
        await asyncio.sleep(2)
    
    log.info(f"\n🎉 完成 {completed_topics}/{len(topics)} 个专题")


# ──────────────────────────────────────────────
# 刷课程模式
# ──────────────────────────────────────────────

async def mode_courses(client, config, log, progress, status, courses, monitor):
    """刷课程模式 - 完成所有未完成课程"""
    data_mgr = DataManager(client.page, config, log)
    log.info("🎯 模式: 刷课程")
    status.set_status("scanning courses")
    
    # 获取课程列表（从缓存或重新获取）
    my_courses = await data_mgr.fetch_courses()
    
    # 过滤未完成课程
    seen_ids = set()
    pending = []
    for c in my_courses:
        if c["status"] in ("学习中", "未开始") and c["course_id"] not in seen_ids:
            seen_ids.add(c["course_id"])
            pending.append(c)
    
    if not pending:
        log.warn("⚠️ 没有待学习的课程")
        return
    
    log.info(f"📚 共 {len(pending)} 门待学习课程")
    status.set_courses(0, len(my_courses), len(pending))
    
    completed = 0
    for i, course in enumerate(pending, 1):
        course_id = course["course_id"]
        if progress.is_course_completed(course_id):
            continue
        
        log.info(f"\n📖 课程 {i}/{len(pending)}: {course['title'][:50]}")
        status.set_video(course["title"], course["url"])
        status.set_status(f"course {i}/{len(pending)}")
        
        try:
            # 关闭多余标签页
            await enforce_single_tab(client.page, log)
            await asyncio.sleep(0.5)
            
            # 导航到课程页
            log.info(f"  🔗 {course['url'][:100]}")
            await client.page.goto(course["url"], wait_until="domcontentloaded", timeout=30000)
            await client.page.wait_for_timeout(5000)
            await enforce_single_tab(client.page, log)
            
            # 播放视频
            player = VideoPlayer(client.page, config, log, progress, status)
            await player.setup()
            monitor._video_playing = True
            progress.reset_stale()
            success = await player.play_and_wait()
            monitor._video_playing = False
            
            # 40909 重试
            if not success and player._last_progress_error == 40909:
                log.warn("⚠️ 40909 冲突，等待 30 秒后重试...")
                await asyncio.sleep(30)
                try:
                    await enforce_single_tab(client.page, log)
                    await client.page.goto(course["url"], wait_until="domcontentloaded", timeout=30000)
                    await client.page.wait_for_timeout(5000)
                    await enforce_single_tab(client.page, log)
                    player = VideoPlayer(client.page, config, log, progress, status)
                    await player.setup()
                    monitor._video_playing = True
                    progress.reset_stale()
                    success = await player.play_and_wait()
                    monitor._video_playing = False
                except Exception as retry_err:
                    log.warn(f"  ⚠️ 重试失败: {retry_err}")
            
            if success:
                progress.mark_course_completed(course_id)
                completed += 1
                log.info(f"  ✅ 完成: {course['title'][:50]}")
                status.set_courses(completed, len(my_courses), len(pending) - completed)
            else:
                log.warn(f"  ❌ 失败: {course['title'][:50]}")
                
        except Exception as e:
            monitor._video_playing = False
            log.error(f"  ❌ 异常: {e}")
        
        await asyncio.sleep(2)
    
    log.info(f"\n🎉 完成 {completed}/{len(pending)} 门课程")


# ──────────────────────────────────────────────
# 刷任务模式
# ──────────────────────────────────────────────

async def mode_tasks(client, config, log, progress, status, courses, monitor):
    """刷任务模式 - 完成指定任务"""
    data_mgr = DataManager(client.page, config, log)
    log.info("🎯 模式: 刷任务")
    status.set_status("scanning tasks")
    
    # 获取任务列表
    tasks = await data_mgr.fetch_tasks()
    
    if not tasks:
        log.warn("⚠️ 未找到任务")
        return
    
    log.info(f"📚 共 {len(tasks)} 个任务")
    
    # 获取 auth token（用于后续 API 调用）
    import json
    token_str = await client.page.evaluate("() => localStorage.getItem('token') || ''")
    try:
        token_data = json.loads(token_str) if token_str else {}
    except:
        token_data = {}
    access_token = token_data.get('access_token', '')
    
    if not access_token:
        log.warn("⚠️ 无法获取 auth token")
        return
    
    try:
        
        completed_tasks = 0
        for i, task in enumerate(tasks, 1):
            task_id = task.get("task_id", "")
            task_name = task.get("name", "未知任务")
            task_status = task.get("status", "未知")
            business_id = task.get("business_id", "")
            business_type = task.get("business_type", "未知")
            
            if task_status == "已完成":
                log.info(f"  ✅ 已完成: {task_name[:50]}")
                continue
            
            if task_status == "已过期":
                log.info(f"  ⏰ 已过期: {task_name[:50]}")
                continue
            
            log.info(f"\n📋 任务 {i}/{len(tasks)}: {task_name[:50]} (类型: {business_type})")
            status.set_status(f"task {i}/{len(tasks)}")
            
            try:
                # 根据任务类型处理
                if business_type == "专题":
                    # 专题任务：导航到专题页面获取课程
                    topic_url = f"https://mooc.ctt.cn/#/study/subject/detail/{business_id}"
                    log.info(f"  📚 进入专题: {topic_url[:60]}")
                    await client.page.goto(topic_url, wait_until="domcontentloaded", timeout=30000)
                    await client.page.wait_for_timeout(3000)
                    
                    # 获取专题内的课程
                    task_courses = await courses.get_subject_courses()
                elif business_type == "考试":
                    log.info(f"  📝 考试任务，跳过")
                    continue
                elif business_type == "直播":
                    log.info(f"  📺 直播任务，跳过")
                    continue
                else:
                    log.info(f"  ❓ 未知任务类型: {business_type}，跳过")
                    continue
                
                if not task_courses:
                    log.info(f"  ⚠️ 任务无关联课程")
                    continue
                
                log.info(f"  📚 任务包含 {len(task_courses)} 门课程")
                
                # 播放任务内的课程
                for j, course in enumerate(task_courses, 1):
                    course_id = course.get("resource_id", "")
                    course_name = course.get("title", "未知课程")
                    
                    if progress.is_course_completed(course_id):
                        log.info(f"  ✅ 已完成: {course_name[:40]}")
                        continue
                    
                    log.info(f"  🎬 {j}/{len(task_courses)}: {course_name[:40]}")
                    status.set_video(course_name, "")
                    
                    # 构造课程 URL
                    course_url = f"https://mooc.ctt.cn/#/study/course/detail/{course_id}"
                    
                    try:
                        await client.page.goto(course_url, wait_until="domcontentloaded", timeout=30000)
                        await client.page.wait_for_timeout(5000)
                        await enforce_single_tab(client.page, log)
                        
                        player = VideoPlayer(client.page, config, log, progress, status)
                        await player.setup()
                        monitor._video_playing = True
                        success = await player.play_and_wait()
                        monitor._video_playing = False
                        
                        if success:
                            progress.mark_course_completed(course_id)
                            log.info(f"  ✅ 完成")
                        
                    except Exception as e:
                        monitor._video_playing = False
                        log.warn(f"  ❌ 失败: {e}")
                    
                    await asyncio.sleep(2)
                
                completed_tasks += 1
                log.info(f"  ✅ 任务完成")
                
            except Exception as e:
                log.warn(f"  ❌ 任务处理失败: {e}")
            
            await asyncio.sleep(2)
        
        log.info(f"\n🎉 完成 {completed_tasks}/{len(tasks)} 个任务")
        
    except Exception as e:
        log.error(f"❌ 获取任务列表失败: {e}")


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="烟草网络学院 - 全自动学习系统")
    parser.add_argument("--mode", choices=["hours", "topics", "courses", "tasks"],
                        default=None, help="运行模式 (默认: 交互式选择)")
    parser.add_argument("--target", type=float, default=None, help="目标学时")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    args = parser.parse_args()

    config = Config(headless=args.headless, target_hours=args.target or 0)
    log = Logger(config.log_file)
    progress = ProgressManager(config, log)
    status = StatusReporter(config.output_dir)

    log.info("🚀 烟草网络学院 - 自动学习系统")
    log.info("=" * 50)

    # 单实例检查
    if not check_single_instance(log):
        return

    try:
        # 登录
        client, success, qr_paths = await login_flow(config, log)
        if not success:
            log.error("❌ 登录失败")
            return

        # 初始化课程管理
        courses = CourseManager(client.page, config, log, progress)
        courses.setup_api_interceptor()

        # 登录后立即获取全部数据（任务、专题、课程、学时）
        data_mgr = DataManager(client.page, config, log)
        all_data = await data_mgr.fetch_all()

        # 初始化监控
        monitor = StudyMonitor(client.page, config, log, progress)
        monitor.setup_api_interceptor()

        # ── 交互式目标选择（除非 CLI 已指定 --mode）──
        mode = args.mode
        target_hours = args.target

        if mode is None:
            # 展示数据看板
            show_user_dashboard(all_data)
            # 询问目标
            goal = ask_user_goal(all_data)
            if goal is None:
                log.info("👋 用户退出")
                return
            mode, target_hours = goal
            config.target_hours = target_hours
            log.info(f"📌 模式: {mode}")
            if target_hours and target_hours != float("inf"):
                log.info(f"🎯 目标: {target_hours}h")

        # 根据模式运行
        if mode == "hours":
            await mode_hours(client, config, log, progress, status, courses, monitor)
        elif mode == "topics":
            await mode_topics(client, config, log, progress, status, courses, monitor)
        elif mode == "courses":
            await mode_courses(client, config, log, progress, status, courses, monitor)
        elif mode == "tasks":
            await mode_tasks(client, config, log, progress, status, courses, monitor)

    except KeyboardInterrupt:
        log.info("\n⏹️ 用户中断")
    except Exception as e:
        log.error(f"❌ 异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 保存进度
        progress.save_progress()
        progress.save_study_time()
        # 关闭浏览器
        try:
            await client.close()
        except Exception:
            pass
        release_lock()
        log.info("👋 程序退出")


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", category=ResourceWarning)
    asyncio.run(main())

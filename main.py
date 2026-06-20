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

from __future__ import annotations

import argparse
import asyncio
import warnings
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from cttc.config import Config
from cttc.course import CourseManager
from cttc.data_manager import DataManager
from cttc.logger import Logger
from cttc.login import CTTCLogin
from cttc.modes import mode_courses, mode_hours, mode_tasks, mode_topics
from cttc.monitor import StudyMonitor
from cttc.process_manager import check_single_instance, release_lock
from cttc.progress import ProgressManager
from cttc.status import StatusReporter
from cttc.ui import ask_user_goal, show_user_dashboard

if TYPE_CHECKING:
    pass


# ──────────────────────────────────────────────
# 登录流程
# ──────────────────────────────────────────────

async def login_flow(
    config: Config,
    log: Logger,
) -> tuple[CTTCLogin, bool, dict[str, str | None]]:
    """完整登录流程

    Args:
        config: 配置对象
        log: 日志记录器

    Returns:
        (client, success, qr_paths)
    """
    client = CTTCLogin(config, log)
    await client.start()
    qr_paths: dict[str, str | None] = {"app": None, "wechat": None}

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

    # 4. 等待登录（无限等待，直到扫码成功）
    success = await client.wait_for_login(timeout=0)

    if success:
        log.info("🎉 登录成功！")
        await client.page.wait_for_timeout(2000)
        await client._save_state()
        # 写入信号文件供 Agent 监控
        signal_file = Path(config.output_dir) / "login-success.txt"
        signal_file.write_text(f"success\n{datetime.now().isoformat()}")
        return client, True, qr_paths
    else:
        log.error("❌ 登录超时")
        await client.close()
        return client, False, qr_paths


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────

async def main() -> None:
    """主入口函数"""
    parser = argparse.ArgumentParser(description="烟草网络学院 - 全自动学习系统")
    parser.add_argument(
        "--mode",
        choices=["hours", "topics", "courses", "tasks"],
        default=None,
        help="运行模式 (默认: 交互式选择)",
    )
    parser.add_argument("--target", type=float, default=None, help="目标学时")
    parser.add_argument("--unlimited", action="store_true", help="无限制模式（跳过目标检查）")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    args = parser.parse_args()

    config = Config(headless=args.headless, target_hours=args.target or 0, unlimited=args.unlimited)
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

        # 登录后立即获取全部数据
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
        mode_handlers = {
            "hours": mode_hours,
            "topics": mode_topics,
            "courses": mode_courses,
            "tasks": mode_tasks,
        }
        handler = mode_handlers.get(mode)
        if handler:
            await handler(client, config, log, progress, status, courses, monitor)

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
    warnings.filterwarnings("ignore", category=ResourceWarning)
    asyncio.run(main())

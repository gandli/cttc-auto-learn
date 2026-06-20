"""全站课程结构分析爬虫

使用 Playwright 登录后，通过 API 和 DOM 爬取全站课程结构，
生成统计报告和数据文件。

用法：
  uv run python scripts/crawl_site.py           # 交互式登录
  uv run python scripts/crawl_site.py --headless # 无头模式（需已有凭证）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from cttc.api import (
    API_COURSE_DETAIL,
    API_COURSES,
    API_STUDY_STATS,
    API_TASKS,
)
from cttc.config import Config
from cttc.data_manager import DataManager
from cttc.logger import Logger
from cttc.login import CTTCLogin


# ──────────────────────────────────────
# 爬虫主逻辑
# ──────────────────────────────────────


async def crawl_site(config: Config, log: Logger):
    """爬取全站课程结构"""

    # 1. 登录
    log.info("🔐 登录中...")
    client = CTTCLogin(config, log)
    await client.setup()

    # 尝试复用凭证
    if config.state_file.exists():
        log.info(f"🍪 发现已保存的凭证: {config.state_file.name}")
        try:
            await client._ctx.add_cookies(json.loads(config.state_file.read_text("utf-8")).get("cookies", []))
            await client.page.goto(config.base_url, wait_until="domcontentloaded", timeout=15000)
            await client.page.wait_for_timeout(3000)
            if await client.is_logged_in():
                log.info("✅ 凭证有效")
            else:
                log.warn("⚠️ 凭证过期，需要重新登录")
                client, success, _ = await _login_flow(config, log)
                if not success:
                    return
        except Exception:
            client, success, _ = await _login_flow(config, log)
            if not success:
                return
    else:
        client, success, _ = await _login_flow(config, log)
        if not success:
            return

    page = client.page
    data_mgr = DataManager(page, config, log)

    results = {
        "crawled_at": datetime.now().isoformat(),
        "base_url": config.base_url,
    }

    # 2. 获取我的课程（含全部分页）
    log.info("\n" + "=" * 60)
    log.info("📖 [1/5] 获取我的课程（全部分页）...")
    courses = await data_mgr._fetch_courses_api()
    if not courses:
        courses = await data_mgr._fetch_courses_dom()

    if courses:
        completed = sum(1 for c in courses if c["status"] == "已完成")
        in_progress = sum(1 for c in courses if c["status"] == "学习中")
        not_started = sum(1 for c in courses if c["status"] == "未开始")
        required = sum(1 for c in courses if c.get("required") == "必修")
        elective = len(courses) - required

        results["my_courses"] = {
            "total": len(courses),
            "completed": completed,
            "in_progress": in_progress,
            "not_started": not_started,
            "required": required,
            "elective": elective,
        }
        log.info(f"  📊 共 {len(courses)} 门 | ✅{completed} 🔄{in_progress} ⏳{not_started}")
        log.info(f"  📊 必修 {required} 门 | 选修 {elective} 门")

        # 按状态分类保存
        _save_json(config.output_dir / "crawl" / "courses_all.json", {
            "total": len(courses),
            "items": courses,
        })
    else:
        log.warn("  ⚠️ 未获取到课程数据")

    # 3. 获取我的任务
    log.info("\n📋 [2/5] 获取我的任务...")
    tasks = await data_mgr.fetch_tasks()
    if tasks:
        in_progress = sum(1 for t in tasks if t.get("status") == "进行中")
        completed = sum(1 for t in tasks if t.get("status") == "已完成")
        results["tasks"] = {
            "total": len(tasks),
            "in_progress": in_progress,
            "completed": completed,
        }
        log.info(f"  📊 共 {len(tasks)} 个 | 🔄{in_progress} ✅{completed}")
        _save_json(config.output_dir / "crawl" / "tasks.json", {
            "total": len(tasks),
            "items": tasks,
        })

    # 4. 获取我的专题
    log.info("\n📚 [3/5] 获取我的专题...")
    topics = await data_mgr.fetch_topics()
    if topics:
        total_topic_courses = sum(t.get("course_count", 0) for t in topics)
        results["topics"] = {
            "total": len(topics),
            "total_courses": total_topic_courses,
        }
        log.info(f"  📊 共 {len(topics)} 个专题 | {total_topic_courses} 门课程")
        _save_json(config.output_dir / "crawl" / "topics.json", {
            "total": len(topics),
            "items": topics,
        })

    # 5. 获取学时统计
    log.info("\n📊 [4/5] 获取学时统计...")
    stats = await data_mgr.fetch_study_stats()
    if stats:
        results["study_stats"] = stats
        online = stats.get("online_completed", 0)
        online_target = stats.get("online_target", 0)
        classroom = stats.get("classroom_completed", 0)
        classroom_target = stats.get("classroom_target", 0)
        log.info(f"  📊 网络自学: {online}/{online_target} 小时")
        log.info(f"  📊 集中培训: {classroom}/{classroom_target} 小时")
        _save_json(config.output_dir / "crawl" / "study_stats.json", stats)

    # 6. 分析课程详情（抽样前 20 门课程获取详细信息）
    log.info("\n🔍 [5/5] 抽样分析课程详情（前 20 门）...")
    sample_details = []
    if courses:
        sample = courses[:20]
        for i, course in enumerate(sample, 1):
            cid = course.get("course_id", "")
            if not cid:
                continue
            try:
                token = await data_mgr._get_token()
                if not token:
                    break
                detail = await data_mgr._api_get(f"{API_COURSE_DETAIL}/{cid}")
                if detail:
                    sections = detail.get("sectionList", [])
                    video_count = sum(
                        1 for s in sections
                        for item in s.get("sectionItems", [])
                        if item.get("sectionItemType") == "13"
                    )
                    total_duration = sum(
                        item.get("totalTime", 0)
                        for s in sections
                        for item in s.get("sectionItems", [])
                    )
                    sample_details.append({
                        "course_id": cid,
                        "title": course.get("title", ""),
                        "sections": len(sections),
                        "video_count": video_count,
                        "total_duration_min": round(total_duration / 60, 1),
                    })
                    log.info(f"  [{i}/{len(sample)}] {course.get('title', '')[:30]} — {len(sections)} 章节, {video_count} 视频")
                await asyncio.sleep(0.5)  # 限速
            except Exception as e:
                log.warn(f"  ⚠️ 获取详情失败: {e}")

    if sample_details:
        results["sample_details"] = sample_details
        _save_json(config.output_dir / "crawl" / "course_details_sample.json", sample_details)

    # 7. 生成汇总报告
    report = _generate_report(results)
    report_path = config.output_dir / "crawl" / "REPORT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    log.info(f"\n📄 报告已保存: {report_path.relative_to(Path.cwd())}")

    # 保存完整结果
    _save_json(config.output_dir / "crawl" / "full_results.json", results)
    log.info(f"📁 数据已保存到: {config.output_dir / 'crawl'}")

    # 8. 打印报告
    print("\n" + report)

    await client.close()


# ──────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────


async def _login_flow(config, log):
    """登录流程"""
    from main import login_flow
    return await login_flow(config, log)


def _save_json(path: Path, data):
    """保存 JSON 文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _generate_report(results: dict) -> str:
    """生成 Markdown 报告"""
    lines = [
        "# 烟草网络学院 — 全站课程结构分析报告",
        "",
        f"> 生成时间：{results.get('crawled_at', 'N/A')}",
        f"> 网站地址：{results.get('base_url', 'N/A')}",
        "",
        "---",
        "",
        "## 📊 总览",
        "",
    ]

    # 课程统计
    mc = results.get("my_courses", {})
    if mc:
        lines.extend([
            "### 我的课程",
            "",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 总课程数 | **{mc.get('total', 0)}** 门 |",
            f"| ✅ 已完成 | {mc.get('completed', 0)} 门 |",
            f"| 🔄 学习中 | {mc.get('in_progress', 0)} 门 |",
            f"| ⏳ 未开始 | {mc.get('not_started', 0)} 门 |",
            f"| 📌 必修 | {mc.get('required', 0)} 门 |",
            f"| 📎 选修 | {mc.get('elective', 0)} 门 |",
            "",
        ])

    # 任务统计
    tasks = results.get("tasks", {})
    if tasks:
        lines.extend([
            "### 我的任务",
            "",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 总任务数 | **{tasks.get('total', 0)}** 个 |",
            f"| 🔄 进行中 | {tasks.get('in_progress', 0)} 个 |",
            f"| ✅ 已完成 | {tasks.get('completed', 0)} 个 |",
            "",
        ])

    # 专题统计
    topics = results.get("topics", {})
    if topics:
        lines.extend([
            "### 我的专题",
            "",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 总专题数 | **{topics.get('total', 0)}** 个 |",
            f"| 包含课程 | {topics.get('total_courses', 0)} 门 |",
            "",
        ])

    # 学时统计
    ss = results.get("study_stats", {})
    if ss:
        online = ss.get("online_completed", 0)
        online_target = ss.get("online_target", 0)
        classroom = ss.get("classroom_completed", 0)
        classroom_target = ss.get("classroom_target", 0)
        online_pct = f"({online / online_target * 100:.1f}%)" if online_target else ""
        classroom_pct = f"({classroom / classroom_target * 100:.1f}%)" if classroom_target else ""
        lines.extend([
            "### 学时统计",
            "",
            f"| 项目 | 已完成 | 目标 | 完成率 |",
            f"|------|--------|------|--------|",
            f"| 网络自学 | {online}h | {online_target}h | {online_pct} |",
            f"| 集中培训 | {classroom}h | {classroom_target}h | {classroom_pct} |",
            "",
        ])

    # 课程详情抽样
    details = results.get("sample_details", [])
    if details:
        total_sections = sum(d.get("sections", 0) for d in details)
        total_videos = sum(d.get("video_count", 0) for d in details)
        total_dur = sum(d.get("total_duration_min", 0) for d in details)
        avg_sections = total_sections / len(details) if details else 0
        avg_videos = total_videos / len(details) if details else 0
        avg_dur = total_dur / len(details) if details else 0

        lines.extend([
            "### 课程详情抽样（前 20 门）",
            "",
            f"| 指标 | 平均值 |",
            f"|------|--------|",
            f"| 章节数 | {avg_sections:.1f} |",
            f"| 视频数 | {avg_videos:.1f} |",
            f"| 总时长 | {avg_dur:.1f} 分钟 |",
            "",
        ])

        # 最长课程 TOP 5
        sorted_by_dur = sorted(details, key=lambda x: x.get("total_duration_min", 0), reverse=True)[:5]
        if sorted_by_dur:
            lines.extend([
                "#### ⏱️ 最长课程 TOP 5",
                "",
                "| 排名 | 课程名称 | 视频数 | 时长 |",
                "|------|----------|--------|------|",
            ])
            for i, d in enumerate(sorted_by_dur, 1):
                lines.append(f"| {i} | {d.get('title', '')[:30]} | {d.get('video_count', 0)} | {d.get('total_duration_min', 0):.0f}分钟 |")
            lines.append("")

    # 数据文件说明
    lines.extend([
        "---",
        "",
        "## 📁 数据文件",
        "",
        "| 文件 | 说明 |",
        "|------|------|",
        "| `crawl/full_results.json` | 完整分析结果 |",
        "| `crawl/courses_all.json` | 全部课程列表 |",
        "| `crawl/tasks.json` | 任务列表 |",
        "| `crawl/topics.json` | 专题列表 |",
        "| `crawl/study_stats.json` | 学时统计 |",
        "| `crawl/course_details_sample.json` | 课程详情抽样 |",
        "| `crawl/REPORT.md` | 本报告 |",
        "",
        "---",
        "",
        "*报告由 cttc-auto-learn 自动生成*",
    ])

    return "\n".join(lines)


# ──────────────────────────────────────
# 入口
# ──────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="烟草网络学院 - 全站课程结构分析")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    args = parser.parse_args()

    config = Config(headless=args.headless)
    log = Logger(config.log_file)

    asyncio.run(crawl_site(config, log))


if __name__ == "__main__":
    main()

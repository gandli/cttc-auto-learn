"""实时监控脚本 — 读取 output/status.json 并持续刷新显示

用法: uv run python scripts/monitor.py
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

STATUS_FILE = Path("output/status.json")


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m}m"


def progress_bar(value: float, width: int = 30) -> str:
    filled = int(width * value / 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {value:.1f}%"


def main():
    print("🔍 cttc-auto-learn 实时监控")
    print("   按 Ctrl+C 退出\n")

    last_update = ""
    while True:
        try:
            if STATUS_FILE.exists():
                data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            else:
                print("⏳ 等待脚本启动...")
                time.sleep(2)
                continue

            updated = data.get("updated_at", "")
            if updated == last_update:
                time.sleep(3)
                continue
            last_update = updated

            clear()

            status = data.get("status", "unknown")
            uptime = format_duration(data.get("uptime_seconds", 0))
            now = datetime.now().strftime("%H:%M:%S")

            # 状态图标
            status_icons = {
                "running": "🟢",
                "playing": "▶️",
                "stalled": "⚠️",
                "recovering": "🔄",
                "completed": "✅",
                "error": "❌",
                "initializing": "⏳",
            }
            icon = status_icons.get(status, "❓")

            print(f"┌─────────────────────────────────────────────────┐")
            print(f"│  🎓 cttc-auto-learn 实时监控                    │")
            print(f"│  {icon} 状态: {status:<20} ⏱️ 运行: {uptime:<10} │")
            print(f"├─────────────────────────────────────────────────┤")

            # 学时
            hours_cur = data.get("study_hours_current", 0)
            hours_target = data.get("study_hours_target", 0)
            hours_pct = (hours_cur / hours_target * 100) if hours_target > 0 else 0
            print(f"│  📊 学时: {hours_cur:.1f}/{hours_target:.1f}h {progress_bar(hours_pct, 20)} │")

            # 课程
            completed = data.get("courses_completed", 0)
            pending = data.get("courses_pending", 0)
            total = data.get("courses_total", 0)
            print(f"│  📚 课程: {completed} 完成 / {pending} 待学 / {total} 总计      │")

            print(f"├─────────────────────────────────────────────────┤")

            # 当前视频
            video_title = data.get("current_video", "无")
            video_pct = data.get("video_progress", 0)
            video_cur = data.get("video_current_time", 0)
            video_dur = data.get("video_duration", 0)
            api_rate = data.get("api_completed_rate", 0)
            api_finish = data.get("api_finish_status", 0)
            api_loc = data.get("api_lesson_location", 0)
            api_remain = data.get("api_remaining_time", 0)

            print(f"│  🎬 视频: {video_title[:38]:<38} │")
            print(f"│  📈 DOM 进度: {progress_bar(video_pct, 20):<36} │")
            print(f"│     {int(video_cur)}s / {int(video_dur)}s ({int(video_cur//60)}/{int(video_dur//60)} 分钟)                     │")
            print(f"│  📡 API 进度: {api_rate}% | loc={api_loc}s | remain={api_remain}s   │")
            print(f"│     finishStatus={api_finish}                                    │")

            print(f"├─────────────────────────────────────────────────┤")

            # 错误统计
            errors = data.get("errors_count", 0)
            repairs = data.get("stall_repairs", 0)
            last_err = data.get("last_error", "")
            last_api = data.get("last_api_time", "")

            print(f"│  ❌ 错误: {errors} 次 | 🔧 停滞修复: {repairs} 次              │")
            if last_err:
                print(f"│  ⚠️ 最近错误: {last_err[:37]:<37} │")
            if last_api:
                print(f"│  📡 最近 API: {last_api[:37]:<37} │")

            print(f"└─────────────────────────────────────────────────┘")
            print(f"\n  更新于 {updated[:19]} | 刷新间隔 3s")

            time.sleep(3)

        except KeyboardInterrupt:
            print("\n\n👋 监控已退出")
            break
        except json.JSONDecodeError:
            time.sleep(2)
        except Exception as e:
            print(f"错误: {e}")
            time.sleep(3)


if __name__ == "__main__":
    main()

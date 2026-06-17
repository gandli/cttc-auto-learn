"""
数据管理模块 - 登录后自动获取任务、专题、课程数据，运行中定时更新

API 优先，DOM 托底。数据保存到 data/ 目录。
"""
import json
import time
from pathlib import Path
from typing import Optional

from playwright.async_api import Page

from cttc.config import Config
from cttc.logger import Logger
from cttc.api import (
    API_COURSES, API_TASKS, API_TASK_CALENDAR,
    API_STUDY_STATS, API_CADRE_STATS
)
from cttc.selectors import (
    SELECTOR_COURSE_LINK, SELECTOR_TOPIC_LINK,
    SELECTOR_ACTION_BUTTON, SELECTOR_TASK_ITEM,
    SELECTOR_CREDIT_LABEL, SELECTOR_NAV_ITEMS
)


class DataManager:
    """统一管理任务、专题、课程数据的获取和缓存"""

    def __init__(self, page: Page, config: Config, log: Logger):
        self.page = page
        self.config = config
        self.log = log
        self._token: str = ""
        self._data_dir = Path(config.output_dir).parent / "data"
        self._data_dir.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────
    # Token 管理
    # ──────────────────────────────────────

    async def _get_token(self) -> str:
        """获取 auth token（缓存）"""
        if self._token:
            return self._token
        token_str = await self.page.evaluate("() => localStorage.getItem('token') || ''")
        try:
            token_data = json.loads(token_str) if token_str else {}
        except Exception:
            token_data = {}
        self._token = token_data.get("access_token", "")
        return self._token

    async def _api_get(self, url: str) -> Optional[dict]:
        """API GET 请求，失败返回 None"""
        token = await self._get_token()
        if not token:
            return None
        try:
            data = await self.page.evaluate(f"""async () => {{
                const resp = await fetch('{url}', {{
                    headers: {{
                        'Authorization': 'Bearer__{token}',
                        'X-Requested-With': 'XMLHttpRequest'
                    }}
                }});
                if (!resp.ok) return null;
                const ct = resp.headers.get('content-type') || '';
                if (!ct.includes('json')) return null;
                return await resp.json();
            }}""")
            return data
        except Exception:
            return None

    def _save_json(self, filename: str, data: dict | list):
        """保存 JSON 到 data/ 目录"""
        path = self._data_dir / filename
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_json(self, filename: str) -> Optional[dict | list]:
        """从 data/ 目录加载 JSON"""
        path = self._data_dir / filename
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    # ──────────────────────────────────────
    # 我的课程（API 优先）
    # ──────────────────────────────────────

    async def fetch_courses(self, status_filter: str = "all") -> list[dict]:
        """获取我的课程列表

        status_filter: 'all', 'in_progress', 'not_started', 'completed'
        """
        self.log.info("📖 获取我的课程...")
        courses = await self._fetch_courses_api()
        method = "API"

        if not courses:
            courses = await self._fetch_courses_dom()
            method = "DOM"

        if courses:
            # 统计
            completed = sum(1 for c in courses if c["status"] == "已完成")
            in_progress = sum(1 for c in courses if c["status"] == "学习中")
            not_started = sum(1 for c in courses if c["status"] == "未开始")
            self.log.info(f"  📊 共 {len(courses)} 门 | ✅{completed} 🔄{in_progress} ⏳{not_started} (来源: {method})")

            # 保存完整数据
            self._save_json("courses.json", {
                "updated_at": int(time.time() * 1000),
                "total": len(courses),
                "completed": completed,
                "in_progress": in_progress,
                "not_started": not_started,
                "source": method,
                "items": courses,
            })

        if status_filter != "all" and courses:
            filter_map = {
                "in_progress": "学习中",
                "not_started": "未开始",
                "completed": "已完成",
            }
            target = filter_map.get(status_filter, status_filter)
            courses = [c for c in courses if c["status"] == target]

        return courses or []

    async def _fetch_courses_api(self) -> list[dict]:
        """API 方式获取课程"""
        token = await self._get_token()
        if not token:
            return []

        all_courses = []
        for page_num in range(1, 11):
            data = await self._api_get(
                f"{API_COURSES}"
                f"?businessType=0&findStudy=0&studyTimeOrder=desc&page={page_num}&pageSize=50"
            )
            if not data:
                break
            items = data.get("items", [])
            if not items:
                break

            for item in items:
                course_id = item.get("courseId", "")
                name = item.get("courseInfo", {}).get("name", "")
                finish_status = item.get("finishStatus", 0)
                study_time = item.get("studyTotalTime", 0)
                total_time = item.get("courseInfo", {}).get("totalTime", 0)
                is_required = item.get("isRequired", 0)

                status_map = {0: "未开始", 1: "学习中", 2: "已完成"}
                status = status_map.get(finish_status, "未知")

                all_courses.append({
                    "title": name,
                    "course_id": course_id,
                    "status": status,
                    "required": "必修" if is_required == 1 else "选修",
                    "study_min": round(study_time / 60, 1) if study_time else 0,
                    "total_min": round(total_time / 60, 1) if total_time else 0,
                    "pct": f"{study_time / total_time * 100:.1f}%" if total_time and study_time else "0%",
                    "url": self.config.course_detail_url(course_id),
                })

            if len(items) < 50:
                break

        return all_courses

    async def _fetch_courses_dom(self) -> list[dict]:
        """DOM 方式获取课程（托底）"""
        await self.page.goto(
            self.config.learning_center_url,
            wait_until="domcontentloaded",
            timeout=self.config.page_timeout
        )
        await self.page.wait_for_timeout(self.config.medium_wait)

        # 点击"我的学习"
        await self.page.evaluate(f"""() => {{
            for (const el of document.querySelectorAll('{SELECTOR_NAV_ITEMS}')) {{
                if ((el.textContent || '').trim() === '我的学习') {{ el.click(); break; }}
            }}
        }}""")
        await self.page.wait_for_timeout(self.config.short_wait)

        # 点击"我的课程"
        await self.page.evaluate(f"""() => {{
            for (const el of document.querySelectorAll('{SELECTOR_NAV_ITEMS}')) {{
                if ((el.textContent || '').trim() === '我的课程') {{ el.click(); break; }}
            }}
        }}""")
        await self.page.wait_for_timeout(self.config.long_wait)

        courses = await self.page.evaluate(f"""() => {{
            const results = [];
            const seen = new Set();
            document.querySelectorAll('{SELECTOR_COURSE_LINK}').forEach(link => {{
                const href = link.href || '';
                const item = link.closest('.item') || link.parentElement;
                const text = (item?.textContent || '').trim().replace(/\\s+/g, ' ');
                const match = href.match(/course\\/detail\\/\\d+&([a-f0-9-]+)/);
                if (!match || seen.has(match[1])) return;
                seen.add(match[1]);
                let status = text.includes('已完成') ? '已完成' : text.includes('未开始') ? '未开始' : '学习中';
                let title = text.replace(/必修|选修|学习中|未开始|已完成|开始学习|继续学习|复习|上次学习时间：[^\\s]*/g, '').trim().replace(/\\s+/g, ' ');
                results.push({{
                    title: title.substring(0, 100), course_id: match[1], status,
                    required: text.includes('选修') ? '选修' : '必修',
                    study_min: 0, total_min: 0, pct: "0%",
                    url: '{self.config.base_url}/#/study/course/detail/{self.config.section_type}&' + match[1],
                }});
            }});
            return results;
        }}""")

        return courses

    # ──────────────────────────────────────
    # 我的专题（DOM 获取，无 API）
    # ──────────────────────────────────────

    async def fetch_topics(self) -> list[dict]:
        """获取专题列表及专题内课程"""
        self.log.info("📚 获取我的专题...")
        topics = await self._fetch_topics_dom()

        if topics:
            self.log.info(f"  📊 共 {len(topics)} 个专题")
            # 获取每个专题内的课程
            for topic in topics:
                try:
                    topic_courses = await self._fetch_topic_courses_dom(topic["href"])
                    topic["courses"] = topic_courses
                    done = sum(1 for c in topic_courses if c["status"] == "已完成")
                    prog = sum(1 for c in topic_courses if c["status"] == "学习中")
                    self.log.info(f"  📖 {topic['title'][:40]} | {len(topic_courses)}门 ✅{done} 🔄{prog}")
                except Exception as e:
                    topic["courses"] = []
                    self.log.warn(f"  ⚠️ {topic['title'][:30]} 获取课程失败: {e}")

            # 保存
            self._save_json("topics.json", {
                "updated_at": int(time.time() * 1000),
                "total": len(topics),
                "source": "DOM",
                "items": topics,
            })

        return topics or []

    async def _fetch_topics_dom(self) -> list[dict]:
        """DOM 方式获取专题列表"""
        await self.page.goto(
            self.config.learning_center_url,
            wait_until="domcontentloaded",
            timeout=self.config.page_timeout
        )
        await self.page.wait_for_timeout(self.config.medium_wait)

        # 点击"专题"
        await self.page.evaluate(f"""() => {{
            for (const el of document.querySelectorAll('{SELECTOR_NAV_ITEMS}')) {{
                if (el.textContent?.trim() === '专题') {{ el.click(); return true; }}
            }}
        }}""")
        await self.page.wait_for_timeout(self.config.long_wait)

        topics = await self.page.evaluate(f"""() => {{
            const results = [];
            const seen = new Set();
            document.querySelectorAll('{SELECTOR_TOPIC_LINK}').forEach(el => {{
                const href = el.href || '';
                const text = (el.textContent || '').trim().replace(/\\s+/g, ' ');
                if (href && !href.includes('javascript:') && text.length > 5 && text.length < 200) {{
                    if (seen.has(href)) return;
                    seen.add(href);
                    results.push({{ title: text.substring(0, 150), href }});
                }}
            }});
            return results;
        }}""")

        return topics

    async def _fetch_topic_courses_dom(self, topic_href: str) -> list[dict]:
        """DOM 方式获取专题内的课程"""
        await self.page.goto(topic_href, wait_until="domcontentloaded", timeout=self.config.page_timeout)
        await self.page.wait_for_timeout(self.config.medium_wait)

        courses = await self.page.evaluate(f"""() => {{
            const results = [];
            const seen = new Set();
            const buttons = document.querySelectorAll('{SELECTOR_ACTION_BUTTON}');
            for (const btn of buttons) {{
                const btnText = (btn.textContent || '').trim();
                if (!['继续学习', '复习', '开始学习'].some(k => btnText.includes(k))) continue;
                let item = btn.closest('.item.current-hover') || btn.closest('.item');
                if (!item) continue;
                const fullText = (item.textContent || '').trim().replace(/\\s+/g, ' ');
                const tags = fullText.match(/\\[(必修|选修)\\]/g);
                if (!tags || tags.length !== 1) continue;
                if (fullText.length < 10 || fullText.length > 200) continue;
                let title = fullText.replace(/课程\\s*/g, '').replace(/\\[必修\\]/g, '').replace(/\\[选修\\]/g, '')
                    .replace(/继续学习/g, '').replace(/复习/g, '').replace(/开始学习/g, '')
                    .trim().replace(/\\s+/g, ' ');
                if (title.length < 2 || seen.has(title)) continue;
                seen.add(title);
                let status = '未知';
                if (btnText.includes('复习')) status = '已完成';
                else if (btnText.includes('继续学习')) status = '学习中';
                else if (btnText.includes('开始学习')) status = '未开始';
                results.push({{ title, status, required: fullText.includes('选修') ? '选修' : '必修' }});
            }}
            return results.slice(0, 30);
        }}""")

        return courses

    # ──────────────────────────────────────
    # 我的任务（API 优先）
    # ──────────────────────────────────────

    async def fetch_tasks(self) -> list[dict]:
        """获取我的任务列表"""
        self.log.info("📋 获取我的任务...")
        tasks = await self._fetch_tasks_api()
        method = "API"

        if not tasks:
            tasks = await self._fetch_tasks_dom()
            method = "DOM"

        if tasks:
            active = sum(1 for t in tasks if t["status"] == "进行中")
            done = sum(1 for t in tasks if t["status"] == "已完成")
            self.log.info(f"  📊 共 {len(tasks)} 个任务 | 🔄{active} ✅{done} (来源: {method})")

            # 保存
            self._save_json("tasks.json", {
                "updated_at": int(time.time() * 1000),
                "total": len(tasks),
                "active": active,
                "completed": done,
                "source": method,
                "items": tasks,
            })

        return tasks or []

    async def _fetch_tasks_api(self) -> list[dict]:
        """API 方式获取任务"""
        all_tasks = []
        for page_num in range(1, 6):
            data = await self._api_get(f"{API_TASKS}?page={page_num}&pageSize=50")
            if not data:
                break
            items = data.get("items", [])
            if not items:
                break

            for item in items:
                status_map = {1: "进行中", 2: "已过期", 3: "已完成"}
                status = status_map.get(item.get("status", 0), "未知")
                if item.get("expired"):
                    status = "已过期"

                # businessType: 2=专题, 3=考试, 6=直播
                type_map = {2: "专题", 3: "考试", 6: "直播"}
                biz_type = type_map.get(item.get("businessType", 0), "其他")

                end_time = item.get("endTime", 0)
                deadline = ""
                if end_time:
                    from datetime import datetime
                    deadline = datetime.fromtimestamp(end_time / 1000).strftime("%Y-%m-%d")

                all_tasks.append({
                    "task_id": item.get("id", ""),
                    "name": item.get("name", ""),
                    "business_id": item.get("businessId", ""),
                    "business_type": biz_type,
                    "status": status,
                    "deadline": deadline,
                    "expired": item.get("expired", False),
                })

            if len(items) < 50:
                break

        return all_tasks

    async def _fetch_tasks_dom(self) -> list[dict]:
        """DOM 方式获取任务（托底）"""
        await self.page.goto(
            self.config.learning_center_url,
            wait_until="domcontentloaded",
            timeout=self.config.page_timeout
        )
        await self.page.wait_for_timeout(self.config.medium_wait)

        # 点击"我的任务"
        await self.page.evaluate(f"""() => {{
            for (const el of document.querySelectorAll('{SELECTOR_NAV_ITEMS}')) {{
                if ((el.textContent || '').trim() === '我的任务') {{ el.click(); break; }}
            }}
        }}""")
        await self.page.wait_for_timeout(self.config.long_wait)

        tasks = await self.page.evaluate(f"""() => {{
            const results = [];
            const seen = new Set();
            document.querySelectorAll('{SELECTOR_TASK_ITEM}').forEach(el => {{
                const text = (el.textContent || '').trim().replace(/\\s+/g, ' ');
                if (text.length < 5 || text.length > 200) return;
                let status = text.includes('已完成') ? '已完成' : text.includes('已过期') ? '已过期' : '进行中';
                let title = text.replace(/已完成|进行中|已过期|学习推送|截止时间：[\\s\\S]*/g, '').trim().replace(/\\s+/g, ' ');
                if (title.length < 3 || seen.has(title)) return;
                seen.add(title);
                results.push({{ name: title.substring(0, 100), status, business_type: "未知", deadline: "", task_id: "", business_id: "" }});
            }});
            return results;
        }}""")

        return tasks

    # ──────────────────────────────────────
    # 学时统计（API 优先）
    # ──────────────────────────────────────

    async def fetch_study_stats(self) -> dict:
        """获取学时统计"""
        self.log.info("📊 获取学时统计...")
        stats = await self._fetch_study_stats_api()

        if not stats:
            stats = await self._fetch_study_stats_dom()

        if stats:
            self._save_json("study_stats.json", {
                "updated_at": int(time.time() * 1000),
                **stats,
            })
            self.log.info(f"  📊 网络自学: {stats.get('online_completed', 0)}/{stats.get('online_target', 0)} 小时")
            self.log.info(f"  📊 集中培训: {stats.get('classroom_completed', 0)}/{stats.get('classroom_target', 0)} 小时")

        return stats or {}

    async def _fetch_study_stats_api(self) -> Optional[dict]:
        """API 方式获取学时"""
        data = await self._api_get(API_STUDY_STATS)
        if not data:
            return None

        if "courseHourResult" in data:
            return {
                "online_completed": data.get("courseHourResult", {}).get("totalHour", 0),
                "online_target": data.get("requireCourseHour", 0),
                "classroom_completed": data.get("totalClassHour", 0),
                "classroom_target": data.get("requireClassHour", 0),
                "total_score": data.get("totalScore", 0),
            }
        elif "hourSelf" in data:
            return {
                "online_completed": data.get("hourSelf", 0),
                "online_target": data.get("requireCourseHour", 0),
                "classroom_completed": data.get("hourTrain", 0),
                "classroom_target": data.get("requireClassHour", 0),
                "total_score": 0,
            }
        return None

    async def _fetch_study_stats_dom(self) -> Optional[dict]:
        """DOM 方式获取学时（托底）"""
        result = await self.page.evaluate(f"""() => {{
            const labels = document.querySelectorAll('{SELECTOR_CREDIT_LABEL}');
            for (const el of labels) {{
                const text = (el.textContent || '').trim();
                const m = text.match(/(\\d+\\.?\\d*)\\s*\\/\\s*(\\d+\\.?\\d*)\\s*网络自学/);
                if (m) return {{ online_completed: parseFloat(m[1]), online_target: parseFloat(m[2]) }};
            }}
            return null;
        }}""")
        return result

    # ──────────────────────────────────────
    # 一键获取全部数据
    # ──────────────────────────────────────

    async def fetch_all(self) -> dict:
        """登录后一键获取全部数据"""
        self.log.info("🔄 获取全部数据...")
        self.log.info("=" * 50)

        courses = await self.fetch_courses()
        topics = await self.fetch_topics()
        tasks = await self.fetch_tasks()
        stats = await self.fetch_study_stats()

        self.log.info("=" * 50)
        self.log.info("✅ 数据获取完成")

        return {
            "courses": courses,
            "topics": topics,
            "tasks": tasks,
            "study_stats": stats,
        }

    async def update_progress(self) -> dict:
        """运行中更新进度（轻量级，只更新学时和课程状态）"""
        self.log.info("🔄 更新进度...")

        # 只更新学时和课程状态（不重新获取专题，因为专题变化慢）
        stats = await self.fetch_study_stats()
        courses = await self.fetch_courses()

        return {
            "courses": courses,
            "study_stats": stats,
        }

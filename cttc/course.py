"""课程模块 - 课程发现、筛选、排序"""

import json
from typing import Optional
from playwright.async_api import Page

from cttc.config import Config
from cttc.logger import Logger
from cttc.progress import ProgressManager
from cttc.api import API_COURSES, API_STUDY_STATS, API_CADRE_STATS
from cttc.selectors import (
    SELECTOR_COURSE_LINK, SELECTOR_TOPIC_LINK,
    SELECTOR_ACTION_BUTTON, SELECTOR_CREDIT_LABEL,
    SELECTOR_HOUR_LABEL, SELECTOR_DIALOG_CLOSE,
    SELECTOR_NAV_ITEMS
)


class CourseManager:
    """课程发现与管理"""

    def __init__(self, page: Page, config: Config, log: Logger, progress: ProgressManager):
        self.page = page
        self.config = config
        self.log = log
        self.progress = progress

    async def get_study_time(self) -> float:
        """通过拦截 API 响应获取网络自学学时（需在页面加载后调用）"""
        if hasattr(self, '_study_stats') and self._study_stats:
            return self._study_stats.get("online_completed", 0)
        
        # 降级: DOM 解析
        result = await self.page.evaluate(f"""() => {{
            const labels = document.querySelectorAll('{SELECTOR_CREDIT_LABEL}');
            for (const el of labels) {{
                const text = (el.textContent || '').trim();
                const m = text.match(/(\\d+\\.?\\d*)\\s*\\/\\s*(\\d+\\.?\\d*)\\s*网络自学/);
                if (m) return {{ online: parseFloat(m[2]), online_target: parseFloat(m[1]) }};
            }}
            return null;
        }}""")
        if result:
            online = result.get("online", 0)
            target = result.get("online_target", 0)
            self.log.info(f"📊 网络自学: {online}/{target} 小时 ({online/target*100:.1f}%)" if target else f"📊 网络自学: {online} 小时")
            return online
        return 0

    async def get_study_stats(self) -> dict:
        """通过拦截 API 响应获取完整学时统计（需在页面加载后调用）"""
        if hasattr(self, '_study_stats') and self._study_stats:
            return self._study_stats
        
        # 降级: DOM 解析
        result = await self.page.evaluate(f"""() => {{
            const stats = {{}};
            const labels = document.querySelectorAll('{SELECTOR_CREDIT_LABEL}');
            for (const el of labels) {{
                const text = (el.textContent || '').trim();
                const m = text.match(/(\\d+\\.?\\d*)\\s*\\/\\s*(\\d+\\.?\\d*)\\s*网络自学/);
                if (m) {{ stats.online_target = parseFloat(m[1]); stats.online_completed = parseFloat(m[2]); }}
            }}
            const hourLabels = document.querySelectorAll('{SELECTOR_HOUR_LABEL}');
            for (const el of hourLabels) {{
                const text = (el.textContent || '').trim();
                const m = text.match(/(\\d+\\.?\\d*)\\s*\\/\\s*(\\d+\\.?\\d*)\\s*集中培训/);
                if (m) {{ stats.classroom_target = parseFloat(m[1]); stats.classroom_completed = parseFloat(m[2]); }}
            }}
            return stats;
        }}""")
        return result or {}

    def setup_api_interceptor(self):
        """设置 API 拦截器，在页面加载时自动捕获学时数据"""
        self._study_stats = {}
        
        async def on_response(response):
            url = response.url
            if 'credit/detail-hour-member' in url or 'cadre-education/detail-hour-member' in url:
                try:
                    data = await response.json()
                    if 'courseHourResult' in data:
                        self._study_stats = {
                            "online_completed": data.get("courseHourResult", {}).get("totalHour", 0),
                            "online_target": data.get("requireCourseHour", 0),
                            "classroom_completed": data.get("totalClassHour", 0),
                            "classroom_target": data.get("requireClassHour", 0),
                            "total_score": data.get("totalScore", 0),
                        }
                    elif 'hourSelf' in data:
                        self._study_stats = {
                            "online_completed": data.get("hourSelf", 0),
                            "online_target": data.get("requireCourseHour", 0),
                            "classroom_completed": data.get("hourTrain", 0),
                            "classroom_target": data.get("requireClassHour", 0),
                            "total_score": 0,
                        }
                except:
                    pass
        
        self.page.on("response", on_response)

    async def navigate_to_learning_center(self):
        """进入学习中心"""
        self.log.info("📍 进入学习中心...")
        # 直接导航到学习中心页面（更可靠）
        try:
            await self.page.goto(
                self.config.learning_center_url,
                wait_until="domcontentloaded",
                timeout=self.config.page_timeout
            )
        except Exception:
            # 回退：点击页面上的"学习中心"链接
            await self.page.evaluate(f"""() => {{
                for (const el of document.querySelectorAll('{SELECTOR_NAV_ITEMS}')) {{
                    if ((el.textContent || '').trim().includes('学习中心')) {{ el.click(); break; }}
                }}
            }}""")
        await self.page.wait_for_timeout(self.config.long_wait)
        # 关闭可能的弹窗
        try:
            close_btns = self.page.locator(SELECTOR_DIALOG_CLOSE)
            for i in range(await close_btns.count()):
                await close_btns.nth(i).click()
                await self.page.wait_for_timeout(self.config.short_wait // 4)
        except Exception:
            pass
        await self.page.wait_for_timeout(self.config.short_wait)

    async def get_special_topics(self) -> list[dict]:
        """获取专题课程列表"""
        self.log.info("📚 获取专题课程列表...")
        topics = await self.page.evaluate(f"""() => {{
            const results = [];
            document.querySelectorAll('{SELECTOR_TOPIC_LINK}').forEach(el => {{
                const href = el.href || '';
                const text = (el.textContent || '').trim().replace(/\\s+/g, ' ');
                if (href && !href.includes('javascript:') && text.length > 5 && text.length < 200) {{
                    results.push({{
                        title: text.substring(0, 150),
                        href: href,
                        id: href.match(/[0-9a-f-]{{36}}/)?.[0] || '',
                    }});
                }}
            }});
            const seen = new Set();
            return results.filter(r => {{
                if (seen.has(r.href)) return false;
                seen.add(r.href);
                return true;
            }});
        }}""")
        self.log.info(f"  找到 {len(topics)} 个专题")
        for t in topics:
            self.log.info(f"  - {t['title'][:60]}")
        return topics

    async def get_my_courses(self, status_filter: str = "in_progress") -> list[dict]:
        """通过 API 获取我的课程列表。
        
        status_filter: 'in_progress' (学习中), 'not_started' (未开始), 'completed' (已完成), 'all' (全部)
        """
        self.log.info("📖 通过 API 获取课程列表...")
        
        # 获取 auth token
        token_str = await self.page.evaluate("() => localStorage.getItem('token') || ''")
        try:
            token_data = json.loads(token_str) if token_str else {}
        except Exception:
            token_data = {}
        access_token = token_data.get('access_token', '')
        
        if not access_token:
            self.log.warn("⚠️ 无法获取 auth token，回退到 DOM 方式")
            return await self._get_my_courses_dom(status_filter)
        
        all_courses = []
        page_num = 1
        
        while page_num <= 10:
            data = await self.page.evaluate(f"""async () => {{
                const resp = await fetch('{API_COURSES}?businessType=0&findStudy=0&studyTimeOrder=desc&page={page_num}&pageSize=50', {{
                    headers: {{
                        'Authorization': 'Bearer__{access_token}',
                        'X-Requested-With': 'XMLHttpRequest'
                    }}
                }});
                return await resp.json();
            }}""")
            
            items = data.get("items", [])
            if not items:
                break
            
            for item in items:
                course_id = item.get("courseId", "")
                name = item.get("courseInfo", {}).get("name", "")
                finish_status = item.get("finishStatus", 0)
                study_time = item.get("studyTotalTime", 0)
                is_required = item.get("isRequired", 0)
                
                # finishStatus: 0=未开始, 1=学习中, 2=已完成
                status_map = {0: "not_started", 1: "in_progress", 2: "completed"}
                status = status_map.get(finish_status, "unknown")
                
                all_courses.append({
                    "title": name,
                    "resource_id": course_id,
                    "section_type": self.config.section_type,
                    "status": status,
                    "req": "required" if is_required == 1 else "elective",
                    "study_time": study_time,
                    "url": self.config.course_detail_url(course_id),
                })
            
            if len(items) < 50:
                break
            page_num += 1
        
        # 按状态筛选
        if status_filter != "all":
            all_courses = [c for c in all_courses if c["status"] == status_filter]
        
        self.log.info(f"  共 {len(all_courses)} 门课程 (筛选: {status_filter})")
        for c in all_courses[:10]:
            self.log.info(f"  - [{c['status']}] [{c['req']}] {c['title'][:50]}")
        if len(all_courses) > 10:
            self.log.info(f"  ... 还有 {len(all_courses) - 10} 门")
        
        return all_courses

    async def _get_my_courses_dom(self, status_filter: str) -> list[dict]:
        """DOM 回退方式获取课程（当 API token 不可用时）"""
        self.log.info("📖 通过 DOM 获取课程列表...")
        await self.navigate_to_learning_center()
        await self.page.evaluate(f"""() => {{
            for (const el of document.querySelectorAll('{SELECTOR_NAV_ITEMS}')) {{
                if ((el.textContent || '').trim() === '我的学习') {{ el.click(); break; }}
            }}
        }}""")
        await self.page.wait_for_timeout(self.config.short_wait)
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
                let status = text.includes('已完成') ? 'completed' : text.includes('未开始') ? 'not_started' : 'in_progress';
                let title = text.replace(/必修|选修|学习中|未开始|已完成|开始学习|继续学习|复习|上次学习时间：[^\\s]*/g, '').trim().replace(/\\s+/g, ' ');
                results.push({{
                    title: title.substring(0, 100), resource_id: match[1], section_type: '{self.config.section_type}',
                    status, req: text.includes('选修') ? 'elective' : 'required', study_time: 0,
                    url: '{self.config.base_url}/#/study/course/detail/{self.config.section_type}&' + match[1]
                }});
            }});
            return results;
        }}""")
        
        if status_filter != "all":
            courses = [c for c in courses if c["status"] == status_filter]
        
        self.log.info(f"  共 {len(courses)} 门课程 (DOM)")
        return courses

    async def get_subject_courses(self) -> list[dict]:
        """进入专题页面，获取课程列表。

        使用 a.normal 按钮作为锚点，从其祖先 .item.current-hover 提取课程信息。
        """
        self.log.info("📖 获取专题课程...")
        courses = await self.page.evaluate(f"""() => {{
            const results = [];
            const seen = new Set();

            // 以操作按钮为锚点
            const buttons = document.querySelectorAll('{SELECTOR_ACTION_BUTTON}');
            for (const btn of buttons) {{
                const btnText = (btn.textContent || '').trim();
                if (!['继续学习', '复习', '开始学习'].some(k => btnText.includes(k))) continue;

                // 向上找 .item.current-hover 祖先
                let item = btn.closest('.item.current-hover') || btn.closest('.item');
                if (!item) continue;

                const fullText = (item.textContent || '').trim().replace(/\\s+/g, ' ');
                // 确保只包含一门课程（文本中恰好有一个 [必修] 或 [选修]）
                const tags = fullText.match(/\\[(必修|选修)\\]/g);
                if (!tags || tags.length !== 1) continue;
                if (fullText.length < 10 || fullText.length > 200) continue;

                // 提取标题：去掉标签、课程前缀、按钮文本
                let title = fullText
                    .replace(/课程\\s*/g, '')
                    .replace(/\\[必修\\]/g, '').replace(/\\[选修\\]/g, '')
                    .replace(/继续学习/g, '').replace(/复习/g, '').replace(/开始学习/g, '')
                    .trim().replace(/\\s+/g, ' ');

                if (title.length < 2 || seen.has(title)) continue;
                seen.add(title);

                // 判断状态
                let action = 'unknown';
                if (btnText.includes('复习')) action = 'review';
                else if (btnText.includes('继续学习')) action = 'continue';
                else if (btnText.includes('开始学习')) action = 'start';

                results.push({{
                    title: title,
                    action: action,
                    status: action === 'review' ? 'completed' : 'in_progress',
                    resource_id: item.getAttribute('data-resource-id') || '',
                    section_type: item.getAttribute('data-section-type') || '10',
                }});
            }}
            return results.slice(0, 30);
        }}""")
        self.log.info(f"  找到 {len(courses)} 门课程")
        for c in courses:
            self.log.info(f"  - [{c['action']}] {c['title'][:50]}")
        return courses

    async def enter_course(self, href: str) -> bool:
        """进入课程页面"""
        if not href or href.startswith('javascript:') or not href.startswith('http'):
            self.log.warn(f"⚠️ 跳过无效链接: {href[:50] if href else '空'}")
            return False
        
        try:
            self.log.info(f"📍 进入课程: {href[:80]}")
            await self.page.goto(href, wait_until="domcontentloaded", timeout=self.config.page_timeout)
            await self.page.wait_for_timeout(self.config.medium_wait)
            return True
        except Exception as e:
            self.log.error(f"❌ 进入课程失败: {e}")
            return False

    async def click_course_action(self, course_title: str) -> Optional[Page]:
        """点击课程的操作按钮（继续学习/复习），返回新打开的页面。
        
        使用 a.normal 按钮的祖先文本匹配课程标题，然后直接点击按钮。
        """
        new_page = None
        all_popups = []
        async def on_popup(page):
            nonlocal new_page
            all_popups.append(page)
            new_page = page  # 始终指向最新的 popup
            self.log.info(f"📄 检测到新页面: {page.url[:80]}")
        
        self.page.context.on("page", on_popup)
        
        # 取标题前 25 字符用于匹配
        match_text = course_title[:25].replace("'", "\\'").replace('"', '\\"')
        
        clicked = await self.page.evaluate(f"""(matchText) => {{
            const buttons = document.querySelectorAll('{SELECTOR_ACTION_BUTTON}');
            for (const btn of buttons) {{
                const btnText = (btn.textContent || '').trim();
                if (!['继续学习', '复习', '开始学习'].some(k => btnText.includes(k))) continue;

                // 向上找到包含课程标题的祖先
                let item = btn.closest('.item.current-hover') || btn.closest('.item');
                if (!item) continue;

                const itemText = (item.textContent || '').trim().replace(/\\s+/g, ' ');
                if (!itemText.includes(matchText)) continue;
                if (!itemText.includes('[必修]') && !itemText.includes('[选修]')) continue;

                btn.click();
                return {{ found: true, action: btnText }};
            }}
            return {{ found: false }};
        }}""", match_text)
        
        if clicked and clicked.get("found"):
            action = clicked.get("action", "?")
            self.log.info(f"▶️ 点击了: {action}")
            
            # 等待所有 popup 打开（可能有 OAuth 中间页 + 最终课程页）
            for _ in range(30):
                await self.page.wait_for_timeout(1000)
                if len(all_popups) >= 2:
                    # 有两个 popup 了，再等一下看有没有更多
                    await self.page.wait_for_timeout(self.config.short_wait)
                    break
                if new_page and len(all_popups) == 1:
                    # 只有一个 popup，检查是否是 OAuth 页
                    if '/oauth/' not in new_page.url:
                        break  # 不是 OAuth，直接用
            
            self.page.context.remove_listener("page", on_popup)
            
            if new_page:
                # 关闭 OAuth 等中间 popup，只保留最后一个（课程页）
                for p in all_popups[:-1]:
                    if p != new_page and not p.is_closed():
                        try:
                            await p.close()
                        except Exception:
                            pass
                # 等待页面加载完成 + SPA 路由跳转完成
                try:
                    await new_page.wait_for_load_state("domcontentloaded", timeout=self.config.page_timeout // 3)
                except Exception:
                    pass
                # 等待 URL 稳定（SPA 可能会多次跳转）
                prev_url = ""
                for _ in range(15):
                    cur_url = new_page.url
                    if cur_url == prev_url and '/oauth/' not in cur_url and 'course/detail' in cur_url:
                        break
                    prev_url = cur_url
                    await new_page.wait_for_timeout(1000)
                self.log.info(f"📄 新窗口已打开: {new_page.url}")
                return new_page
            
            self.log.info("📄 未检测到新窗口，使用当前页面")
            return self.page
        
        self.page.context.remove_listener("page", on_popup)
        self.log.warn(f"⚠️ 未找到匹配的课程按钮: {course_title[:40]}")
        return None

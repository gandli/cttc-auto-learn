// ==UserScript==
// @name         烟草网络学院自动学习助手
// @namespace    https://github.com/gandli/cttc-auto-learn
// @version      0.1.0
// @description  自动刷任务、刷专题、刷课、刷学时。扫码登录 → 获取数据 → 选择模式 → 自动学习。
// @author       gandli
// @match        https://mooc.ctt.cn/*
// @match        https://*.mooc.ctt.cn/*
// @icon         https://mooc.ctt.cn/favicon.ico
// @grant        GM_xmlhttpRequest
// @grant        GM_addStyle
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_notification
// @connect      mooc.ctt.cn
// @connect      wx.zhixueyun.com
// @run-at       document-idle
// @license      MIT
// ==/UserScript==

(function () {
  'use strict';

  // ═══════════════════════════════════════════
  // 常量
  // ═══════════════════════════════════════════

  const API_BASE = 'https://mooc.ctt.cn';
  const OAUTH_BASE = 'https://mooc.ctt.cn/oauth/api/v1';
  const WX_QR_BASE = 'https://wx.zhixueyun.com/mswx/wechat/tobaccoQR/login';

  const API = {
    courses: '/api/v1/course-study/course-study-progress/personCourse-list',
    videoProgress: '/api/v1/course-study/course-front/video-progress',
    tasks: '/api/v1/human/task',
    taskCalendar: '/api/v1/human/task/findMyTaskCalendar',
    taskRemind: '/api/v1/human/task/findMyTaskRemind',
    studyStats: '/api/v1/system/credit/detail-hour-member',
    cadreStats: '/api/v1/system/cadre-education/detail-hour-member',
    courseDetail: '/api/v1/course-study/course-info',
    organization: '/api/v1/system/home-config/organization',
    topics: '/api/v1/human/special-topic/findMySpecialTopicPage',
    topicDetail: '/api/v1/human/special-topic/findMySpecialTopicDetail',
    classes: '/api/v1/human/class/findMyClassPage',
  };

  // ═══════════════════════════════════════════
  // 工具函数
  // ═══════════════════════════════════════════

  function getToken() {
    try {
      const raw = localStorage.getItem('token');
      if (!raw) return '';
      const data = JSON.parse(raw);
      return data.access_token || '';
    } catch {
      return '';
    }
  }

  function isLoggedIn() {
    const token = getToken();
    const text = document.body?.innerText || '';
    return token && text.includes('退出') && !location.href.includes('/login') && !location.href.includes('/oauth/');
  }

  async function apiGet(url) {
    const token = getToken();
    if (!token) return null;
    try {
      const resp = await fetch(url.startsWith('http') ? url : API_BASE + url, {
        headers: {
          'Authorization': `Bearer__${token}`,
          'X-Requested-With': 'XMLHttpRequest',
        },
      });
      if (!resp.ok) return null;
      const ct = resp.headers.get('content-type') || '';
      if (!ct.includes('json')) return null;
      return await resp.json();
    } catch {
      return null;
    }
  }

  async function apiPost(url, body) {
    const token = getToken();
    if (!token) return null;
    try {
      const resp = await fetch(API_BASE + url, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer__${token}`,
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify(body),
      });
      if (!resp.ok) return null;
      return await resp.json();
    } catch {
      return null;
    }
  }

  function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
  }

  function log(msg) {
    const ts = new Date().toLocaleTimeString();
    console.log(`[CTTC ${ts}] ${msg}`);
    appendLog(`[${ts}] ${msg}`);
  }

  // ═══════════════════════════════════════════
  // UI 面板
  // ═══════════════════════════════════════════

  let panelEl = null;
  let logEl = null;
  let statusEl = null;

  GM_addStyle(`
    #cttc-panel {
      position: fixed; top: 10px; right: 10px; z-index: 999999;
      width: 380px; max-height: 90vh; overflow-y: auto;
      background: #1a1a2e; color: #eee; border-radius: 12px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.4);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 14px; line-height: 1.5;
    }
    #cttc-panel * { box-sizing: border-box; }
    #cttc-panel .header {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      padding: 12px 16px; border-radius: 12px 12px 0 0;
      display: flex; justify-content: space-between; align-items: center;
      cursor: move; user-select: none;
    }
    #cttc-panel .header h3 { margin: 0; font-size: 15px; }
    #cttc-panel .header .close-btn {
      cursor: pointer; font-size: 18px; opacity: 0.8;
      background: none; border: none; color: #fff;
    }
    #cttc-panel .header .close-btn:hover { opacity: 1; }
    #cttc-panel .body { padding: 12px 16px; }
    #cttc-panel .section { margin-bottom: 12px; }
    #cttc-panel .section-title {
      font-size: 12px; color: #888; text-transform: uppercase;
      margin-bottom: 6px; letter-spacing: 1px;
    }
    #cttc-panel .btn {
      display: inline-block; padding: 8px 14px; margin: 3px;
      border: none; border-radius: 8px; cursor: pointer;
      font-size: 13px; font-weight: 500; transition: all 0.2s;
      color: #fff;
    }
    #cttc-panel .btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
    #cttc-panel .btn:active { transform: translateY(0); }
    #cttc-panel .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
    #cttc-panel .btn-primary { background: #667eea; }
    #cttc-panel .btn-success { background: #2ecc71; }
    #cttc-panel .btn-warning { background: #f39c12; }
    #cttc-panel .btn-danger { background: #e74c3c; }
    #cttc-panel .btn-info { background: #3498db; }
    #cttc-panel .btn-sm { padding: 5px 10px; font-size: 12px; }
    #cttc-panel .status-bar {
      background: #16213e; padding: 8px 12px; border-radius: 8px;
      margin-bottom: 10px; font-size: 13px;
    }
    #cttc-panel .status-bar .label { color: #888; }
    #cttc-panel .status-bar .value { color: #2ecc71; font-weight: 600; }
    #cttc-panel .data-card {
      background: #16213e; padding: 10px 12px; border-radius: 8px;
      margin-bottom: 8px; font-size: 13px;
    }
    #cttc-panel .data-card .title { font-weight: 600; margin-bottom: 4px; }
    #cttc-panel .data-card .meta { color: #888; font-size: 12px; }
    #cttc-panel .log-box {
      background: #0f0f23; padding: 8px; border-radius: 8px;
      max-height: 200px; overflow-y: auto; font-family: monospace;
      font-size: 12px; color: #aaa; line-height: 1.6;
    }
    #cttc-panel .log-box .log-line { margin: 1px 0; }
    #cttc-panel .log-box .log-info { color: #3498db; }
    #cttc-panel .log-box .log-warn { color: #f39c12; }
    #cttc-panel .log-box .log-error { color: #e74c3c; }
    #cttc-panel .log-box .log-success { color: #2ecc71; }
    #cttc-panel .progress-bar {
      height: 6px; background: #16213e; border-radius: 3px; overflow: hidden;
      margin-top: 6px;
    }
    #cttc-panel .progress-bar .fill {
      height: 100%; background: linear-gradient(90deg, #667eea, #764ba2);
      border-radius: 3px; transition: width 0.5s;
    }
    #cttc-panel .qr-container {
      text-align: center; padding: 16px;
    }
    #cttc-panel .qr-container img {
      max-width: 200px; border-radius: 8px; border: 2px solid #333;
    }
    #cttc-panel .qr-container p {
      margin: 8px 0 0; font-size: 13px; color: #aaa;
    }
    #cttc-panel .tab-bar {
      display: flex; gap: 4px; margin-bottom: 10px;
    }
    #cttc-panel .tab {
      flex: 1; padding: 6px; text-align: center; border-radius: 6px;
      cursor: pointer; font-size: 12px; background: #16213e; color: #888;
      transition: all 0.2s;
    }
    #cttc-panel .tab.active { background: #667eea; color: #fff; }
    #cttc-panel .tab:hover:not(.active) { background: #1a1a3e; color: #ccc; }
    #cttc-panel .hidden { display: none !important; }
    #cttc-panel .toggle-btn {
      position: fixed; top: 10px; right: 10px; z-index: 999998;
      width: 48px; height: 48px; border-radius: 50%;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: #fff; border: none; cursor: pointer;
      font-size: 20px; box-shadow: 0 4px 16px rgba(0,0,0,0.3);
      display: flex; align-items: center; justify-content: center;
    }
    #cttc-panel .toggle-btn:hover { transform: scale(1.1); }
  `);

  function createPanel() {
    // 切换按钮
    const toggleBtn = document.createElement('button');
    toggleBtn.className = 'toggle-btn';
    toggleBtn.id = 'cttc-toggle';
    toggleBtn.innerHTML = '📚';
    toggleBtn.title = '烟草网络学院自动学习助手';
    toggleBtn.onclick = () => {
      const p = document.getElementById('cttc-panel');
      if (p) p.classList.toggle('hidden');
    };
    document.body.appendChild(toggleBtn);

    // 主面板
    const panel = document.createElement('div');
    panel.id = 'cttc-panel';
    panel.innerHTML = `
      <div class="header" id="cttc-drag-handle">
        <h3>📚 烟草网络学院 · 自动学习助手</h3>
        <button class="close-btn" id="cttc-close">✕</button>
      </div>
      <div class="body">
        <!-- 登录区域 -->
        <div id="cttc-login-section" class="section hidden">
          <div class="section-title">🔐 登录</div>
          <div class="qr-container" id="cttc-qr-area">
            <p>正在获取二维码...</p>
          </div>
        </div>

        <!-- 状态栏 -->
        <div id="cttc-status-section" class="status-bar">
          <span class="label">状态：</span>
          <span class="value" id="cttc-status-text">检测中...</span>
          <div class="progress-bar" id="cttc-progress-bar" style="display:none">
            <div class="fill" id="cttc-progress-fill" style="width:0%"></div>
          </div>
        </div>

        <!-- 数据统计 -->
        <div id="cttc-stats-section" class="section hidden">
          <div class="section-title">📊 学习统计</div>
          <div id="cttc-stats-content"></div>
        </div>

        <!-- 功能选项卡 -->
        <div id="cttc-tabs-section" class="section hidden">
          <div class="tab-bar">
            <div class="tab active" data-tab="tasks">📋 任务</div>
            <div class="tab" data-tab="topics">📖 专题</div>
            <div class="tab" data-tab="courses">🎓 课程</div>
            <div class="tab" data-tab="hours">⏱️ 学时</div>
          </div>
          <div id="cttc-tab-content"></div>
        </div>

        <!-- 操作按钮 -->
        <div id="cttc-actions-section" class="section hidden">
          <div class="section-title">🎮 操作</div>
          <div id="cttc-actions-content"></div>
        </div>

        <!-- 日志 -->
        <div class="section">
          <div class="section-title">📝 日志</div>
          <div class="log-box" id="cttc-log"></div>
        </div>
      </div>
    `;
    document.body.appendChild(panel);

    // 绑定事件
    document.getElementById('cttc-close').onclick = () => panel.classList.add('hidden');

    // 拖拽
    makeDraggable(panel, document.getElementById('cttc-drag-handle'));

    // 选项卡切换
    panel.querySelectorAll('.tab').forEach(tab => {
      tab.onclick = () => {
        panel.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        renderTabContent(tab.dataset.tab);
      };
    });

    panelEl = panel;
    logEl = document.getElementById('cttc-log');
    statusEl = document.getElementById('cttc-status-text');
    return panel;
  }

  function makeDraggable(el, handle) {
    let isDragging = false, startX, startY, startLeft, startTop;
    handle.onmousedown = (e) => {
      isDragging = true;
      startX = e.clientX; startY = e.clientY;
      const rect = el.getBoundingClientRect();
      startLeft = rect.left; startTop = rect.top;
      e.preventDefault();
    };
    document.onmousemove = (e) => {
      if (!isDragging) return;
      el.style.left = (startLeft + e.clientX - startX) + 'px';
      el.style.top = (startTop + e.clientY - startY) + 'px';
      el.style.right = 'auto';
    };
    document.onmouseup = () => { isDragging = false; };
  }

  function appendLog(msg, level = 'info') {
    if (!logEl) return;
    const line = document.createElement('div');
    line.className = `log-line log-${level}`;
    line.textContent = msg;
    logEl.appendChild(line);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function setStatus(text, showProgress = false) {
    if (statusEl) statusEl.textContent = text;
    const bar = document.getElementById('cttc-progress-bar');
    if (bar) bar.style.display = showProgress ? 'block' : 'none';
  }

  function setProgress(pct) {
    const fill = document.getElementById('cttc-progress-fill');
    if (fill) fill.style.width = `${Math.min(100, Math.max(0, pct))}%`;
  }

  // ═══════════════════════════════════════════
  // 数据获取
  // ═══════════════════════════════════════════

  let appData = {
    courses: [],
    tasks: [],
    topics: [],
    classes: [],
    studyStats: null,
    cadreStats: null,
    organization: null,
  };

  async function fetchAllData() {
    log('📡 开始获取数据...');

    // 并行获取
    const [courses, tasks, topics, studyStats, cadreStats, org] = await Promise.all([
      fetchCourses(),
      fetchTasks(),
      fetchTopics(),
      fetchStudyStats(),
      fetchCadreStats(),
      fetchOrganization(),
    ]);

    appData.courses = courses;
    appData.tasks = tasks;
    appData.topics = topics;
    appData.studyStats = studyStats;
    appData.cadreStats = cadreStats;
    appData.organization = org;

    log(`✅ 数据获取完成: ${courses.length}门课程, ${tasks.length}个任务, ${topics.length}个专题`);
    renderStats();
    renderTabContent('tasks');
    showActions();
  }

  async function fetchCourses() {
    const allCourses = [];
    for (let page = 1; page <= 20; page++) {
      const data = await apiGet(
        `${API.courses}?businessType=0&findStudy=0&studyTimeOrder=desc&page=${page}&pageSize=50`
      );
      if (!data) break;
      const items = data.items || [];
      for (const item of items) {
        const ci = item.courseInfo || {};
        const finishStatus = item.finishStatus || 0;
        const statusMap = { 0: '未开始', 1: '学习中', 2: '已完成' };
        allCourses.push({
          title: ci.name || '',
          courseId: item.courseId || '',
          status: statusMap[finishStatus] || '未知',
          required: item.isRequired === 1 ? '必修' : '选修',
          studyMin: item.studyTotalTime ? Math.round(item.studyTotalTime / 60) : 0,
          totalMin: ci.totalTime ? Math.round(ci.totalTime / 60) : 0,
          pct: ci.totalTime && item.studyTotalTime
            ? (item.studyTotalTime / ci.totalTime * 100).toFixed(1) + '%'
            : '0%',
          url: `${API_BASE}/#/course/info/${item.courseId}`,
        });
      }
      if (items.length < 50) break;
    }
    return allCourses;
  }

  async function fetchTasks() {
    const data = await apiGet(API.taskRemind);
    if (!data || !Array.isArray(data)) return [];
    return data.map(t => ({
      id: t.id || '',
      title: t.taskName || t.title || '',
      status: t.statusName || t.status || '',
      deadline: t.endTime || '',
      businessId: t.businessId || '',
      businessType: t.businessType || '',
    }));
  }

  async function fetchTopics() {
    const data = await apiGet(`${API.topics}?page=1&pageSize=50`);
    if (!data) return [];
    const items = data.items || data.records || [];
    return items.map(t => ({
      id: t.id || '',
      title: t.name || t.title || '',
      status: t.statusName || t.status || '',
      courseCount: t.courseCount || 0,
      completedCount: t.completedCount || 0,
    }));
  }

  async function fetchStudyStats() {
    return await apiGet(API.studyStats);
  }

  async function fetchCadreStats() {
    return await apiGet(API.cadreStats);
  }

  async function fetchOrganization() {
    return await apiGet(API.organization);
  }

  // ═══════════════════════════════════════════
  // 渲染
  // ═══════════════════════════════════════════

  function renderStats() {
    const el = document.getElementById('cttc-stats-content');
    if (!el) return;

    const stats = appData.studyStats || {};
    const credit = stats.creditHour || 0;
    const target = 50;

    const completed = appData.courses.filter(c => c.status === '已完成').length;
    const inProgress = appData.courses.filter(c => c.status === '学习中').length;
    const notStarted = appData.courses.filter(c => c.status === '未开始').length;

    el.innerHTML = `
      <div class="data-card">
        <div class="title">⏱️ 学时: ${credit.toFixed(1)} / ${target} 小时</div>
        <div class="progress-bar"><div class="fill" style="width:${Math.min(100, credit / target * 100)}%"></div></div>
        <div class="meta" style="margin-top:4px">已完成 ${completed} 门 | 进行中 ${inProgress} 门 | 未开始 ${notStarted} 门</div>
      </div>
      <div class="data-card">
        <div class="title">📋 任务: ${appData.tasks.length} 个</div>
        <div class="meta">${appData.tasks.filter(t => t.status !== '已完成').length} 个待完成</div>
      </div>
      <div class="data-card">
        <div class="title">📖 专题: ${appData.topics.length} 个</div>
        <div class="meta">${appData.topics.filter(t => t.status !== '已完成').length} 个待完成</div>
      </div>
    `;
    document.getElementById('cttc-stats-section').classList.remove('hidden');
  }

  function renderTabContent(tab) {
    const el = document.getElementById('cttc-tab-content');
    if (!el) return;

    switch (tab) {
      case 'tasks':
        el.innerHTML = renderTaskList();
        break;
      case 'topics':
        el.innerHTML = renderTopicList();
        break;
      case 'courses':
        el.innerHTML = renderCourseList();
        break;
      case 'hours':
        el.innerHTML = renderHoursPanel();
        break;
    }

    // 绑定按钮事件
    el.querySelectorAll('[data-action]').forEach(btn => {
      btn.onclick = () => handleAction(btn.dataset.action, btn.dataset);
    });
  }

  function renderTaskList() {
    if (!appData.tasks.length) return '<div class="data-card"><div class="meta">暂无任务</div></div>';
    return appData.tasks.map(t => `
      <div class="data-card">
        <div class="title">${t.title}</div>
        <div class="meta">状态: ${t.status} | 截止: ${t.deadline || '无'}</div>
        <div style="margin-top:6px">
          <button class="btn btn-sm btn-primary" data-action="do-task" data-id="${t.id}" data-business-id="${t.businessId}" data-business-type="${t.businessType}">▶️ 执行</button>
        </div>
      </div>
    `).join('');
  }

  function renderTopicList() {
    if (!appData.topics.length) return '<div class="data-card"><div class="meta">暂无专题</div></div>';
    return appData.topics.map(t => `
      <div class="data-card">
        <div class="title">${t.title}</div>
        <div class="meta">状态: ${t.status} | 课程: ${t.completedCount}/${t.courseCount}</div>
        <div style="margin-top:6px">
          <button class="btn btn-sm btn-primary" data-action="do-topic" data-id="${t.id}">▶️ 执行</button>
        </div>
      </div>
    `).join('');
  }

  function renderCourseList() {
    const notDone = appData.courses.filter(c => c.status !== '已完成');
    if (!notDone.length) return '<div class="data-card"><div class="meta">🎉 所有课程已完成！</div></div>';
    const shown = notDone.slice(0, 20);
    return `
      <div style="margin-bottom:8px">
        <button class="btn btn-sm btn-success" data-action="do-all-courses">▶️ 自动刷全部 (${notDone.length}门)</button>
      </div>
      ${shown.map(c => `
        <div class="data-card">
          <div class="title">${c.title}</div>
          <div class="meta">${c.required} | ${c.status} | ${c.pct} | ${c.studyMin}/${c.totalMin}分钟</div>
          <div style="margin-top:6px">
            <button class="btn btn-sm btn-primary" data-action="do-course" data-course-id="${c.courseId}" data-url="${c.url}">▶️ 播放</button>
          </div>
        </div>
      `).join('')}
      ${notDone.length > 20 ? `<div class="data-card"><div class="meta">...还有 ${notDone.length - 20} 门课程</div></div>` : ''}
    `;
  }

  function renderHoursPanel() {
    const stats = appData.studyStats || {};
    const credit = stats.creditHour || 0;
    const target = 50;
    const remaining = Math.max(0, target - credit);

    return `
      <div class="data-card">
        <div class="title">⏱️ 学时模式</div>
        <div class="meta">当前: ${credit.toFixed(1)}h | 目标: ${target}h | 还需: ${remaining.toFixed(1)}h</div>
        <div class="progress-bar"><div class="fill" style="width:${Math.min(100, credit / target * 100)}%"></div></div>
      </div>
      <div style="margin-top:8px">
        <button class="btn btn-success" data-action="do-hours">▶️ 开始刷学时</button>
        <button class="btn btn-info" data-action="refresh-stats">🔄 刷新统计</button>
      </div>
    `;
  }

  function showActions() {
    const el = document.getElementById('cttc-actions-content');
    if (!el) return;
    el.innerHTML = `
      <button class="btn btn-primary" data-action="do-tasks">📋 刷任务</button>
      <button class="btn btn-primary" data-action="do-topics">📖 刷专题</button>
      <button class="btn btn-primary" data-action="do-courses">🎓 刷课程</button>
      <button class="btn btn-success" data-action="do-hours">⏱️ 刷学时</button>
      <button class="btn btn-warning" data-action="stop">⏹️ 停止</button>
      <button class="btn btn-info btn-sm" data-action="refresh">🔄 刷新数据</button>
    `;
    el.querySelectorAll('[data-action]').forEach(btn => {
      btn.onclick = () => handleAction(btn.dataset.action, btn.dataset);
    });
    document.getElementById('cttc-actions-section').classList.remove('hidden');
    document.getElementById('cttc-tabs-section').classList.remove('hidden');
  }

  // ═══════════════════════════════════════════
  // 自动学习逻辑
  // ═══════════════════════════════════════════

  let isRunning = false;
  let stopRequested = false;

  async function handleAction(action, dataset) {
    switch (action) {
      case 'do-tasks':
        await autoTasks();
        break;
      case 'do-topics':
        await autoTopics();
        break;
      case 'do-courses':
      case 'do-all-courses':
        await autoCourses();
        break;
      case 'do-hours':
        await autoHours();
        break;
      case 'do-task':
        await doSingleTask(dataset.businessId, dataset.businessType);
        break;
      case 'do-topic':
        await doSingleTopic(dataset.id);
        break;
      case 'do-course':
        await doSingleCourse(dataset.courseId, dataset.url);
        break;
      case 'refresh':
        await fetchAllData();
        break;
      case 'refresh-stats':
        appData.studyStats = await fetchStudyStats();
        renderStats();
        renderTabContent('hours');
        break;
      case 'stop':
        stopRequested = true;
        log('⏹️ 停止请求已发送', 'warn');
        setStatus('停止中...');
        break;
    }
  }

  async function autoTasks() {
    if (isRunning) { log('⚠️ 已有任务在运行', 'warn'); return; }
    isRunning = true; stopRequested = false;
    log('📋 开始刷任务...');
    setStatus('刷任务中...', true);

    const tasks = appData.tasks.filter(t => t.status !== '已完成');
    for (let i = 0; i < tasks.length; i++) {
      if (stopRequested) break;
      const t = tasks[i];
      log(`📋 [${i + 1}/${tasks.length}] ${t.title}`);
      setProgress((i + 1) / tasks.length * 100);
      await doSingleTask(t.businessId, t.businessType);
      await sleep(2000);
    }

    isRunning = false;
    log(stopRequested ? '⏹️ 已停止' : '✅ 任务刷完');
    setStatus(stopRequested ? '已停止' : '任务完成');
  }

  async function autoTopics() {
    if (isRunning) { log('⚠️ 已有任务在运行', 'warn'); return; }
    isRunning = true; stopRequested = false;
    log('📖 开始刷专题...');
    setStatus('刷专题中...', true);

    const topics = appData.topics.filter(t => t.status !== '已完成');
    for (let i = 0; i < topics.length; i++) {
      if (stopRequested) break;
      log(`📖 [${i + 1}/${topics.length}] ${topics[i].title}`);
      setProgress((i + 1) / topics.length * 100);
      await doSingleTopic(topics[i].id);
      await sleep(2000);
    }

    isRunning = false;
    log(stopRequested ? '⏹️ 已停止' : '✅ 专题刷完');
    setStatus(stopRequested ? '已停止' : '专题完成');
  }

  async function autoCourses() {
    if (isRunning) { log('⚠️ 已有任务在运行', 'warn'); return; }
    isRunning = true; stopRequested = false;
    log('🎓 开始刷课程...');
    setStatus('刷课程中...', true);

    const courses = appData.courses.filter(c => c.status !== '已完成');
    for (let i = 0; i < courses.length; i++) {
      if (stopRequested) break;
      const c = courses[i];
      log(`🎓 [${i + 1}/${courses.length}] ${c.title} (${c.pct})`);
      setProgress((i + 1) / courses.length * 100);
      await doSingleCourse(c.courseId, c.url);
      await sleep(3000);
    }

    isRunning = false;
    log(stopRequested ? '⏹️ 已停止' : '✅ 课程刷完');
    setStatus(stopRequested ? '已停止' : '课程完成');
  }

  async function autoHours() {
    if (isRunning) { log('⚠️ 已有任务在运行', 'warn'); return; }
    isRunning = true; stopRequested = false;
    const target = 50;
    log(`⏱️ 开始刷学时 (目标: ${target}h)...`);
    setStatus('刷学时中...', true);

    let round = 0;
    while (!stopRequested) {
      round++;
      const stats = await fetchStudyStats();
      const current = stats?.creditHour || 0;
      log(`⏱️ 第${round}轮 | 当前: ${current.toFixed(1)}h / ${target}h`);
      setProgress(current / target * 100);

      if (current >= target) {
        log('🎉 已达到目标学时！');
        break;
      }

      // 刷未完成的课程
      const courses = await fetchCourses();
      const notDone = courses.filter(c => c.status !== '已完成');
      if (!notDone.length) {
        log('⚠️ 没有未完成的课程', 'warn');
        break;
      }

      for (const c of notDone) {
        if (stopRequested) break;
        log(`▶️ ${c.title} (${c.pct})`);
        await doSingleCourse(c.courseId, c.url);
        await sleep(2000);
      }

      // 刷新统计
      await sleep(5000);
    }

    isRunning = false;
    log(stopRequested ? '⏹️ 已停止' : '✅ 学时任务完成');
    setStatus(stopRequested ? '已停止' : '学时完成');
  }

  // ═══════════════════════════════════════════
  // 单项执行
  // ═══════════════════════════════════════════

  async function doSingleTask(businessId, businessType) {
    if (!businessId) { log('⚠️ 无效的任务ID', 'warn'); return; }
    // 导航到任务对应的课程
    const url = `${API_BASE}/#/course/info/${businessId}`;
    log(`🔗 打开任务课程: ${url}`);
    location.href = url;
    await sleep(5000);
    await playCurrentVideo();
  }

  async function doSingleTopic(topicId) {
    if (!topicId) { log('⚠️ 无效的专题ID', 'warn'); return; }
    // 获取专题详情，遍历课程
    const data = await apiGet(`${API.topicDetail}?id=${topicId}`);
    if (!data) { log('⚠️ 无法获取专题详情', 'warn'); return; }
    const courses = data.courses || data.items || [];
    log(`📖 专题包含 ${courses.length} 门课程`);
    for (const c of courses) {
      if (stopRequested) break;
      const courseId = c.courseId || c.id;
      const url = `${API_BASE}/#/course/info/${courseId}`;
      log(`▶️ ${c.name || c.title || courseId}`);
      location.href = url;
      await sleep(5000);
      await playCurrentVideo();
      await sleep(2000);
    }
  }

  async function doSingleCourse(courseId, url) {
    if (!courseId) { log('⚠️ 无效的课程ID', 'warn'); return; }
    const targetUrl = url || `${API_BASE}/#/course/info/${courseId}`;
    log(`🔗 打开课程: ${targetUrl}`);
    location.href = targetUrl;
    await sleep(5000);
    await playCurrentVideo();
  }

  // ═══════════════════════════════════════════
  // 视频播放
  // ═══════════════════════════════════════════

  async function playCurrentVideo() {
    log('🔍 查找视频...');

    // 等待视频元素
    let videoFound = false;
    for (let i = 0; i < 20; i++) {
      const hasVideo = document.querySelectorAll('video').length > 0;
      if (hasVideo) { videoFound = true; break; }
      await sleep(1000);
    }

    if (!videoFound) {
      log('⚠️ 未找到视频元素', 'warn');
      return false;
    }

    // 播放视频
    const played = await tryPlayVideo();
    if (!played) {
      log('⚠️ 无法播放视频', 'warn');
      return false;
    }

    log('▶️ 视频开始播放');

    // 设置普清
    setQualityStandard();

    // 等待播放完成
    return await waitForVideoComplete();
  }

  async function tryPlayVideo() {
    // 策略 1: 直接播放
    const v = document.querySelector('video');
    if (v && v.paused) {
      try {
        await v.play();
        if (!v.paused) return true;
      } catch {}
    }

    // 策略 2: 点击播放按钮
    const selectors = ['.vjs-big-play-button', '.vjs-play-control', 'video'];
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && el.offsetParent !== null) {
        el.click();
        await sleep(2000);
        const v2 = document.querySelector('video');
        if (v2 && !v2.paused) return true;
      }
    }

    return false;
  }

  function setQualityStandard() {
    try {
      const items = document.querySelectorAll('.vjs-def-box .vjs-menu-item, .vjs-subs-caps-button .vjs-menu-item');
      for (const item of items) {
        const t = (item.textContent || '').trim();
        if (t === '普清' || t.includes('普清')) {
          item.click();
          log('🎨 画质: 普清');
          return;
        }
      }
    } catch {}
  }

  async function waitForVideoComplete() {
    const timeout = 7200; // 2 小时
    const start = Date.now();
    let lastProgress = 0;
    let stallCount = 0;

    while (Date.now() - start < timeout * 1000) {
      if (stopRequested) {
        log('⏹️ 停止等待视频');
        return false;
      }

      // 防挂机
      if (Math.random() < 0.02) {
        document.dispatchEvent(new MouseEvent('mousemove', {
          clientX: Math.random() * 800 + 100,
          clientY: Math.random() * 400 + 100,
          bubbles: true,
        }));
      }

      const v = document.querySelector('video');
      if (!v) {
        // 视频消失 — 可能已完成
        if (lastProgress > 70) {
          log('✅ 视频播放完成（元素消失）');
          return true;
        }
        log('⚠️ 视频元素消失', 'warn');
        return false;
      }

      if (v.ended) {
        log('✅ 视频播放完成');
        return true;
      }

      if (v.paused && v.currentTime > 0) {
        log('▶️ 恢复暂停');
        try { await v.play(); } catch {}
      }

      const progress = v.duration > 0 ? (v.currentTime / v.duration * 100) : 0;

      // 检测停滞
      if (Math.abs(progress - lastProgress) < 0.5) {
        stallCount++;
        if (stallCount > 60) { // 60 * 5s = 300s
          log('⚠️ 视频进度停滞', 'warn');
          // 尝试点击恢复
          try { await v.play(); } catch {}
          stallCount = 0;
        }
      } else {
        stallCount = 0;
      }
      lastProgress = progress;

      // 每 30 秒打印进度
      if (Math.floor(Date.now() / 30000) !== Math.floor((Date.now() - 5000) / 30000)) {
        const curMin = Math.floor(v.currentTime / 60);
        const durMin = Math.floor(v.duration / 60);
        log(`⏱️ ${progress.toFixed(1)}% (${curMin}/${durMin}分钟)`);
        setStatus(`播放中 ${progress.toFixed(1)}%`, true);
        setProgress(progress);
      }

      await sleep(5000);
    }

    log('⚠️ 视频播放超时', 'warn');
    return false;
  }

  // ═══════════════════════════════════════════
  // 登录处理
  // ═══════════════════════════════════════════

  async function showLoginQR() {
    const loginSection = document.getElementById('cttc-login-section');
    const qrArea = document.getElementById('cttc-qr-area');
    if (!loginSection || !qrArea) return;

    loginSection.classList.remove('hidden');
    qrArea.innerHTML = '<p>🔄 正在获取二维码...</p>';

    try {
      // 创建微信二维码 UUID
      const uuid = crypto.randomUUID();
      const resp = await new Promise((resolve, reject) => {
        GM_xmlhttpRequest({
          method: 'POST',
          url: `${OAUTH_BASE}/createQRCode?uuid=${uuid}`,
          headers: { 'Referer': 'https://mooc.ctt.cn/oauth/' },
          onload: resolve,
          onerror: reject,
        });
      });

      const data = JSON.parse(resp.responseText);
      const wxUuid = data.uuid || uuid;
      const qrUrl = `${WX_QR_BASE}/${wxUuid}/v5/online`;

      qrArea.innerHTML = `
        <p style="margin-bottom:12px">📱 请使用微信扫码登录</p>
        <img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qrUrl)}" alt="微信扫码">
        <p>⏳ 等待扫码... (75秒后自动刷新)</p>
      `;

      // 轮询扫码状态
      pollLoginStatus(wxUuid, 75);
    } catch (e) {
      qrArea.innerHTML = `<p style="color:#e74c3c">❌ 获取二维码失败: ${e.message}</p>`;
    }
  }

  async function pollLoginStatus(wxUuid, timeout) {
    const start = Date.now();
    while (Date.now() - start < timeout * 1000) {
      try {
        const resp = await new Promise((resolve, reject) => {
          GM_xmlhttpRequest({
            method: 'POST',
            url: `${OAUTH_BASE}/checkUUIDStatus?uuid=${wxUuid}`,
            headers: {
              'Referer': 'https://mooc.ctt.cn/oauth/',
              'X-Requested-With': 'XMLHttpRequest',
            },
            onload: resolve,
            onerror: reject,
          });
        });

        const data = JSON.parse(resp.responseText);
        if (data && data.status === true) {
          log('✅ 扫码成功！', 'success');
          // 保存 token
          if (data.access_token) {
            localStorage.setItem('token', JSON.stringify({
              access_token: data.access_token,
              token_type: 'Bearer',
            }));
          }
          // 刷新页面
          location.reload();
          return;
        }
      } catch {}

      await sleep(3000);
    }

    // 超时 — 刷新二维码
    log('🔄 二维码过期，刷新中...', 'warn');
    showLoginQR();
  }

  // ═══════════════════════════════════════════
  // 初始化
  // ═══════════════════════════════════════════

  async function init() {
    createPanel();
    log('🚀 烟草网络学院自动学习助手已启动');
    setStatus('检测登录状态...');

    // 等待页面加载
    await sleep(2000);

    if (isLoggedIn()) {
      log('✅ 已登录');
      setStatus('已登录，获取数据中...');
      await fetchAllData();
    } else {
      log('❌ 未登录，显示扫码页面', 'warn');
      setStatus('未登录');
      await showLoginQR();
    }
  }

  // 启动
  if (document.readyState === 'complete') {
    init();
  } else {
    window.addEventListener('load', init);
  }

})();

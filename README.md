# 🎓 cttc-auto-learn

[中文版](./README_CN.md) | English

Automated video learning system for China Tobacco's online training platform ([mooc.ctt.cn](https://mooc.ctt.cn)). Supports four modes: study hours, topics, courses, and tasks. Built with Playwright.

## ✨ Features

- 🔐 **QR Login** — WeChat QR code scan, session persistence via `auth-state.json`
- 📺 **Auto Playback** — Play video courses sequentially, track to 100% completion
- 📊 **Study Hour Monitoring** — Real-time API interception for credit / cadre-education stats
- 🎯 **Target-Driven** — Configurable target hours (default: 50h), auto-exit when reached
- 🛡️ **Anti-Detection** — Periodic mouse movement (every 25 min), single-instance lock, single-tab enforcement
- 🔄 **Crash Recovery** — Auto-restart up to 5 times on browser crash, force-kill stale processes
- 📈 **Real-time Status** — Live status file (`output/status.json`) for external monitoring
- 🖥️ **Terminal Dashboard** — Interactive monitoring panel with progress bars
- 🎮 **Four Modes** — Study hours, topics, courses, tasks

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (package manager)
- Windows 10/11

### Installation

```bash
npx skills add gandli/cttc-auto-learn
```

### Run

```bash
# Study hours (default)
uv run python main.py

# Topics
uv run python main.py --mode topics

# Courses
uv run python main.py --mode courses

# Tasks
uv run python main.py --mode tasks
```

**Parameters:**
- `--mode hours` - Study hours (default)
- `--mode topics` - Complete topics
- `--mode courses` - Complete all courses
- `--mode tasks` - Complete tasks
- `--target 50` - Target hours (default: 50)
- `--headless` - Headless mode

1. A browser window will open showing the login page
2. Scan the QR code with WeChat
3. After login, the script automatically starts learning

Credentials are saved in `output/auth-state.json`, no need to scan again.

### AI Agent Usage

After installing the SKILL, simply say to your Agent:

```
Help me complete my study hours
```

or

```
Help me complete topics
Help me complete courses
Help me complete tasks
```

The Agent will automatically:
1. Check and clone the project
2. Install Python dependencies
3. Open browser for login (scan QR on first run)
4. Play video courses automatically
5. Monitor study hour progress
6. Auto-exit when target is reached

---

## 🎮 Four Running Modes

| Mode | Command | Description | Trigger |
|------|---------|-------------|---------|
| Study Hours | `--mode hours` | Play videos to accumulate study hours (default) | "Help me with study hours" |
| Topics | `--mode topics` | Complete topic courses | "Help me complete topics" |
| Courses | `--mode courses` | Complete all incomplete courses | "Help me complete courses" |
| Tasks | `--mode tasks` | Complete specified tasks | "Help me complete tasks" |

### Study Hours Mode (Default)

```bash
uv run python main.py --mode hours --target 50
```

- Play videos to accumulate study hours
- Auto-exit when target hours reached
- Refresh study hours via API every 30 minutes

### Topics Mode

```bash
uv run python main.py --mode topics
```

- Auto-discover and complete topic courses
- Traverse all courses within topics

### Courses Mode

```bash
uv run python main.py --mode courses
```

- Complete all incomplete courses
- Skip already completed courses

### Tasks Mode

```bash
uv run python main.py --mode tasks
```

- Complete specified tasks
- Fetch task list via API

---

## 📊 Real-time Monitoring

### View Status File

```bash
cat output/status.json | python -m json.tool
```

### Terminal Dashboard

```bash
uv run python scripts/monitor.py
```

### Status Fields

| Field | Description |
|-------|-------------|
| `status` | Current state: playing/paused/completed |
| `video_progress` | Current video playback progress (%) |
| `study_hours_current` | Current study hours |
| `study_hours_target` | Target study hours |
| `courses_completed` | Number of completed courses |
| `courses_pending` | Number of pending courses |

---

## 📁 Project Structure

```
cttc-auto-learn/
├── main.py              # Entry point
├── cttc/                # Core modules
│   ├── login.py         # Login (QR code, credentials)
│   ├── player.py        # Video playback
│   ├── course.py        # Course management
│   ├── status.py        # Status reporting
│   └── ...
├── scripts/             # Utility scripts
│   └── monitor.py       # Terminal monitoring dashboard
├── SKILLS/              # AI Agent workflow
│   └── SKILL.md         # Auto-executed after installation
├── output/              # Output directory
│   ├── auth-state.json  # Login credentials
│   └── status.json      # Real-time status
└── logs/                # Log directory
```

---

## 📄 License

MIT

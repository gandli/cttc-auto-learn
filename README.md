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

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Windows 10/11

### Clone

```bash
git clone https://github.com/gandli/cttc-auto-learn.git
cd cttc-auto-learn
```

### Install Dependencies

**uv (recommended):**

```bash
uv sync
```

**pip + venv (Python native):**

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
pip install .
```

### Run

**uv:**

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

**pip (venv activated):**

```bash
python main.py
python main.py --mode topics
python main.py --mode courses
python main.py --mode tasks
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

Install the SKILL:

```bash
npx skills add gandli/cttc-auto-learn
```

After installation, simply say to your Agent:

```
Help me complete my study hours
```

or

```
Help me complete topics
Help me complete courses
Help me complete tasks
Help me complete classes
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
├── main.py                # Entry point
├── cttc/                  # Core modules
│   ├── login.py           # Login (QR code, credentials)
│   ├── player.py          # Video playback
│   ├── course.py          # Course management
│   ├── data_manager.py    # API data fetching
│   ├── monitor.py         # Study time monitoring
│   ├── progress.py        # Progress tracking
│   ├── config.py          # Configuration
│   ├── logger.py          # Logging
│   ├── qr.py              # QR code generation
│   ├── selectors.py       # CSS selectors
│   ├── status.py          # Status reporting
│   └── process_manager.py # Process management
├── scripts/               # Utility scripts
│   ├── explore/           # API exploration scripts
│   │   ├── api_explore.py
│   │   ├── crawl_site.py
│   │   └── ...
│   ├── cdp_login_analyzer.py
│   └── monitor.py         # Terminal monitoring dashboard
├── tests/                 # Test files (168 tests)
├── docs/                  # Documentation
│   ├── analysis/          # Technical analysis reports
│   └── crawl/             # API crawl results
├── SKILLS/                # AI Agent workflow
│   └── cttc-auto-learn/
│       └── SKILL.md       # Auto-executed after installation
├── data/                  # Runtime data (gitignored)
├── output/                # Output directory (gitignored)
│   ├── auth-state.json    # Login credentials
│   ├── status.json        # Real-time status
│   └── crawl/             # Crawl raw data
├── pyproject.toml         # Project config
├── CHANGELOG.md           # Version history
└── README.md
```

---

## 🗺️ Roadmap

### ✅ Completed (v0.0.1)

| Module | Description |
|--------|-------------|
| QR Login | APP + WeChat dual-channel QR code login |
| v22 Fast Login | Headless Chrome + HTTP parallel polling |
| Four Modes | hours / topics / courses / tasks |
| Auto Playback | Video auto-play with progress monitoring |
| Study Hour Tracking | API-based credit stats, auto-stop on target |
| DataManager | REST API data fetching |
| StudyPlanner | Intelligent learning plan generation |
| Testing | 168 tests passed (login, playback, progress, monitoring, scheduler) |

### 🔜 Planned

**v0.1.0 — Usability + Classes Mode**
- Credential encryption (`auth-state.json` → `auth-state.enc`)
- Graceful session renewal (auto-refresh before expiry)
- `config.yaml` for presets (target hours, mode, headless, etc.)
- `python -m cttc` entry point
- **New「Classes Mode」** — Auto-complete class training courses (`--mode classes`)
  - Fetch my classes list (`/api/v1/human/class/findMyClassPage`)
  - Traverse class courses, play each one
  - Track classroom training hours (`classroom_completed / classroom_target`)
  - Sync implementation for Tampermonkey and CDP versions

**v0.2.0 — Monitoring**
- Web dashboard for real-time progress viewing
- Email / WeChat notification on task completion
- Learning history and statistics export (CSV / JSON)

**v0.3.0 — Intelligence**
- Smart course scheduling (priority, difficulty, deadline)
- Automatic exam preparation with question bank
- Multi-account support

**v1.0.0 — Production**
- Docker containerization
- GitHub Actions CI/CD
- Cross-platform support (Linux / macOS)
- PyPI release (`pip install cttc-auto-learn`)

---

## 📄 License

MIT

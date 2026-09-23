# Basketball Flow Lab - AI Agent Context

## Project Overview

**Basketball Flow Lab** is a comprehensive basketball analytics system that combines NBA official data analysis with automated YouTube video analysis. The project generates shot charts, play-by-play data, 3D visualizations, and statistical insights.

**Core Capabilities:**
- NBA Stats API integration (2019-2025 seasons)
- YouTube video analysis using YOLOv8 object detection
- Kirk Goldsberry-style shot chart generation
- 3D shot visualization and heatmaps
- Run analysis (momentum detection)
- Causal inference (DiD analysis for B.League)

## Architecture

### Design Philosophy

This project follows **Vertical Slice Architecture** principles:
- Features are organized by capability, not by layer
- Each analysis module is self-contained with its own data loading, processing, and visualization
- Domain logic is colocated with related utilities

### Key Architectural Patterns

**1. Coordinator-Specialist Pattern:**
- Main agent coordinates analysis workflow
- Specialist agents handle specific domains:
  - `nba-analyst`: NBA Stats API data analysis
  - `video-analyst`: YouTube video processing with YOLOv8
  - `visualizer`: Shot chart and 3D visualization generation
  - `stats-reporter`: Statistical summary and report generation

**2. Progressive Disclosure:**
- Heavy data files (videos, NBA cache) are not loaded upfront
- Skills provide just-in-time context when needed
- Agents request specific analysis modules only when required

**3. Filesystem-Based Skills:**
- Reusable analysis workflows stored in `.claude/skills/`
- Domain-specific expertise encoded as markdown guides
- Best practices for shot chart styling, statistical methods

## Directory Structure

```
basketball_analysis/
├── CLAUDE.md                          # This file - AI agent context
│
├── .claude/                           # Claude Code configuration
│   ├── subagents/                     # Specialist agent definitions
│   │   ├── nba-analyst.md            # NBA data analysis specialist
│   │   ├── video-analyst.md          # Video processing specialist
│   │   ├── visualizer.md             # Chart generation specialist
│   │   └── stats-reporter.md         # Report generation specialist
│   │
│   ├── skills/                        # Reusable analysis workflows
│   │   ├── shot-chart-generation/    # Kirk Goldsberry styling
│   │   ├── video-detection/          # YOLOv8 configuration
│   │   ├── statistical-analysis/     # Run analysis, DiD methods
│   │   └── 3d-visualization/         # 3D plotting techniques
│   │
│   └── commands/                      # Custom slash commands
│       ├── analyze-nba.md            # /analyze-nba [player]
│       ├── analyze-video.md          # /analyze-video [url]
│       └── generate-report.md        # /generate-report [type]
│
├── src/                               # Core modules (flat structure)
│   ├── data_loader.py                # NBA Stats API client
│   ├── run_detector.py               # Run (momentum) detection
│   ├── shot_chart_analyzer.py        # Shot chart generation
│   ├── shot_chart_3d_heatmap.py     # 3D heatmap visualization
│   ├── yolo_ball_detector.py        # YOLOv8 ball detection
│   └── court_visualizer.py          # Court diagram utilities
│
├── features/                          # Vertical slices (self-contained)
│   ├── nba-finals-analysis/          # 2024 Finals Run analysis
│   │   ├── run_finals_hc_analysis.py
│   │   ├── README.md
│   │   └── outputs/
│   │
│   ├── hachimura-evolution/          # Rui Hachimura 6-season analysis
│   │   ├── generate_hachimura_3d_heatmap.py
│   │   ├── analyze_hachimura_3p_trend.py
│   │   └── outputs/
│   │
│   ├── youtube-video-analysis/       # YouTube automated analysis
│   │   ├── analyze_three_games_fast.py
│   │   ├── create_manual_stats.py
│   │   └── outputs/three_games/
│   │
│   └── bleague-arena-effect/         # B.League DiD analysis
│       ├── comprehensive_analysis.py
│       └── outputs/
│
├── data/                              # External data (not in git)
│   ├── videos/                       # YouTube downloads
│   ├── cache/                        # NBA API cache
│   └── *.pdf                         # B.League documents
│
├── outputs/                           # Generated artifacts
│   ├── images/                       # 35 PNG shot charts
│   ├── videos/                       # 5 3D visualization videos
│   ├── reports/                      # Statistical reports
│   └── [feature-specific]/          # Feature outputs
│
├── docs/                              # Documentation
│   ├── strategy/                     # Project roadmap, posting strategy
│   ├── research/                     # Academic research notes
│   ├── analysis/                     # Analysis guides
│   └── posts/                        # SNS content drafts
│
├── Dockerfile                         # Docker environment
├── docker-compose.yml                 # Compose configuration
├── Makefile                           # One-command shortcuts
├── requirements.txt                   # Python dependencies
│
├── README.md                          # Project overview
├── QUICK_START.md                     # Getting started guide
├── DOCKER_SETUP.md                    # Docker detailed guide
└── FINAL_SUMMARY.md                   # Project completion summary
```

## Key Decisions & Rationale

### Why Vertical Slices?

**Problem:** Original flat structure (`src/`, `outputs/`) made it hard to:
- Find related code for a specific analysis
- Understand dependencies between modules
- Isolate feature-specific logic

**Solution:** Group by feature/capability:
- `features/nba-finals-analysis/` contains all Finals-related code
- `features/hachimura-evolution/` is self-contained for Rui analysis
- Each slice has its own outputs, docs, and entrypoint script

**Benefits:**
- Claude agents can load just the relevant slice
- Easy to add new analyses without touching existing code
- Clear ownership and testing boundaries

### Why Skills Over Traditional Tools?

**Skills provide:**
- **Domain expertise:** "How to style a Kirk Goldsberry shot chart"
- **Best practices:** "YOLOv8 confidence threshold tuning for low-res videos"
- **Workflows:** "Step-by-step Run analysis methodology"

**Traditional tools provide:**
- Function execution (e.g., "read this file")

**Use case:** When an agent needs to create a shot chart:
1. Load `skills/shot-chart-generation/` skill
2. Follow styling guide (court colors, marker sizes, legend placement)
3. Use `src/shot_chart_analyzer.py` module with correct parameters

### Why Subagents?

**Specialization:** Each subagent has:
- Focused system prompt (e.g., "You are an NBA data analyst")
- Tool restrictions (video-analyst can't access NBA API)
- Domain-specific knowledge

**Context preservation:** Main agent delegates tasks:
- "Analyze Hachimura's 3P trend" → `nba-analyst` subagent
- "Process YouTube video" → `video-analyst` subagent
- Main conversation stays clean and high-level

## Coding Standards

### Python Style

- **PEP 8 compliant** with line length 100 chars
- **Type hints** for public functions
- **Docstrings** in Google style
- **Class-based** for stateful analyzers, **functions** for utilities

### Module Organization

```python
# Good: Feature-based imports
from features.nba_finals_analysis.run_detector import RunDetector

# Avoid: Deep nesting
from src.analysis.advanced.statistical.run_detector import RunDetector
```

### Configuration

- **Environment variables** for secrets (API keys)
- **Dataclasses** for configuration objects
- **JSON/YAML** for external configuration (not Python files)

### Error Handling

- **Graceful degradation:** If YOLOv8 fails, offer manual input
- **Clear error messages:** "Video resolution 640×360 too low (need ≥720p)"
- **Retry logic:** NBA API calls with exponential backoff

## Common Workflows

### Adding a New Analysis Feature

1. Create feature directory: `features/my-new-analysis/`
2. Add entrypoint script: `analyze_my_feature.py`
3. Create outputs subdir: `outputs/my-feature/`
4. Document in feature's README.md
5. Add Makefile target: `make analyze-my-feature`
6. Optional: Create subagent in `.claude/subagents/my-analyst.md`

### Processing a YouTube Video

```bash
# 1. Download video
yt-dlp [URL] -f "best[height<=720]" -o "data/videos/game.mp4"

# 2. Run analysis
python features/youtube-video-analysis/analyze_video.py

# 3. Check outputs
ls outputs/youtube-analysis/
```

### Generating a Shot Chart

```python
from src.shot_chart_analyzer import ShotChartAnalyzer

analyzer = ShotChartAnalyzer(player_id=1629060, player_name="Rui Hachimura")
analyzer.generate_chart(season="2024-25", style="goldsberry")
```

## Technical Stack

### Core Technologies

- **Python 3.13**
- **pandas 3.0.1** - Data manipulation
- **matplotlib 3.10.8** - 2D visualization
- **seaborn 0.13.2** - Statistical plotting
- **numpy 2.4.3** - Numerical computation

### AI/ML

- **YOLOv8 (ultralytics)** - Object detection
- **OpenCV 4.x** - Video processing
- **scipy 1.11+** - Statistical tests

### Data Sources

- **NBA Stats API (nba_api 1.11.4)** - Official NBA data
- **yt-dlp** - YouTube video downloads
- **B.League official PDFs** - Japanese league data

### Infrastructure

- **Docker + Docker Compose** - Reproducible environment
- **Make** - Build automation
- **Git** - Version control (not initialized yet)

## Known Issues & Limitations

### 1. Low-Resolution Video Detection

**Problem:** YOLOv8 fails on 640×360 videos
**Workaround:** Manual stats entry via `create_manual_stats.py`
**Future:** Implement color-based detection (orange ball tracking)

### 2. NBA API Rate Limiting

**Problem:** 30 requests/minute limit
**Solution:** Request caching in `data/cache/`
**Note:** Cache invalidates after 24 hours

### 3. Memory Usage

**Problem:** 3D video generation requires 8GB+ RAM
**Solution:** Docker mem_limit set to 8g in `docker-compose.yml`
**Alternative:** Use static 3D images instead of videos

## Environment Setup

### Required Environment Variables

```bash
# None currently - NBA Stats API is public
# Future: Add if implementing private data sources
```

### Docker Quick Start

```bash
make build          # Build Docker image
make analyze-three  # Run 3-video analysis
make shell          # Enter container shell
```

### Local Development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Testing Strategy

**Current state:** No formal test suite (MVP phase)

**Future:**
- Unit tests for core modules (`src/`)
- Integration tests for feature slices
- Snapshot tests for shot chart styling
- Performance benchmarks for video processing

## Performance Considerations

### Video Processing

- **10-frame sampling:** Analyze 1 frame every 10 frames (3 fps)
- **Confidence threshold:** 0.4 (40%) for YOLOv8
- **Shot deduplication:** 3-second time window

### NBA API Optimization

- **Batch requests:** Fetch full season data in single call
- **Caching:** Store responses locally
- **Async processing:** Parallel requests for multiple players

## Security & Privacy

- **No PII collected:** Only public NBA statistics
- **YouTube:** Downloaded videos stored locally, not shared
- **API keys:** None required currently
- **Data retention:** Outputs are generated artifacts, safe to share

## Contributing Guidelines

**Current state:** Personal project, not open source yet

**If opening:**
1. Fork repository
2. Create feature branch
3. Follow coding standards (this document)
4. Add tests for new features
5. Update relevant docs
6. Submit PR with clear description

## Agent-Specific Instructions

### For NBA Analysis Agent

- Always cache NBA API responses in `data/cache/`
- Use `nba_api` library, not direct HTTP requests
- Season format: "2024-25" (not "2024" or "2024-2025")
- Player ID source: `nba_api.stats.static.players.find_players_by_full_name()`

### For Video Analysis Agent

- Check video resolution before processing: `cv2.VideoCapture.get()`
- Sample every 10th frame for speed: `cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)`
- YOLOv8 class 32 = "sports ball"
- Shot threshold: 80 pixels from goal center

### For Visualization Agent

- Shot charts: 940×720 court dimensions
- Goal positions: (470, 50) top, (470, 670) bottom
- Color scheme: Green (made), Red (missed)
- Kirk Goldsberry style: Use `skills/shot-chart-generation/goldsberry_style.md`

### For Stats Reporter Agent

- Use markdown tables for readability
- Include: Total shots, FG%, Shots per minute
- Format percentages: `66.7%` not `0.667`
- Date format: `YYYY-MM-DD HH:MM:SS`

## Project Status

**Phase:** MVP Complete (2026-04-08)

**Completed:**
- ✅ NBA Finals Run analysis (5 games)
- ✅ Rui Hachimura evolution (6 seasons, 3,500+ shots)
- ✅ YouTube video analysis system (YOLOv8)
- ✅ 3D visualization pipeline (5 videos)
- ✅ Docker environment (fully reproducible)
- ✅ Manual stats entry tool (low-res fallback)
- ✅ Comprehensive documentation (86 total files)

**In Progress:**
- Manual data entry for 3 YouTube videos
- Project restructuring to Vertical Slice Architecture
- Subagent and skills setup

**Backlog:**
- Git repository initialization
- SNS account creation (X, Note)
- First 3 content posts
- Test suite implementation
- CI/CD pipeline

## Quick Reference

### Most Important Files

1. **CLAUDE.md** (this file) - Start here for context
2. **QUICK_START.md** - User-facing getting started
3. **features/[feature-name]/README.md** - Feature-specific docs
4. **src/data_loader.py** - NBA API integration
5. **src/yolo_ball_detector.py** - Video analysis core

### Common Commands

```bash
# Docker
make build && make analyze-three

# Local
source venv/bin/activate
python features/youtube-video-analysis/analyze_three_games_fast.py

# Manual stats
python features/youtube-video-analysis/create_manual_stats.py
```

### Key Metrics

- **86 total files** generated
- **35 PNG images** (shot charts, heatmaps)
- **5 MP4 videos** (3D visualizations)
- **29 documents** (reports, articles, strategies)
- **3,500+ shots** analyzed (Hachimura 6-season study)
- **9 games** processed (Finals 5 + YouTube 3 + other 1)

---

**Last Updated:** 2026-04-12
**Project Started:** 2026-03-15
**Analysis Period:** 28 days

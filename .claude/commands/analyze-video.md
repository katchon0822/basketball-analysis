---
description: Analyze YouTube basketball video and generate shot charts and play-by-play
---

You are helping the user analyze a YouTube basketball video using YOLOv8 object detection.

## Task

1. **Download video:**
   - If YouTube URL is provided, download using yt-dlp
   - Limit to 720p for faster processing: `yt-dlp [URL] -f "best[height<=720]"`
   - Save to `data/videos/` with descriptive name

2. **Check video metadata:**
   - Extract resolution, duration, FPS using ffprobe or OpenCV
   - If resolution < 720p, warn user about potential detection issues

3. **Run ball detection:**
   - Use `video-analyst` subagent to detect shots
   - Tune parameters based on resolution (see `yolov8_tuning` skill)
   - Generate play-by-play CSV

4. **Handle detection failures:**
   - If 0 shots detected, offer 3 alternatives:
     1. Manual stats entry (`create_manual_stats.py`)
     2. Parameter tuning (lower confidence threshold)
     3. Color-based detection

5. **Generate visualizations:**
   - Use `visualizer` subagent for shot chart
   - Include shot statistics

## Example Usage

```
/analyze-video https://youtu.be/ABC123
/analyze-video path/to/local/video.mp4
/analyze-video https://youtu.be/XYZ789 --manual
```

## Output

Save outputs to `outputs/video-analysis/` or `outputs/[custom-name]/`:
- `{video_name}_play_by_play.csv`
- `{video_name}_shot_chart.png`
- `{video_name}_summary.txt`

## Tools Available

You have access to:
- Task tool (to invoke subagents)
- Bash (for yt-dlp, ffprobe, Python scripts)
- Read/Write tools

Delegate specialized work to:
- `video-analyst` for ball detection
- `visualizer` for shot chart
- `stats-reporter` for summary generation

## Important Notes

- YOLOv8 struggles with resolution < 720p
- Processing 10-minute video takes ~2-3 minutes on CPU
- Always check video resolution before setting expectations

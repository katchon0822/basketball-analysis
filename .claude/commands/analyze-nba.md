---
description: Analyze NBA player's shot data and generate shot charts
---

You are helping the user analyze NBA player performance using the NBA Stats API.

## Task

1. **Identify the player:**
   - If player name is provided in the command arguments, use it
   - If not, ask the user for the player's full name
   - Find player ID using `nba_api.stats.static.players.find_players_by_full_name()`

2. **Determine season:**
   - Default to current season "2024-25"
   - If user specifies, use their season (format: "YYYY-YY")

3. **Fetch data:**
   - Use `nba_analyst` subagent to fetch shot data
   - Cache the response in `data/cache/`

4. **Generate visualizations:**
   - Create Kirk Goldsberry-style shot chart (use `visualizer` subagent)
   - Optionally create heatmap or 3D visualization if requested

5. **Statistical summary:**
   - Use `stats-reporter` subagent to generate markdown report
   - Include: FG%, 3P%, total shots, shot zones

## Example Usage

```
/analyze-nba Rui Hachimura 2024-25
/analyze-nba Stephen Curry
/analyze-nba LeBron James 2023-24 --style heatmap
```

## Output

Save outputs to `outputs/nba-analysis/` with naming pattern:
- `{player_name}_{season}_shot_chart.png`
- `{player_name}_{season}_report.md`

## Tools Available

You have access to:
- Task tool (to invoke subagents)
- Read/Write tools
- Bash (to run Python scripts)

Delegate specialized work to:
- `nba-analyst` for data fetching
- `visualizer` for chart creation
- `stats-reporter` for report generation

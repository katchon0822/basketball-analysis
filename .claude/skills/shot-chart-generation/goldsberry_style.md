# Kirk Goldsberry Style Shot Chart - Design Guide

This skill provides best practices for creating professional basketball shot charts following Kirk Goldsberry's influential visualization style.

## Core Design Principles

### 1. Simplicity and Clarity
- Minimize visual clutter
- Let the data speak for itself
- Use intuitive color schemes
- Clear typography hierarchy

### 2. Actionable Insights
- Highlight patterns immediately visible
- Use color to convey efficiency
- Show both volume (size) and accuracy (color)

### 3. Professional Aesthetic
- Clean lines and spacing
- Consistent styling across charts
- Publication-ready quality

## Color Palette

### Primary Shot Colors

```python
# Made shots (successful)
MADE_COLOR = '#00AA00'        # Green
MADE_EDGE = '#006600'         # Dark green
MADE_ALPHA = 0.7              # Transparency

# Missed shots (unsuccessful)
MISSED_COLOR = '#FF0000'      # Red
MISSED_EDGE = '#AA0000'       # Dark red
MISSED_ALPHA = 0.5            # More transparent

# Alternative gradient (for heatmaps)
HEATMAP_CMAP = 'RdYlGn'      # Red-Yellow-Green
```

### Court Elements

```python
# Background and court
BACKGROUND_COLOR = '#F5F5F5'  # Light gray
COURT_COLOR = '#FFFFFF'       # White
COURT_LINE_COLOR = '#333333'  # Dark gray
COURT_LINE_WIDTH = 3          # pixels

# Goals/baskets
GOAL_FILL = '#FFE5D9'        # Light orange
GOAL_EDGE = '#FF6B35'        # Orange
GOAL_ALPHA = 0.7

# 3-point line
THREE_PT_COLOR = '#00AA00'   # Green
THREE_PT_STYLE = '--'        # Dashed
THREE_PT_ALPHA = 0.6
```

## Typography

### Font Hierarchy

```python
# Title
TITLE_FONT_SIZE = 16
TITLE_FONT_WEIGHT = 'bold'
TITLE_COLOR = '#000000'

# Subtitle (stats)
SUBTITLE_FONT_SIZE = 12
SUBTITLE_FONT_WEIGHT = 'normal'
SUBTITLE_COLOR = '#333333'

# Legend
LEGEND_FONT_SIZE = 10
LEGEND_COLOR = '#333333'

# Font family (system default or specified)
FONT_FAMILY = 'Hiragino Sans'  # macOS
# FONT_FAMILY = 'Arial'         # Cross-platform
```

### Title Format

```python
# Player name - Season - Chart type
title = f"{player_name} - {season} - Shot Chart"

# With statistics
title_with_stats = (
    f"{player_name} - {season}\n"
    f"FG%: {fg_pct:.1f}% | 3P%: {three_pct:.1f}% | {total_shots} Shots"
)
```

## Marker Styling

### Size and Shape

```python
# Made shots
MADE_MARKER_SIZE = 150      # Larger, more prominent
MADE_MARKER_SHAPE = 'o'     # Circle
MADE_EDGE_WIDTH = 2.5       # Thicker edge

# Missed shots
MISSED_MARKER_SIZE = 100    # Smaller
MISSED_MARKER_SHAPE = 'x'   # X mark (or 'o' with less opacity)
MISSED_EDGE_WIDTH = 2.0     # Thinner edge
```

### Matplotlib Implementation

```python
import matplotlib.pyplot as plt

# Made shots
ax.scatter(
    made_x, made_y,
    c=MADE_COLOR,
    s=MADE_MARKER_SIZE,
    alpha=MADE_ALPHA,
    edgecolors=MADE_EDGE,
    linewidths=MADE_EDGE_WIDTH,
    marker=MADE_MARKER_SHAPE,
    label='Made Shot',
    zorder=3  # Draw on top
)

# Missed shots
ax.scatter(
    missed_x, missed_y,
    c=MISSED_COLOR,
    s=MISSED_MARKER_SIZE,
    alpha=MISSED_ALPHA,
    edgecolors=MISSED_EDGE,
    linewidths=MISSED_EDGE_WIDTH,
    marker=MISSED_MARKER_SHAPE,
    label='Missed Shot',
    zorder=2  # Draw below made shots
)
```

## Court Diagram

### Standard Court Dimensions

```python
# Full court in pixels (940×720)
COURT_WIDTH = 940
COURT_HEIGHT = 720

# Court outline (with margins)
COURT_LEFT = 50
COURT_TOP = 0
COURT_RIGHT = 890  # COURT_LEFT + 840
COURT_BOTTOM = 720

# Center line
CENTER_LINE_Y = 360

# Goals
TOP_GOAL_X = 420
TOP_GOAL_Y = 0
TOP_GOAL_WIDTH = 100
TOP_GOAL_HEIGHT = 50

BOTTOM_GOAL_X = 420
BOTTOM_GOAL_Y = 670
BOTTOM_GOAL_WIDTH = 100
BOTTOM_GOAL_HEIGHT = 50

# 3-point arc radius
THREE_POINT_RADIUS = 210
```

### Drawing Court Elements

```python
import matplotlib.patches as patches

def draw_goldsberry_court(ax):
    """Draw court in Kirk Goldsberry style."""
    # Background
    ax.set_facecolor(BACKGROUND_COLOR)

    # Court outline
    court = patches.Rectangle(
        (COURT_LEFT, COURT_TOP),
        COURT_RIGHT - COURT_LEFT,
        COURT_BOTTOM - COURT_TOP,
        linewidth=COURT_LINE_WIDTH,
        edgecolor=COURT_LINE_COLOR,
        facecolor=COURT_COLOR,
        zorder=1
    )
    ax.add_patch(court)

    # Center line
    ax.plot(
        [COURT_LEFT, COURT_RIGHT],
        [CENTER_LINE_Y, CENTER_LINE_Y],
        color=COURT_LINE_COLOR,
        linewidth=2.5,
        zorder=1
    )

    # Top goal (basket)
    top_goal = patches.Rectangle(
        (TOP_GOAL_X, TOP_GOAL_Y),
        TOP_GOAL_WIDTH,
        TOP_GOAL_HEIGHT,
        linewidth=2.5,
        edgecolor=GOAL_EDGE,
        facecolor=GOAL_FILL,
        alpha=GOAL_ALPHA,
        zorder=1
    )
    ax.add_patch(top_goal)
    ax.text(
        470, 25, 'チームA',
        ha='center', va='center',
        fontsize=13, fontweight='bold',
        color='#333', zorder=2
    )

    # Bottom goal
    bottom_goal = patches.Rectangle(
        (BOTTOM_GOAL_X, BOTTOM_GOAL_Y),
        BOTTOM_GOAL_WIDTH,
        BOTTOM_GOAL_HEIGHT,
        linewidth=2.5,
        edgecolor='#4a90e2',
        facecolor='#d6e9ff',
        alpha=GOAL_ALPHA,
        zorder=1
    )
    ax.add_patch(bottom_goal)
    ax.text(
        470, 695, 'チームB',
        ha='center', va='center',
        fontsize=13, fontweight='bold',
        color='#333', zorder=2
    )

    # 3-point arcs
    arc_top = patches.Arc(
        (470, TOP_GOAL_Y + TOP_GOAL_HEIGHT),
        THREE_POINT_RADIUS * 2,
        THREE_POINT_RADIUS * 2,
        theta1=180, theta2=0,
        linewidth=2,
        edgecolor=THREE_PT_COLOR,
        linestyle=THREE_PT_STYLE,
        alpha=THREE_PT_ALPHA,
        zorder=1
    )
    ax.add_patch(arc_top)

    arc_bottom = patches.Arc(
        (470, BOTTOM_GOAL_Y),
        THREE_POINT_RADIUS * 2,
        THREE_POINT_RADIUS * 2,
        theta1=0, theta2=180,
        linewidth=2,
        edgecolor=THREE_PT_COLOR,
        linestyle=THREE_PT_STYLE,
        alpha=THREE_PT_ALPHA,
        zorder=1
    )
    ax.add_patch(arc_bottom)

    # Set limits and remove axes
    ax.set_xlim(0, COURT_WIDTH)
    ax.set_ylim(COURT_HEIGHT, 0)  # Flip Y-axis
    ax.axis('off')

    return ax
```

## Layout and Composition

### Figure Size

```python
# Single chart
fig, ax = plt.subplots(figsize=(10, 12))

# Multi-chart comparison (2×3 grid)
fig, axes = plt.subplots(2, 3, figsize=(18, 12))
```

### Legend Placement

```python
# Upper right corner (Goldsberry standard)
ax.legend(
    loc='upper right',
    fontsize=LEGEND_FONT_SIZE,
    framealpha=0.9,
    edgecolor='#CCCCCC',
    fancybox=False
)
```

### Title and Stats

```python
# Title with two lines: name and stats
ax.set_title(
    f'{player_name} - {season} - Shot Chart\n'
    f'FG%: {fg_pct:.1f}% | 3P%: {three_pct:.1f}% | Total: {total_shots} shots',
    fontsize=TITLE_FONT_SIZE,
    fontweight=TITLE_FONT_WEIGHT,
    pad=20  # Space above chart
)
```

## Advanced Variations

### Heatmap Style

For frequency/efficiency visualization:

```python
import matplotlib.pyplot as plt

# Hexbin for shot frequency
hexbin = ax.hexbin(
    shots_x, shots_y,
    gridsize=12,
    cmap='Blues',      # Or 'RdYlGn' for efficiency
    alpha=0.8,
    edgecolors='white',
    linewidths=0.5,
    mincnt=1,          # Minimum 1 shot to show
    zorder=2
)

# Colorbar
plt.colorbar(
    hexbin,
    label='Shot Attempts',
    ax=ax,
    pad=0.02,
    shrink=0.8
)
```

### Zone-Based Coloring

Color by FG% in each zone:

```python
# Calculate FG% per shot
colors = []
for _, shot in shots.iterrows():
    if shot['SHOT_MADE_FLAG'] == 1:
        colors.append(MADE_COLOR)
    else:
        colors.append(MISSED_COLOR)

# Or use gradient based on local FG%
from scipy.ndimage import gaussian_filter
# ... calculate local FG% with smoothing ...
ax.scatter(x, y, c=local_fg_pcts, cmap='RdYlGn', vmin=0, vmax=100)
```

## Output Quality

### Resolution and DPI

```python
# Save at high resolution
plt.savefig(
    'shot_chart.png',
    dpi=300,                # Print quality
    bbox_inches='tight',    # Trim whitespace
    facecolor='white',      # White background
    edgecolor='none'
)

# Or for web
plt.savefig(
    'shot_chart_web.png',
    dpi=150,               # Screen quality
    bbox_inches='tight'
)
```

### File Size Optimization

```python
# PNG with compression
plt.savefig(
    'shot_chart.png',
    dpi=300,
    bbox_inches='tight',
    pil_kwargs={'optimize': True, 'quality': 85}
)

# SVG for vector graphics (scalable)
plt.savefig('shot_chart.svg', bbox_inches='tight')
```

## Complete Example

```python
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd

def create_goldsberry_shot_chart(shots_df, player_name, season, output_path):
    """
    Create a Kirk Goldsberry-style shot chart.

    Args:
        shots_df: DataFrame with columns ['LOC_X', 'LOC_Y', 'SHOT_MADE_FLAG']
        player_name: Player's name (str)
        season: Season (str, e.g., "2024-25")
        output_path: Where to save the chart
    """
    # Setup
    fig, ax = plt.subplots(figsize=(10, 12))
    draw_goldsberry_court(ax)

    # Separate made/missed
    made = shots_df[shots_df['SHOT_MADE_FLAG'] == 1]
    missed = shots_df[shots_df['SHOT_MADE_FLAG'] == 0]

    # Plot missed first (behind)
    ax.scatter(
        missed['LOC_X'], missed['LOC_Y'],
        c='#FF0000', s=100, alpha=0.5,
        edgecolors='#AA0000', linewidths=2,
        marker='x', label='Missed',
        zorder=2
    )

    # Plot made on top
    ax.scatter(
        made['LOC_X'], made['LOC_Y'],
        c='#00AA00', s=150, alpha=0.7,
        edgecolors='#006600', linewidths=2.5,
        marker='o', label='Made',
        zorder=3
    )

    # Calculate stats
    total = len(shots_df)
    fg_pct = (len(made) / total * 100) if total > 0 else 0

    # Title with stats
    ax.set_title(
        f'{player_name} - {season} - Shot Chart\n'
        f'FG%: {fg_pct:.1f}% ({len(made)}/{total} shots)',
        fontsize=16, fontweight='bold', pad=20
    )

    # Legend
    ax.legend(loc='upper right', fontsize=11, framealpha=0.9)

    # Save
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"✅ Shot chart saved: {output_path}")

# Usage
shots = pd.read_pickle('data/cache/player_1629060_2024-25.pkl')
create_goldsberry_shot_chart(shots, 'Rui Hachimura', '2024-25',
                             'outputs/hachimura_goldsberry.png')
```

## Common Mistakes to Avoid

❌ **Don't:**
- Use too many colors (confusing)
- Make markers too large (overlapping)
- Forget to separate made/missed visually
- Use low DPI for print (< 300)
- Overcomplicate with unnecessary elements

✅ **Do:**
- Stick to 2-3 primary colors
- Size markers appropriately for data density
- Use color + shape to distinguish categories
- Export at 300 DPI for publication
- Keep it simple and readable

## References

This style guide is based on:
- Kirk Goldsberry's shot chart visualizations (ESPN, Grantland)
- Modern data visualization best practices
- Basketball analytics community standards

"""
shots.csv → FIBA ハーフコート ショットチャート生成

出力:
  outputs/shot_chart_fiba.png   全シュート（チーム別）
  outputs/shot_chart_team.png   白チーム / 紺チーム 分割表示
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Circle, Arc, Rectangle, FancyArrowPatch
import os

try:
    import japanize_matplotlib
except ImportError:
    pass

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── コート描画（NBA座標系: ±250 x, -47.5~422.5 y）──────────────
def draw_nba_court(ax, color='black', lw=1.5):
    # ゴール・バックボード
    ax.add_patch(Circle((0, 0), 7.5, color=color, lw=lw, fill=False))
    ax.add_patch(Rectangle((-30, -7.5), 60, -1, color=color, lw=lw))

    # ペイントエリア
    ax.add_patch(Rectangle((-80, -47.5), 160, 190, color=color, lw=lw, fill=False))
    ax.add_patch(Rectangle((-60, -47.5), 120, 190, color=color, lw=lw, fill=False))

    # フリースローサークル
    ax.add_patch(Arc((0, 142.5), 120, 120, theta1=0,   theta2=180, color=color, lw=lw))
    ax.add_patch(Arc((0, 142.5), 120, 120, theta1=180, theta2=360, color=color, lw=lw, linestyle='dashed'))

    # 3ポイントライン
    ax.add_patch(Rectangle((-220, -47.5), 0, 140, color=color, lw=lw))
    ax.add_patch(Rectangle(( 220, -47.5), 0, 140, color=color, lw=lw))
    ax.add_patch(Arc((0, 0), 475, 475, theta1=22, theta2=158, color=color, lw=lw))

    # エンドライン・センター境界
    ax.add_patch(Rectangle((-250, -47.5), 500, 470, color=color, lw=lw, fill=False))

    # センターサークル（半分）
    ax.add_patch(Arc((0, 422.5), 120, 120, theta1=180, theta2=0, color=color, lw=lw))

    ax.set_xlim(-260, 260)
    ax.set_ylim(-60, 430)
    ax.set_aspect('equal')
    ax.axis('off')


# ── データ読み込み ──────────────────────────────────────────────
df = pd.read_csv("outputs/hsv_only/shots.csv")
print(f"Total shots: {len(df)}")
print(df['team'].value_counts())
print(df['made'].value_counts())

# made 列を bool に統一
df['made'] = df['made'].astype(str).str.strip().str.lower().isin(['true', '1', 'yes'])

teams      = {'白': ('#3399FF', 'White'), '紺': ('#003399', 'Navy'), '不明': ('#999999', 'Unknown')}


# ── ① 全シュート 1枚図 ──────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 9), facecolor='#F8F8F0')
ax.set_facecolor('#F8F8F0')
draw_nba_court(ax)

for _, row in df.iterrows():
    x, y = row['nba_x'], row['nba_y']
    color, _ = teams.get(row['team'], ('#999999', 'Unknown'))
    if row['made']:
        ax.scatter(x, y, c=color, s=120, marker='o', edgecolors='black', lw=0.8, zorder=3, alpha=0.85)
    else:
        ax.scatter(x, y, c=color, s=80,  marker='x', linewidths=1.5, zorder=3, alpha=0.6)

# 凡例
legend_handles = [
    mpatches.Patch(color='#3399FF', label='White team'),
    mpatches.Patch(color='#003399', label='Navy team'),
    mpatches.Patch(color='#999999', label='Unknown'),
    plt.Line2D([0],[0], marker='o', color='gray', markersize=8, label='Made', lw=0),
    plt.Line2D([0],[0], marker='x', color='gray', markersize=8, label='Missed', markeredgewidth=2, lw=0),
]
ax.legend(handles=legend_handles, loc='upper right', fontsize=10, framealpha=0.9)

n_made   = df['made'].sum()
n_total  = len(df)
fg_pct   = n_made / n_total * 100
ax.set_title(f"Shot Chart  FG: {n_made}/{n_total} ({fg_pct:.1f}%)",
             fontsize=14, fontweight='bold', pad=12)

out1 = os.path.join(OUTPUT_DIR, "shot_chart_fiba.png")
plt.tight_layout()
plt.savefig(out1, dpi=150, bbox_inches='tight')
plt.close()
print(f"Saved: {out1}")


# ── ② チーム別 2パネル ────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(18, 9), facecolor='#F8F8F0')
fig.suptitle("Shot Chart by Team", fontsize=16, fontweight='bold')

for ax, (team_name, team_color, label) in zip(axes, [('白', '#3399FF', 'White'), ('紺', '#003399', 'Navy')]):
    ax.set_facecolor('#F8F8F0')
    draw_nba_court(ax, color='#444444')
    sub = df[df['team'] == team_name]

    made_s   = sub[sub['made']]
    missed_s = sub[~sub['made']]

    ax.scatter(missed_s['nba_x'], missed_s['nba_y'],
               c=team_color, s=100, marker='x', linewidths=2, alpha=0.7, label='Missed')
    ax.scatter(made_s['nba_x'],   made_s['nba_y'],
               c=team_color, s=140, marker='o', edgecolors='black', lw=0.8, alpha=0.9, label='Made')

    fg = f"{len(made_s)}/{len(sub)} ({len(made_s)/len(sub)*100:.1f}%)" if len(sub) > 0 else "0/0"
    ax.set_title(f"{label} Team  FG: {fg}", fontsize=13, fontweight='bold')
    ax.legend(fontsize=10, loc='upper right', framealpha=0.9)

out2 = os.path.join(OUTPUT_DIR, "shot_chart_team.png")
plt.tight_layout()
plt.savefig(out2, dpi=150, bbox_inches='tight')
plt.close()
print(f"Saved: {out2}")


# ── ③ ゾーン別集計 ───────────────────────────────────────────
print("\n--- Zone summary ---")
zone_stats = df.groupby(['team', 'zone'])['made'].agg(['sum','count']).rename(columns={'sum':'made','count':'attempts'})
zone_stats['fg_pct'] = (zone_stats['made'] / zone_stats['attempts'] * 100).round(1)
print(zone_stats.to_string())

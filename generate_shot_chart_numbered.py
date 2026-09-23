"""
番号付きショットチャート + コンタクトシート対応版

出力:
  outputs/shot_chart_numbered.jpg  — 番号付きショットチャート
  outputs/shot_chart_contact.jpg   — チャート（左）＋コンタクトシート（右）の対応表
"""

import cv2
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Circle, Arc, Rectangle
import os

VIDEO   = "data/videos/game_EE1swQMsXJc_720p.mp4"
CSV     = "outputs/hsv_only/shots.csv"
OUT_DIR = "outputs"

df = pd.read_csv(CSV)
df['made'] = df['made'].astype(str).str.strip().str.lower().isin(['true', '1', 'yes'])
TEAM_MAP = {'白': 'White', '紺': 'Navy', '不明': 'Unknown'}
TEAM_COLOR = {'White': '#3399FF', 'Navy': '#003399', 'Unknown': '#999999'}


# ── コート描画 ──────────────────────────────────────
def draw_nba_court(ax, color='#333333', lw=1.5):
    ax.add_patch(Circle((0, 0), 7.5, color=color, lw=lw, fill=False))
    ax.add_patch(Rectangle((-30, -7.5), 60, -1, color=color, lw=lw))
    ax.add_patch(Rectangle((-80, -47.5), 160, 190, color=color, lw=lw, fill=False))
    ax.add_patch(Rectangle((-60, -47.5), 120, 190, color=color, lw=lw, fill=False))
    ax.add_patch(Arc((0, 142.5), 120, 120, theta1=0,   theta2=180, color=color, lw=lw))
    ax.add_patch(Arc((0, 142.5), 120, 120, theta1=180, theta2=360, color=color, lw=lw, linestyle='dashed'))
    ax.add_patch(Rectangle((-220, -47.5), 0, 140, color=color, lw=lw))
    ax.add_patch(Rectangle(( 220, -47.5), 0, 140, color=color, lw=lw))
    ax.add_patch(Arc((0, 0), 475, 475, theta1=22, theta2=158, color=color, lw=lw))
    ax.add_patch(Rectangle((-250, -47.5), 500, 470, color=color, lw=lw, fill=False))
    ax.add_patch(Arc((0, 422.5), 120, 120, theta1=180, theta2=0, color=color, lw=lw))
    ax.set_xlim(-260, 260)
    ax.set_ylim(-60, 430)
    ax.set_aspect('equal')
    ax.axis('off')


# ── ① 番号付きショットチャート（matplotlib → PNG → cv2）─────
fig, ax = plt.subplots(figsize=(9, 8), facecolor='#F5F5EE')
ax.set_facecolor('#F5F5EE')
draw_nba_court(ax)

for _, row in df.iterrows():
    x, y   = row['nba_x'], row['nba_y']
    team   = TEAM_MAP.get(str(row['team']), 'Unknown')
    color  = TEAM_COLOR[team]
    no     = int(row['No'])
    made   = bool(row['made'])

    marker = 'o' if made else 'x'
    ms     = 120 if made else 80
    ax.scatter(x, y, c=color, s=ms, marker=marker,
               edgecolors='black' if made else 'none',
               linewidths=0.8 if made else 1.8,
               zorder=3, alpha=0.85)
    # 番号ラベル
    ax.text(x + 8, y + 6, str(no), fontsize=6.5, color='black',
            fontweight='bold', zorder=4,
            bbox=dict(boxstyle='round,pad=0.1', fc='white', ec='none', alpha=0.7))

legend_handles = [
    mpatches.Patch(color='#3399FF', label='White'),
    mpatches.Patch(color='#003399', label='Navy'),
    mpatches.Patch(color='#999999', label='Unknown'),
    plt.Line2D([0],[0], marker='o', color='gray', ms=7, label='Made', lw=0),
    plt.Line2D([0],[0], marker='x', color='gray', ms=7, label='Missed',
               markeredgewidth=2, lw=0),
]
ax.legend(handles=legend_handles, loc='upper right', fontsize=8, framealpha=0.9)
n_made  = df['made'].sum()
ax.set_title(f"Shot Chart (numbered)  FG: {n_made}/{len(df)} ({n_made/len(df)*100:.1f}%)",
             fontsize=12, fontweight='bold')

chart_path = os.path.join(OUT_DIR, "shot_chart_numbered.png")
plt.savefig(chart_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"Saved: {chart_path}")


# ── ② コンタクトシート（番号 + フレーム）────────────────────
THUMB_W, THUMB_H = 280, 158
BAR_H = 24
COLS  = 6
MARGIN = 3

cap = cv2.VideoCapture(VIDEO)
fps = cap.get(cv2.CAP_PROP_FPS)

cells = []
for _, row in df.iterrows():
    ts      = float(row['timestamp'])
    frame_n = int(ts * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_n)
    ret, frame = cap.read()
    if not ret:
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    thumb = cv2.resize(frame, (THUMB_W, THUMB_H))

    team   = TEAM_MAP.get(str(row.get('team', '?')), '?')
    made   = bool(row['made'])
    zone   = str(row.get('zone', ''))
    no     = int(row['No'])
    label  = f"#{no} {row['time']}  {team}  {zone}  {'MADE' if made else 'miss'}"

    bar_color = (0, 140, 0) if made else (40, 40, 180)
    bar = np.full((BAR_H, THUMB_W, 3), bar_color, dtype=np.uint8)
    cv2.putText(bar, label, (4, BAR_H - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (255, 255, 255), 1, cv2.LINE_AA)

    # 番号を大きく左上に
    cv2.rectangle(thumb, (0, 0), (22, 18), (0, 0, 0), -1)
    cv2.putText(thumb, str(no), (2, 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1, cv2.LINE_AA)

    cells.append(np.vstack([thumb, bar]))
cap.release()

cell_h  = THUMB_H + BAR_H
rows    = (len(cells) + COLS - 1) // COLS
sheet_w = COLS * (THUMB_W + MARGIN) + MARGIN
sheet_h = rows * (cell_h + MARGIN) + MARGIN
sheet   = np.full((sheet_h, sheet_w, 3), 25, dtype=np.uint8)

for i, cell in enumerate(cells):
    r, c = divmod(i, COLS)
    y = MARGIN + r * (cell_h + MARGIN)
    x = MARGIN + c * (THUMB_W + MARGIN)
    sheet[y:y+cell_h, x:x+THUMB_W] = cell

contact_path = os.path.join(OUT_DIR, "shot_contact_numbered.jpg")
cv2.imwrite(contact_path, sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
print(f"Saved: {contact_path}")


# ── ③ 左右並べた対応表 ──────────────────────────────────────
chart_img   = cv2.imread(chart_path)
contact_img = cv2.imread(contact_path)

# 高さを揃えて横連結
th = max(chart_img.shape[0], contact_img.shape[0])
def pad_h(img, h):
    if img.shape[0] < h:
        pad = np.full((h - img.shape[0], img.shape[1], 3), 25, dtype=np.uint8)
        return np.vstack([img, pad])
    return img

combined = np.hstack([pad_h(chart_img, th), pad_h(contact_img, th)])
combined_path = os.path.join(OUT_DIR, "shot_chart_contact.jpg")
cv2.imwrite(combined_path, combined, [cv2.IMWRITE_JPEG_QUALITY, 90])
print(f"Saved: {combined_path}")

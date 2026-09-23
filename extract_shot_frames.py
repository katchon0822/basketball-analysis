"""
shots.csv の各シュートをタイムスタンプで動画から切り出して
コンタクトシート (8列 × n行) として保存する。

出力: outputs/shot_frames/shot_{No:02d}_t{time}.jpg  (個別)
      outputs/shot_contact_sheet.jpg                  (一覧)
"""

import cv2
import pandas as pd
import numpy as np
import os

VIDEO   = "data/videos/game_EE1swQMsXJc_720p.mp4"
CSV     = "outputs/hsv_only/shots.csv"
OUT_DIR = "outputs/shot_frames"
SHEET   = "outputs/shot_contact_sheet.jpg"
os.makedirs(OUT_DIR, exist_ok=True)

THUMB_W  = 320
THUMB_H  = 180
COLS     = 6
MARGIN   = 4
BAR_H    = 28  # ラベル帯の高さ

df  = pd.read_csv(CSV)
df['made'] = df['made'].astype(str).str.strip().str.lower().isin(['true', '1', 'yes'])

cap = cv2.VideoCapture(VIDEO)
fps = cap.get(cv2.CAP_PROP_FPS)
print(f"Video: {fps:.2f}fps  Shots: {len(df)}")

frames_out = []

for _, row in df.iterrows():
    ts      = float(row['timestamp'])
    frame_n = int(ts * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_n)
    ret, frame = cap.read()
    if not ret:
        print(f"  [WARN] frame {frame_n} (t={ts:.1f}s) read failed")
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    # サムネイル
    thumb = cv2.resize(frame, (THUMB_W, THUMB_H))

    # ラベルバー
    team_map = {'白': 'White', '紺': 'Navy', '不明': 'Unknown'}
    team  = team_map.get(str(row.get('team', '?')), str(row.get('team', '?')))
    made  = bool(row['made'])
    zone  = str(row.get('zone', ''))
    label = f"#{int(row['No'])} {row['time']}  {team}  {zone}  {'MADE' if made else 'miss'}"
    bar_color = (0, 160, 0) if made else (0, 0, 180)
    bar = np.full((BAR_H, THUMB_W, 3), bar_color, dtype=np.uint8)
    cv2.putText(bar, label, (4, BAR_H - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.36,
                (255, 255, 255), 1, cv2.LINE_AA)

    cell = np.vstack([thumb, bar])
    frames_out.append(cell)

    # 個別保存
    fname = f"shot_{int(row['No']):02d}_t{row['time'].replace(':','')}.jpg"
    cv2.imwrite(os.path.join(OUT_DIR, fname), frame)

cap.release()

# ── コンタクトシート ────────────────────────────────
cell_h = THUMB_H + BAR_H
rows   = (len(frames_out) + COLS - 1) // COLS
sheet_w = COLS * (THUMB_W + MARGIN) + MARGIN
sheet_h = rows * (cell_h + MARGIN) + MARGIN
sheet   = np.full((sheet_h, sheet_w, 3), 30, dtype=np.uint8)

for i, cell in enumerate(frames_out):
    r, c = divmod(i, COLS)
    y = MARGIN + r * (cell_h + MARGIN)
    x = MARGIN + c * (THUMB_W + MARGIN)
    sheet[y:y+cell_h, x:x+THUMB_W] = cell

cv2.imwrite(SHEET, sheet)
print(f"Contact sheet -> {SHEET}")
print(f"Individual frames -> {OUT_DIR}/")

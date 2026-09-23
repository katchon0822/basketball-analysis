#!/usr/bin/env python3
"""
quick_shot_chart.py — キャリブレーション不要のクイックシュートチャート

アルゴリズム:
  1. MOG2背景差分 × オレンジ色フィルタ でボール候補を検出
  2. フレーム間IoUトラッキングで軌跡を構築
  3. 放物線フィット (R²>0.70) でシュートを検出
  4. ショットチャート画像を出力 (コート図 + 各シュート位置)

Usage:
  python quick_shot_chart.py --video data/videos/game_2-1.mp4 --sec 30
"""

import cv2
import numpy as np
import json
import argparse
from pathlib import Path
from collections import deque
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# ── パラメータ ────────────────────────────────────────────────────────
ORANGE_LO  = np.array([ 5, 100, 100])   # HSV lower
ORANGE_HI  = np.array([25, 255, 255])   # HSV upper
BALL_R_MIN = 4       # px
BALL_R_MAX = 22      # px
CIRC_MIN   = 0.45    # 円形度
MOTION_THR = 15      # 背景差分の閾値

SKIP       = 2       # N フレームごとに処理
TRACK_DIST = 50      # トラッキング: 前フレームからの最大移動距離 (px)
MIN_TRAJ   = 8       # 最小軌跡長 (フレーム数)
FIT_WIN    = 12      # 放物線フィットのウィンドウ幅 (フレーム)
R2_THR     = 0.70    # 放物線フィット R² 閾値
DEDUP_DIST = 60      # 重複シュート除外距離 (px)

OUT_DIR    = Path("outputs/quick_shot")
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── ボール検出 ────────────────────────────────────────────────────────
def detect_ball_candidates(frame, fgmask):
    hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    cmask = cv2.inRange(hsv, ORANGE_LO, ORANGE_HI)
    # 背景差分と AND
    combined = cv2.bitwise_and(cmask, fgmask)
    combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN,  np.ones((3,3), np.uint8))
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, np.ones((7,7), np.uint8))

    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cands = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 1:
            continue
        peri = cv2.arcLength(cnt, True)
        circ = 4 * np.pi * area / (peri * peri + 1e-9)
        if circ < CIRC_MIN:
            continue
        (cx, cy), r = cv2.minEnclosingCircle(cnt)
        if not (BALL_R_MIN <= r <= BALL_R_MAX):
            continue
        cands.append((float(cx), float(cy), float(r)))
    return cands


# ── シンプルトラッカー ────────────────────────────────────────────────
class BallTracker:
    def __init__(self):
        self.tracks: dict[int, deque] = {}   # id → deque of (fi, x, y)
        self._next_id = 0
        self._last_pos: dict[int, tuple] = {}

    def update(self, fi, cands):
        if not cands:
            return
        used = set()
        for cid, (lx, ly) in list(self._last_pos.items()):
            best, best_d = None, float('inf')
            for i, (cx, cy, r) in enumerate(cands):
                if i in used:
                    continue
                d = np.hypot(cx - lx, cy - ly)
                if d < TRACK_DIST and d < best_d:
                    best_d, best = d, i
            if best is not None:
                cx, cy, _ = cands[best]
                self.tracks[cid].append((fi, cx, cy))
                self._last_pos[cid] = (cx, cy)
                used.add(best)

        for i, (cx, cy, r) in enumerate(cands):
            if i not in used:
                nid = self._next_id
                self._next_id += 1
                self.tracks[nid] = deque([(fi, cx, cy)], maxlen=200)
                self._last_pos[nid] = (cx, cy)

    def long_tracks(self):
        return {k: list(v) for k, v in self.tracks.items() if len(v) >= MIN_TRAJ}


# ── 放物線フィット → シュート検出 ─────────────────────────────────────
def fit_parabola(ys, xs):
    """y = a*x^2 + b*x + c を fit (x=frame, y=ピクセルy). 上向き放物線 (a>0) を想定"""
    if len(xs) < 4:
        return None, 0.0
    try:
        coeffs = np.polyfit(xs, ys, 2)
        a, b, c = coeffs
        if a <= 0:   # y は上から下なので上向き放物線 (ピクセルyが増える) → a>0
            return None, 0.0
        pred = np.polyval(coeffs, xs)
        ss_res = np.sum((np.array(ys) - pred)**2)
        ss_tot = np.sum((np.array(ys) - np.mean(ys))**2)
        r2 = 1 - ss_res / (ss_tot + 1e-9)
        return coeffs, r2
    except Exception:
        return None, 0.0


def detect_shots(tracks, fps):
    shots = []
    for tid, pts in tracks.items():
        pts = sorted(pts, key=lambda p: p[0])
        n = len(pts)
        for start in range(0, n - FIT_WIN + 1, FIT_WIN // 2):
            window = pts[start:start + FIT_WIN]
            if len(window) < 4:
                continue
            fis = [p[0] for p in window]
            ys  = [p[2] for p in window]   # y pixel (下向き増加)
            xs  = [p[1] for p in window]   # x pixel
            coeffs, r2 = fit_parabola(ys, fis)
            if coeffs is not None and r2 >= R2_THR:
                # 射出点 (最初のフレーム)
                launch_fi, lx, ly = window[0]
                # 最高点 (ポテンシャルのシュートピーク)
                a, b, _ = coeffs
                peak_fi = -b / (2 * a)
                if fis[0] <= peak_fi <= fis[-1]:
                    # シュートとして記録
                    ts = launch_fi / fps
                    shots.append({
                        "track_id": tid,
                        "launch_fi": launch_fi,
                        "launch_x":  lx,
                        "launch_y":  ly,
                        "peak_fi":   peak_fi,
                        "r2":        round(r2, 3),
                        "ts":        round(ts, 1),
                    })
    # 重複除去 (近い位置は同じシュート)
    shots.sort(key=lambda s: s["launch_fi"])
    deduped = []
    for s in shots:
        if not any(
            np.hypot(s["launch_x"] - d["launch_x"], s["launch_y"] - d["launch_y"]) < DEDUP_DIST
            and abs(s["launch_fi"] - d["launch_fi"]) < 30
            for d in deduped
        ):
            deduped.append(s)
    return deduped


# ── シュートチャート出力 ───────────────────────────────────────────────
def make_shot_chart(shots, ref_frame, video_name, total_frames, fps):
    h, w = ref_frame.shape[:2]

    # ── (1) ビデオフレーム上のショット位置 ──────────────────────────
    vis = ref_frame.copy()
    for i, s in enumerate(shots):
        cx, cy = int(s["launch_x"]), int(s["launch_y"])
        cv2.circle(vis, (cx, cy), 12, (0, 80, 255), -1)
        cv2.circle(vis, (cx, cy), 12, (255, 255, 255), 2)
        cv2.putText(vis, str(i + 1), (cx - 5, cy + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    cv2.putText(vis, f"Shot positions (n={len(shots)}, no calibration)",
                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 200), 2)
    out1 = OUT_DIR / f"{video_name}_shots_on_frame.jpg"
    cv2.imwrite(str(out1), vis)
    print(f"Saved: {out1}")

    # ── (2) matplotlib でコート図風ショットチャート ──────────────────
    # キャリブレーションなしなのでピクセル座標をそのまま使う
    # 映像座標系をコート図として表示 (右90度回転してハーフコート風に)
    fig, ax = plt.subplots(figsize=(8, 5), facecolor="#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    # 映像フレームを背景に表示 (暗くして)
    frame_rgb = cv2.cvtColor(ref_frame, cv2.COLOR_BGR2RGB)
    ax.imshow(frame_rgb, alpha=0.35, extent=[0, w, h, 0])

    # シュート位置をプロット
    for i, s in enumerate(shots):
        cx, cy = s["launch_x"], s["launch_y"]
        ax.plot(cx, cy, 'o', color="#FF4444", markersize=12,
                markeredgecolor="white", markeredgewidth=1.5, zorder=5)
        ax.text(cx, cy - 14, str(i + 1), color="white", fontsize=8,
                ha="center", fontweight="bold", zorder=6)

    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"Shot Chart — {video_name}  (n={len(shots)}, pre-calibration)",
                 color="white", fontsize=12, pad=8)
    ax.text(0.5, -0.04,
            "※ Court coordinates are pixel-based (calibrate for accurate positions)",
            transform=ax.transAxes, ha="center", color="#888888", fontsize=8)

    plt.tight_layout()
    out2 = OUT_DIR / f"{video_name}_shot_chart.png"
    fig.savefig(out2, dpi=120, bbox_inches="tight", facecolor="#1a1a2e")
    plt.close(fig)
    print(f"Saved: {out2}")

    # ── (3) タイムライン出力 ─────────────────────────────────────────
    print(f"\n{'#':>3}  {'time':>6}  {'x':>5}  {'y':>5}  {'R2':>5}  track_id")
    for i, s in enumerate(shots):
        ts = s['ts']
        mm, ss = int(ts // 60), int(ts % 60)
        print(f"{i+1:3d}  {mm}:{ss:02d}     {s['launch_x']:5.0f}  {s['launch_y']:5.0f}  {s['r2']:5.3f}  {s['track_id']}")

    # JSON 保存
    out3 = OUT_DIR / f"{video_name}_shots.json"
    with open(out3, "w") as f:
        json.dump(shots, f, indent=2)
    print(f"Saved: {out3}")

    return str(out1), str(out2)


# ── メイン ───────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="data/videos/game_2-1.mp4")
    ap.add_argument("--sec",   type=int, default=30, help="処理秒数")
    ap.add_argument("--out",   default=None)
    args = ap.parse_args()

    video_name = Path(args.video).stem
    out_dir    = Path(args.out) if args.out else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 29.4
    max_fi = int(args.sec * fps)
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    max_fi = min(max_fi, total)

    print(f"Video: {args.video}  {int(cap.get(3))}x{int(cap.get(4))} @{fps:.1f}fps")
    print(f"Processing: {args.sec}s ({max_fi} frames)  skip={SKIP}")

    # 背景差分
    bg = cv2.createBackgroundSubtractorMOG2(
        history=100, varThreshold=MOTION_THR, detectShadows=False)

    tracker   = BallTracker()
    ref_frame = None
    fi        = 0

    while fi < max_fi:
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ret, frame = cap.read()
        if not ret:
            break

        # 最初の1秒は背景学習のみ
        fgmask = bg.apply(frame)
        if fi < int(fps):
            fi += SKIP
            continue

        if ref_frame is None:
            ref_frame = frame.copy()

        cands = detect_ball_candidates(frame, fgmask)
        tracker.update(fi, cands)

        if fi % (int(fps) * 5) == 0:
            t = fi / fps
            n_cands = len(cands)
            n_tracks = len(tracker.long_tracks())
            print(f"  t={t:.0f}s  cands={n_cands}  long_tracks={n_tracks}")

        fi += SKIP

    cap.release()

    tracks = tracker.long_tracks()
    print(f"\nTotal long tracks: {len(tracks)}")

    shots = detect_shots(tracks, fps)
    print(f"Shots detected: {len(shots)}")

    if ref_frame is None:
        print("No frames processed.")
        return

    make_shot_chart(shots, ref_frame, video_name, max_fi, fps)


if __name__ == "__main__":
    main()

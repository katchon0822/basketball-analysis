#!/usr/bin/env python3
"""
sam3_shot_chart.py — SAM3ボール軌跡からキャリブレーション不要のショットチャート

アルゴリズム:
  1. ball_positions_sam3_300s.json を読み込み (93%追跡率)
  2. ピクセルy座標の速度反転 (上昇→下降) = ショットアペックス を検出
  3. クールダウン2秒で重複除去
  4. ショットチャート画像を出力 (ビデオフレーム + matplotlib)

Usage:
  python sam3_shot_chart.py
  python sam3_shot_chart.py --sec 300 --video data/videos/game_EE1swQMsXJc_720p.mp4
"""

import cv2
import json
import argparse
import numpy as np
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── パラメータ ─────────────────────────────────────────────────────────────
BALL_JSON   = "ball_positions_sam3_300s.json"
VIDEO       = "data/videos/game_EE1swQMsXJc_720p.mp4"
OUT_DIR     = Path("outputs/sam3_shot_chart")
OUT_DIR.mkdir(parents=True, exist_ok=True)

VY_UP_THR   = -60.0  # 上昇中 (pixel y が減る) の速度閾値 (px/s)
VY_DOWN_THR =  60.0  # 下降中 (pixel y が増える) の速度閾値 (px/s)
COOLDOWN    =  2.5   # 秒: 同じシュートの重複防止
SMOOTH_WIN  =  5     # 速度平滑化ウィンドウ (フレーム数)
MIN_Y_RANGE =  80    # アペックス付近の y 変化量 (px) — 小さい動きを除外


def detect_shots_from_sam3(ball_json_path, fps, max_frames=None):
    """SAM3 ball positions から shot apex を検出"""
    with open(ball_json_path) as f:
        raw = json.load(f)

    # frame index → (x, y) or None
    ball = {int(k): (v[0], v[1]) if v else None for k, v in raw.items()}
    max_fi = max(ball.keys())
    if max_frames is not None:
        max_fi = min(max_fi, max_frames)

    # ---- 速度計算 (平滑化) ----
    fis = sorted(k for k in ball if k <= max_fi and ball[k] is not None)
    ys  = [ball[fi][1] for fi in fis]

    # 5点移動平均で平滑化
    def smooth(arr, w):
        out = []
        for i in range(len(arr)):
            sl = arr[max(0, i - w // 2): i + w // 2 + 1]
            out.append(float(np.mean(sl)))
        return out

    ys_s = smooth(ys, SMOOTH_WIN)

    # フレーム間速度
    vy = [0.0]
    for i in range(1, len(fis)):
        dt = (fis[i] - fis[i - 1]) / fps
        vy.append((ys_s[i] - ys_s[i - 1]) / (dt + 1e-9))

    vy_s = smooth(vy, SMOOTH_WIN)

    # ---- apex 検出 ----
    shots = []
    last_shot_ts = -999.0

    for i in range(1, len(fis) - 1):
        fi   = fis[i]
        ts   = fi / fps
        if ts - last_shot_ts < COOLDOWN:
            continue

        # 直前が上昇 (vy < VY_UP_THR) かつ 直後が下降 (vy > VY_DOWN_THR)
        if vy_s[i - 1] < VY_UP_THR and vy_s[i] > VY_DOWN_THR:
            # アペックス周辺の y 変化量チェック
            window = 15  # フレーム前後
            i_lo = max(0, i - window)
            i_hi = min(len(fis) - 1, i + window)
            y_range = max(ys_s[i_lo:i_hi + 1]) - min(ys_s[i_lo:i_hi + 1])
            if y_range < MIN_Y_RANGE:
                continue

            px, py = ball[fi]
            shots.append({
                "fi":    fi,
                "ts":    round(ts, 2),
                "px":    round(px, 1),
                "py":    round(py, 1),
                "y_range": round(y_range, 1),
            })
            last_shot_ts = ts

    return shots


def make_shot_chart(shots, video_path, video_name, fps):
    cap = cv2.VideoCapture(video_path)

    # 代表フレーム: 最初のシュートより少し前か、30秒付近
    ref_fi = shots[len(shots) // 2]["fi"] if shots else int(fps * 30)
    cap.set(cv2.CAP_PROP_POS_FRAMES, ref_fi)
    ret, ref_frame = cap.read()
    if not ret:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        _, ref_frame = cap.read()
    cap.release()

    h, w = ref_frame.shape[:2]

    # ── (1) ビデオフレーム上のショット位置 ──────────────────────────────────
    vis = ref_frame.copy()
    for i, s in enumerate(shots):
        cx, cy = int(s["px"]), int(s["py"])
        cv2.circle(vis, (cx, cy), 14, (0, 80, 255), -1)
        cv2.circle(vis, (cx, cy), 14, (255, 255, 255), 2)
        cv2.putText(vis, str(i + 1), (cx - 6, cy + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(vis, f"SAM3 Shots  n={len(shots)}  (pixel coords, no calibration)",
                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 200), 2)
    out1 = OUT_DIR / f"{video_name}_shots_on_frame.jpg"
    cv2.imwrite(str(out1), vis)
    print(f"Saved: {out1}")

    # ── (2) matplotlib ショットチャート ─────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 6), facecolor="#0d1117")
    ax.set_facecolor("#0d1117")

    frame_rgb = cv2.cvtColor(ref_frame, cv2.COLOR_BGR2RGB)
    ax.imshow(frame_rgb, alpha=0.30, extent=[0, w, h, 0])

    # 時系列でカラーマップ
    if shots:
        ts_arr = np.array([s["ts"] for s in shots])
        ts_norm = (ts_arr - ts_arr.min()) / (ts_arr.max() - ts_arr.min() + 1e-9)
        cmap = plt.cm.plasma

        for i, s in enumerate(shots):
            cx, cy = s["px"], s["py"]
            color = cmap(ts_norm[i])
            ax.plot(cx, cy, 'o', color=color, markersize=13,
                    markeredgecolor="white", markeredgewidth=1.5, zorder=5)
            ax.text(cx, cy - 17, str(i + 1), color="white", fontsize=7,
                    ha="center", fontweight="bold", zorder=6)

        sm = plt.cm.ScalarMappable(cmap=cmap,
                                    norm=plt.Normalize(ts_arr.min(), ts_arr.max()))
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax, orientation="vertical", pad=0.01, shrink=0.7)
        cbar.set_label("Time (s)", color="white", fontsize=9)
        cbar.ax.yaxis.set_tick_params(color="white")
        plt.setp(plt.getp(cbar.ax.axes, "yticklabels"), color="white")

    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"SAM3 Shot Chart — {video_name}  (n={len(shots)} shots detected)",
                 color="white", fontsize=13, pad=10)
    ax.text(0.5, -0.03,
            "Pixel coordinates (no calibration). Color = shot time.",
            transform=ax.transAxes, ha="center", color="#888888", fontsize=8)

    plt.tight_layout()
    out2 = OUT_DIR / f"{video_name}_shot_chart.png"
    fig.savefig(out2, dpi=130, bbox_inches="tight", facecolor="#0d1117")
    plt.close(fig)
    print(f"Saved: {out2}")

    # ── (3) タイムライン ─────────────────────────────────────────────────────
    print(f"\n{'#':>3}  {'time':>6}  {'x':>6}  {'y':>6}  {'y_range':>8}")
    for i, s in enumerate(shots):
        ts = s["ts"]
        mm, ss = int(ts // 60), int(ts % 60)
        print(f"{i+1:3d}  {mm}:{ss:02d}    {s['px']:6.0f}  {s['py']:6.0f}  {s['y_range']:8.1f}")

    # JSON保存
    out3 = OUT_DIR / f"{video_name}_shots.json"
    with open(out3, "w") as f:
        json.dump(shots, f, indent=2)
    print(f"Saved: {out3}")
    return str(out1), str(out2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ball_json", default=BALL_JSON)
    ap.add_argument("--video",     default=VIDEO)
    ap.add_argument("--sec",       type=int, default=300)
    args = ap.parse_args()

    video_name = Path(args.video).stem

    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 29.97
    cap.release()

    max_frames = int(args.sec * fps)
    print(f"Ball JSON : {args.ball_json}")
    print(f"Video     : {args.video}  @{fps:.2f}fps")
    print(f"Analysing : {args.sec}s ({max_frames} frames)")

    shots = detect_shots_from_sam3(args.ball_json, fps, max_frames)
    print(f"Shots detected: {len(shots)}")

    if not shots:
        print("No shots detected. Try lowering MIN_Y_RANGE or thresholds.")
        return

    make_shot_chart(shots, args.video, video_name, fps)


if __name__ == "__main__":
    main()

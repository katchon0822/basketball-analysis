#!/usr/bin/env python3
"""
render_shot_video.py — キャリブレーション済みショット結果を動画に書き出す

- コートラインオーバーレイ (ホモグラフィー投影)
- SAM3ボール軌跡描画
- シュート検出フレームでマーカー表示 (番号 + フラッシュ)
- 右上にミニコート図 (現在のシュート位置をリアルタイム表示)

Usage:
  python render_shot_video.py
  python render_shot_video.py --profile outputs/venue_profiles/game2-1.json \
                               --shots   outputs/calibrated_shots/game_2-1_shots.json \
                               --ball    outputs/sam3_tracking/ball_positions_game_2-1_30s.json
"""

import cv2
import json
import numpy as np
import subprocess
import argparse
from pathlib import Path

# ── コート定数 (cm) ──────────────────────────────────────────────────────────
SIDELINE = 750
HALF_Y   = 1432
FT_Y     = 580
LANE_X   = 245
BASKET_Y = 160
PT3_CX   = 665
PT3_CY   = 420
PT3_R    = 705

OUT_DIR = Path("outputs/calibrated_shots")
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── ホモグラフィー投影 ────────────────────────────────────────────────────────
def make_projector(H, sx=1.0, sy=1.0):
    def proj(cx, cy):
        pt  = np.array([[[float(cx), float(cy)]]], dtype=np.float64)
        out = cv2.perspectiveTransform(pt, H)
        return (int(out[0,0,0] * sx), int(out[0,0,1] * sy))
    return proj


def draw_court_overlay(frame, proj, w, h):
    """コートラインをフレームに投影"""
    def line(x1, y1, x2, y2, color, thickness=1):
        p1, p2 = proj(x1, y1), proj(x2, y2)
        if (0 <= p1[0] < w and 0 <= p1[1] < h and
                0 <= p2[0] < w and 0 <= p2[1] < h):
            cv2.line(frame, p1, p2, color, thickness, cv2.LINE_AA)

    W  = (180, 180, 180)
    B  = (100, 200, 255)
    O  = ( 50, 220, 255)

    # 外枠
    line(-SIDELINE, 0,      SIDELINE, 0,      W, 2)
    line(-SIDELINE, 0,     -SIDELINE, HALF_Y, W, 2)
    line( SIDELINE, 0,      SIDELINE, HALF_Y, W, 2)
    line(-SIDELINE, HALF_Y, SIDELINE, HALF_Y, W, 1)
    # ペイント
    line(-LANE_X, 0, -LANE_X, FT_Y, B, 1)
    line( LANE_X, 0,  LANE_X, FT_Y, B, 1)
    line(-LANE_X, FT_Y, LANE_X, FT_Y, B, 1)
    # 3PT直線
    line(-PT3_CX, 0, -PT3_CX, PT3_CY, O, 1)
    line( PT3_CX, 0,  PT3_CX, PT3_CY, O, 1)
    # 3PTアーク
    arc_pts = []
    for deg in range(-115, 116, 3):
        rad = np.radians(deg)
        cx  = PT3_R * np.sin(rad)
        cy  = BASKET_Y + PT3_R * np.cos(rad)
        if abs(cx) <= PT3_CX:
            p = proj(cx, cy)
            if 0 <= p[0] < w and 0 <= p[1] < h:
                arc_pts.append(p)
    if len(arc_pts) > 1:
        for i in range(len(arc_pts) - 1):
            cv2.line(frame, arc_pts[i], arc_pts[i+1], O, 1, cv2.LINE_AA)
    # バスケット
    basket_pts = []
    for deg in range(0, 361, 8):
        rad = np.radians(deg)
        p = proj(23.75 * np.cos(rad), BASKET_Y + 23.75 * np.sin(rad))
        if 0 <= p[0] < w and 0 <= p[1] < h:
            basket_pts.append(p)
    if len(basket_pts) > 1:
        for i in range(len(basket_pts) - 1):
            cv2.line(frame, basket_pts[i], basket_pts[i+1], (60, 80, 255), 2, cv2.LINE_AA)


# ── ミニコート図 ──────────────────────────────────────────────────────────────
MINI_W, MINI_H = 160, 200

def make_mini_court():
    img = np.full((MINI_H, MINI_W, 3), 20, dtype=np.uint8)
    pad = 8

    scl = min((MINI_W - pad*2) / (SIDELINE*2), (MINI_H - pad*2) / HALF_Y)
    ox  = (MINI_W - int(SIDELINE*2*scl)) // 2

    def c2p(cx, cy):
        return (ox + int((cx + SIDELINE)*scl), pad + int((HALF_Y - cy)*scl))

    W = (130, 130, 130)
    B = (80, 160, 200)
    O = (40, 160, 200)

    def mline(x1,y1,x2,y2,col,t=1):
        cv2.line(img, c2p(x1,y1), c2p(x2,y2), col, t, cv2.LINE_AA)

    mline(-SIDELINE,0, SIDELINE,0, W,2)
    mline(-SIDELINE,0,-SIDELINE,HALF_Y, W,1)
    mline( SIDELINE,0, SIDELINE,HALF_Y, W,1)
    mline(-SIDELINE,HALF_Y,SIDELINE,HALF_Y, W,1)
    mline(-LANE_X,0,-LANE_X,FT_Y, B,1)
    mline( LANE_X,0, LANE_X,FT_Y, B,1)
    mline(-LANE_X,FT_Y,LANE_X,FT_Y, B,1)
    mline(-PT3_CX,0,-PT3_CX,PT3_CY, O,1)
    mline( PT3_CX,0, PT3_CX,PT3_CY, O,1)
    arc = []
    for deg in range(-115,116,4):
        rad = np.radians(deg)
        cx = PT3_R*np.sin(rad)
        cy = BASKET_Y + PT3_R*np.cos(rad)
        if abs(cx) <= PT3_CX:
            arc.append(c2p(cx,cy))
    for i in range(len(arc)-1):
        cv2.line(img, arc[i], arc[i+1], O, 1, cv2.LINE_AA)
    cv2.circle(img, c2p(0, BASKET_Y), max(1, int(23.75*scl)),
               (60, 60, 220), 1)

    return img, c2p


def draw_mini_shots(base, c2p, shots_so_far, current_shot_idx):
    img = base.copy()
    for i, s in enumerate(shots_so_far):
        cx, cy = s["court_x"], s["court_y"]
        p = c2p(cx, cy)
        if i == current_shot_idx:
            cv2.circle(img, p, 7, (0, 220, 255), -1)
            cv2.circle(img, p, 7, (255,255,255), 1)
        else:
            cv2.circle(img, p, 5, (0, 180, 80), -1)
        cv2.putText(img, str(i+1), (p[0]-3, p[1]+3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.25, (255,255,255), 1)
    return img


# ── メイン ───────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="outputs/venue_profiles/game2-1.json")
    ap.add_argument("--shots",   default="outputs/calibrated_shots/game_2-1_shots.json")
    ap.add_argument("--ball",    default="outputs/sam3_tracking/ball_positions_game_2-1_30s.json")
    ap.add_argument("--sec",     type=int, default=30)
    args = ap.parse_args()

    with open(args.profile) as f:
        prof = json.load(f)
    with open(args.shots) as f:
        shots = json.load(f)
    with open(args.ball) as f:
        ball_raw = json.load(f)
    ball = {int(k): (v[0], v[1]) if v else None for k, v in ball_raw.items()}

    H        = np.array(prof["H_court_to_image"])
    video    = f"data/videos/{prof['video']}"
    stem     = Path(video).stem

    cap  = cv2.VideoCapture(video)
    fps  = cap.get(cv2.CAP_PROP_FPS) or 29.4
    W    = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H_px = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    max_fi = min(int(args.sec * fps), int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))

    proj = make_projector(H)
    mini_base, c2p = make_mini_court()

    out_tmp = str(OUT_DIR / f"{stem}_shot_video_tmp.mp4")
    out_fin = str(OUT_DIR / f"{stem}_shot_video.mp4")
    writer  = cv2.VideoWriter(out_tmp, cv2.VideoWriter_fourcc(*"mp4v"),
                               fps, (W, H_px))

    # シュートのフレームインデックスとフラッシュ持続時間
    FLASH_DUR = int(fps * 1.5)   # 1.5秒間マーカーを表示
    shot_fi   = {s["launch_fi"]: (i, s) for i, s in enumerate(shots)}

    active_shots: list[tuple[int, int, dict]] = []  # (expire_fi, shot_idx, shot)
    shown_shots:  list[dict] = []
    current_shot_idx = None

    print(f"Rendering {max_fi} frames → {out_fin}")
    trail: list[tuple[int,int]] = []

    for fi in range(max_fi):
        ret, frame = cap.read()
        if not ret:
            break

        # コートラインオーバーレイ
        draw_court_overlay(frame, proj, W, H_px)

        # SAM3ボール軌跡
        pos = ball.get(fi)
        if pos:
            trail.append((int(pos[0]), int(pos[1])))
            if len(trail) > 20:
                trail.pop(0)
        for i in range(1, len(trail)):
            alpha = i / len(trail)
            col   = (int(50*alpha), int(220*alpha), int(255*alpha))
            cv2.line(frame, trail[i-1], trail[i], col, 2, cv2.LINE_AA)
        if pos and trail:
            cv2.circle(frame, trail[-1], 8, (0, 220, 255), -1)
            cv2.circle(frame, trail[-1], 8, (255,255,255), 1)

        # シュートマーカー登録
        if fi in shot_fi:
            sidx, s = shot_fi[fi]
            active_shots.append((fi + FLASH_DUR, sidx, s))
            shown_shots.append(s)
            current_shot_idx = sidx

        # アクティブなシュートマーカーを描画
        active_shots = [(exp, sidx, s) for exp, sidx, s in active_shots if fi <= exp]
        for exp, sidx, s in active_shots:
            cx_px, cy_px = int(s["launch_x"]), int(s["launch_y"])
            fade = max(0.3, (exp - fi) / FLASH_DUR)
            r   = int(12 + (1 - fade) * 10)   # 縮小アニメ
            col = (int(0*fade), int(60*fade), int(255*fade))
            cv2.circle(frame, (cx_px, cy_px), r, col, -1)
            cv2.circle(frame, (cx_px, cy_px), r, (255,255,255), 2)
            cv2.putText(frame, str(sidx+1), (cx_px-5, cy_px+4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,255), 1)
            # コート座標ラベル
            mm, ss = int(s["ts"]//60), int(s["ts"]%60)
            label = f"#{sidx+1} ({s['court_x']:.0f},{s['court_y']:.0f})cm  {mm}:{ss:02d}"
            cv2.putText(frame, label, (cx_px + 15, cy_px),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0,0,0), 3)
            cv2.putText(frame, label, (cx_px + 15, cy_px),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0,230,255), 1)

        # ミニコート図 (右上)
        cur_idx = active_shots[-1][1] if active_shots else None
        mini = draw_mini_shots(mini_base, c2p, shown_shots, cur_idx)
        mx, my = W - MINI_W - 6, 6
        frame[my:my+MINI_H, mx:mx+MINI_W] = mini
        cv2.rectangle(frame, (mx-1,my-1), (mx+MINI_W,my+MINI_H), (80,80,80), 1)

        # タイムスタンプ + シュートカウント
        ts = fi / fps
        mm, ss = int(ts//60), int(ts%60)
        hdr = f"t={mm}:{ss:02d}  shots={len(shown_shots)}"
        cv2.putText(frame, hdr, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,0,0), 3)
        cv2.putText(frame, hdr, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200,200,200), 1)

        writer.write(frame)

        if fi % int(fps * 5) == 0:
            print(f"  {fi}/{max_fi}  t={ts:.0f}s  shots={len(shown_shots)}")

    cap.release()
    writer.release()

    # H.264 再エンコード
    subprocess.run([
        "ffmpeg", "-y", "-i", out_tmp,
        "-vcodec", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "20", "-movflags", "+faststart", out_fin,
    ], capture_output=True)
    Path(out_tmp).unlink(missing_ok=True)
    print(f"\nDone: {out_fin}")


if __name__ == "__main__":
    main()

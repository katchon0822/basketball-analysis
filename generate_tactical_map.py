"""
generate_tactical_map.py
ブロードキャスト映像 → トップダウン戦術マップ (サイドバイサイド)

左: オリジナル放送映像
右: フルコート俯瞰図 (ニアハーフのみ選手位置マッピング)
  - 白線コーナー検出による定期再キャリブレーション
  - チームカラー + 軌跡
  - SAM3ボール位置
"""
import cv2, json, numpy as np, argparse
from pathlib import Path
from collections import defaultdict, deque

import supervision as sv
from ultralytics import YOLO

from court_line_accuracy import build_H_inv, key_to_frame, project, court_lines
from auto_fit_3pt import collect_arc_points, fit_radius_ransac
from generate_detection_video import (
    HomographyTracker, OpticalFlowTracker, load_annotations
)

# ── 定数 ───────────────────────────────────────────────────────────────────────
VIDEO      = "data/videos/game_EE1swQMsXJc_720p.mp4"
MODEL_DET  = "models/player_detector.pt"
ANN_JSON   = "outputs/annotations.json"
OUT_DIR    = Path("outputs/sam3_300s")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CLS_PLAYER = 4
CLS_REF    = 5
CONF       = 0.35

# コート定数 (cm)
COURT_W      = 750          # ハーフ幅
COURT_L      = 1432         # ニアハーフ長 (エンドライン〜ハーフライン)
COURT_FULL_L = COURT_L * 2  # フルコート長 (2864cm)
BASKET_Y     = 160          # ニアバスケット位置
PT3_DEFAULT  = 705

TRAIL_LEN  = 45   # フレーム数 (約1.5秒)

# ── カラーパレット (BGR) ───────────────────────────────────────────────────────
BG_COLOR   = (18, 18, 28)
COURT_BG   = (25, 55, 25)
LINE_COLOR = (210, 210, 210)
TEAM1_C    = (255, 160,  60)   # orange (White team)
TEAM2_C    = ( 60, 160, 255)   # blue   (Navy team)
UNKN_C     = (140, 140, 140)
BALL_C     = ( 30, 210, 255)
REF_C      = (200, 255,  80)
ACCENT     = (255, 220,  60)

TEAM_C = {1: TEAM1_C, 2: TEAM2_C, -1: UNKN_C}

# ── 出力フレームサイズ ─────────────────────────────────────────────────────────
OUT_W, OUT_H = 1280, 720
HALF_W = OUT_W // 2   # 640

# ── 戦術マップ コート描画パラメータ ────────────────────────────────────────────
TMAP_PAD_TOP  = 52
TMAP_PAD_BOT  = 110
TMAP_PAD_SIDE = 28
TMAP_CW = HALF_W - 2 * TMAP_PAD_SIDE           # 584px
TMAP_CH = OUT_H  - TMAP_PAD_TOP - TMAP_PAD_BOT  # 558px

# フルコートをポートレートで配置 (幅1500cm × 高さ2864cm)
SCALE_X = TMAP_CW / (COURT_W * 2)      # 584/1500 = 0.389
SCALE_Y = TMAP_CH / COURT_FULL_L       # 558/2864 = 0.195
SCALE   = min(SCALE_X, SCALE_Y)        # = 0.195 px/cm

COURT_DISPLAY_W = COURT_W * 2 * SCALE
COURT_DISPLAY_H = COURT_FULL_L * SCALE

COURT_ORIGIN_X = TMAP_PAD_SIDE + (TMAP_CW - COURT_DISPLAY_W) / 2
COURT_ORIGIN_Y = TMAP_PAD_TOP  + (TMAP_CH - COURT_DISPLAY_H) / 2


def ct(cx, cy):
    """コート座標 (cm) → 右パネル内ピクセル座標 (フルコート対応)
    cy=0: ニアエンドライン (下) / cy=COURT_FULL_L: ファーエンドライン (上)
    """
    px = int(COURT_ORIGIN_X + (cx + COURT_W) * SCALE)
    py = int(COURT_ORIGIN_Y + (COURT_FULL_L - cy) * SCALE)
    return px, py


# ── コートライン (ファーハーフはニアハーフを y 軸対称で生成) ──────────────────
def court_lines_full():
    """ニア + ファー両ハーフのコートラインリストを返す"""
    near = court_lines()                       # cy: 0..1432
    far  = []
    for color, pts in near:
        far_pts = [[p[0], COURT_FULL_L - p[1]] for p in pts]
        far.append((color, far_pts))
    return near + far


# ── コート背景を事前描画 ────────────────────────────────────────────────────────
def build_court_base():
    panel = np.full((OUT_H, HALF_W, 3), BG_COLOR, dtype=np.uint8)

    # コート面
    cv2.rectangle(panel, ct(-COURT_W, COURT_FULL_L), ct(COURT_W, 0), COURT_BG, -1)

    # ハーフコート境界を淡い帯で区別
    hl_y = ct(0, COURT_L)[1]
    cv2.line(panel, (int(COURT_ORIGIN_X), hl_y),
             (int(COURT_ORIGIN_X + COURT_DISPLAY_W), hl_y),
             (80, 120, 80), 1)

    # コートライン (両ハーフ)
    for _, pts in court_lines_full():
        pxpts = [ct(p[0], p[1]) for p in pts]
        for i in range(len(pxpts) - 1):
            p1, p2 = pxpts[i], pxpts[i+1]
            if (0 <= p1[0] < HALF_W and 0 <= p1[1] < OUT_H and
                    0 <= p2[0] < HALF_W and 0 <= p2[1] < OUT_H):
                cv2.line(panel, p1, p2, LINE_COLOR, 1, cv2.LINE_AA)

    # 外周
    corners = [ct(-COURT_W, 0), ct(COURT_W, 0),
               ct( COURT_W, COURT_FULL_L), ct(-COURT_W, COURT_FULL_L)]
    cv2.polylines(panel, [np.array(corners)], True, LINE_COLOR, 2, cv2.LINE_AA)

    # ニアバスケット
    bp_near = ct(0, BASKET_Y)
    cv2.circle(panel, bp_near, max(2, int(23.75 * SCALE)), (80, 80, 220), 1, cv2.LINE_AA)
    cv2.circle(panel, bp_near, max(1, int(5 * SCALE)),  (80, 80, 220), -1)

    # ファーバスケット
    bp_far = ct(0, COURT_FULL_L - BASKET_Y)
    cv2.circle(panel, bp_far, max(2, int(23.75 * SCALE)), (80, 80, 220), 1, cv2.LINE_AA)
    cv2.circle(panel, bp_far, max(1, int(5 * SCALE)),  (80, 80, 220), -1)

    # センターサークル (半径 180cm)
    cc = ct(0, COURT_L)
    cv2.circle(panel, cc, max(2, int(180 * SCALE)), LINE_COLOR, 1, cv2.LINE_AA)

    # ハーフコートライン
    p1h = ct(-COURT_W, COURT_L)
    p2h = ct( COURT_W, COURT_L)
    cv2.line(panel, p1h, p2h, LINE_COLOR, 1, cv2.LINE_AA)

    # ニアハーフに "NEAR" ラベル
    near_lbl = ct(-COURT_W + 30, BASKET_Y + 80)
    cv2.putText(panel, "NEAR", near_lbl, cv2.FONT_HERSHEY_SIMPLEX,
                0.35, (100, 160, 100), 1, cv2.LINE_AA)
    far_lbl = ct(-COURT_W + 30, COURT_FULL_L - BASKET_Y - 80)
    cv2.putText(panel, "FAR", far_lbl, cv2.FONT_HERSHEY_SIMPLEX,
                0.35, (80, 120, 80), 1, cv2.LINE_AA)

    return panel


COURT_BASE = build_court_base()


# ── ホモグラフィーユーティリティ ──────────────────────────────────────────────
def img_to_court(H_i2c, px, py):
    """画像ピクセル → コート座標 (ニアハーフのみ有効)"""
    pt  = np.array([[[float(px), float(py)]]], dtype=np.float64)
    out = cv2.perspectiveTransform(pt, H_i2c)
    cx, cy = float(out[0, 0, 0]), float(out[0, 0, 1])
    if abs(cx) > COURT_W + 60 or cy < -60 or cy > COURT_L + 60:
        return None
    return cx, cy


# ── チーム分類 ────────────────────────────────────────────────────────────────
def classify_team(frame, bbox):
    x1, y1, x2, y2 = map(int, bbox)
    h = y2 - y1
    roi = frame[y1 + int(h*0.15): y1 + int(h*0.65), x1:x2]
    if roi.size == 0:
        return -1
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    t   = roi.shape[0] * roi.shape[1]
    if cv2.inRange(hsv, (0,   0, 170), (180,  70, 255)).sum() / 255 / t > 0.12:
        return 1
    if cv2.inRange(hsv, (90, 60,  15), (140, 255, 170)).sum() / 255 / t > 0.07:
        return 2
    return -1


# ── グロー描画 ────────────────────────────────────────────────────────────────
def draw_glow(panel, pt, color, radius=8, intensity=0.6):
    overlay = np.zeros_like(panel)
    cv2.circle(overlay, pt, radius * 2, color, -1)
    overlay = cv2.GaussianBlur(overlay, (radius*4+1, radius*4+1), 0)
    cv2.addWeighted(overlay, intensity, panel, 1.0, 0, panel)
    cv2.circle(panel, pt, radius, color, -1, cv2.LINE_AA)
    cv2.circle(panel, pt, radius, (255,255,255), 1, cv2.LINE_AA)


# ── 統計バー描画 ──────────────────────────────────────────────────────────────
def draw_stats(panel, ts, n1, n2, n_ref, ball_ok, refine_ok):
    mm, ss = int(ts//60), int(ts%60)
    y_base = OUT_H - TMAP_PAD_BOT + 14
    cv2.rectangle(panel, (0, OUT_H - TMAP_PAD_BOT), (HALF_W, OUT_H), (12, 12, 22), -1)

    def stat_box(x, label, value, color):
        cv2.putText(panel, label, (x, y_base),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (150,150,150), 1)
        cv2.putText(panel, str(value), (x, y_base + 28),
                    cv2.FONT_HERSHEY_DUPLEX, 0.8, color, 2)

    stat_box(20,  "TEAM A", n1,      TEAM1_C)
    stat_box(110, "TEAM B", n2,      TEAM2_C)
    stat_box(200, "REF",    n_ref,   REF_C)
    stat_box(270, "BALL",   "ON" if ball_ok else "OFF", BALL_C)

    # キャリブレーション状態インジケーター
    cal_color = (0, 220, 80) if refine_ok else (200, 80, 80)
    cv2.circle(panel, (HALF_W - 100, y_base + 12), 5, cal_color, -1)
    cv2.putText(panel, "CAL", (HALF_W - 92, y_base + 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.3, (180,180,180), 1)

    cv2.putText(panel, f"{mm:02d}:{ss:02d}", (HALF_W - 80, y_base + 28),
                cv2.FONT_HERSHEY_DUPLEX, 0.9, ACCENT, 2)


# ── ヘッダー描画 ──────────────────────────────────────────────────────────────
def draw_header(panel):
    cv2.rectangle(panel, (0, 0), (HALF_W, TMAP_PAD_TOP), (10, 10, 20), -1)
    cv2.putText(panel, "TACTICAL MAP — FULL COURT", (TMAP_PAD_SIDE, 20),
                cv2.FONT_HERSHEY_DUPLEX, 0.55, ACCENT, 1)
    cv2.putText(panel, "TOP-DOWN VIEW  |  AUTO-CALIBRATED COURT DETECTION",
                (TMAP_PAD_SIDE, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.30, (140,140,140), 1)
    cv2.line(panel, (0, TMAP_PAD_TOP-1), (HALF_W, TMAP_PAD_TOP-1), ACCENT, 1)


# ── 左パネル: 放送映像 ────────────────────────────────────────────────────────
def draw_broadcast(frame, player_tracks, ball_px, VW, VH):
    out = cv2.resize(frame, (HALF_W, OUT_H))
    sx, sy = HALF_W / VW, OUT_H / VH
    if ball_px is not None:
        bx, by = int(ball_px[0] * sx), int(ball_px[1] * sy)
        cv2.circle(out, (bx, by), 12, (0,0,0), -1)
        cv2.circle(out, (bx, by), 10, BALL_C, -1)
        cv2.circle(out, (bx, by), 10, (255,255,255), 1)
    for tid, bbox, team in player_tracks:
        fx = int((bbox[0] + bbox[2]) / 2 * sx)
        fy = int(bbox[3] * sy)
        color = TEAM_C.get(team, UNKN_C)
        cv2.circle(out, (fx, fy), 6, (0,0,0), -1)
        cv2.circle(out, (fx, fy), 5, color,   -1)
    cv2.rectangle(out, (0,0), (HALF_W, 30), (0,0,0), -1)
    cv2.putText(out, "BROADCAST", (10, 21),
                cv2.FONT_HERSHEY_DUPLEX, 0.6, (200,200,200), 1)
    cv2.circle(out, (HALF_W - 20, 15), 6, (0, 50, 255), -1)
    cv2.putText(out, "LIVE", (HALF_W - 50, 21),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 80, 255), 1)
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  メイン
# ══════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sec",  type=float, default=300.0)
    parser.add_argument("--sam3", type=str,   default="ball_positions_sam3_300s.json")
    args = parser.parse_args()

    with open(args.sam3) as f:
        raw = json.load(f)
    sam3_ball = {int(k): (v[0], v[1]) if v else None for k, v in raw.items()}
    print(f"SAM3: {sum(1 for v in sam3_ball.values() if v)}/{len(sam3_ball)} frames")

    cap = cv2.VideoCapture(VIDEO)
    fps = cap.get(cv2.CAP_PROP_FPS)
    VW  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    VH  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_frames = min(int(args.sec * fps), int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))

    print("Loading annotations & Optical Flow tracker ...")
    ann_map    = load_annotations(ANN_JSON, fps)
    of_tracker = OpticalFlowTracker(ann_map)
    of_tracker.cache_ann_frames(cap)
    print(f"  {len(ann_map)} annotation frames cached")

    print("Pre-computing RANSAC radii ...")
    from auto_fit_3pt import collect_arc_points, fit_radius_ransac
    radii = {}
    for fi, (H_inv, _) in ann_map.items():
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ret, frm = cap.read()
        if not ret: continue
        hits = collect_arc_points(frm, H_inv, init_radius=PT3_DEFAULT)
        r, inliers = fit_radius_ransac(hits, H_inv)
        radii[fi] = r if (r and len(inliers) >= 8) else PT3_DEFAULT

    model      = YOLO(MODEL_DET)
    tracker    = sv.ByteTrack(minimum_matching_threshold=0.8,
                               minimum_consecutive_frames=1,
                               lost_track_buffer=90)
    team_votes = defaultdict(list)
    trails     = defaultdict(lambda: deque(maxlen=TRAIL_LEN))

    sec_tag  = int(args.sec)
    out_path = OUT_DIR / f"tactical_map_{sec_tag}s.mp4"
    writer   = cv2.VideoWriter(str(out_path),
                               cv2.VideoWriter_fourcc(*"mp4v"),
                               fps, (OUT_W, OUT_H))
    print(f"Output: {out_path}")
    print(f"Processing {n_frames} frames ({args.sec:.0f}s) ...")

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    for fi in range(n_frames):
        ret, frame = cap.read()
        if not ret:
            break
        ts = fi / fps

        # ホモグラフィー取得 (update内で自動再キャリブレーション実行)
        H_c2i, is_ann = of_tracker.update(fi, frame)
        H_i2c = None
        if H_c2i is not None:
            try:
                if abs(np.linalg.det(H_c2i)) > 1e-8:
                    H_i2c = np.linalg.inv(H_c2i)
            except np.linalg.LinAlgError:
                pass
        last_refine_ok = is_ann or of_tracker.last_refine_ok

        # YOLO + ByteTrack
        results = model.predict(frame, conf=CONF, verbose=False)[0]
        p_dets, r_dets = [], []
        for box in results.boxes:
            cls  = int(box.cls[0])
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].cpu().numpy()
            if cls == CLS_PLAYER and conf >= CONF: p_dets.append((xyxy, conf))
            elif cls == CLS_REF and conf >= 0.3:   r_dets.append(xyxy)

        if p_dets:
            sv_det = sv.Detections(
                xyxy=np.array([d[0] for d in p_dets]),
                confidence=np.array([d[1] for d in p_dets]),
                class_id=np.zeros(len(p_dets), dtype=int))
            tracks = tracker.update_with_detections(sv_det)
        else:
            tracks = sv.Detections.empty()

        player_tracks = []
        for i in range(len(tracks)):
            tid  = int(tracks.tracker_id[i])
            bbox = tracks.xyxy[i]
            team = classify_team(frame, bbox)
            team_votes[tid].append(team)
            votes  = [t for t in team_votes[tid][-20:] if t in (1, 2)]
            stable = max(set(votes), key=votes.count) if votes else -1
            player_tracks.append((tid, bbox, stable))

            # 足元ピクセル → コート座標
            if H_i2c is not None:
                fx  = (bbox[0] + bbox[2]) / 2
                fy  = bbox[3]
                cpos = img_to_court(H_i2c, fx, fy)
                if cpos is not None:
                    trails[tid].append((*cpos, stable))

        ball = sam3_ball.get(fi)
        ball_court = None
        if ball is not None and H_i2c is not None:
            ball_court = img_to_court(H_i2c, ball[0], ball[1])

        # ── 左パネル ──────────────────────────────────────────────────────
        left = draw_broadcast(frame, player_tracks, ball, VW, VH)

        # ── 右パネル: 戦術マップ ──────────────────────────────────────────
        right = COURT_BASE.copy()
        draw_header(right)

        # 軌跡
        for tid, trail in trails.items():
            trail_pts = list(trail)
            if len(trail_pts) < 2:
                continue
            team = trail_pts[-1][2]
            base_color = np.array(TEAM_C.get(team, UNKN_C), dtype=float)
            for i in range(1, len(trail_pts)):
                alpha = i / len(trail_pts)
                color = tuple((base_color * alpha * 0.7).astype(int).tolist())
                p1 = ct(trail_pts[i-1][0], trail_pts[i-1][1])
                p2 = ct(trail_pts[i][0],   trail_pts[i][1])
                if (0 <= p1[0] < HALF_W and 0 <= p1[1] < OUT_H and
                        0 <= p2[0] < HALF_W and 0 <= p2[1] < OUT_H):
                    cv2.line(right, p1, p2, color, 2, cv2.LINE_AA)

        # 選手ドット
        plotted = set()
        for tid, bbox, team in player_tracks:
            trail_pts = list(trails.get(tid, []))
            if not trail_pts:
                continue
            cx, cy, _ = trail_pts[-1]
            cpt = ct(cx, cy)
            if not (0 <= cpt[0] < HALF_W and 0 <= cpt[1] < OUT_H):
                continue
            color = TEAM_C.get(team, UNKN_C)
            draw_glow(right, cpt, color, radius=9, intensity=0.5)
            cv2.putText(right, str(tid % 100), (cpt[0]+10, cpt[1]+4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255,255,255), 1)
            plotted.add(tid)

        # ボール
        if ball_court is not None:
            bpt = ct(*ball_court)
            if 0 <= bpt[0] < HALF_W and 0 <= bpt[1] < OUT_H:
                draw_glow(right, bpt, BALL_C, radius=7, intensity=0.7)

        # 統計バー
        n1    = sum(1 for _, _, t in player_tracks if t == 1)
        n2    = sum(1 for _, _, t in player_tracks if t == 2)
        n_ref = len(r_dets)
        draw_stats(right, ts, n1, n2, n_ref,
                   ball is not None, last_refine_ok)

        cv2.line(right, (0, TMAP_PAD_TOP), (HALF_W, TMAP_PAD_TOP), ACCENT, 1)

        # ── 合成 ──────────────────────────────────────────────────────────
        out_frame = np.hstack([left, right])
        writer.write(out_frame)

        if fi % int(fps * 30) == 0:
            pct = fi / n_frames * 100
            print(f"  [{pct:5.1f}%] t={ts:.0f}s  tracked={len(plotted)}"
                  f"  ball={'Y' if ball_court else 'N'}"
                  f"  cal={'OK' if last_refine_ok else '--'}")

    cap.release()
    writer.release()
    size_mb = out_path.stat().st_size / 1e6
    print(f"\nDone: {out_path}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()

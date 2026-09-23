#!/usr/bin/env python3
"""
calibrated_shot_detection.py — キャリブレーション済みショット検出

1. 会場プロファイル (H行列) を読み込む
2. MOG2 + オレンジフィルタ でボール候補検出
3. 放物線フィット でシュート検出
4. H逆行列 でコート座標に変換
5. FIBA コート図上にプロット

Usage:
  python calibrated_shot_detection.py --profile outputs/venue_profiles/game2-1.json --sec 30
"""

import cv2, json, argparse, numpy as np
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Arc
from collections import deque

# ── パラメータ ──────────────────────────────────────────────────────────────
ORANGE_LO  = np.array([ 5, 100, 100])
ORANGE_HI  = np.array([25, 255, 255])
BALL_R_MIN = 3
BALL_R_MAX = 25
CIRC_MIN   = 0.40
MOTION_THR = 15
SKIP       = 2
TRACK_DIST = 60
MIN_TRAJ   = 8
FIT_WIN    = 12
R2_THR     = 0.72
DEDUP_DIST = 80
DEDUP_FI   = 35

# コート定数 (cm)
SIDELINE  = 750
HALF_Y    = 1432
BASKET_Y  = 160
FT_Y      = 580
LANE_X    = 245
PT3_CX    = 665
PT3_CY    = 420
PT3_R     = 705

OUT_DIR = Path("outputs/calibrated_shots")
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── プロファイル読み込み ────────────────────────────────────────────────────
def load_profile(path):
    with open(path) as f:
        prof = json.load(f)
    H = np.array(prof["H_court_to_image"])   # court → image
    H_inv = np.linalg.inv(H)                  # image → court
    hull = np.array(prof["trust_hull_court"]) if prof.get("trust_hull_court") else None
    return H, H_inv, hull, prof


def img_to_court(H_inv, px, py):
    """画像ピクセル → コート座標 (cm)"""
    pt  = np.array([[[float(px), float(py)]]], dtype=np.float64)
    out = cv2.perspectiveTransform(pt, H_inv)
    return float(out[0, 0, 0]), float(out[0, 0, 1])


def in_trust_hull(hull, cx, cy, margin=200):
    """信頼領域 (凸包) 内かどうか"""
    if hull is None:
        return True
    pt = np.array([[float(cx), float(cy)]])
    # 外側マージンを加えた判定
    dist = cv2.pointPolygonTest(
        hull.reshape(-1, 1, 2).astype(np.float32), (float(cx), float(cy)), True)
    return dist >= -margin


# ── ボール検出 (quick_shot_chartと同じ) ────────────────────────────────────
def detect_ball_candidates(frame, fgmask):
    hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    cmask = cv2.inRange(hsv, ORANGE_LO, ORANGE_HI)
    combined = cv2.bitwise_and(cmask, fgmask)
    combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN,  np.ones((3,3), np.uint8))
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, np.ones((7,7), np.uint8))
    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cands = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 1: continue
        peri = cv2.arcLength(cnt, True)
        circ = 4 * np.pi * area / (peri * peri + 1e-9)
        if circ < CIRC_MIN: continue
        (cx, cy), r = cv2.minEnclosingCircle(cnt)
        if BALL_R_MIN <= r <= BALL_R_MAX:
            cands.append((float(cx), float(cy), float(r)))
    return cands


# ── トラッカー ──────────────────────────────────────────────────────────────
class BallTracker:
    def __init__(self):
        self.tracks: dict[int, deque] = {}
        self._next_id = 0
        self._last_pos: dict[int, tuple] = {}

    def update(self, fi, cands):
        if not cands: return
        used = set()
        for cid, (lx, ly) in list(self._last_pos.items()):
            best, best_d = None, float('inf')
            for i, (cx, cy, r) in enumerate(cands):
                if i in used: continue
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
                nid = self._next_id; self._next_id += 1
                self.tracks[nid] = deque([(fi, cx, cy)], maxlen=200)
                self._last_pos[nid] = (cx, cy)

    def long_tracks(self):
        return {k: list(v) for k, v in self.tracks.items() if len(v) >= MIN_TRAJ}


# ── 放物線フィット → シュート検出 ──────────────────────────────────────────
def fit_parabola(ys, xs):
    if len(xs) < 4: return None, 0.0
    try:
        coeffs = np.polyfit(xs, ys, 2)
        a, b, c = coeffs
        if a <= 0: return None, 0.0
        pred  = np.polyval(coeffs, xs)
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
            if len(window) < 4: continue
            fis = [p[0] for p in window]
            ys  = [p[2] for p in window]
            coeffs, r2 = fit_parabola(ys, fis)
            if coeffs is not None and r2 >= R2_THR:
                a, b, _ = coeffs
                peak_fi = -b / (2 * a)
                if fis[0] <= peak_fi <= fis[-1]:
                    launch_fi, lx, ly = window[0]
                    shots.append({
                        "track_id":  tid,
                        "launch_fi": launch_fi,
                        "launch_x":  lx,
                        "launch_y":  ly,
                        "r2":        round(r2, 3),
                        "ts":        round(launch_fi / fps, 1),
                    })
    shots.sort(key=lambda s: s["launch_fi"])
    deduped = []
    for s in shots:
        if not any(
            np.hypot(s["launch_x"] - d["launch_x"],
                     s["launch_y"] - d["launch_y"]) < DEDUP_DIST
            and abs(s["launch_fi"] - d["launch_fi"]) < DEDUP_FI
            for d in deduped
        ):
            deduped.append(s)
    return deduped


# ── シュート成否判定 ────────────────────────────────────────────────────────
def judge_shots(shots, ball, fps, H_mat):
    """
    SAM3ボール位置からシュート成否を判定

    アルゴリズム (2段階):
      1. 放物線延長でバスケット高さの着地x → バスケット中心との距離で判定
      2. 放物線が収束しない場合 → バスケット最近接距離で判定

    Returns shots list with 'outcome': 'made' | 'missed' | 'unknown'
    """
    def proj_court(cx_cm, cy_cm):
        pt  = np.array([[[float(cx_cm), float(cy_cm)]]], dtype=np.float64)
        out = cv2.perspectiveTransform(pt, H_mat)
        return float(out[0,0,0]), float(out[0,0,1])

    bx_px, by_px = proj_court(0, BASKET_Y)
    rx_px, _     = proj_court(23.75, BASKET_Y)
    rim_r_px     = abs(rx_px - bx_px)
    # SAM3追跡誤差・視点歪みを考慮した広めの閾値
    THRESH_X  = max(90, rim_r_px * 18)
    THRESH_2D = max(110, rim_r_px * 22)   # 2Dフォールバック用

    print(f"  basket pixel=({bx_px:.0f},{by_px:.0f})  rim_r={rim_r_px:.1f}px  "
          f"thresh_x={THRESH_X:.0f}px  thresh_2d={THRESH_2D:.0f}px")

    LOOK_AHEAD = 120
    MIN_PTS    = 3

    for shot in shots:
        fi0 = shot["launch_fi"]

        pts = [(fi, ball[fi][0], ball[fi][1])
               for fi in range(fi0, fi0 + LOOK_AHEAD)
               if ball.get(fi) is not None]

        if len(pts) < MIN_PTS:
            shot["outcome"] = "unknown"
            continue

        fis = np.array([p[0] for p in pts], dtype=float)
        xs  = np.array([p[1] for p in pts], dtype=float)
        ys  = np.array([p[2] for p in pts], dtype=float)

        # ── 1次: 放物線延長 ──────────────────────────────────
        judged = False
        try:
            cy    = np.polyfit(fis, ys, 2)
            cx_ft = np.polyfit(fis, xs, 1)
            a, b, c = cy
            if a > 0:  # 画像y座標: 最小値=弧頂点 (a>0が正常)
                peak_fi = -b / (2 * a)
                disc = b**2 - 4 * a * (c - by_px)
                if disc >= 0:
                    t1 = (-b + np.sqrt(disc)) / (2 * a)
                    t2 = (-b - np.sqrt(disc)) / (2 * a)
                    cands = [t for t in [t1, t2] if t > peak_fi and t >= fi0]
                    if cands:
                        fi_land = min(cands)
                        x_land  = float(np.polyval(cx_ft, fi_land))
                        dist_px = abs(x_land - bx_px)
                        shot["outcome"]        = "made" if dist_px <= THRESH_X else "missed"
                        shot["dist_basket_px"] = round(dist_px, 1)
                        shot["fi_land"]        = round(fi_land, 1)
                        shot["judge_method"]   = "parabola"
                        judged = True
        except Exception:
            pass

        # ── 2次: 最近接距離フォールバック ────────────────────
        if not judged:
            dists = np.sqrt((xs - bx_px)**2 + (ys - by_px)**2)
            min_dist = float(dists.min())
            shot["outcome"]        = "made" if min_dist <= THRESH_2D else "missed"
            shot["dist_basket_px"] = round(min_dist, 1)
            shot["judge_method"]   = "proximity"

    return shots


# ── FIBA コート描画 ─────────────────────────────────────────────────────────
def draw_half_court(ax):
    kw  = dict(lw=1.2, color='#666', fill=False)
    bkw = dict(lw=1.0, color='#888', fill=False)
    # 外枠
    ax.add_patch(patches.Rectangle((-SIDELINE, 0), SIDELINE*2, HALF_Y,
                                    lw=1.5, edgecolor='#999', facecolor='none'))
    # センターライン
    ax.axhline(HALF_Y, color='#999', lw=1.2)
    # ペイント
    ax.add_patch(patches.Rectangle((-LANE_X, 0), LANE_X*2, FT_Y, **kw))
    # 3PT
    ax.plot([-PT3_CX, -PT3_CX], [0, PT3_CY], color='#888', lw=1.2)
    ax.plot([ PT3_CX,  PT3_CX], [0, PT3_CY], color='#888', lw=1.2)
    ax.add_patch(Arc((0, BASKET_Y), PT3_R*2, PT3_R*2,
                     theta1=0, theta2=180, color='#888', lw=1.2))
    # バスケット
    ax.add_patch(plt.Circle((0, BASKET_Y), 23.75, fill=False, color='#e55', lw=1.5))
    ax.set_xlim(-SIDELINE - 30, SIDELINE + 30)
    ax.set_ylim(-40, HALF_Y + 40)
    ax.set_aspect('equal')
    ax.axis('off')


# ── メイン ─────────────────────────────────────────────────────────────────
def run_mog2_detection(video_path, fps, max_fi):
    """MOG2 + オレンジフィルタでシュート検出"""
    cap     = cv2.VideoCapture(video_path)
    bg      = cv2.createBackgroundSubtractorMOG2(
                  history=100, varThreshold=MOTION_THR, detectShadows=False)
    tracker = BallTracker()
    ref_frame = None
    fi = 0
    while fi < max_fi:
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ret, frame = cap.read()
        if not ret: break
        fgmask = bg.apply(frame)
        if fi < int(fps):
            fi += SKIP; continue
        if ref_frame is None:
            ref_frame = frame.copy()
        cands = detect_ball_candidates(frame, fgmask)
        tracker.update(fi, cands)
        fi += SKIP
    cap.release()
    tracks = tracker.long_tracks()
    shots  = detect_shots(tracks, fps)
    return shots, ref_frame


def run_sam3_detection(ball_json_path, fps, max_fi):
    """SAM3ボール位置JSONからシュート検出 (放物線フィット方式)"""
    with open(ball_json_path) as f:
        raw = json.load(f)
    ball = {int(k): (v[0], v[1]) if v else None for k, v in raw.items()}

    # 検出済みフレームのみ抽出
    pts = [(fi, ball[fi][0], ball[fi][1])
           for fi in sorted(ball)
           if fi <= max_fi and ball[fi] is not None]

    if not pts:
        return []

    # 連続セグメントに分割 (フレーム間隔が20超で切断)
    segments, seg = [], [pts[0]]
    for i in range(1, len(pts)):
        if pts[i][0] - pts[i-1][0] > 20:
            if len(seg) >= 4:
                segments.append(seg)
            seg = []
        seg.append(pts[i])
    if len(seg) >= 4:
        segments.append(seg)

    # セグメントを1本のトラックとして扱い放物線フィット
    track = {"sam3": pts}
    return detect_shots(track, fps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile",   default="outputs/venue_profiles/game2-1.json")
    ap.add_argument("--sec",       type=int, default=30)
    ap.add_argument("--ball_json", default=None,
                    help="SAM3ボール位置JSON。省略時はMOG2検出を使用")
    args = ap.parse_args()

    H, H_inv, hull, prof = load_profile(args.profile)
    video_path = f"data/videos/{prof['video']}"
    video_name = Path(video_path).stem
    print(f"Profile : {args.profile}  ({prof['n_pairs']} pairs)")
    print(f"Video   : {video_path}")

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 29.4
    max_fi = min(int(args.sec * fps), int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    cap.release()

    # 参照フレーム取得
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, min(int(fps * 5), max_fi - 1))
    _, ref_frame = cap.read()
    cap.release()

    if args.ball_json:
        print(f"Mode    : SAM3  ({args.ball_json})")
        shots = run_sam3_detection(args.ball_json, fps, max_fi)
    else:
        print(f"Detect  : MOG2  {args.sec}s ({max_fi} frames)  skip={SKIP}")
        shots, ref_frame = run_mog2_detection(video_path, fps, max_fi)
    print(f"Raw shots detected: {len(shots)}")

    # ── コート座標変換 + フィルタ ────────────────────────────────────────
    calibrated = []
    for s in shots:
        cx, cy = img_to_court(H_inv, s["launch_x"], s["launch_y"])
        # コート内かつ信頼領域内のみ
        if not (-SIDELINE - 150 <= cx <= SIDELINE + 150):
            continue
        if not (-100 <= cy <= HALF_Y + 100):
            continue
        if not in_trust_hull(hull, cx, cy, margin=150):
            continue
        s["court_x"] = round(cx, 1)
        s["court_y"] = round(cy, 1)
        calibrated.append(s)

    print(f"In-court shots  : {len(calibrated)}")

    # ── シュート成否判定 (SAM3モード時のみ) ──────────────────────────────────
    if args.ball_json and calibrated:
        with open(args.ball_json) as f:
            ball_raw = json.load(f)
        ball = {int(k): (v[0], v[1]) if v else None for k, v in ball_raw.items()}
        print("Judging shot outcomes...")
        calibrated = judge_shots(calibrated, ball, fps, H)
        for i, s in enumerate(calibrated):
            dist = s.get("dist_basket_px", "N/A")
            dist_str = f"{dist:.1f}px" if isinstance(dist, float) else dist
            print(f"  #{i+1} {s.get('outcome','unknown'):7s}  dist={dist_str}")

    # ── 映像フレーム上のショット位置 ────────────────────────────────────
    if ref_frame is not None:
        vis = ref_frame.copy()
        H_ct2img = H  # court → image
        # コートラインオーバーレイ
        def proj(court_x, court_y):
            pt  = np.array([[[float(court_x), float(court_y)]]], dtype=np.float64)
            out = cv2.perspectiveTransform(pt, H_ct2img)
            return (int(out[0,0,0]), int(out[0,0,1]))

        h_img, w_img = vis.shape[:2]
        lines = [
            [(-SIDELINE,0),(SIDELINE,0)], [(-SIDELINE,0),(-SIDELINE,HALF_Y)],
            [(SIDELINE,0),(SIDELINE,HALF_Y)], [(-LANE_X,0),(-LANE_X,FT_Y)],
            [(LANE_X,0),(LANE_X,FT_Y)],  [(-LANE_X,FT_Y),(LANE_X,FT_Y)],
        ]
        for (x1,y1),(x2,y2) in lines:
            p1, p2 = proj(x1,y1), proj(x2,y2)
            if all(0<=v[0]<w_img and 0<=v[1]<h_img for v in [p1,p2]):
                cv2.line(vis, p1, p2, (0,220,150), 1, cv2.LINE_AA)

        for i, s in enumerate(calibrated):
            cx_px, cy_px = int(s["launch_x"]), int(s["launch_y"])
            cv2.circle(vis, (cx_px, cy_px), 12, (0,60,255), -1)
            cv2.circle(vis, (cx_px, cy_px), 12, (255,255,255), 2)
            cv2.putText(vis, str(i+1), (cx_px-5, cy_px+5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,255), 1)
        cv2.putText(vis, f"Calibrated shots  n={len(calibrated)}",
                    (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,200), 2)
        out1 = OUT_DIR / f"{video_name}_shots_on_frame.jpg"
        cv2.imwrite(str(out1), vis)
        print(f"Saved: {out1}")

    # ── コート図ショットチャート ─────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(7, 8), facecolor="#0d1117")
    ax.set_facecolor("#0d1117")
    draw_half_court(ax)

    if calibrated:
        xs = [s["court_x"] for s in calibrated]
        ys = [s["court_y"] for s in calibrated]
        ts = [s["ts"]      for s in calibrated]
        ts_norm = (np.array(ts) - min(ts)) / (max(ts) - min(ts) + 1e-9)
        sc = ax.scatter(xs, ys, c=ts_norm, cmap="plasma", s=160,
                        edgecolors="white", linewidths=1.2, zorder=5)
        for i, (x, y, t) in enumerate(zip(xs, ys, ts)):
            mm, ss = int(t//60), int(t%60)
            ax.text(x, y - 55, f"{mm}:{ss:02d}", color="white",
                    fontsize=6.5, ha="center", zorder=6)
        cb = fig.colorbar(plt.cm.ScalarMappable(
                cmap="plasma", norm=plt.Normalize(min(ts), max(ts))),
                ax=ax, shrink=0.5, pad=0.02)
        cb.set_label("Time (s)", color="white", fontsize=9)
        cb.ax.yaxis.set_tick_params(color="white")
        plt.setp(cb.ax.yaxis.get_ticklabels(), color="white")

    ax.set_title(f"Shot Chart (calibrated) — {video_name}\n"
                 f"n={len(calibrated)} shots / {args.sec}s",
                 color="white", fontsize=12, pad=10)
    ax.text(0.5, -0.02, f"Profile: {prof['n_pairs']} pairs  |  FIBA half-court (cm)",
            transform=ax.transAxes, ha="center", color="#888", fontsize=8)

    plt.tight_layout()
    out2 = OUT_DIR / f"{video_name}_court_shot_chart.png"
    fig.savefig(out2, dpi=130, bbox_inches="tight", facecolor="#0d1117")
    plt.close(fig)
    print(f"Saved: {out2}")

    # ── タイムライン ─────────────────────────────────────────────────────
    print(f"\n{'#':>3}  {'time':>6}  {'court_x':>8}  {'court_y':>8}  {'R2':>5}")
    for i, s in enumerate(calibrated):
        ts = s["ts"]
        mm, ss = int(ts//60), int(ts%60)
        print(f"{i+1:3d}  {mm}:{ss:02d}    {s['court_x']:8.0f}  {s['court_y']:8.0f}  {s['r2']:5.3f}")

    out3 = OUT_DIR / f"{video_name}_shots.json"
    with open(out3, "w") as f:
        json.dump(calibrated, f, indent=2)
    print(f"\nSaved: {out3}")


if __name__ == "__main__":
    main()

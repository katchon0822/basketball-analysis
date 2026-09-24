#!/usr/bin/env python3
"""
render_full_detection.py — ボール・選手・ゴール・コート統合検知動画

DeNA方式を参考に:
  - コートライン自動検知 (CourtDetector) → フレームごとH更新 (アノテーション不要)
  - 選手背番号OCR (PlayerNumberTracker) → Tracking IDに紐づけ
  - ボールハンドラー検出 → ハンドラー位置をボール位置として使用
  - SAM3ボール軌跡 + YOLO+ByteTrack選手検知
  - シュートマーカー (MADE=緑 / MISSED=赤 / unknown=灰)
  - 右サイドバー: ミニコート図 + 累積シュートリスト

Usage:
  python render_full_detection.py
  python render_full_detection.py --sec 30 --profile outputs/venue_profiles/game2-1.json
"""

import cv2, json, numpy as np, argparse, subprocess
from pathlib import Path
from collections import defaultdict, deque

import supervision as sv
from ultralytics import YOLO

from player_number_ocr import PlayerNumberTracker

TRAIL_LEN = 90   # 選手軌跡: 直近 N フレーム (≈3秒 @ 30fps)

# ── コート定数 (cm) ─────────────────────────────────────────────────────────
SIDELINE = 750;  HALF_Y = 1432;  FULL_Y = HALF_Y * 2;  BASKET_Y = 160
FT_Y = 580;      LANE_X = 245;   CENTER_R = 180
PT3_CX = 665;    PT3_CY = 420;   PT3_R = 705

SIDEBAR_W = 220
OUT_DIR   = Path("outputs/full_detection")
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── ホモグラフィー投影 ───────────────────────────────────────────────────────
def make_proj(H):
    def proj(cx, cy):
        pt  = np.array([[[float(cx), float(cy)]]], dtype=np.float64)
        out = cv2.perspectiveTransform(pt, H)
        return (int(out[0,0,0]), int(out[0,0,1]))
    return proj


def draw_court_overlay(frame, proj, W, H_px):
    def seg(x1,y1,x2,y2,col,t=1):
        p1,p2 = proj(x1,y1),proj(x2,y2)
        if all(0<=p[0]<W and 0<=p[1]<H_px for p in (p1,p2)):
            cv2.line(frame,p1,p2,col,t,cv2.LINE_AA)
    WH=(170,170,170); BL=(100,190,255); OR=(40,210,255)
    seg(-SIDELINE,0, SIDELINE,0,      WH,2)
    seg(-SIDELINE,0,-SIDELINE,HALF_Y, WH,2)
    seg( SIDELINE,0, SIDELINE,HALF_Y, WH,2)
    seg(-SIDELINE,HALF_Y,SIDELINE,HALF_Y, WH,1)
    seg(-LANE_X,0,-LANE_X,FT_Y,BL); seg(LANE_X,0,LANE_X,FT_Y,BL)
    seg(-LANE_X,FT_Y,LANE_X,FT_Y,BL)
    seg(-PT3_CX,0,-PT3_CX,PT3_CY,OR); seg(PT3_CX,0,PT3_CX,PT3_CY,OR)
    arc=[]
    for d in range(-115,116,3):
        r=np.radians(d); cx=PT3_R*np.sin(r); cy=BASKET_Y+PT3_R*np.cos(r)
        if abs(cx)<=PT3_CX:
            p=proj(cx,cy)
            if 0<=p[0]<W and 0<=p[1]<H_px: arc.append(p)
    for i in range(len(arc)-1): cv2.line(frame,arc[i],arc[i+1],OR,1,cv2.LINE_AA)
    bk=[proj(23.75*np.cos(np.radians(d)),BASKET_Y+23.75*np.sin(np.radians(d)))
        for d in range(0,361,8)]
    bk=[p for p in bk if 0<=p[0]<W and 0<=p[1]<H_px]
    for i in range(len(bk)-1): cv2.line(frame,bk[i],bk[i+1],(60,80,255),2,cv2.LINE_AA)


def _draw_one_goal(frame, p, label="GOAL"):
    cv2.circle(frame, p, 20, (0,0,0), 3)
    cv2.circle(frame, p, 20, (0,80,255), 2)
    cv2.line(frame,(p[0]-14,p[1]),(p[0]+14,p[1]),(0,80,255),1,cv2.LINE_AA)
    cv2.line(frame,(p[0],p[1]-14),(p[0],p[1]+14),(0,80,255),1,cv2.LINE_AA)
    cv2.putText(frame,label,(p[0]+22,p[1]+4),cv2.FONT_HERSHEY_SIMPLEX,0.38,(0,0,0),3)
    cv2.putText(frame,label,(p[0]+22,p[1]+4),cv2.FONT_HERSHEY_SIMPLEX,0.38,(0,160,255),1)


def draw_goal_marker(frame, proj, W, H_px, far_ring_px=None):
    # 近端ゴール (Hで投影)
    p = proj(0, BASKET_Y)
    if 0<=p[0]<W and 0<=p[1]<H_px:
        _draw_one_goal(frame, p, "GOAL")
    # 遠端ゴール (固定ピクセル座標)
    if far_ring_px is not None:
        fp = tuple(far_ring_px)
        if 0<=fp[0]<W and 0<=fp[1]<H_px:
            _draw_one_goal(frame, fp, "GOAL")


# ── チーム分類 ───────────────────────────────────────────────────────────────
def classify_team(frame, bbox):
    x1,y1,x2,y2 = map(int,bbox); h=y2-y1
    roi = frame[y1+int(h*0.15):y1+int(h*0.65), x1:x2]
    if roi.size==0: return 0
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    t   = roi.shape[0]*roi.shape[1]
    white = cv2.inRange(hsv,(0,0,170),(180,70,255)).sum()/255/t
    navy  = cv2.inRange(hsv,(90,60,15),(140,255,170)).sum()/255/t
    if white>0.12: return 1
    if navy >0.07: return 2
    return 0


# ── ボールハンドラー検出 ─────────────────────────────────────────────────────
def find_ball_handler(ball_pos, track_ids, bboxes):
    """
    ボール位置に最も近い選手 = ボールハンドラー

    DeNA方式: ボールハンドラーの位置をボール位置として使用
    Returns: (handler_track_id, feet_pos) or (None, None)
    """
    if ball_pos is None or not track_ids:
        return None, None
    bx, by = ball_pos
    best_tid, best_dist, best_feet = None, float('inf'), None
    for tid, bbox in zip(track_ids, bboxes):
        x1, y1, x2, y2 = map(int, bbox)
        # BBox内にボールが入っているか
        if x1-20 <= bx <= x2+20 and y1-25 <= by <= y2+15:
            feet = ((x1+x2)//2, y2)
            return tid, feet
        # 最近接距離
        cx, cy = (x1+x2)/2, (y1+y2)/2
        dist = np.hypot(bx-cx, by-cy)
        if dist < best_dist:
            best_dist, best_tid = dist, tid
            best_feet = ((x1+x2)//2, y2)
    if best_dist < 80:
        return best_tid, best_feet
    return None, None


# ── コート座標変換 ───────────────────────────────────────────────────────────
def img_to_court(H_inv, px, py):
    """画像ピクセル → コート座標 (cm)"""
    pt  = np.array([[[float(px), float(py)]]], dtype=np.float64)
    out = cv2.perspectiveTransform(pt, H_inv)
    return float(out[0,0,0]), float(out[0,0,1])


def is_on_court(cx, cy, margin=300):
    return (-SIDELINE-margin <= cx <= SIDELINE+margin and
            -margin <= cy <= HALF_Y+margin)


# ── DeNA風ミニマップ ─────────────────────────────────────────────────────────
OUTCOME_COL = {"made":(0,220,60),"missed":(60,60,255),"unknown":(140,140,140)}

# フルコート比率: 1500cm × 2864cm → MAP_W : MAP_H ≈ 130 : 248
MAP_W, MAP_H = 130, 250
MAP_PAD = 8

def _build_court_base():
    """黒背景フルコート図ベース画像を生成 (毎フレーム再使用)"""
    img   = np.zeros((MAP_H, MAP_W, 3), dtype=np.uint8)
    scl   = (MAP_W - MAP_PAD*2) / (SIDELINE * 2)
    scl_y = (MAP_H - MAP_PAD*2) / FULL_Y

    def c2p(cx, cy):
        """コート座標(cm) → ミニマップピクセル (y=0=手前ベースライン=下)"""
        return (MAP_PAD + int((cx + SIDELINE) * scl),
                MAP_PAD + int((FULL_Y - cy) * scl_y))

    G  = (70, 70, 70)
    WL = (110, 110, 110)

    def ml(x1, y1, x2, y2, col=G, t=1):
        cv2.line(img, c2p(x1, y1), c2p(x2, y2), col, t, cv2.LINE_AA)

    # ── 外枠・中央線 ──────────────────────────────────────────────────────────
    ml(-SIDELINE, 0,      SIDELINE, 0,      WL, 2)   # 手前ベースライン
    ml(-SIDELINE, FULL_Y, SIDELINE, FULL_Y, WL, 2)   # 奥ベースライン
    ml(-SIDELINE, 0,     -SIDELINE, FULL_Y, WL, 2)   # 左サイドライン
    ml( SIDELINE, 0,      SIDELINE, FULL_Y, WL, 2)   # 右サイドライン
    ml(-SIDELINE, HALF_Y, SIDELINE, HALF_Y, WL, 1)   # センターライン

    # センターサークル
    cv2.circle(img, c2p(0, HALF_Y), max(1, int(CENTER_R * scl)), G, 1)

    rim_r = max(1, int(23.75 * scl))

    # ── 手前ハーフ (y: 0 → HALF_Y) ──────────────────────────────────────────
    ml(-LANE_X, 0, -LANE_X, FT_Y)
    ml( LANE_X, 0,  LANE_X, FT_Y)
    ml(-LANE_X, FT_Y, LANE_X, FT_Y)
    ml(-PT3_CX, 0, -PT3_CX, PT3_CY)
    ml( PT3_CX, 0,  PT3_CX, PT3_CY)
    arc = []
    for d in range(-115, 116, 4):
        r = np.radians(d)
        cx = PT3_R * np.sin(r); cy = BASKET_Y + PT3_R * np.cos(r)
        if abs(cx) <= PT3_CX: arc.append(c2p(cx, cy))
    for i in range(len(arc)-1): cv2.line(img, arc[i], arc[i+1], G, 1, cv2.LINE_AA)
    cv2.circle(img, c2p(0, BASKET_Y), rim_r, (60, 80, 200), 1)

    # ── 奥ハーフ (y: HALF_Y → FULL_Y、手前の鏡像) ──────────────────────────
    FAR_B = FULL_Y - BASKET_Y   # 2704cm
    FAR_F = FULL_Y - FT_Y       # 2284cm
    FAR_P = FULL_Y - PT3_CY     # 2444cm
    ml(-LANE_X, FULL_Y, -LANE_X, FAR_F)
    ml( LANE_X, FULL_Y,  LANE_X, FAR_F)
    ml(-LANE_X, FAR_F, LANE_X, FAR_F)
    ml(-PT3_CX, FULL_Y, -PT3_CX, FAR_P)
    ml( PT3_CX, FULL_Y,  PT3_CX, FAR_P)
    arc2 = []
    for d in range(-115, 116, 4):
        r = np.radians(d)
        cx = PT3_R * np.sin(r); cy = FAR_B - PT3_R * np.cos(r)
        if abs(cx) <= PT3_CX: arc2.append(c2p(cx, cy))
    for i in range(len(arc2)-1): cv2.line(img, arc2[i], arc2[i+1], G, 1, cv2.LINE_AA)
    cv2.circle(img, c2p(0, FAR_B), rim_r, (60, 80, 200), 1)

    # 方向ラベル
    cv2.putText(img, "NEAR", (MAP_PAD, MAP_H-3),
                cv2.FONT_HERSHEY_SIMPLEX, 0.22, (90,90,90), 1)
    cv2.putText(img, "FAR",  (MAP_PAD, MAP_PAD+8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.22, (90,90,90), 1)

    return img, c2p

_COURT_BASE, _C2P = _build_court_base()


TEAM_COL = {1:(230,230,255), 2:(255,140,60), 0:(160,255,160)}


def make_tracking_map(players, player_trails, ball_court, handler_tid):
    """
    リアルタイムトラッキングマップ:
    - 選手軌跡 (直近 TRAIL_LEN フレーム、チームカラーでフェード)
    - 選手ドット (ハンドラー強調)
    - ボール
    """
    img = _COURT_BASE.copy()
    c2p = _C2P

    # ── 選手軌跡 ────────────────────────────────────────────────────────────
    for tid, (team, trail) in player_trails.items():
        col = TEAM_COL.get(team, (160, 255, 160))
        pts = list(trail)
        for i in range(1, len(pts)):
            alpha = i / len(pts)           # 古い方 = 暗い
            p1, p2 = c2p(*pts[i-1]), c2p(*pts[i])
            if not (0<=p1[0]<MAP_W and 0<=p1[1]<MAP_H and
                    0<=p2[0]<MAP_W and 0<=p2[1]<MAP_H):
                continue
            c = tuple(int(v * alpha * 0.65) for v in col)
            cv2.line(img, p1, p2, c, 1, cv2.LINE_AA)

    # ── ボール ───────────────────────────────────────────────────────────────
    if ball_court:
        bp = c2p(ball_court[0], ball_court[1])
        if 0<=bp[0]<MAP_W and 0<=bp[1]<MAP_H:
            cv2.circle(img, bp, 7, (0,220,255), -1)
            cv2.circle(img, bp, 7, (255,255,255), 1)

    # ── 選手ドット ───────────────────────────────────────────────────────────
    for tid, team, cx, cy, label in players:
        p = c2p(cx, cy)
        if not (0<=p[0]<MAP_W and 0<=p[1]<MAP_H):
            continue
        col = TEAM_COL.get(team, (160,255,160))
        is_handler = (tid == handler_tid)
        r = 8 if is_handler else 6
        cv2.circle(img, p, r, col, -1)
        cv2.circle(img, p, r, (255,255,255) if is_handler else (40,40,40), 1)
        cv2.putText(img, label, (p[0]-4, p[1]+3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.22, (0,0,0), 1)
    return img


def make_shot_chart(shots_so_far, active_shot_idx=None):
    """
    シュートチャートマップ:
    - MADE = 緑塗り / MISS = 赤塗り
    - チーム色のリング
    - シュート番号ラベル
    """
    img = _COURT_BASE.copy()
    c2p = _C2P
    OUTCOME_FILL = {"made":(30,200,60), "missed":(50,50,220), "unknown":(110,110,110)}

    for i, s in enumerate(shots_so_far):
        cx_c, cy_c = s.get("court_x",0), s.get("court_y",0)
        p = c2p(cx_c, cy_c)
        if not (0<=p[0]<MAP_W and 0<=p[1]<MAP_H):
            continue
        outcome = s.get("outcome","unknown")
        fill  = OUTCOME_FILL.get(outcome,(110,110,110))
        team  = s.get("team", 0)
        ring  = TEAM_COL.get(team, (160,160,160))
        is_active = (i == active_shot_idx)
        r = 8 if is_active else 6
        # 塗り
        cv2.circle(img, p, r, fill, -1)
        # チームカラーのリング
        cv2.circle(img, p, r, ring, 1)
        # ハイライト中はさらに外枠
        if is_active:
            cv2.circle(img, p, r+3, (255,255,255), 1)
        # 番号
        lbl = str(i+1)
        cv2.putText(img, lbl, (p[0]-3, p[1]+3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.20, (0,0,0), 2)
        cv2.putText(img, lbl, (p[0]-3, p[1]+3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.20, (230,230,230), 1)
    return img


def make_sidebar(H_px, players, player_trails, ball_court, handler_tid,
                 shots_so_far, active_shot_idx, num_tracker=None):
    """
    サイドバー:
      [TRACKING] コートマップ + 選手軌跡 + ボール
      [SHOTS]    シュートチャート
      [STATS]    FG%・チーム別
      [LIST]     シュートリスト (残り高さ)
    """
    bar = np.full((H_px, SIDEBAR_W, 3), 15, dtype=np.uint8)
    pad = (SIDEBAR_W - MAP_W) // 2
    y   = 0

    def hdr(txt, yy):
        cv2.putText(bar, txt, (pad, yy+12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.30, (120,120,120), 1)

    # ── TRACKING MAP ─────────────────────────────────────────────────────────
    hdr("TRACKING", y); y += 16
    tmap = make_tracking_map(players, player_trails, ball_court, handler_tid)
    bar[y:y+MAP_H, pad:pad+MAP_W] = tmap
    cv2.rectangle(bar, (pad-1,y-1), (pad+MAP_W,y+MAP_H), (55,55,55), 1)
    y += MAP_H + 8

    # ── SHOT CHART ───────────────────────────────────────────────────────────
    SHOT_H = min(170, H_px - y - 100)
    if SHOT_H > 60:
        hdr("SHOTS", y); y += 16
        # shot chart は half_y比率に合わせた高さにトリミング
        schart_full = make_shot_chart(shots_so_far, active_shot_idx)
        # フルコートの上半分(NEAR側)だけ表示 → y_top: MAP_H/2〜MAP_H
        # ただし full_y使うので下半分(NEAR)は img y=125〜250
        near_start = MAP_H // 2
        near_crop  = schart_full[near_start:, :]   # near半面のみ
        crop_h     = near_crop.shape[0]
        target_h   = min(SHOT_H, crop_h)
        if target_h > 0:
            shot_img = near_crop[:target_h, :]
            bar[y:y+target_h, pad:pad+MAP_W] = shot_img
            cv2.rectangle(bar, (pad-1,y-1), (pad+MAP_W,y+target_h), (55,55,55), 1)
            # 凡例
            lx, ly = pad, y+target_h+12
            for col, txt in [((30,200,60),"MADE"),((50,50,220),"MISS"),((110,110,110),"?")]:
                cv2.circle(bar,(lx+4,ly-3),4,col,-1)
                cv2.putText(bar,txt,(lx+10,ly),cv2.FONT_HERSHEY_SIMPLEX,0.26,(160,160,160),1)
                lx += 50
            y += target_h + 18

    # ── STATS ────────────────────────────────────────────────────────────────
    if H_px - y > 60:
        made_all    = sum(1 for s in shots_so_far if s.get("outcome")=="made")
        missed_all  = sum(1 for s in shots_so_far if s.get("outcome")=="missed")
        total_rated = made_all + missed_all
        fg_pct      = f"{made_all}/{total_rated}  {100*made_all/total_rated:.0f}%" if total_rated else "—"
        # チーム別
        def team_stats(t):
            m = sum(1 for s in shots_so_far if s.get("team")==t and s.get("outcome")=="made")
            n = sum(1 for s in shots_so_far if s.get("team")==t and s.get("outcome") in ("made","missed"))
            return f"{m}/{n}" if n else "0/0"

        lines = [
            ("FG%",      fg_pct,      (180,180,180)),
            ("White",    team_stats(1),(230,230,255)),
            ("Navy",     team_stats(2),(255,160,80)),
        ]
        cv2.putText(bar, "STATS", (pad, y+12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.30, (120,120,120), 1)
        y += 16
        for lbl, val, col in lines:
            cv2.putText(bar, f"{lbl}: {val}", (pad, y+10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.28, col, 1)
            y += 13

    # ── SHOT LIST ────────────────────────────────────────────────────────────
    y += 4
    row_h    = 14
    max_rows = max(1, (H_px - y - 4) // row_h)
    offset   = max(0, len(shots_so_far) - max_rows)
    disp     = shots_so_far[offset:]
    for j, s in enumerate(disp):
        idx  = offset + j
        ts   = s.get("ts", 0); mm = int(ts//60); ss_ = int(ts%60)
        outcome = s.get("outcome","unknown")
        sym  = {"made":"O","missed":"X"}.get(outcome, "?")
        txt  = f"#{idx+1} {mm}:{ss_:02d}[{sym}]({s.get('court_x',0):.0f},{s.get('court_y',0):.0f})"
        col  = (0,220,255) if idx==active_shot_idx else OUTCOME_COL.get(outcome,(110,110,110))
        cv2.putText(bar, txt, (pad, y+j*row_h+10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.24, col, 1)

    return bar


# ── メイン ──────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile",      default="outputs/venue_profiles/game2-1.json")
    ap.add_argument("--shots",        default="outputs/calibrated_shots/game_2-1_shots.json")
    ap.add_argument("--ball",         default="outputs/sam3_tracking/ball_positions_game_2-1_30s.json")
    ap.add_argument("--model",        default="models/player_detector.pt")
    ap.add_argument("--sec",  type=int,   default=30)
    ap.add_argument("--conf", type=float, default=0.40)
    ap.add_argument("--no_ocr", action="store_true", help="背番号OCRをスキップ")
    args = ap.parse_args()

    # ── データ読み込み ────────────────────────────────────────────────────
    with open(args.profile) as f: prof = json.load(f)
    with open(args.shots)   as f: shots = json.load(f)
    with open(args.ball)    as f: ball_raw = json.load(f)
    ball_sam3 = {int(k):(v[0],v[1]) if v else None for k,v in ball_raw.items()}

    # アノテーション済みH行列 (固定)
    H_mat       = np.array(prof["H_court_to_image"])
    H_inv       = np.linalg.inv(H_mat)
    far_ring_px = prof.get("far_ring_image_xy")   # 遠端ゴール固定ピクセル (optional)
    video = f"data/videos/{prof['video']}"
    stem  = Path(video).stem
    proj  = make_proj(H_mat)

    # ── モデル / トラッカー ───────────────────────────────────────────────
    det_model  = YOLO(args.model)
    sv_tracker = sv.ByteTrack(minimum_matching_threshold=0.7,
                               minimum_consecutive_frames=2,
                               lost_track_buffer=60)
    team_votes  = defaultdict(list)
    num_tracker = PlayerNumberTracker(ocr_every=8) if not args.no_ocr else None

    cap   = cv2.VideoCapture(video)
    fps   = cap.get(cv2.CAP_PROP_FPS) or 29.4
    W     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H_px  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    max_fi = min(int(args.sec*fps), int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    print(f"Video  : {video}  {W}x{H_px} @{fps:.1f}fps  {args.sec}s")
    print(f"Shots  : {len(shots)}")
    print(f"OCR    : {'OFF' if args.no_ocr else 'ON'}")

    out_w   = W + SIDEBAR_W
    out_tmp = str(OUT_DIR / f"{stem}_full_tmp.mp4")
    out_fin = str(OUT_DIR / f"{stem}_full_detection.mp4")
    writer  = cv2.VideoWriter(out_tmp, cv2.VideoWriter_fourcc(*"mp4v"),
                               fps, (out_w, H_px))

    FLASH_DUR    = int(fps*2.0)
    shot_fi      = {s["launch_fi"]:(i,s) for i,s in enumerate(shots)}
    active_shots: list = []
    shown_shots:  list = []
    trail:        list = []
    TEAM_BGR     = {1:(220,220,255), 2:(255,160,80), 0:(160,255,160)}
    CLS_PLAYER   = 4
    handler_tid  = None
    # 選手軌跡: {track_id: (team, deque[(court_x,court_y)])}
    player_trails: dict = {}

    for fi in range(max_fi):
        ret, frame = cap.read()
        if not ret: break

        canvas = np.zeros((H_px, out_w, 3), dtype=np.uint8)
        canvas[:, :W] = frame

        draw_court_overlay(canvas, proj, W, H_px)
        draw_goal_marker(canvas, proj, W, H_px, far_ring_px)

        # ── SAM3 ボール軌跡 ──────────────────────────────────────────────
        pos_sam3 = ball_sam3.get(fi)
        if pos_sam3:
            trail.append((int(pos_sam3[0]), int(pos_sam3[1])))
            if len(trail) > 25: trail.pop(0)
        for i in range(1, len(trail)):
            a = i/len(trail)
            cv2.line(canvas, trail[i-1], trail[i],
                     (int(30*a),int(200*a),int(255*a)), 2, cv2.LINE_AA)
        if pos_sam3 and trail:
            cv2.circle(canvas, trail[-1], 9, (0,220,255), -1)
            cv2.circle(canvas, trail[-1], 9, (255,255,255), 1)

        # ── 選手検知 + ByteTrack ─────────────────────────────────────────
        results  = det_model.predict(frame, conf=args.conf, verbose=False)[0]
        p_dets   = [(box.xyxy[0].cpu().numpy(), float(box.conf[0]))
                    for box in results.boxes
                    if int(box.cls[0])==CLS_PLAYER and float(box.conf[0])>=args.conf]

        if p_dets:
            boxes_np = np.array([d[0] for d in p_dets])
            confs_np = np.array([d[1] for d in p_dets])
            sv_det   = sv.Detections(xyxy=boxes_np, confidence=confs_np,
                                      class_id=np.zeros(len(p_dets),dtype=int))
            tracks   = sv_tracker.update_with_detections(sv_det)
        else:
            tracks = sv.Detections.empty()

        # ボールハンドラー特定
        cur_tids  = list(tracks.tracker_id) if len(tracks) else []
        cur_bboxes= list(tracks.xyxy) if len(tracks) else []
        handler_tid, handler_feet = find_ball_handler(pos_sam3, cur_tids, cur_bboxes)

        # 背番号OCR更新
        if num_tracker and len(tracks):
            num_tracker.update(frame, cur_tids, cur_bboxes)

        for i in range(len(tracks)):
            tid  = int(tracks.tracker_id[i])
            bbox = tracks.xyxy[i]
            team = classify_team(frame, bbox)
            team_votes[tid].append(team)
            recent = team_votes[tid][-20:]
            votes  = [t for t in recent if t in (1,2)]
            stable = max(set(votes),key=votes.count) if votes else 0

            x1,y1,x2,y2 = map(int, bbox)
            col = TEAM_BGR.get(stable,(160,255,160))

            # ボールハンドラーは特別強調
            is_handler = (tid == handler_tid)
            border_col = (0,255,255) if is_handler else col
            thick      = 3 if is_handler else 2

            overlay = canvas.copy()
            cv2.rectangle(overlay,(x1,y1),(x2,y2),col,-1)
            cv2.addWeighted(overlay,0.18,canvas,0.82,0,canvas)
            cv2.rectangle(canvas,(x1,y1),(x2,y2),border_col,thick)

            # 背番号 or Tracking ID
            label = num_tracker.get_label(tid) if num_tracker else f"P{tid%100}"
            if is_handler:
                label += " BALL"
            cv2.putText(canvas,label,(x1,y1-4),cv2.FONT_HERSHEY_SIMPLEX,0.40,(0,0,0),3)
            cv2.putText(canvas,label,(x1,y1-4),cv2.FONT_HERSHEY_SIMPLEX,0.40,border_col,1)

            # 足元マーカー (コート位置の基準点)
            feet = ((x1+x2)//2, y2)
            cv2.circle(canvas, feet, 3, col, -1)

        # ── シュートマーカー ─────────────────────────────────────────────
        if fi in shot_fi:
            sidx,s = shot_fi[fi]
            active_shots.append((fi+FLASH_DUR, sidx, s))
            shown_shots.append(s)
        active_shots = [(e,si,s) for e,si,s in active_shots if fi<=e]
        OUTCOME_BGR  = {"made":(0,220,60),"missed":(60,60,255),"unknown":(140,140,140)}
        for exp,sidx,s in active_shots:
            fade    = max(0.3,(exp-fi)/FLASH_DUR)
            px,py   = int(s["launch_x"]),int(s["launch_y"])
            r       = int(14+(1-fade)*12)
            outcome = s.get("outcome","unknown")
            base    = OUTCOME_BGR.get(outcome,(140,140,140))
            shot_col= tuple(int(c*fade) for c in base)
            cv2.circle(canvas,(px,py),r,shot_col,-1)
            cv2.circle(canvas,(px,py),r,(255,255,255),2)
            cv2.putText(canvas,f"#{sidx+1}",(px-7,py+5),
                        cv2.FONT_HERSHEY_SIMPLEX,0.45,(255,255,255),1)
            sym  = {"made":"MADE","missed":"MISS"}.get(outcome,"?")
            lbl  = f"SHOT #{sidx+1} {sym}  ({s['court_x']:.0f},{s['court_y']:.0f})cm"
            cv2.putText(canvas,lbl,(px+18,py),cv2.FONT_HERSHEY_SIMPLEX,0.38,(0,0,0),3)
            cv2.putText(canvas,lbl,(px+18,py),cv2.FONT_HERSHEY_SIMPLEX,0.38,base,1)

        # ── 選手・ボールのコート座標変換 + 軌跡蓄積 ─────────────────
        players_court = []
        alive_tids_set = set()
        for i in range(len(tracks)):
            tid  = int(tracks.tracker_id[i])
            bbox = tracks.xyxy[i]
            x1,y1,x2,y2 = map(int,bbox)
            cx, cy = img_to_court(H_inv, (x1+x2)//2, y2)
            if not is_on_court(cx, cy):
                continue
            team   = classify_team(frame, bbox)
            team_votes[tid].append(team)
            recent = team_votes[tid][-20:]
            votes  = [t for t in recent if t in (1,2)]
            stable = max(set(votes),key=votes.count) if votes else 0
            label  = num_tracker.get_label(tid) if num_tracker else f"P{tid%100}"
            players_court.append((tid, stable, cx, cy, label))
            alive_tids_set.add(tid)
            # 軌跡更新
            if tid not in player_trails:
                player_trails[tid] = (stable, deque(maxlen=TRAIL_LEN))
            _, trail_dq = player_trails[tid]
            player_trails[tid] = (stable, trail_dq)
            trail_dq.append((cx, cy))

        # シュートに発射時点のチームを付与 (ハンドラー情報を利用)
        if fi in shot_fi:
            sidx, s = shot_fi[fi]
            for p_tid, p_team, _, _, _ in players_court:
                if p_tid == handler_tid:
                    s = dict(s); s["team"] = p_team
                    shot_fi[fi] = (sidx, s)
                    break

        ball_court = None
        if pos_sam3:
            bx_c, by_c = img_to_court(H_inv, pos_sam3[0], pos_sam3[1])
            if is_on_court(bx_c, by_c):
                ball_court = (bx_c, by_c)

        # ── サイドバー ─────────────────────────────────────────────
        cur_idx = active_shots[-1][1] if active_shots else None
        sidebar = make_sidebar(H_px, players_court, player_trails, ball_court,
                               handler_tid, shown_shots, cur_idx,
                               num_tracker=num_tracker)
        canvas[:, W:] = sidebar
        cv2.line(canvas,(W,0),(W,H_px),(60,60,60),2)

        # ── HUD ─────────────────────────────────────────────────────────
        ts=fi/fps; mm=int(ts//60); ss_=int(ts%60)
        hud = f"t={mm}:{ss_:02d}  players={len(tracks)}  shots={len(shown_shots)}"
        cv2.putText(canvas,hud,(8,18),cv2.FONT_HERSHEY_SIMPLEX,0.42,(0,0,0),3)
        cv2.putText(canvas,hud,(8,18),cv2.FONT_HERSHEY_SIMPLEX,0.42,(210,210,210),1)

        # 凡例
        legend = [(TEAM_BGR[1],"White"),(TEAM_BGR[2],"Navy"),
                  ((0,220,255),"Ball"),((0,80,255),"Goal"),
                  ((0,220,60),"MADE"),((60,60,255),"MISS")]
        for yi,(col,txt) in enumerate(legend):
            cv2.circle(canvas,(8,H_px-14-yi*15),4,col,-1)
            cv2.putText(canvas,txt,(16,H_px-10-yi*15),
                        cv2.FONT_HERSHEY_SIMPLEX,0.28,(180,180,180),1)

        writer.write(canvas)
        if fi % int(fps*5) == 0:
            print(f"  {fi}/{max_fi}  t={ts:.0f}s  players={len(tracks)}"
                  f"  shots={len(shown_shots)}")

    cap.release()
    writer.release()

    subprocess.run(["ffmpeg","-y","-i",out_tmp,
                    "-vcodec","libx264","-pix_fmt","yuv420p",
                    "-crf","20","-movflags","+faststart",out_fin],
                   capture_output=True)
    Path(out_tmp).unlink(missing_ok=True)

    # 背番号サマリー
    if num_tracker:
        print("\n背番号認識結果:")
        for tid, num in sorted(num_tracker.summary().items()):
            print(f"  Tracking ID {tid:3d} → #{num}")

    size = Path(out_fin).stat().st_size/1e6
    print(f"\nDone: {out_fin}  ({size:.1f}MB)")


if __name__ == "__main__":
    main()

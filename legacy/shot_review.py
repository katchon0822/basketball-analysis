"""
シュート評価ツール — アノテーター風インタラクティブUI

【操作】
  A / ←        前のシュートへ
  D / →        次のシュートへ
  1 ~ 9        その番号のシュートへジャンプ（1始まり、2桁は連続入力）
  O            正しい (OK)  とマーク
  X            位置ずれ (Wrong position) とマーク
  F            誤検出 (False positive) とマーク
  S            評価を CSV に保存
  Q / Esc      終了

【出力】
  outputs/shot_review.csv   — 評価結果
"""

import cv2
import pandas as pd
import numpy as np
import json
import pickle
import os

VIDEO        = "data/videos/game_EE1swQMsXJc_720p.mp4"
CSV          = "outputs/shots_v2.csv"
REVIEW       = "outputs/shot_review.csv"
HOMOGRAPHY_J = "outputs/homography/homography.json"
STUBS        = "outputs/hsv_only/stubs/hsv_tracks_v18.pkl"

CHART_W, CHART_H = 600, 560   # 左パネル: コート図
VIDEO_W, VIDEO_H = 720, 405   # 右パネル: ビデオ (16:9)
WIN_W = CHART_W + VIDEO_W
WIN_H = max(CHART_H, VIDEO_H) + 60  # 下部ステータスバー

TEAM_MAP   = {'白': 'White', '紺': 'Navy', '不明': 'Unknown'}
TEAM_COLOR = {'White': (220,120,30), 'Navy': (180,60,0), 'Unknown': (150,150,150)}
STATUS_COLOR = {'ok': (0,180,0), 'wrong_pos': (0,120,255), 'false_pos': (0,0,220), '': (80,80,80)}
STATUS_LABEL = {'ok': 'OK', 'wrong_pos': 'WRONG POS', 'false_pos': 'FALSE POS', '': '--'}

# ── コート描定数（NBA座標 → チャートピクセル）──────────────────
# NBA: x∈[-260,260]  y∈[-60,435]
NX0, NX1 = -260.0, 260.0
NY0, NY1 = -60.0, 435.0
PAD_L, PAD_T = 30, 30

def court2px(nx, ny):
    px = int(PAD_L + (nx - NX0) / (NX1 - NX0) * (CHART_W - PAD_L*2))
    py = int(PAD_T + (1.0 - (ny - NY0) / (NY1 - NY0)) * (CHART_H - PAD_T*2))
    return px, py

def draw_court(canvas):
    lw = 1
    col = (80, 80, 80)

    def line(p1, p2): cv2.line(canvas, court2px(*p1), court2px(*p2), col, lw)
    def rect(x0, y0, w, h):
        cv2.rectangle(canvas, court2px(x0, y0), court2px(x0+w, y0+h), col, lw)
    def arc_cv(cx, cy, rx, ry, a1, a2):
        axes = (int(rx/(NX1-NX0)*(CHART_W-PAD_L*2)),
                int(ry/(NY1-NY0)*(CHART_H-PAD_T*2)))
        cv2.ellipse(canvas, court2px(cx, cy), axes, 0, -a2, -a1, col, lw)

    # 外枠
    rect(-250, -47.5, 500, 470)
    # ペイント
    rect(-80, -47.5, 160, 190)
    rect(-60, -47.5, 120, 190)
    # フリースロー円
    arc_cv(0, 142.5, 60, 60, 0, 180)
    arc_cv(0, 142.5, 60, 60, 180, 360)
    # ゴール
    cv2.circle(canvas, court2px(0, 0), max(2, int(7.5/(NX1-NX0)*(CHART_W-PAD_L*2))),
               col, lw)
    # バックボード
    line((-30, -7.5), (30, -7.5))
    # 3Pライン
    line((-220, -47.5), (-220, 92.5))
    line(( 220, -47.5), ( 220, 92.5))
    arc_cv(0, 0, 237.5, 237.5, 22, 158)
    # センター境界
    line((-250, 422.5), (250, 422.5))
    arc_cv(0, 422.5, 60, 60, 180, 360)

# ── ホモグラフィー読み込み（FIBA cm → pixel 逆変換用）─────────
with open(HOMOGRAPHY_J) as f:
    _hraw = json.load(f)

# フレーム名からタイムスタンプ（秒）を取得
def _fname_to_sec(fname):
    base = os.path.splitext(fname)[0]         # e.g. frame_0026s
    return int(base.split('_')[-1].rstrip('s'))

_h_entries = sorted(
    [(_fname_to_sec(k), np.linalg.inv(np.array(v))) for k, v in _hraw.items()],
    key=lambda x: x[0]
)

def get_H_inv(ts_sec):
    """タイムスタンプに最近傍のH逆行列を返す（FIBA cm → pixel）"""
    best = min(_h_entries, key=lambda x: abs(x[0] - ts_sec))
    return best[1]

def fiba_to_px(H_inv, cx, cy):
    """FIBA cm座標 → ビデオピクセル座標"""
    pt = cv2.perspectiveTransform(np.float32([[[cx, cy]]]), H_inv)
    return int(pt[0][0][0]), int(pt[0][0][1])

# FIBA コートライン定義（始点・終点のペアリスト）
COURT_LINES_FIBA = [
    # エンドライン
    [(-750, 0), (750, 0)],
    # サイドライン
    [(-750, 0), (-750, 1400)],
    [(750, 0), (750, 1400)],
    # センターライン
    [(-750, 1400), (750, 1400)],
    # フリースローライン
    [(-245, 580), (245, 580)],
    # レーン縦線
    [(-245, 0), (-245, 580)],
    [(245, 0), (245, 580)],
    # フリースロー横（サイドライン延長）
    [(-750, 580), (-245, 580)],
    [(245, 580), (750, 580)],
]
# フリースローサークル（近似: 折れ線）
def fiba_circle_pts(cx, cy, r, n=32):
    return [(cx + r*np.cos(2*np.pi*i/n), cy + r*np.sin(2*np.pi*i/n)) for i in range(n+1)]

FREETHROW_CIRCLE = fiba_circle_pts(0, 580, 180)   # 半径180cm

def draw_court_overlay(frame, H_inv, alpha=0.7):
    """ビデオフレームにFIBAコートラインをオーバーレイ"""
    overlay = frame.copy()
    col = (0, 255, 180)
    lw = 2

    for line in COURT_LINES_FIBA:
        pts = []
        for cx, cy in line:
            px, py = fiba_to_px(H_inv, cx, cy)
            pts.append((px, py))
        # フレーム外の点を含む線は描かない
        valid = all(-200 <= p[0] <= 1479 and -200 <= p[1] <= 919 for p in pts)
        if valid:
            cv2.line(overlay, pts[0], pts[1], col, lw, cv2.LINE_AA)

    # フリースローサークル
    circle_pts = FREETHROW_CIRCLE
    for i in range(len(circle_pts) - 1):
        p1 = fiba_to_px(H_inv, *circle_pts[i])
        p2 = fiba_to_px(H_inv, *circle_pts[i+1])
        if all(-200 <= p[0] <= 1479 and -200 <= p[1] <= 919 for p in [p1, p2]):
            cv2.line(overlay, p1, p2, col, lw, cv2.LINE_AA)

    # バスケット位置
    bx, by = fiba_to_px(H_inv, 0, 157)
    if 0 <= bx <= 1279 and 0 <= by <= 719:
        cv2.circle(overlay, (bx, by), 10, (0, 100, 255), 2, cv2.LINE_AA)
        cv2.circle(overlay, (bx, by), 3,  (0, 100, 255), -1)

    return cv2.addWeighted(overlay, alpha, frame, 1-alpha, 0)


# ── バックボード検出位置の読み込み ────────────────────────────
with open(STUBS, 'rb') as f:
    _stubs = pickle.load(f)
_goal_px_list = _stubs['goal_px']   # [frame] ((lx,ly),(rx,ry))

def get_goal_px(ts_sec):
    fc = min(int(ts_sec * 29.97), len(_goal_px_list) - 1)
    return _goal_px_list[fc]        # ((lx,ly) or None, (rx,ry) or None)

# ── データ読み込み ──────────────────────────────────────────────
df = pd.read_csv(CSV)
df['made'] = df['made'].astype(str).str.strip().str.lower().isin(['true','1','yes'])
df['team_en'] = df['team'].map(TEAM_MAP).fillna('Unknown')
shots = df.to_dict('records')
n_shots = len(shots)

# 評価状態を読み込み or 初期化
review = {}
if os.path.exists(REVIEW):
    rv = pd.read_csv(REVIEW)
    review = dict(zip(rv['No'].astype(int), rv['status'].fillna('')))

# ── ビデオ ──────────────────────────────────────────────────────
cap = cv2.VideoCapture(VIDEO)
fps = cap.get(cv2.CAP_PROP_FPS)

def get_frame(ts, with_overlay=True, rim_px=None):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(ts * fps))
    ret, f = cap.read()
    if not ret:
        f = np.zeros((720, 1280, 3), dtype=np.uint8)
    if with_overlay:
        H_inv = get_H_inv(ts)
        f = draw_court_overlay(f, H_inv, alpha=0.75)

    # ── バックボード検出位置を描画 (cyan=L, yellow=R) ──
    lp, rp = get_goal_px(ts)
    for side_pt, label, col in [(lp, 'L', (0,255,255)), (rp, 'R', (255,180,0))]:
        if side_pt is not None:
            gx, gy = int(side_pt[0]), int(side_pt[1])
            if 0 <= gx < f.shape[1] and 0 <= gy < f.shape[0]:
                cv2.circle(f, (gx, gy), 14, col, 2, cv2.LINE_AA)
                cv2.circle(f, (gx, gy), 3,  col, -1)
                cv2.putText(f, f'BB-{label}', (gx + 16, gy - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1, cv2.LINE_AA)

    # ── ターゲットバスケット (green) を強調表示 ──
    if rim_px is not None:
        rx, ry = int(rim_px[0]), int(rim_px[1])
        if 0 <= rx < f.shape[1] and 0 <= ry < f.shape[0]:
            cv2.circle(f, (rx, ry), 26, (0, 255, 0), 3, cv2.LINE_AA)
            cv2.circle(f, (rx, ry), 5,  (0, 255, 0), -1)
            cv2.putText(f, 'TARGET', (rx + 30, ry + 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
    return f

def save_review():
    rows = [{'No': no, 'status': st} for no, st in review.items()]
    pd.DataFrame(rows).sort_values('No').to_csv(REVIEW, index=False)
    print(f"Saved: {REVIEW}")

    # F(false_pos) を除いたクリーンな shots CSV を出力
    rv_map = {r['No']: r['status'] for r in rows}
    clean = df[df['No'].apply(lambda n: rv_map.get(int(n), '') != 'false_pos')].copy()
    clean_path = CSV.replace('.csv', '_clean.csv')
    clean.to_csv(clean_path, index=False)
    n_removed = len(df) - len(clean)
    print(f"Clean CSV ({len(clean)} shots, {n_removed} false_pos removed): {clean_path}")

# ── 描画 ──────────────────────────────────────────────────────
def render(shot_idx):
    s     = shots[shot_idx]
    no    = int(s['No'])
    team  = s['team_en']
    made  = bool(s['made'])
    ts    = float(s['timestamp'])
    zone  = str(s.get('zone', ''))

    canvas = np.full((WIN_H, WIN_W, 3), 28, dtype=np.uint8)

    # ── 左: コート ──
    court_bg = np.full((CHART_H, CHART_W, 3), 42, dtype=np.uint8)
    draw_court(court_bg)

    for i, sh in enumerate(shots):
        nx, ny = float(sh['nba_x']), float(sh['nba_y'])
        px, py = court2px(nx, ny)
        tc  = TEAM_COLOR.get(sh['team_en'], (150,150,150))
        sno = int(sh['No'])
        is_cur = (i == shot_idx)

        sh_st = review.get(sno, '')
        is_fp = sh_st == 'false_pos'

        if is_cur:
            cv2.circle(court_bg, (px, py), 14, (255,255,255), -1)
            cv2.circle(court_bg, (px, py), 12, tc, -1)
            marker = 'O' if sh['made'] else 'X'
            cv2.putText(court_bg, marker, (px-5, py+5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,255), 1, cv2.LINE_AA)
        else:
            r = 8 if sh['made'] else 6
            col_dot = (60, 60, 60) if is_fp else tc
            cv2.circle(court_bg, (px, py), r, col_dot, -1 if sh['made'] else 1)
            if is_fp:  # 取り消し線（×）
                cv2.line(court_bg, (px-8, py-8), (px+8, py+8), (0,0,200), 2)
                cv2.line(court_bg, (px+8, py-8), (px-8, py+8), (0,0,200), 2)

        # 番号ラベル
        color_no = (255,255,0) if is_cur else ((100,100,100) if is_fp else (200,200,200))
        cv2.putText(court_bg, str(sno), (px+8, py-4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3 if not is_cur else 0.38,
                    color_no, 1, cv2.LINE_AA)

    # 評価マーク
    st = review.get(no, '')
    if st:
        sc = STATUS_COLOR[st]
        cv2.putText(court_bg, STATUS_LABEL[st],
                    court2px(float(s['nba_x']) + 12, float(s['nba_y']) + 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, sc, 1, cv2.LINE_AA)

    canvas[:CHART_H, :CHART_W] = court_bg

    # ── 右: ビデオフレーム ──
    rim_px = None
    if 'rim_px_x' in s and pd.notna(s.get('rim_px_x')):
        rim_px = (float(s['rim_px_x']), float(s['rim_px_y']))
    frame = get_frame(ts, rim_px=rim_px)
    frame_r = cv2.resize(frame, (VIDEO_W, VIDEO_H))
    canvas[:VIDEO_H, CHART_W:CHART_W+VIDEO_W] = frame_r

    # フレーム右上: チーム・ゾーン・made
    info_bg = np.full((22, VIDEO_W, 3), 20, dtype=np.uint8)
    info_txt = (f"#{no}  t={s['time']}  {team}  {zone}"
                f"  {'MADE' if made else 'miss'}")
    cv2.putText(info_bg, info_txt, (6, 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                (0,200,0) if made else (80,80,255), 1, cv2.LINE_AA)
    canvas[VIDEO_H:VIDEO_H+22, CHART_W:CHART_W+VIDEO_W] = info_bg

    # ── 下部ステータスバー ──
    bar_y = WIN_H - 38
    cv2.rectangle(canvas, (0, bar_y), (WIN_W, WIN_H), (20,20,20), -1)

    # 現在の評価状態
    st_col = STATUS_COLOR.get(st, (80,80,80))
    cv2.putText(canvas, f"Status: [{STATUS_LABEL[st]}]",
                (6, bar_y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, st_col, 1)

    # キー操作ガイド
    guide = ("O=OK  X=WrongPos  F=FalsePos  | A/D=prev/next  S=save  Q=quit"
             f"  [{shot_idx+1}/{n_shots}]")
    cv2.putText(canvas, guide, (6, bar_y + 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (180,180,180), 1)

    # 進捗バー
    bar_w = WIN_W - 12
    bar_filled = int(bar_w * (shot_idx + 1) / n_shots)
    cv2.rectangle(canvas, (6, bar_y - 6), (6 + bar_w, bar_y - 2), (50,50,50), -1)
    cv2.rectangle(canvas, (6, bar_y - 6), (6 + bar_filled, bar_y - 2), (80,180,80), -1)

    return canvas

# ── メインループ ─────────────────────────────────────────────
WIN = "Shot Review"
cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
cv2.resizeWindow(WIN, WIN_W, WIN_H)

idx        = 0
num_buf    = ""   # 数字ジャンプ用バッファ

def on_mouse(event, x, y, flags, param):
    global idx
    if event != cv2.EVENT_LBUTTONDOWN:
        return
    # コート上クリックで近いシュートを選択
    if x < CHART_W:
        best_d, best_i = 1e9, idx
        for i, sh in enumerate(shots):
            px, py = court2px(float(sh['nba_x']), float(sh['nba_y']))
            d = (px - x)**2 + (py - y)**2
            if d < best_d:
                best_d, best_i = d, i
        if best_d < 400:   # 20px以内
            idx = best_i

cv2.setMouseCallback(WIN, on_mouse)

while True:
    cv2.imshow(WIN, render(idx))
    raw = cv2.waitKey(30)
    if raw == -1:
        continue
    key = raw & 0xFF

    no = int(shots[idx]['No'])

    if key in (ord('q'), 27):
        save_review()
        break
    elif key in (ord('d'), 83):          # 次
        num_buf = ""
        idx = (idx + 1) % n_shots
    elif key in (ord('a'), 81):          # 前
        num_buf = ""
        idx = (idx - 1) % n_shots
    elif key == ord('o'):                # OK
        review[no] = 'ok'
        idx = (idx + 1) % n_shots
    elif key == ord('x'):                # Wrong position
        review[no] = 'wrong_pos'
        idx = (idx + 1) % n_shots
    elif key == ord('f'):                # False positive
        review[no] = 'false_pos'
        idx = (idx + 1) % n_shots
    elif key == ord('s'):
        save_review()
    elif ord('0') <= key <= ord('9'):    # 番号ジャンプ
        num_buf += chr(key)
        target = int(num_buf)
        matches = [i for i, sh in enumerate(shots) if int(sh['No']) == target]
        if matches:
            idx = matches[0]
            num_buf = ""
        elif len(num_buf) >= 2:
            num_buf = ""

cap.release()
cv2.destroyAllWindows()
print("Done.")

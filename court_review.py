"""
コート検知レビュー & アノテーションツール

【レビューモード】
  D / →       +1秒進む
  A / ←       -1秒戻る
  F            +10秒スキップ
  B            -10秒スキップ
  E            このフレームをアノテーション（修正）モードへ
  Q / Esc      終了

【アノテーションモード】（E で起動）
  左クリック   表示中のキーポイントを確定
  N / Space    このキーポイントをスキップ（見えない場合）
  Backspace    直前のキーポイントを取り消し
  ホイール     ズームイン / アウト
  R            ズームリセット
  S / Enter    保存 → ホモグラフィー再計算 → レビューに戻る
  Esc          キャンセルしてレビューに戻る
"""

import cv2
import json
import numpy as np
import os
import subprocess
import sys

VIDEO        = "data/videos/game_EE1swQMsXJc_720p.mp4"
HOMOGRAPHY_J = "outputs/homography/homography.json"
ANNOT_JSON   = "outputs/annotations.json"
FRAME_DIR    = "outputs/annotation_frames"
os.makedirs(FRAME_DIR, exist_ok=True)

DISPLAY_W = 1280
DISPLAY_H = 720

# ── FIBA キーポイント定義 ────────────────────────────────────────
KEYPOINTS = [
    ("end_near_side",  "Endline x Near sideline",   +750,    0),
    ("end_far_side",   "Endline x Far sideline",     -750,    0),
    ("end_near_lane",  "Endline x Near lane",        +245,    0),
    ("end_far_lane",   "Endline x Far lane",         -245,    0),
    ("ft_near_lane",   "FreethrowLine x Near lane",  +245,  580),
    ("ft_far_lane",    "FreethrowLine x Far lane",   -245,  580),
    ("ft_near_side",   "FreethrowLine x Near side",  +750,  580),
    ("ft_far_side",    "FreethrowLine x Far side",   -750,  580),
    ("center_near",    "Centerline x Near side",     +750, 1400),
    ("center_far",     "Centerline x Far side",      -750, 1400),
]
KP_COLORS = [
    (0,220,0),(0,180,255),(255,160,0),(200,0,255),
    (0,220,220),(255,100,0),(100,255,0),(255,0,100),
    (80,80,255),(255,255,0),
]

# ── ホモグラフィー読み込み ────────────────────────────────────────
def load_homography():
    with open(HOMOGRAPHY_J) as f:
        raw = json.load(f)
    def _ts(fname):
        return int(os.path.splitext(fname)[0].split('_')[-1].rstrip('s'))
    entries = sorted(
        [(_ts(k), np.linalg.inv(np.array(v))) for k, v in raw.items()],
        key=lambda x: x[0]
    )
    return entries, [t for t, _ in entries]

_h_entries, ANNOT_TIMES = load_homography()

def get_H_inv(ts):
    best = min(_h_entries, key=lambda x: abs(x[0] - ts))
    return best[1], best[0]

def fiba_to_px(H_inv, cx, cy):
    pt = cv2.perspectiveTransform(np.float32([[[cx, cy]]]), H_inv)
    return int(pt[0][0][0]), int(pt[0][0][1])

# ── コートオーバーレイ ────────────────────────────────────────────
COURT_LINES = [
    [(-750,0),(750,0)], [(-750,0),(-750,1400)], [(750,0),(750,1400)],
    [(-750,1400),(750,1400)], [(-245,580),(245,580)],
    [(-245,0),(-245,580)], [(245,0),(245,580)],
    [(-750,580),(-245,580)], [(245,580),(750,580)],
]
FT_CIRCLE = [(180*np.cos(2*np.pi*i/32), 580+180*np.sin(2*np.pi*i/32)) for i in range(33)]

def draw_overlay(frame, H_inv):
    ov = frame.copy()
    col = (0, 255, 180)
    for seg in COURT_LINES:
        pts = [fiba_to_px(H_inv, cx, cy) for cx, cy in seg]
        if all(-200 <= p[0] <= 1479 and -200 <= p[1] <= 919 for p in pts):
            cv2.line(ov, pts[0], pts[1], col, 2, cv2.LINE_AA)
    for i in range(len(FT_CIRCLE)-1):
        p1 = fiba_to_px(H_inv, *FT_CIRCLE[i])
        p2 = fiba_to_px(H_inv, *FT_CIRCLE[i+1])
        if all(-200 <= p[0] <= 1479 and -200 <= p[1] <= 919 for p in [p1, p2]):
            cv2.line(ov, p1, p2, col, 2, cv2.LINE_AA)
    bx, by = fiba_to_px(H_inv, 0, 157)
    if 0 <= bx <= 1279 and 0 <= by <= 719:
        cv2.circle(ov, (bx, by), 12, (0,80,255), 2, cv2.LINE_AA)
        cv2.circle(ov, (bx, by), 4, (0,80,255), -1)
    return cv2.addWeighted(ov, 0.75, frame, 0.25, 0)

# ── ビデオ ────────────────────────────────────────────────────────
cap = cv2.VideoCapture(VIDEO)
FPS      = cap.get(cv2.CAP_PROP_FPS)
N_FRAMES = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
DURATION = N_FRAMES / FPS

def read_frame(ts):
    fc = max(0, min(int(ts * FPS), N_FRAMES - 1))
    cap.set(cv2.CAP_PROP_POS_FRAMES, fc)
    ret, f = cap.read()
    return f if ret else np.zeros((720, 1280, 3), dtype=np.uint8)

# ── 情報バー描画ヘルパー ──────────────────────────────────────────
def make_info_bar(ts, annot_t, mode_label, extra=""):
    bar = np.full((80, DISPLAY_W, 3), 18, dtype=np.uint8)
    mm, ss = int(ts//60), int(ts%60)
    diff = abs(ts - annot_t)
    diff_col = (0,200,0) if diff<=5 else (0,140,255) if diff<=15 else (0,60,220)

    # 行1: タイムスタンプ + モード
    cv2.putText(bar, f"t = {mm:02d}:{ss:02d}  ({ts:.1f}s)   [{mode_label}]  {extra}",
                (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (220,220,220), 1)
    # 行2: H行列情報
    cv2.putText(bar, f"H from t={annot_t:.0f}s  (diff={diff:.1f}s)   "
                     f"Annotated: {' '.join(str(t)+'s' for t in ANNOT_TIMES)}",
                (8, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.42, diff_col, 1)
    # 行3: 操作説明
    if mode_label == "REVIEW":
        guide = "D/→=+1s  A/←=-1s  F=+10s  B=-10s  E=annotate this frame  Q=quit"
    else:
        guide = ("Click=set KP  N=skip  BS=undo  Wheel=zoom  "
                 "R=reset  V=overlay on/off  S/Enter=save+recompute  Esc=cancel")
    cv2.putText(bar, guide, (8, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (140,200,140), 1)
    return bar

# ════════════════════════════════════════════════════════════════════
# レビューモード
# ════════════════════════════════════════════════════════════════════
def run_review():
    global _h_entries, ANNOT_TIMES

    cur_ts = 0.0
    WIN = "Court Review & Annotator"
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN, DISPLAY_W, DISPLAY_H + 80)

    while True:
        raw_frame = read_frame(cur_ts)
        H_inv, annot_t = get_H_inv(cur_ts)
        overlaid = draw_overlay(raw_frame, H_inv)
        overlaid_disp = cv2.resize(overlaid, (DISPLAY_W, DISPLAY_H))

        bar = make_info_bar(cur_ts, annot_t, "REVIEW")
        img = np.vstack([overlaid_disp, bar])
        cv2.imshow(WIN, img)

        key = cv2.waitKey(30) & 0xFF
        if key in (ord('q'), 27):
            break
        elif key in (ord('d'), 83):
            cur_ts = min(cur_ts + 1.0, DURATION - 1)
        elif key in (ord('a'), 81):
            cur_ts = max(cur_ts - 1.0, 0.0)
        elif key == ord('f'):
            cur_ts = min(cur_ts + 10.0, DURATION - 1)
        elif key == ord('b'):
            cur_ts = max(cur_ts - 10.0, 0.0)
        elif key == ord('e'):
            # アノテーションモードへ
            result = run_annotate(cur_ts, raw_frame, WIN)
            if result:
                # ホモグラフィー再計算 → 再読み込み
                print("Recomputing homography...")
                subprocess.run([sys.executable, "compute_homography.py"], check=False)
                _h_entries, ANNOT_TIMES = load_homography()
                print(f"Reloaded. Annotations: {ANNOT_TIMES}")

    cap.release()
    cv2.destroyAllWindows()
    print("Done.")


# ════════════════════════════════════════════════════════════════════
# アノテーションモード
# ════════════════════════════════════════════════════════════════════
def run_annotate(ts, raw_frame, win_name):
    """
    クリックでキーポイントをアノテーション。
    Returns True if saved, False if cancelled.
    """
    # フレームキー: frame_0045s.jpg 形式
    frame_key = f"frame_{int(round(ts)):04d}s.jpg"
    frame_path = os.path.join(FRAME_DIR, frame_key)

    # フレーム画像を保存（annotator.py と共有）
    cv2.imwrite(frame_path, raw_frame)

    # 既存アノテーション読み込み
    if os.path.exists(ANNOT_JSON):
        with open(ANNOT_JSON) as f:
            annotations = json.load(f)
    else:
        annotations = {}

    if frame_key not in annotations or annotations[frame_key] == "__skipped__":
        annotations[frame_key] = []

    # ── アノテーションモード状態 ──
    zoom    = 1.0
    zoom_cx = raw_frame.shape[1] // 2
    zoom_cy = raw_frame.shape[0] // 2
    cursor  = [DISPLAY_W // 2, DISPLAY_H // 2]
    scale   = DISPLAY_W / raw_frame.shape[1]

    def img_to_disp(x, y):
        dx = (x * scale - zoom_cx) * zoom + DISPLAY_W / 2
        dy = (y * scale - zoom_cy) * zoom + DISPLAY_H / 2
        return int(dx), int(dy)

    def disp_to_img(dx, dy):
        x = ((dx - DISPLAY_W / 2) / zoom + zoom_cx) / scale
        y = ((dy - DISPLAY_H / 2) / zoom + zoom_cy) / scale
        return int(x), int(y)

    def next_kp():
        done = {a['id'] for a in annotations[frame_key]}
        for i, (kid, *_) in enumerate(KEYPOINTS):
            if kid not in done:
                return i
        return len(KEYPOINTS)

    def save():
        with open(ANNOT_JSON, 'w') as f:
            json.dump(annotations, f, indent=2, ensure_ascii=False)
        print(f"Saved annotations for {frame_key}")

    def on_mouse(event, x, y, flags, param):
        nonlocal zoom, zoom_cx, zoom_cy
        # vis は y=0 から始まる（バーのオフセットなし）
        cursor[0], cursor[1] = x, y

        if event == cv2.EVENT_LBUTTONDOWN:
            ki = next_kp()
            if ki >= len(KEYPOINTS):
                return
            kid, kdesc, kcx, kcy = KEYPOINTS[ki]
            ox, oy = disp_to_img(x, y)
            annotations[frame_key].append({'id': kid, 'img': [ox, oy], 'court': [kcx, kcy]})
            save()
            print(f"  KP [{kid}] img=({ox},{oy})")

        elif event == cv2.EVENT_MOUSEWHEEL:
            # ズーム前にカーソル位置の画像座標を確定してからズーム倍率を更新
            ox, oy = disp_to_img(x, y)
            new_zoom = max(1.0, min(8.0, zoom + (0.3 if flags > 0 else -0.3)))
            # カーソル位置が画面上で動かないようにズーム中心を調整
            zoom_cx = ox * scale - (x - DISPLAY_W / 2) / new_zoom
            zoom_cy = oy * scale - (y - DISPLAY_H / 2) / new_zoom
            zoom = new_zoom

    cv2.setMouseCallback(win_name, on_mouse)

    H_inv, annot_t = get_H_inv(ts)
    img_scaled = cv2.resize(raw_frame, (DISPLAY_W, int(raw_frame.shape[0] * scale)))
    show_overlay = True   # V キーでトグル

    def draw_kp_diagram(ki_active):
        """
        アノテーション用 FIBA コート図
          ・現在クリックすべき交点を大きく強調
          ・Near(手前)/ Far(奥) / Basket 方向ラベル付き
        """
        dw, dh = 240, 220
        diag = np.full((dh, dw, 3), 22, dtype=np.uint8)
        mg_l, mg_r, mg_t, mg_b = 30, 10, 22, 28

        def kp_to_d(cx, cy):
            px = int(mg_l + (cx + 750) / 1500 * (dw - mg_l - mg_r))
            py = int(mg_t + (1400 - cy) / 1400 * (dh - mg_t - mg_b))
            return px, py

        # コートライン
        lc = (70, 70, 70)
        for seg in COURT_LINES:
            cv2.line(diag, kp_to_d(*seg[0]), kp_to_d(*seg[1]), lc, 1)
        bx, by = kp_to_d(0, 157)
        cv2.circle(diag, (bx, by), 3, (0, 80, 255), -1)

        # 方向ラベル
        # 上 = センターライン側 (Far from basket)
        cv2.putText(diag, "Center", (dw//2-18, 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, (140,140,140), 1)
        # 下 = エンドライン側 (basket side)
        cv2.putText(diag, "Basket end", (dw//2-24, dh-6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, (0,80,255), 1)
        # 左 = Far side (-750)
        cv2.putText(diag, "Far", (2, dh//2+4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (140,140,140), 1)
        # 右 = Near side (+750)
        cv2.putText(diag, "Near", (dw-28, dh//2+4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (140,140,140), 1)

        # キーポイント
        for i, (kid, _, kcx, kcy) in enumerate(KEYPOINTS):
            px, py = kp_to_d(kcx, kcy)
            col = KP_COLORS[i % len(KP_COLORS)]
            if i == ki_active:
                cv2.circle(diag, (px, py), 9, col, -1)
                cv2.circle(diag, (px, py), 10, (255,255,255), 2)
                cv2.putText(diag, str(i+1), (px+11, py+5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,255), 1)
            else:
                cv2.circle(diag, (px, py), 4, col, -1)
                cv2.putText(diag, str(i+1), (px+5, py+4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, col, 1)

        cv2.rectangle(diag, (0,0), (dw-1,dh-1), (120,120,120), 1)
        return diag

    while True:
        M = np.float32([
            [zoom, 0, DISPLAY_W/2 - zoom_cx*zoom],
            [0,    zoom, DISPLAY_H/2 - zoom_cy*zoom],
        ])
        # ベース画像（ズーム変換）
        vis = cv2.warpAffine(img_scaled, M, (DISPLAY_W, DISPLAY_H),
                             flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(40,40,40))

        # コートオーバーレイ（V でトグル）
        if show_overlay:
            ov_scaled = cv2.resize(draw_overlay(raw_frame, H_inv),
                                   (DISPLAY_W, int(raw_frame.shape[0] * scale)))
            ov_warped = cv2.warpAffine(ov_scaled, M, (DISPLAY_W, DISPLAY_H),
                                       flags=cv2.INTER_LINEAR,
                                       borderMode=cv2.BORDER_CONSTANT, borderValue=(40,40,40))
            vis = cv2.addWeighted(vis, 0.5, ov_warped, 0.5, 0)

        # 確定済みキーポイント
        for ann in annotations[frame_key]:
            if ann['img'] is None:
                continue
            dx, dy = img_to_disp(*ann['img'])
            i = next((j for j, (k,*_) in enumerate(KEYPOINTS) if k == ann['id']), 0)
            col = KP_COLORS[i % len(KP_COLORS)]
            cv2.circle(vis, (dx, dy), 8, col, -1)
            cv2.circle(vis, (dx, dy), 9, (255,255,255), 1)
            cv2.putText(vis, ann['id'].split('_')[0],
                        (dx+10, dy-6), cv2.FONT_HERSHEY_SIMPLEX, 0.38, col, 1)

        # 十字カーソル
        cv2.line(vis, (cursor[0], 0), (cursor[0], DISPLAY_H), (255,255,255), 1)
        cv2.line(vis, (0, cursor[1]), (DISPLAY_W, cursor[1]), (255,255,255), 1)

        # ルーペ（右下）
        ox_l, oy_l = disp_to_img(cursor[0], cursor[1])
        lupe_sz = 120
        lx0 = max(0, int(ox_l*scale) - lupe_sz//8)
        ly0 = max(0, int(oy_l*scale) - lupe_sz//8)
        lx1, ly1 = lx0 + lupe_sz//4, ly0 + lupe_sz//4
        if lx1 < img_scaled.shape[1] and ly1 < img_scaled.shape[0]:
            src = img_scaled[ly0:ly1, lx0:lx1]
            if src.size > 0:
                lupe = cv2.resize(src, (lupe_sz, lupe_sz), interpolation=cv2.INTER_NEAREST)
                cv2.rectangle(lupe, (lupe_sz//2-2, lupe_sz//2-2),
                              (lupe_sz//2+2, lupe_sz//2+2), (0,255,0), 1)
                vis[DISPLAY_H-lupe_sz-4:DISPLAY_H-4,
                    DISPLAY_W-lupe_sz-4:DISPLAY_W-4] = lupe

        # ── コート図（左下）──
        ki = next_kp()
        diag = draw_kp_diagram(ki)
        dh2, dw2 = diag.shape[:2]
        vis[DISPLAY_H-dh2-4:DISPLAY_H-4, 4:4+dw2] = diag

        # ── 現在KP情報をオーバーレイ（スタックしない → 座標ずれなし）──
        overlay_bar = vis[:40].copy()
        cv2.rectangle(vis, (0,0), (DISPLAY_W, 40), (25,25,25), -1)
        if ki < len(KEYPOINTS):
            kid, kdesc, kcx, kcy = KEYPOINTS[ki]
            col = KP_COLORS[ki % len(KP_COLORS)]
            cv2.putText(vis,
                        f"KP {ki+1}/{len(KEYPOINTS)}: {kdesc}  court({kcx},{kcy})cm",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
        else:
            cv2.putText(vis, "All KPs done!  Press S to save & recompute.",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

        bar = make_info_bar(ts, annot_t, "ANNOTATE",
                            f"zoom={zoom:.1f}x  {frame_key}  KP={ki}/{len(KEYPOINTS)}")
        # vis(720) + bar(80) をスタック → クリックは y=0-719 に対応
        img_out = np.vstack([vis, bar])
        cv2.imshow(win_name, img_out)

        key = cv2.waitKey(30) & 0xFF
        if key in (27,):                        # Esc → キャンセル
            cv2.setMouseCallback(win_name, lambda *a: None)
            return False

        elif key in (ord('s'), 13):             # S / Enter → 保存
            save()
            cv2.setMouseCallback(win_name, lambda *a: None)
            return True

        elif key in (ord('n'), ord(' ')):       # N → このKPをスキップ
            ki = next_kp()
            if ki < len(KEYPOINTS):
                kid, _, kcx, kcy = KEYPOINTS[ki]
                annotations[frame_key].append({'id': kid, 'img': None, 'court': [kcx, kcy]})
                save()
                print(f"  KP [{kid}] skipped")

        elif key in (8, 127):                   # Backspace → 直前削除
            if annotations[frame_key]:
                removed = annotations[frame_key].pop()
                save()
                print(f"  Removed KP [{removed['id']}]")

        elif key == ord('r'):                   # R → ズームリセット
            zoom = 1.0
            zoom_cx = raw_frame.shape[1] // 2
            zoom_cy = raw_frame.shape[0] // 2

        elif key == ord('v'):                   # V → オーバーレイ表示トグル
            show_overlay = not show_overlay


# ── エントリーポイント ────────────────────────────────────────────
if __name__ == "__main__":
    print(__doc__)
    print(f"Video: {DURATION:.1f}s  FPS:{FPS:.2f}")
    print(f"Annotation times: {ANNOT_TIMES}")
    run_review()

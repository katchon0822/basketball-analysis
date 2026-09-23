"""
Court keypoint annotator — 交点を直接クリックする高精度アノテーター

【起動】
    python3 annotator.py

【操作方法】
    左クリック        現在のキーポイントを確定
    N / Space         このキーポイントをスキップ（見えない場合）
    Backspace         直前の確定を取り消し
    S / D / →         次のフレームへ（自動保存）
    A / ←             前のフレームへ（自動保存）
    スクロールUp/Down  ズームイン/アウト
    Q / Esc           保存して終了

【アノテーション方針】
    各フレームで表示される「クリックすべき交点」を順番にクリックする。
    見えない・判別できない交点は N でスキップ。

【出力】
    outputs/annotations.json
    形式: {fname: [{id, img:[x,y], court:[cx,cy]}, ...]}
    court座標: FIBA半コート(cm)、原点=エンドライン中央

【詳細ドキュメント】
    docs/court_line_detection.md
"""

import cv2
import json
import os
import glob
import numpy as np

# ── 設定 ──────────────────────────────────────────
FRAME_DIR   = "outputs/annotation_frames"
OUTPUT_JSON = "outputs/annotations.json"
DISPLAY_W   = 1280

# ── FIBA 半コートキーポイント一覧 ──────────────────
# (id, 説明, court_x, court_y)
# court座標: x=±750(サイドライン), y=0(エンドライン)→1400(センター)
KEYPOINTS = [
    ("end_near_side",  "Endline x Near sideline corner",    +750,    0),
    ("end_far_side",   "Endline x Far sideline corner",     -750,    0),
    ("end_near_lane",  "Endline x Near lane corner",        +245,    0),
    ("end_far_lane",   "Endline x Far lane corner",         -245,    0),
    ("ft_near_lane",   "Freethrow x Near lane corner",      +245,  580),
    ("ft_far_lane",    "Freethrow x Far lane corner",       -245,  580),
    ("ft_near_side",   "Freethrow x Near sideline",         +750,  580),
    ("ft_far_side",    "Freethrow x Far sideline",          -750,  580),
    ("center_near",    "Centerline x Near sideline",        +750, 1400),
    ("center_far",     "Centerline x Far sideline",         -750, 1400),
]

KP_COLORS = [
    (0,  220,  0), (0,  180, 255), (255, 160,  0), (200,   0, 255),
    (0,  220,220), (255, 100,  0), (100, 255,  0), (255,   0, 100),
    (80,  80, 255), (255, 255,   0),
]

# ── グローバル状態 ─────────────────────────────────
frames       = sorted(glob.glob(os.path.join(FRAME_DIR, "*.jpg")))
frame_idx    = 0
kp_idx       = 0          # 現在確定しようとしているキーポイントのインデックス
annotations  = {}         # {fname: [{id, img, court}, ...] | "__skipped__"}
scale        = 1.0
zoom         = 1.0        # 追加ズーム倍率
zoom_cx      = 640        # ズーム中心 x
zoom_cy      = 360        # ズーム中心 y
cursor_x     = 0
cursor_y     = 0

if os.path.exists(OUTPUT_JSON):
    with open(OUTPUT_JSON) as f:
        annotations = json.load(f)
    print(f"Loaded: {OUTPUT_JSON}")


def get_fname():
    return os.path.basename(frames[frame_idx])


def save_json():
    with open(OUTPUT_JSON, 'w') as f:
        json.dump(annotations, f, indent=2, ensure_ascii=False)


def frame_anns():
    v = annotations.get(get_fname())
    return v if isinstance(v, list) else []


def frame_status(fname):
    v = annotations.get(fname)
    if v == "__skipped__":
        return "skip"
    if isinstance(v, list) and v:
        return "done"
    return "todo"


def next_kp_idx():
    """このフレームでまだ確定していないキーポイントの先頭インデックスを返す。"""
    done_ids = {a['id'] for a in frame_anns()}
    for i, (kid, *_) in enumerate(KEYPOINTS):
        if kid not in done_ids:
            return i
    return len(KEYPOINTS)   # 全完了


def img_to_display(x, y):
    """オリジナル座標 → 表示座標"""
    dx = (x * scale - zoom_cx) * zoom + DISPLAY_W / 2
    dy = (y * scale - zoom_cy) * zoom + 360
    return int(dx), int(dy)


def display_to_img(dx, dy):
    """表示座標 → オリジナル座標"""
    x = ((dx - DISPLAY_W / 2) / zoom + zoom_cx) / scale
    y = ((dy - 360) / zoom + zoom_cy) / scale
    return int(x), int(y)


def draw_frame(base_img):
    global kp_idx
    kp_idx = next_kp_idx()

    vis = base_img.copy()
    h, w = vis.shape[:2]
    fname = get_fname()

    # ── ズーム変換 ──
    M = np.float32([
        [zoom, 0, DISPLAY_W/2 - zoom_cx*zoom],
        [0, zoom, 360        - zoom_cy*zoom],
    ])
    vis = cv2.warpAffine(vis, M, (w, h), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(40,40,40))

    # ── 確定済みキーポイント ──
    for ann in frame_anns():
        kid = ann['id']
        if ann['img'] is None:
            continue
        ix, iy = ann['img']
        dx, dy = img_to_display(ix, iy)
        i = next((j for j, (k,*_) in enumerate(KEYPOINTS) if k == kid), 0)
        col = KP_COLORS[i % len(KP_COLORS)]
        cv2.circle(vis, (dx, dy), 8, col, -1)
        cv2.circle(vis, (dx, dy), 9, (255,255,255), 1)
        cx, cy = ann['court']
        cv2.putText(vis, f"{kid.split('_')[0]}({cx},{cy})",
                    (dx+10, dy-6), cv2.FONT_HERSHEY_SIMPLEX, 0.38, col, 1)

    # ── 十字カーソル ──
    cv2.line(vis, (cursor_x, 0), (cursor_x, h), (255,255,255,128), 1)
    cv2.line(vis, (0, cursor_y), (w, cursor_y), (255,255,255,128), 1)

    # ── 拡大ルーペ（右下） ──
    lupe_size = 120
    lupe_zoom = 4
    ox, oy = display_to_img(cursor_x, cursor_y)
    lx0 = max(0, int(ox*scale) - lupe_size//(lupe_zoom*2))
    ly0 = max(0, int(oy*scale) - lupe_size//(lupe_zoom*2))
    lx1 = lx0 + lupe_size // lupe_zoom
    ly1 = ly0 + lupe_size // lupe_zoom
    if lx1 <= base_img.shape[1] and ly1 <= base_img.shape[0]:
        lupe_src = base_img[ly0:ly1, lx0:lx1]
        if lupe_src.size > 0:
            lupe = cv2.resize(lupe_src, (lupe_size, lupe_size), interpolation=cv2.INTER_NEAREST)
            cv2.rectangle(lupe, (lupe_size//2-2, lupe_size//2-2),
                          (lupe_size//2+2, lupe_size//2+2), (0,255,0), 1)
            cv2.rectangle(vis, (w-lupe_size-4, h-lupe_size-32-4),
                          (w-4, h-32-4), (200,200,200), 1)
            vis[h-lupe_size-32-3:h-32-3, w-lupe_size-3:w-3] = lupe

    # ── ラベルバー（上部）──
    bar_h = 50
    cv2.rectangle(vis, (0, 0), (w, bar_h), (20, 20, 20), -1)

    # 現在のキーポイント表示
    if kp_idx < len(KEYPOINTS):
        kid, kdesc, kcx, kcy = KEYPOINTS[kp_idx]
        col = KP_COLORS[kp_idx % len(KP_COLORS)]
        cv2.rectangle(vis, (0, 0), (w, bar_h), (30, 30, 30), -1)
        cv2.putText(vis,
                    f"KP {kp_idx+1}/{len(KEYPOINTS)}: {kdesc}  -> court ({kcx}, {kcy}) cm",
                    (10, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.62, col, 2)
    else:
        cv2.putText(vis, "All KPs done! Press S to next frame.",
                    (10, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 255, 0), 2)

    # ── 進捗バー ──
    prog_y, prog_h = bar_h + 2, 10
    cell_w = max(1, w // len(frames))
    for i, fp in enumerate(frames):
        st = frame_status(os.path.basename(fp))
        col_bar = (60,200,60) if st=="done" else (60,60,180) if st=="skip" else (80,80,80)
        x0 = i * cell_w
        cv2.rectangle(vis, (x0, prog_y), (x0+cell_w-1, prog_y+prog_h), col_bar, -1)
    cx_ = frame_idx * cell_w
    cv2.rectangle(vis, (cx_, prog_y), (cx_+cell_w-1, prog_y+prog_h), (255,255,255), 1)

    # ── ステータスバー（下部）──
    n_done = sum(1 for fp in frames if frame_status(os.path.basename(fp)) == "done")
    n_skip = sum(1 for fp in frames if frame_status(os.path.basename(fp)) == "skip")
    n_kp   = len(frame_anns())
    status = (f" [{frame_idx+1}/{len(frames)}] {fname}"
              f"  KP={n_kp}/{len(KEYPOINTS)}"
              f"  done={n_done} skip={n_skip} todo={len(frames)-n_done-n_skip}"
              f"  zoom={zoom:.1f}x"
              f"  | Click=confirm  N=skip  BS=undo  S=next  X=skip-frame  Q=quit")
    cv2.rectangle(vis, (0, h-28), (w, h), (20, 20, 20), -1)
    cv2.putText(vis, status, (6, h-8), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (220,220,220), 1)

    return vis


def on_mouse(event, x, y, flags, param):
    global cursor_x, cursor_y, zoom_cx, zoom_cy, kp_idx, zoom

    cursor_x, cursor_y = x, y

    if event == cv2.EVENT_LBUTTONDOWN:
        if kp_idx >= len(KEYPOINTS):
            return
        kid, kdesc, kcx, kcy = KEYPOINTS[kp_idx]
        ox, oy = display_to_img(x, y)
        fname = get_fname()
        if fname not in annotations or annotations[fname] == "__skipped__":
            annotations[fname] = []
        annotations[fname].append({
            'id':    kid,
            'img':   [ox, oy],
            'court': [kcx, kcy],
        })
        save_json()
        print(f"  KP [{kid}] img=({ox},{oy}) court=({kcx},{kcy})")

    elif event == cv2.EVENT_MOUSEWHEEL:
        delta = 1 if flags > 0 else -1
        new_zoom = max(1.0, min(8.0, zoom + delta * 0.3))
        zoom_cx, zoom_cy = x, y   # ズーム中心をカーソル位置に
        zoom = new_zoom


def main():
    global frame_idx, kp_idx, scale, zoom, zoom_cx, zoom_cy

    if not frames:
        print(f"No frames in {FRAME_DIR}")
        return

    WIN = "Court KP Annotator"
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN, DISPLAY_W, 760)
    cv2.setMouseCallback(WIN, on_mouse)

    sample = cv2.imread(frames[0])
    if sample is not None:
        scale = DISPLAY_W / sample.shape[1]

    print(__doc__)
    print(f"Frames: {len(frames)}  KPs per frame: {len(KEYPOINTS)}  Output: {OUTPUT_JSON}")

    while True:
        img = cv2.imread(frames[frame_idx])
        if img is None:
            frame_idx = (frame_idx + 1) % len(frames)
            continue

        disp_h = int(img.shape[0] * scale)
        img_disp = cv2.resize(img, (DISPLAY_W, disp_h))
        cv2.imshow(WIN, draw_frame(img_disp))

        raw = cv2.waitKey(30)
        if raw == -1:
            continue
        key = raw & 0xFF

        if key in (ord('q'), 27):                     # Q / Esc → 終了
            save_json()
            break

        elif key in (ord('n'), ord(' ')):              # N / Space → KP スキップ
            if kp_idx < len(KEYPOINTS):
                kid = KEYPOINTS[kp_idx][0]
                fname = get_fname()
                if fname not in annotations or annotations[fname] == "__skipped__":
                    annotations[fname] = []
                annotations[fname].append({
                    'id':    kid,
                    'img':   None,
                    'court': list(KEYPOINTS[kp_idx][2:]),
                })
                save_json()
                print(f"  KP [{kid}] skipped")

        elif key in (8, 127):                          # Backspace → 直前削除
            fname = get_fname()
            ann_list = annotations.get(fname)
            if isinstance(ann_list, list) and ann_list:
                removed = ann_list.pop()
                save_json()
                print(f"  Removed KP [{removed['id']}]")

        elif key in (ord('s'), ord('d'), 83):          # S / D / → → 次フレーム
            save_json()
            zoom = 1.0
            frame_idx = (frame_idx + 1) % len(frames)

        elif key in (ord('a'), 81):                    # A / ← → 前フレーム
            save_json()
            zoom = 1.0
            frame_idx = (frame_idx - 1) % len(frames)

        elif key == ord('x'):                          # X → フレームスキップ
            fname = get_fname()
            annotations[fname] = "__skipped__"
            save_json()
            zoom = 1.0
            frame_idx = (frame_idx + 1) % len(frames)

        elif key == ord('r'):                          # R → ズームリセット
            zoom = 1.0
            zoom_cx, zoom_cy = DISPLAY_W // 2, 360

    cv2.destroyAllWindows()
    print("Done.")


if __name__ == "__main__":
    main()

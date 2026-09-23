#!/usr/bin/env python3
"""
calibrate.py — 会場×カメラ位置キャリブレーションツール

使い方:
    python calibrate.py --video data/videos/game.mp4 --venue 体育館A
    python calibrate.py --video data/videos/game.mp4 --venue 体育館A --fullcourt
    python calibrate.py --video data/videos/game.mp4 --load 体育館A

操作:
    右コート図でランドマーク番号をクリック → 選択
    左映像で対応する位置をクリック          → ペア登録
    ← →   : ±1秒移動
    A  D   : ±5秒移動
    Tab    : 次の未登録ランドマークへ
    U  BS  : 直前のペアを取り消し
    C      : 全ペアをクリア
    S  Enter: 保存して終了
    Q  Esc : 終了(保存なし)
"""

import cv2
import json
import numpy as np
import argparse
import sys
from pathlib import Path

# ── コート定数 (cm) ──────────────────────────────────────────────────────────
SIDELINE    = 750
HALF_Y      = 1432
FULL_Y      = HALF_Y * 2   # 2864
FT_Y        = 580
LANE_X      = 245
BASKET_Y    = 160
PT3_CX      = 665
PT3_CY      = 420
PT3_R       = 705

# ── ランドマーク定義 ─────────────────────────────────────────────────────────
# (id, 説明, court_x, court_y)
# y: 0=ニアエンドライン … HALF_Y=センター … FULL_Y=ファーエンドライン
_LM_NEAR = [
    ("end_ns",   "near endline × near sideline",    +750,    0),
    ("end_fs",   "near endline × far sideline",     -750,    0),
    ("end_nl",   "near endline × near lane",        +245,    0),
    ("end_fl",   "near endline × far lane",         -245,    0),
    ("ft_nl",    "FT line × near lane",             +245,  580),
    ("ft_fl",    "FT line × far lane",              -245,  580),
    ("ft_ns",    "FT line × near sideline",         +750,  580),
    ("ft_fs",    "FT line × far sideline",          -750,  580),
    ("3pt_nt",   "3PT straight top × near",         +665,  420),
    ("3pt_ft",   "3PT straight top × far",          -665,  420),
    ("ctr_ns",   "center line × near sideline",     +750, 1432),
    ("ctr_fs",   "center line × far sideline",      -750, 1432),
    ("ctr_mid",  "center line × mid",                  0, 1432),
    ("ctr_circ", "center circle near edge",             0, 1252),
    ("ring",     "near basket (ring center)",           0,  160),
]

_LM_FAR = [
    ("far_end_ns",  "far endline × near sideline",   +750, 2864),
    ("far_end_fs",  "far endline × far sideline",    -750, 2864),
    ("far_end_nl",  "far endline × near lane",       +245, 2864),
    ("far_end_fl",  "far endline × far lane",        -245, 2864),
    ("far_ft_nl",   "far FT × near lane",            +245, 2284),
    ("far_ft_fl",   "far FT × far lane",             -245, 2284),
    ("far_ft_ns",   "far FT × near sideline",        +750, 2284),
    ("far_ft_fs",   "far FT × far sideline",         -750, 2284),
    ("far_3pt_nt",  "far 3PT straight top × near",   +665, 2444),
    ("far_3pt_ft",  "far 3PT straight top × far",    -665, 2444),
    ("far_ring",    "far basket (ring center)",           0, 2704),
]

LM_HALF = _LM_NEAR
LM_FULL  = _LM_NEAR + _LM_FAR

PROFILE_DIR = Path("outputs/venue_profiles")

# ── 画面レイアウト ────────────────────────────────────────────────────────────
VID_W, VID_H = 896, 504     # 16:9 映像パネル
CRT_W        = 460          # コート図パネル幅
INFO_H       = 170          # ペアリスト高
STA_H        = 44           # ステータスバー高
WIN_W        = VID_W + CRT_W
WIN_H        = VID_H + STA_H
CRT_H        = WIN_H - INFO_H - STA_H  # コート図パネル高


# ── コート図描画 ──────────────────────────────────────────────────────────────
def _make_c2d(court_h: int):
    """コート座標 → コート図パネルのピクセル座標変換関数"""
    pad  = 18
    top  = 30   # タイトル分
    avail_w = CRT_W - pad * 2
    avail_h = CRT_H - top - pad
    scl  = min(avail_w / (SIDELINE * 2), avail_h / court_h)
    dw   = int(SIDELINE * 2 * scl)
    ox   = (CRT_W - dw) // 2

    def c2d(cx, cy):
        px = ox + int((cx + SIDELINE) * scl)
        py = top + int((court_h - cy) * scl)
        return (px, py)

    c2d.scl = scl
    c2d.ox  = ox
    c2d.top = top
    return c2d


def _half_court_lines(c2d, y_end, y_ctr):
    """
    1ハーフ分のコートライン (court座標 → c2dパネルpx) を返す。
    y_end < y_ctr ならニアハーフ、y_end > y_ctr ならファーハーフ (ミラー)。
    """
    sign     = 1 if y_ctr > y_end else -1
    basket_y = y_end + sign * BASKET_Y
    ft_y     = y_end + sign * FT_Y
    pt3_y    = y_end + sign * PT3_CY   # 3PT直線の内側端点

    W = (200, 200, 200)
    B = (255, 160,  50)   # レーン: オレンジ系
    O = ( 60, 180, 255)   # 3PT: シアン系
    R = ( 80, 100, 255)   # バスケット: 赤紫

    lines = []

    # エンドライン・サイドライン
    lines.append((W, [c2d(-SIDELINE, y_end), c2d(SIDELINE, y_end)]))
    lines.append((W, [c2d(-SIDELINE, y_end), c2d(-SIDELINE, y_ctr)]))
    lines.append((W, [c2d( SIDELINE, y_end), c2d( SIDELINE, y_ctr)]))

    # ペイントエリア
    lines.append((B, [c2d(-LANE_X, y_end), c2d(-LANE_X, ft_y)]))
    lines.append((B, [c2d( LANE_X, y_end), c2d( LANE_X, ft_y)]))
    lines.append((B, [c2d(-LANE_X, ft_y),  c2d( LANE_X, ft_y)]))

    # 3PTライン (直線部)
    lines.append((O, [c2d(-PT3_CX, y_end), c2d(-PT3_CX, pt3_y)]))
    lines.append((O, [c2d( PT3_CX, y_end), c2d( PT3_CX, pt3_y)]))

    # 3PTアーク ── ファーハーフは sign=-1 で basket_y 側に向かって反転
    arc = []
    for deg in range(-115, 116, 3):
        rad = np.radians(deg)
        cx  = PT3_R * np.sin(rad)
        cy  = basket_y + sign * PT3_R * np.cos(rad)
        if abs(cx) <= PT3_CX:
            arc.append(c2d(cx, cy))
    if arc:
        lines.append((O, arc))

    # バスケット (小円)
    bk = [c2d(23.75 * np.cos(np.radians(d)), basket_y + 23.75 * np.sin(np.radians(d)))
          for d in range(0, 361, 8)]
    lines.append((R, bk))

    return lines


def _make_diag_lines(c2d, court_h: int):
    """コート図全ライン"""
    lines = _half_court_lines(c2d, 0, HALF_Y)                  # ニアハーフ

    # センターライン
    W = (200, 200, 200)
    lines.append((W, [c2d(-SIDELINE, HALF_Y), c2d(SIDELINE, HALF_Y)]))

    # センターサークル
    cc = [c2d(180 * np.sin(np.radians(d)),
               HALF_Y - 180 * np.cos(np.radians(d)))
          for d in range(0, 181, 4)]
    lines.append((W, cc))

    if court_h == FULL_Y:
        lines += _half_court_lines(c2d, FULL_Y, HALF_Y)        # ファーハーフ (ミラー)
        cc2 = [c2d(180 * np.sin(np.radians(d)),
                    HALF_Y + 180 * np.cos(np.radians(d)))
               for d in range(0, 181, 4)]
        lines.append((W, cc2))

    return lines


def _make_overlay_lines(court_h: int):
    """映像オーバーレイ用ラインリスト (court座標)"""
    W = (255, 255, 255)
    B = (255, 190,  80)
    O = ( 50, 200, 255)

    def half(y_end, y_ctr):
        sign     = 1 if y_ctr > y_end else -1
        basket_y = y_end + sign * BASKET_Y
        ft_y     = y_end + sign * FT_Y
        pt3_y    = y_end + sign * PT3_CY
        result = [
            (W, [(-SIDELINE, y_end), (SIDELINE, y_end)]),
            (W, [(-SIDELINE, y_end), (-SIDELINE, y_ctr)]),
            (W, [( SIDELINE, y_end), ( SIDELINE, y_ctr)]),
            (B, [(-LANE_X, y_end), (-LANE_X, ft_y)]),
            (B, [( LANE_X, y_end), ( LANE_X, ft_y)]),
            (B, [(-LANE_X, ft_y),  ( LANE_X, ft_y)]),
            (O, [(-PT3_CX, y_end), (-PT3_CX, pt3_y)]),
            (O, [( PT3_CX, y_end), ( PT3_CX, pt3_y)]),
        ]
        arc = []
        for deg in range(-115, 116, 2):
            rad = np.radians(deg)
            cx  = PT3_R * np.sin(rad)
            cy  = basket_y + sign * PT3_R * np.cos(rad)
            if abs(cx) <= PT3_CX:
                arc.append((cx, cy))
        if arc:
            result.append((O, arc))
        return result

    lines = half(0, HALF_Y)
    lines.append((W, [(-SIDELINE, HALF_Y), (SIDELINE, HALF_Y)]))
    if court_h == FULL_Y:
        lines += half(FULL_Y, HALF_Y)
    return lines


# ── Calibrator ───────────────────────────────────────────────────────────────
class Calibrator:
    def __init__(self, video_path: str,
                 venue_name: str | None = None,
                 fullcourt: bool = False):
        self.video_path = str(video_path)
        self.venue_name = venue_name or Path(video_path).stem
        self.fullcourt  = fullcourt
        self.court_h    = FULL_Y if fullcourt else HALF_Y
        self.landmarks  = LM_FULL if fullcourt else LM_HALF

        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            print(f"Error: cannot open {self.video_path}", file=sys.stderr)
            sys.exit(1)
        self.fps    = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total  = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.orig_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.orig_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.sx     = VID_W / self.orig_w
        self.sy     = VID_H / self.orig_h
        self.fi     = 0
        self.frame  = None
        self._load_frame(0)

        self._c2d           = _make_c2d(self.court_h)
        self._diag_lines    = _make_diag_lines(self._c2d, self.court_h)
        self._overlay_lines = _make_overlay_lines(self.court_h)

        self.pairs:    list[tuple[int, tuple[int, int]]] = []
        self.sel_lm:   int | None = None
        self.H:        np.ndarray | None = None
        self.trust_hull: np.ndarray | None = None
        self.msg = ""

    # ── 内部 ─────────────────────────────────────────────────────────────
    def _load_frame(self, fi: int):
        fi = max(0, min(fi, self.total - 1))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ret, frame = self.cap.read()
        if ret:
            self.fi, self.frame = fi, frame

    def _recompute(self):
        if len(self.pairs) < 4:
            self.H = self.trust_hull = None
            return
        crt = np.float32([[self.landmarks[i][2], self.landmarks[i][3]]
                           for i, _ in self.pairs])
        img = np.float32([[x, y] for _, (x, y) in self.pairs])
        H, _ = cv2.findHomography(crt, img, cv2.RANSAC, 8.0, maxIters=2000)
        self.H = H
        if H is not None and len(crt) >= 3:
            hull = cv2.convexHull(crt.reshape(-1, 1, 2).astype(np.float32))
            self.trust_hull = hull.reshape(-1, 2)

    def _project(self, cx, cy):
        if self.H is None:
            return None
        pt  = np.array([[[float(cx), float(cy)]]], dtype=np.float64)
        out = cv2.perspectiveTransform(pt, self.H)
        ox, oy = float(out[0, 0, 0]) * self.sx, float(out[0, 0, 1]) * self.sy
        return (int(ox), int(oy))

    def _confirmed_ids(self):
        return {self.landmarks[i][0] for i, _ in self.pairs}

    def _tab_next(self):
        """未登録ランドマークを順番に選択"""
        confirmed = self._confirmed_ids()
        n = len(self.landmarks)
        start = (self.sel_lm + 1) if self.sel_lm is not None else 0
        for offset in range(n):
            idx = (start + offset) % n
            if self.landmarks[idx][0] not in confirmed:
                self.sel_lm = idx
                lid = self.landmarks[idx][1]
                self.msg = f"[{idx+1}] {lid}"
                return
        self.msg = "All landmarks confirmed!"

    # ── 描画: 映像パネル ──────────────────────────────────────────────────
    def _draw_video(self) -> np.ndarray:
        vis = cv2.resize(self.frame, (VID_W, VID_H))

        # コートラインオーバーレイ
        if self.H is not None:
            for color, pts in self._overlay_lines:
                prev = None
                for cx, cy in pts:
                    p = self._project(cx, cy)
                    if p and 0 <= p[0] < VID_W and 0 <= p[1] < VID_H:
                        if prev:
                            cv2.line(vis, prev, p, color, 1, cv2.LINE_AA)
                        prev = p
                    else:
                        prev = None

        # 信頼領域
        if self.trust_hull is not None and len(self.trust_hull) >= 3:
            poly = [self._project(cx, cy) for cx, cy in self.trust_hull]
            poly = [p for p in poly if p]
            if len(poly) >= 3:
                cv2.polylines(vis, [np.array(poly)], True, (0, 220, 170), 1)

        # 登録済みペアの映像上の点
        confirmed = self._confirmed_ids()
        for i, (lm_i, (ox, oy)) in enumerate(self.pairs):
            dx, dy = int(ox * self.sx), int(oy * self.sy)
            lid = self.landmarks[lm_i][0]
            num = lm_i + 1
            cv2.circle(vis, (dx, dy), 10, (0, 0, 0), -1)
            cv2.circle(vis, (dx, dy), 8, (0, 220, 100), -1)
            cv2.putText(vis, str(num), (dx - 5, dy + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 1)

        # 選択中ランドマーク表示
        if self.sel_lm is not None:
            lm = self.landmarks[self.sel_lm]
            label = f"[{self.sel_lm+1}] {lm[1]}"
            # 背景帯
            cv2.rectangle(vis, (0, VID_H - 40), (VID_W, VID_H), (0, 0, 0), -1)
            cv2.putText(vis, f">> Click this point in the video:  {label}",
                        (10, VID_H - 12), cv2.FONT_HERSHEY_SIMPLEX,
                        0.58, (0, 230, 255), 1)
            # 十字カーソルヒント
            cv2.putText(vis, "STEP 2", (VID_W - 90, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 230, 255), 2)
        else:
            cv2.putText(vis, "STEP 1", (VID_W - 90, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 200, 50), 2)

        # タイムスタンプ
        ts = self.fi / self.fps
        mm, ss = int(ts // 60), int(ts % 60)
        cv2.putText(vis, f"t={mm}:{ss:02d}  [{self.fi}/{self.total}]",
                    (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1)
        return vis

    # ── 描画: コート図パネル ─────────────────────────────────────────────
    def _draw_court(self) -> np.ndarray:
        panel = np.full((CRT_H, CRT_W, 3), 18, dtype=np.uint8)
        mode  = "Full Court" if self.fullcourt else "Half Court"
        cv2.putText(panel, f"FIBA {mode} — click a landmark",
                    (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (160, 160, 160), 1)

        # コートライン
        for color, pts in self._diag_lines:
            for i in range(len(pts) - 1):
                cv2.line(panel, pts[i], pts[i + 1], color, 1, cv2.LINE_AA)

        confirmed = self._confirmed_ids()
        for i, (lid, desc, cx, cy) in enumerate(self.landmarks):
            px, py = self._c2d(cx, cy)
            num    = i + 1
            sel    = (i == self.sel_lm)
            ok     = (lid in confirmed)

            if sel:
                # 選択中: 大きな白枠円 + 番号
                cv2.circle(panel, (px, py), 14, (0, 230, 255), -1)
                cv2.circle(panel, (px, py), 14, (255, 255, 255), 2)
                txt_col = (0, 0, 0)
            elif ok:
                # 登録済み: 緑円
                cv2.circle(panel, (px, py), 9, (0, 200, 80), -1)
                cv2.circle(panel, (px, py), 9, (0, 255, 100), 1)
                txt_col = (0, 0, 0)
            else:
                # 未登録: グレー円
                cv2.circle(panel, (px, py), 7, (80, 80, 80), -1)
                cv2.circle(panel, (px, py), 7, (140, 140, 140), 1)
                txt_col = (200, 200, 200)

            # 番号
            tw = 6 if num < 10 else 10
            cv2.putText(panel, str(num), (px - tw // 2, py + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.33, txt_col, 1)
            # ラベル (選択時のみ)
            if sel:
                cv2.putText(panel, lid, (px + 16, py + 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.30, (0, 230, 255), 1)

        return panel

    # ── 描画: ペアリストパネル ───────────────────────────────────────────
    def _draw_info(self) -> np.ndarray:
        panel = np.full((INFO_H, CRT_W, 3), 30, dtype=np.uint8)
        n = len(self.pairs)
        clr = (0, 200, 80) if n >= 6 else (0, 180, 255) if n >= 4 else (160, 100, 50)
        cv2.putText(panel, f"Pairs: {n}  ({'GOOD' if n >= 6 else 'OK >= 4' if n >= 4 else 'need >= 4'})",
                    (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.50, clr, 1)

        # ペアリスト (2列表示)
        row_h = 16
        max_rows = (INFO_H - 30) // row_h
        col_w    = CRT_W // 2
        for idx, (lm_i, (ox, oy)) in enumerate(self.pairs[:max_rows * 2]):
            lid  = self.landmarks[lm_i][0]
            num  = lm_i + 1
            col  = idx // max_rows
            row  = idx % max_rows
            x0   = 10 + col * col_w
            y0   = 32 + row * row_h
            cv2.putText(panel, f"{num:2d}. {lid}", (x0, y0),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.33, (0, 210, 100), 1)

        if n > max_rows * 2:
            cv2.putText(panel, f"... +{n - max_rows*2} more",
                        (10, INFO_H - 8), cv2.FONT_HERSHEY_SIMPLEX,
                        0.32, (120, 120, 120), 1)
        return panel

    # ── 描画: ステータスバー ─────────────────────────────────────────────
    def _draw_status(self, canvas: np.ndarray):
        y0 = WIN_H - STA_H
        canvas[y0:, :] = (45, 45, 45)
        h_ok  = self.H is not None
        h_txt = "H: OK" if h_ok else "H: ---"
        h_col = (0, 220, 80) if h_ok else (100, 100, 100)
        cv2.putText(canvas, h_txt, (10, y0 + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, h_col, 1)
        msg = self.msg or ("Select landmark (right panel)" if self.sel_lm is None
                           else "Click point in video (left panel)")
        cv2.putText(canvas, msg, (80, y0 + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (210, 210, 210), 1)
        cv2.putText(canvas,
                    "Tab=next  U=undo  C=clear  ←→=1s  A/D=5s  S=save  Q=quit",
                    (10, y0 + 36), cv2.FONT_HERSHEY_SIMPLEX,
                    0.36, (100, 100, 100), 1)

    def _render(self) -> np.ndarray:
        canvas = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)
        canvas[:VID_H, :VID_W] = self._draw_video()
        canvas[:CRT_H, VID_W:] = self._draw_court()
        canvas[CRT_H:CRT_H + INFO_H, VID_W:] = self._draw_info()
        self._draw_status(canvas)
        # セパレーター
        canvas[:, VID_W - 1: VID_W + 1] = (60, 60, 60)
        canvas[CRT_H: CRT_H + 2, VID_W:] = (50, 50, 50)
        return canvas

    # ── マウスコールバック ────────────────────────────────────────────────
    def on_mouse(self, event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return

        if x < VID_W and y < VID_H:
            # 映像パネル → 登録
            if self.sel_lm is None:
                self.msg = "Select a landmark on the court diagram first (right panel)"
                return
            ox = int(x / self.sx)
            oy = int(y / self.sy)
            # 同じランドマークの登録済みを上書き
            self.pairs = [(i, xy) for i, xy in self.pairs if i != self.sel_lm]
            self.pairs.append((self.sel_lm, (ox, oy)))
            lid = self.landmarks[self.sel_lm][0]
            self.msg = f"[{self.sel_lm+1}] {lid} registered  ({len(self.pairs)} pairs)"
            self.sel_lm = None
            self._recompute()

        elif x >= VID_W and y < CRT_H:
            # コート図パネル → ランドマーク選択
            cx = x - VID_W
            lm_i = self._nearest_lm(cx, y)
            if lm_i is not None:
                self.sel_lm = lm_i
                lm = self.landmarks[lm_i]
                self.msg = f"[{lm_i+1}] {lm[1]}  →  click in video"
            else:
                self.msg = "Click closer to a landmark circle"

    def _nearest_lm(self, px, py, thr=20):
        best, best_d = None, float("inf")
        for i, (_, _, cx, cy) in enumerate(self.landmarks):
            dx, dy = self._c2d(cx, cy)
            d = np.hypot(px - dx, py - dy)
            if d < thr and d < best_d:
                best_d, best = d, i
        return best

    # ── 保存 / 読み込み ───────────────────────────────────────────────────
    def save(self):
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "venue":            self.venue_name,
            "video":            Path(self.video_path).name,
            "fullcourt":        self.fullcourt,
            "frame_idx":        self.fi,
            "n_pairs":          len(self.pairs),
            "pairs": [
                {
                    "landmark_id":   self.landmarks[i][0],
                    "landmark_desc": self.landmarks[i][1],
                    "court_xy":      [self.landmarks[i][2], self.landmarks[i][3]],
                    "image_xy":      list(xy),
                }
                for i, xy in self.pairs
            ],
            "H_court_to_image":  self.H.tolist() if self.H is not None else None,
            "trust_hull_court":  self.trust_hull.tolist() if self.trust_hull is not None else None,
        }
        path = PROFILE_DIR / f"{self.venue_name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.msg = f"Saved: {path}"
        print(f"Saved: {path}")
        return path

    def load(self, name: str):
        path = PROFILE_DIR / f"{name}.json"
        if not path.exists():
            print(f"Profile not found: {path}")
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        ids = [lm[0] for lm in self.landmarks]
        self.pairs = []
        for e in data.get("pairs", []):
            if e["landmark_id"] in ids:
                i = ids.index(e["landmark_id"])
                self.pairs.append((i, tuple(e["image_xy"])))
        self._recompute()
        self.venue_name = data.get("venue", name)
        self.msg = f"Profile '{self.venue_name}' loaded ({len(self.pairs)} pairs)"

    # ── メインループ ──────────────────────────────────────────────────────
    def run(self):
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        win = "Court Calibration"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win, WIN_W, WIN_H)
        cv2.setMouseCallback(win, self.on_mouse)

        step_s = max(1, int(self.fps))

        while True:
            cv2.imshow(win, self._render())
            key = cv2.waitKey(30) & 0xFF

            if key in (ord("q"), 27):       # Q / Esc — quit
                break
            elif key == ord("\t"):           # Tab — next landmark
                self._tab_next()
            elif key in (8, ord("u")):       # Backspace / U — undo
                if self.pairs:
                    removed = self.pairs.pop()
                    self._recompute()
                    lid = self.landmarks[removed[0]][0]
                    self.msg = f"Undo: [{lid}]  ({len(self.pairs)} pairs)"
            elif key == ord("c"):            # C — clear
                self.pairs.clear()
                self.sel_lm = self.H = self.trust_hull = None
                self.msg = "Cleared all pairs"
            elif key in (2, ord("a")):       # Left / A — -5s
                self._load_frame(max(0, self.fi - step_s * 5))
                self.msg = f"t={self.fi/self.fps:.1f}s"
            elif key in (3, ord("d")):       # Right / D — +5s
                self._load_frame(self.fi + step_s * 5)
                self.msg = f"t={self.fi/self.fps:.1f}s"
            elif key == 81 or key == 0:      # ← arrow — -1s
                self._load_frame(max(0, self.fi - step_s))
                self.msg = f"t={self.fi/self.fps:.1f}s"
            elif key == 83 or key == 1:      # → arrow — +1s
                self._load_frame(self.fi + step_s)
                self.msg = f"t={self.fi/self.fps:.1f}s"
            elif key in (13, ord("s")):      # Enter / S — save
                if len(self.pairs) < 4:
                    self.msg = "Need at least 4 pairs to save"
                else:
                    self.save()

        cv2.destroyAllWindows()
        self.cap.release()


# ── エントリーポイント ────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Court calibration tool")
    ap.add_argument("--video",     required=True)
    ap.add_argument("--venue",     default=None)
    ap.add_argument("--load",      default=None)
    ap.add_argument("--fullcourt", action="store_true")
    args = ap.parse_args()

    fc = args.fullcourt
    if args.load:
        prof_path = PROFILE_DIR / f"{args.load}.json"
        if prof_path.exists():
            with open(prof_path) as f:
                fc = json.load(f).get("fullcourt", fc)

    cal = Calibrator(args.video, args.venue, fullcourt=fc)
    if args.load:
        cal.load(args.load)
    cal.run()


if __name__ == "__main__":
    main()

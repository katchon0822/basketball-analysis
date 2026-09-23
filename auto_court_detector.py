#!/usr/bin/env python3
"""
auto_court_detector.py — アノテーション不要の自動コート検知

DeNA方式: ラインセグメンテーション → フレームごとホモグラフィー推定

Algorithm:
  1. コート床面 (木製フロア HSV) でフロアマスク生成
  2. フロア内の白ラインを検出 → HoughLinesP
  3. 水平線 / 垂直線に分類 → 境界4本特定
  4. 交点4つ = コートコーナー → H行列計算
  5. EMAスムージングで時系列安定化 (カメラ移動対応)
"""

import cv2
import numpy as np
from typing import Optional

# FIBA コート定数 (cm)
SIDELINE = 750
HALF_Y   = 1432

# ハーフコート4隅 (コート座標)
HALF_COURT_SRC = np.float32([
    [-SIDELINE, HALF_Y],   # 奥左
    [ SIDELINE, HALF_Y],   # 奥右
    [-SIDELINE, 0],        # 手前左
    [ SIDELINE, 0],        # 手前右
])


def _intersect(l1, l2):
    """2線分の延長交点を求める"""
    x1, y1, x2, y2 = l1
    x3, y3, x4, y4 = l2
    d = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
    if abs(d) < 1e-6:
        return None
    t = ((x1-x3)*(y3-y4) - (y1-y3)*(x3-x4)) / d
    return (x1 + t*(x2-x1), y1 + t*(y2-y1))


def _quad_ok(pts, W, H):
    """4点が合理的な四角形かチェック"""
    if any(p is None for p in pts):
        return False
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    margin = max(W, H) * 0.9
    if any(x < -margin or x > W+margin or y < -margin or y > H+margin
           for x, y in zip(xs, ys)):
        return False
    if max(xs)-min(xs) < W*0.25 or max(ys)-min(ys) < H*0.15:
        return False
    return True


class CourtDetector:
    """
    フレームごとにコートHomography (court→image) を自動推定。

    Usage:
        det = CourtDetector()
        for frame in frames:
            H = det.update(frame)   # None の場合は検出失敗 (前回値を保持)
            if H is not None:
                proj = make_proj(H)
    """

    def __init__(self, smooth_alpha: float = 0.25, detect_every: int = 6):
        """
        smooth_alpha : EMA係数 (0=固定, 1=即時更新)
        detect_every : 何フレームおきに検出するか (速度トレードオフ)
        """
        self.alpha  = smooth_alpha
        self.every  = detect_every
        self._H: Optional[np.ndarray] = None
        self._tick  = 0
        self._ok    = 0   # 成功カウント
        self._fail  = 0   # 失敗カウント

    @property
    def H(self) -> Optional[np.ndarray]:
        return self._H

    @property
    def stats(self) -> dict:
        total = self._ok + self._fail
        rate  = self._ok / total if total else 0
        return {"ok": self._ok, "fail": self._fail, "rate": rate}

    def update(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """フレームを受け取り、最新のH行列を返す"""
        self._tick += 1
        if self._tick % self.every != 0:
            return self._H

        H_new = self._detect(frame)
        if H_new is None:
            self._fail += 1
            return self._H

        self._ok += 1
        if self._H is None:
            self._H = H_new
        else:
            self._H = self.alpha * H_new + (1 - self.alpha) * self._H
        return self._H

    def _detect(self, frame: np.ndarray) -> Optional[np.ndarray]:
        H_px, W = frame.shape[:2]
        hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # ── 1. フロアマスク ───────────────────────────────────────
        # 木製コートの暖色系: H=10-50, S=40-200, V=80-240
        f1 = cv2.inRange(hsv, (8,  35,  80), (50, 210, 245))
        f2 = cv2.inRange(hsv, (0,  20,  90), (15, 190, 255))
        floor = cv2.bitwise_or(f1, f2)
        # 上部 30% (観客席・照明) を除外
        floor[:int(H_px*0.30), :] = 0
        floor = cv2.morphologyEx(floor, cv2.MORPH_CLOSE,
                                  np.ones((15, 15), np.uint8))
        floor = cv2.morphologyEx(floor, cv2.MORPH_OPEN,
                                  np.ones((7, 7), np.uint8))

        floor_pixels = int(floor.sum() // 255)
        if floor_pixels < W * H_px * 0.08:  # フロアが小さすぎる
            return None

        # ── 2. 白ライン検出: アダプティブ閾値 + フロアマスク ─────
        # グレースケールで局所的に明るい部分を検出 (照明変化に強い)
        blur   = cv2.GaussianBlur(gray, (5, 5), 0)
        adapt  = cv2.adaptiveThreshold(blur, 255,
                                        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY, 25, -12)
        # フロア内かつ絶対的に明るい (V>145) の AND
        bright = cv2.inRange(hsv, (0, 0, 145), (180, 80, 255))
        lines_mask = cv2.bitwise_and(adapt, bright)
        lines_mask = cv2.bitwise_and(lines_mask, floor)
        # 小さいノイズ除去のみ (細線化はHoughに任せる)
        lines_mask = cv2.morphologyEx(lines_mask, cv2.MORPH_OPEN,
                                       np.ones((2, 2), np.uint8))

        # ── 3. HoughLinesP ────────────────────────────────────────
        min_len = max(W // 16, 25)
        segs = cv2.HoughLinesP(
            lines_mask, rho=1, theta=np.pi/360,
            threshold=22, minLineLength=min_len, maxLineGap=15)

        if segs is None or len(segs) < 4:
            return None

        # ── 4. 角度で分類 (この動画は斜め視点なので範囲を広めに) ──
        # 水平方向: ±40°以内
        # 垂直方向: 50-130°
        horiz, vert = [], []
        for seg in segs[:, 0]:
            x1, y1, x2, y2 = seg
            angle  = abs(np.degrees(np.arctan2(y2-y1, x2-x1))) % 180
            length = np.hypot(x2-x1, y2-y1)
            if angle < 40 or angle > 140:
                horiz.append((seg, length))
            elif 50 < angle < 130:
                vert.append((seg, length))

        if len(horiz) < 2 or len(vert) < 2:
            return None

        # ── 5. 境界ライン: y/x の中央値で2分割し各グループ最長線 ─
        horiz.sort(key=lambda x: (x[0][1]+x[0][3])/2)
        vert.sort(key=lambda x:  (x[0][0]+x[0][2])/2)

        mid_h = max(1, len(horiz)//2)
        mid_v = max(1, len(vert) //2)

        far_h   = max(horiz[:mid_h],             key=lambda x: x[1])[0]
        near_h  = max(horiz[mid_h:] or horiz[-1:], key=lambda x: x[1])[0]
        left_v  = max(vert [:mid_v],             key=lambda x: x[1])[0]
        right_v = max(vert [mid_v:] or vert[-1:],  key=lambda x: x[1])[0]

        # ── 6. 4隅交点 → H計算 ──────────────────────────────────
        tl = _intersect(far_h,  left_v)
        tr = _intersect(far_h,  right_v)
        bl = _intersect(near_h, left_v)
        br = _intersect(near_h, right_v)

        if not _quad_ok([tl, tr, bl, br], W, H_px):
            return None

        dst    = np.float32([tl, tr, bl, br])
        H_new, _ = cv2.findHomography(HALF_COURT_SRC, dst, cv2.RANSAC, 8.0)
        if H_new is None:
            return None

        # ── 7. バリデーション ─────────────────────────────────────
        test = HALF_COURT_SRC.reshape(-1, 1, 2).astype(np.float64)
        proj = cv2.perspectiveTransform(test, H_new)
        if proj is None:
            return None
        in_view = sum(
            -W*0.6 < p[0][0] < W*1.6 and -H_px*0.5 < p[0][1] < H_px*1.5
            for p in proj
        )
        if in_view < 2:
            return None

        return H_new

    def draw_debug(self, frame: np.ndarray) -> np.ndarray:
        """検出結果をデバッグ描画"""
        vis = frame.copy()
        if self._H is None:
            cv2.putText(vis, "COURT: not detected",
                        (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,0,255), 1)
            return vis

        # コート境界を投影
        corners = HALF_COURT_SRC.reshape(-1, 1, 2).astype(np.float64)
        proj = cv2.perspectiveTransform(corners, self._H)
        if proj is not None:
            pts = proj[:, 0, :].astype(np.int32)
            H_px, W = frame.shape[:2]
            for i in range(4):
                p1 = tuple(pts[i])
                p2 = tuple(pts[(i+1) % 4])
                cv2.line(vis, p1, p2, (0, 255, 0), 2, cv2.LINE_AA)

        s = self.stats
        cv2.putText(vis,
                    f"COURT auto  ok={s['ok']} fail={s['fail']} rate={s['rate']:.0%}",
                    (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0,255,0), 1)
        return vis

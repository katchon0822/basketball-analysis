"""
generate_detection_video.py  v2
改善点:
  1. コートライン: ORBフィーチャーマッチングでフレーム間ホモグラフィーを精密追跡
  2. 選手表示: yolov8n-seg でセグメンテーション（チームカラーで人体を塗りつぶし）
  3. ミニマップ: 右下にコート上の現在位置をリアルタイム表示
"""
import cv2, json, numpy as np, argparse
from pathlib import Path
from collections import defaultdict

import supervision as sv
from ultralytics import YOLO

from court_line_accuracy import (
    build_H_inv, key_to_frame, project, court_lines
)
from auto_fit_3pt import collect_arc_points, fit_radius_ransac

# ── 定数 ───────────────────────────────────────────────────────────────────────
VIDEO      = "data/videos/game_EE1swQMsXJc_720p.mp4"
MODEL_DET  = "models/player_detector.pt"
MODEL_SEG  = "yolov8n-seg.pt"
ANN_JSON   = "outputs/annotations.json"
OUT_DIR    = Path("outputs/sam3_300s")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CLS_PLAYER = 4
CLS_REF    = 5
CONF_DET   = 0.35
CONF_SEG   = 0.40

PT3_DEFAULT  = 705
PT3_CORNER_X = 665

# コート定数 (cm)
COURT_W      = 750     # ハーフ幅
COURT_L      = 1432    # ハーフ長
COURT_FULL_L = COURT_L * 2   # フルコート長 (2864cm)
BASKET_Y     = 160     # エンドラインからバスケットまで

# チームカラー (BGR)
TEAM_BGR  = {1: (200, 200, 255), 2: (255, 120,  60), -1: (160, 160, 160)}
REF_BGR   = (0, 220, 255)
BALL_BGR  = (0, 220, 255)
ALPHA_SEG = 0.55   # セグメントマスクの不透明度

# ミニマップ: フルコート横向き表示
# フルコート 2864cm × 1500cm → 300px × 157px (横向き)
MM_W   = 300                          # ピクセル幅 (コート長方向)
MM_H   = int(MM_W * (COURT_W*2) / COURT_FULL_L)  # ≈157px
MM_PAD = 8
MM_SCALE = MM_W / COURT_FULL_L       # px/cm (等方)


# ══════════════════════════════════════════════════════════════════════════════
#  ORB ホモグラフィートラッカー (fallback用)
# ══════════════════════════════════════════════════════════════════════════════
class HomographyTracker:
    """アノテーションフレームのORB特徴量から各フレームのH_invを精密推定する"""

    def __init__(self, max_features=2000):
        self.orb     = cv2.ORB_create(nfeatures=max_features)
        self.bf      = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        self.refs    = {}

    def add_reference(self, fi, frame, H_c2i):
        kp, des = self.orb.detectAndCompute(frame, None)
        self.refs[fi] = (kp, des, H_c2i)

    def get_H_c2i(self, fi, frame):
        if not self.refs:
            return None
        ref_fi = min(self.refs.keys(), key=lambda k: abs(k - fi))
        ref_kp, ref_des, ref_H = self.refs[ref_fi]
        if ref_fi == fi:
            return ref_H
        kp, des = self.orb.detectAndCompute(frame, None)
        if des is None or ref_des is None or len(des) < 10:
            return ref_H
        matches = self.bf.match(ref_des, des)
        if len(matches) < 10:
            return ref_H
        matches = sorted(matches, key=lambda m: m.distance)[:80]
        pts_ref = np.float32([ref_kp[m.queryIdx].pt for m in matches])
        pts_cur = np.float32([kp[m.trainIdx].pt     for m in matches])
        H_ref2cur, mask = cv2.findHomography(pts_ref, pts_cur, cv2.RANSAC, 4.0)
        if H_ref2cur is None or mask.sum() < 8:
            return ref_H
        return H_ref2cur @ ref_H


# ── 自動再キャリブレーション定数 ─────────────────────────────────────────────
# コートのキーポイント (エンドライン4点 + FTライン-レーン交点2点)
REFINE_COURT_PTS = [
    (-750, 0), (-245, 0), (245, 0), (750, 0),
    (-245, 580), (245, 580),
]
REFINE_INTERVAL = 90   # フレーム間隔 (≈3秒@30fps)


def _find_court_corner(frame, px, py, search_r=45):
    """
    (px, py) 周辺でコートラインの交差コーナーを Harris 検出で特定。
    白ピクセルマスクに goodFeaturesToTrack を適用してコーナー座標を返す。
    """
    h, w = frame.shape[:2]
    x1, y1 = max(0, px - search_r), max(0, py - search_r)
    x2, y2 = min(w, px + search_r), min(h, py + search_r)
    if x2 - x1 < 15 or y2 - y1 < 15:
        return None
    roi = frame[y1:y2, x1:x2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, white = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    corners = cv2.goodFeaturesToTrack(
        white.astype(np.float32), maxCorners=5,
        qualityLevel=0.05, minDistance=5,
        useHarrisDetector=True, k=0.04)
    if corners is None:
        return None
    cx_roi, cy_roi = float(px - x1), float(py - y1)
    best, best_d = None, float('inf')
    for c in corners:
        ccx, ccy = c[0]
        d = np.hypot(ccx - cx_roi, ccy - cy_roi)
        if d < best_d:
            best_d = d
            best = (ccx + x1, ccy + y1)
    if best is None or best_d > search_r * 0.9:
        return None
    return float(best[0]), float(best[1])


# ══════════════════════════════════════════════════════════════════════════════
#  オプティカルフロー ホモグラフィートラッカー (主tracker)
# ══════════════════════════════════════════════════════════════════════════════
class OpticalFlowTracker:
    """
    Lucas-Kanade光学流量でアノテーションキーポイントを毎フレーム追跡し
    H_c2i (court→image) を精密再計算する。

    動作:
      - アノテーションフレームで init() → キーポイントをseedとして設定
      - 以降のフレームで update() → LK追跡 + RANSAC findHomography
      - 追跡点が4点未満に減ったら最後の良好なHを返す
      - ann_map内の次のアノテーションフレームに来たら自動リセット
    """
    LK_PARAMS = dict(
        winSize=(25, 25),
        maxLevel=4,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )

    def __init__(self, ann_map):
        self.ann_map        = ann_map        # {fi: (H_c2i, pts_list)}
        self.ann_frames     = {}             # {fi: gray}  事前キャッシュ
        self.prev_gray      = None
        self.tracked_img    = None           # (N,1,2) float32: 追跡中の画像座標
        self.tracked_crt    = None           # (N,2)   float32: 対応コート座標
        self.current_H      = None
        self._next_ann      = None           # 次のリセット対象アノテーションfi
        self.last_refine_ok = False          # 直近の自動再キャリブレーション結果

    def cache_ann_frames(self, cap):
        """アノテーションフレームのgrayを事前キャッシュ"""
        for fi, (H_c2i, pts_list) in self.ann_map.items():
            cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
            ret, frm = cap.read()
            if ret:
                self.ann_frames[fi] = cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY)
        self._sorted_anns = sorted(self.ann_map.keys())

    def _init_from_ann(self, fi, gray):
        H_c2i, pts_list = self.ann_map[fi]
        img_pts, crt_pts = [], []
        for p in pts_list:
            if p.get('img') is not None:
                img_pts.append(p['img'])
                crt_pts.append(p['court'])
        if len(img_pts) < 4:
            return False
        self.prev_gray   = gray
        self.tracked_img = np.float32(img_pts).reshape(-1, 1, 2)
        self.tracked_crt = np.float32(crt_pts)
        self.current_H   = H_c2i
        return True

    def try_auto_refine(self, frame):
        """
        白線コーナー検出でH_c2iを再キャリブレーション。
        成功した場合は current_H と光学流量シード点を更新して True を返す。
        """
        if self.current_H is None:
            return False
        img_pts, crt_pts = [], []
        for cx, cy in REFINE_COURT_PTS:
            proj = project(self.current_H, cx, cy)
            if proj is None:
                continue
            corner = _find_court_corner(frame, proj[0], proj[1])
            if corner is None:
                continue
            img_pts.append(corner)
            crt_pts.append([cx, cy])
        if len(img_pts) < 4:
            return False
        H_new, mask = cv2.findHomography(
            np.float32(crt_pts), np.float32(img_pts), cv2.RANSAC, 8.0)
        if H_new is None or mask.sum() < 4:
            return False
        if abs(np.linalg.det(H_new)) < 1e-8:
            return False
        inl = mask.ravel() == 1
        self.current_H      = H_new
        self.tracked_img    = np.float32(img_pts)[inl].reshape(-1, 1, 2)
        self.tracked_crt    = np.float32(crt_pts)[inl]
        self.prev_gray      = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self.last_refine_ok = True
        return True

    def update(self, fi, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # アノテーションフレームに来たらリセット
        if fi in self.ann_map:
            self._init_from_ann(fi, gray)
            return self.current_H, True

        # 定期的に白線コーナー検出で再キャリブレーション
        if fi % REFINE_INTERVAL == 0 and fi > 0:
            self.try_auto_refine(frame)

        if self.prev_gray is None or self.tracked_img is None:
            # 最初のアノテーションより前: 最近傍アノテーションで初期化
            if self._sorted_anns:
                nearest = min(self._sorted_anns, key=lambda k: abs(k - fi))
                ann_gray = self.ann_frames.get(nearest)
                if ann_gray is not None:
                    self._init_from_ann(nearest, ann_gray)
            return self.current_H, False

        # LK光学流量
        new_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            self.prev_gray, gray,
            self.tracked_img, None, **self.LK_PARAMS)

        if new_pts is None:
            self.prev_gray = gray
            return self.current_H, False

        good = status.ravel() == 1
        good_img = new_pts[good]
        good_crt = self.tracked_crt[good]

        if len(good_img) < 4:
            self.prev_gray = gray
            return self.current_H, False

        # 追跡点からH再計算 (court→image)
        H_new, hmask = cv2.findHomography(
            good_crt, good_img.reshape(-1, 2), cv2.RANSAC, 4.0)

        if (H_new is not None and hmask is not None and hmask.sum() >= 4
                and abs(np.linalg.det(H_new)) > 1e-8):
            inlier = hmask.ravel() == 1
            self.tracked_img = good_img[inlier].reshape(-1, 1, 2)
            self.tracked_crt = good_crt[inlier]
            self.current_H   = H_new

        self.prev_gray = gray
        return self.current_H, False


# ══════════════════════════════════════════════════════════════════════════════
#  アノテーション読み込み
# ══════════════════════════════════════════════════════════════════════════════
def load_annotations(ann_path, fps):
    with open(ann_path) as f:
        data = json.load(f)
    result = {}
    for key, pts in data.items():
        if not isinstance(pts, list):
            continue
        fi = key_to_frame(key, fps)
        H_inv = build_H_inv(pts)
        if H_inv is not None:
            result[fi] = (H_inv, pts)
    return result


def get_nearest_ann(ann_map, fi):
    if not ann_map:
        return None, None
    closest = min(ann_map.keys(), key=lambda k: abs(k - fi))
    return ann_map[closest]


def precompute_ransac(ann_map, cap, fps):
    radii = {}
    for fi, (H_inv, pts) in ann_map.items():
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ret, frame = cap.read()
        if not ret:
            continue
        hits = collect_arc_points(frame, H_inv, init_radius=PT3_DEFAULT)
        fitted_r, inliers = fit_radius_ransac(hits, H_inv)
        radii[fi] = fitted_r if (fitted_r and len(inliers) >= 8) else PT3_DEFAULT
    return radii


def get_nearest_radius(radii, fi):
    if not radii:
        return PT3_DEFAULT
    return radii[min(radii.keys(), key=lambda k: abs(k - fi))]


# ══════════════════════════════════════════════════════════════════════════════
#  コートライン描画
# ══════════════════════════════════════════════════════════════════════════════
def draw_court(frame, H_c2i, pt3_r):
    for color, pts in court_lines(pt3_radius=pt3_r):
        pxpts = [project(H_c2i, p[0], p[1]) for p in pts]
        pxpts = [p for p in pxpts if p]
        for i in range(len(pxpts) - 1):
            cv2.line(frame, pxpts[i], pxpts[i+1], color, 2, cv2.LINE_AA)


# ══════════════════════════════════════════════════════════════════════════════
#  チーム分類
# ══════════════════════════════════════════════════════════════════════════════
def classify_team(frame, bbox):
    x1, y1, x2, y2 = map(int, bbox)
    h = y2 - y1
    roi = frame[y1 + int(h*0.15): y1 + int(h*0.65), x1:x2]
    if roi.size == 0:
        return -1
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    t   = roi.shape[0] * roi.shape[1]
    if cv2.inRange(hsv, (0,   0, 170), (180,  70, 255)).sum() / 255 / t > 0.12:
        return 1   # White
    if cv2.inRange(hsv, (90, 60,  15), (140, 255, 170)).sum() / 255 / t > 0.07:
        return 2   # Navy
    return -1


# ══════════════════════════════════════════════════════════════════════════════
#  セグメンテーション → チームカラー塗りつぶし
# ══════════════════════════════════════════════════════════════════════════════
def apply_seg_masks(frame, seg_results, player_tracks, frame_teams):
    """yolov8n-seg のマスクをチームカラーで塗りつぶす"""
    overlay = frame.copy()
    H, W    = frame.shape[:2]

    # yolov8n-seg の person マスク (class 0)
    seg_res = seg_results[0]
    if seg_res.masks is None:
        return frame

    masks_data = seg_res.masks.data.cpu().numpy()    # (N, mH, mW)
    seg_boxes  = seg_res.boxes.xyxy.cpu().numpy()    # (N, 4)
    seg_cls    = seg_res.boxes.cls.cpu().numpy()

    # player_detector の bboxes (ByteTrackで追跡済み)
    # player_tracks: [(tid, bbox_xyxy, team)]
    for mi in range(len(masks_data)):
        if int(seg_cls[mi]) != 0:   # person のみ
            continue

        # セグメントbboxと最もIoUが高い検出選手を探す
        sb = seg_boxes[mi]
        best_team = -1
        best_iou  = 0.25   # 最低IoU閾値
        for tid, pbbox, pteam in player_tracks:
            pb = pbbox
            ix1 = max(sb[0], pb[0]); iy1 = max(sb[1], pb[1])
            ix2 = min(sb[2], pb[2]); iy2 = min(sb[3], pb[3])
            if ix2 <= ix1 or iy2 <= iy1:
                continue
            inter = (ix2 - ix1) * (iy2 - iy1)
            area_s = (sb[2]-sb[0]) * (sb[3]-sb[1])
            area_p = (pb[2]-pb[0]) * (pb[3]-pb[1])
            iou = inter / (area_s + area_p - inter + 1e-6)
            if iou > best_iou:
                best_iou  = iou
                best_team = pteam

        color = TEAM_BGR.get(best_team, TEAM_BGR[-1])

        # マスクをフレームサイズにリサイズ
        mask = masks_data[mi]
        mask_resized = cv2.resize(mask, (W, H), interpolation=cv2.INTER_LINEAR)
        mask_bin = (mask_resized > 0.5).astype(np.uint8)

        # チームカラーで塗りつぶし
        colored = np.zeros_like(frame)
        colored[:] = color
        overlay[mask_bin == 1] = (
            ALPHA_SEG * np.array(color) +
            (1 - ALPHA_SEG) * frame[mask_bin == 1]
        ).astype(np.uint8)

        # 輪郭線を追加
        contours, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, color, 2)

    return overlay


# ══════════════════════════════════════════════════════════════════════════════
#  ミニマップ (フルコート横向き: court_lines() を使用)
# ══════════════════════════════════════════════════════════════════════════════
def court_to_mm(cx, cy):
    """
    コート座標 (cx: ±750, cy: 0-2864) → ミニマップピクセル (横向きフルコート)
    横: cy=0(ニアエンド) → 左端  cy=2864(ファーエンド) → 右端
    縦: cx=-750 → 上端  cx=+750 → 下端
    """
    mx = int(np.clip(cy * MM_SCALE, 0, MM_W - 1))
    my = int(np.clip((cx + COURT_W) * MM_SCALE, 0, MM_H - 1))
    return mx, my


def _draw_court_half(mm, offset_y=0, flip=False):
    """
    court_lines() を使って半コートをミニマップに描画。
    offset_y: コートY座標のオフセット (near=0, far=COURT_L)
    flip: True のときY座標を反転（ファー側は鏡像）
    """
    LINE_COLOR = (200, 200, 200)
    for _, pts in court_lines():
        pxpts = []
        for p in pts:
            cx, cy_half = p[0], p[1]
            # ファー側: Y=COURT_L が遠エンドライン、cy_halfを反転
            cy = (COURT_FULL_L - cy_half) if flip else cy_half
            pxpt = court_to_mm(cx, cy)
            if 0 <= pxpt[0] < MM_W and 0 <= pxpt[1] < MM_H:
                pxpts.append(pxpt)
            else:
                if pxpts:
                    pxpts.append(None)
        for i in range(len(pxpts) - 1):
            if pxpts[i] is not None and pxpts[i+1] is not None:
                cv2.line(mm, pxpts[i], pxpts[i+1], LINE_COLOR, 1, cv2.LINE_AA)


def build_minimap_base():
    """フルコートのミニマップ背景を court_lines() で描画"""
    mm = np.full((MM_H, MM_W, 3), (20, 90, 20), dtype=np.uint8)

    # ニアハーフ (cy: 0 → COURT_L、左半分)
    _draw_court_half(mm, flip=False)
    # ファーハーフ (cy: COURT_L → COURT_FULL_L、右半分、鏡像)
    _draw_court_half(mm, flip=True)

    # ハーフコートライン
    hx = court_to_mm(0, COURT_L)[0]
    cv2.line(mm, (hx, 0), (hx, MM_H), (200, 200, 200), 1, cv2.LINE_AA)

    # バスケット (ニア・ファー)
    for basket_cy in [BASKET_Y, COURT_FULL_L - BASKET_Y]:
        bpt = court_to_mm(0, basket_cy)
        cv2.circle(mm, bpt, max(2, int(4 * MM_SCALE * 100)), (0, 60, 220), -1)

    return mm


MM_BASE = build_minimap_base()


def draw_minimap(frame, player_tracks, ball_px, H_c2i):
    """ミニマップを右下に重ねる"""
    mm = MM_BASE.copy()
    fH, fW = frame.shape[:2]

    # H_c2i の逆 (image → court near-half coords)
    H_i2c = None
    if H_c2i is not None:
        try:
            H_i2c = np.linalg.inv(H_c2i)
        except Exception:
            pass

    def proj_to_mm(px, py):
        if H_i2c is None:
            return None
        pt = np.array([[[float(px), float(py)]]], dtype=np.float64)
        out = cv2.perspectiveTransform(pt, H_i2c)
        cx, cy = float(out[0, 0, 0]), float(out[0, 0, 1])
        # ニアハーフの範囲外は除外
        if abs(cx) > COURT_W + 50 or cy < -50 or cy > COURT_L + 50:
            return None
        mpt = court_to_mm(cx, cy)
        if 0 <= mpt[0] < MM_W and 0 <= mpt[1] < MM_H:
            return mpt
        return None

    # 選手をプロット
    for tid, bbox, team in player_tracks:
        fx = (bbox[0] + bbox[2]) / 2
        fy = bbox[3]   # 足元
        mpt = proj_to_mm(fx, fy)
        if mpt is None:
            continue
        color = TEAM_BGR.get(team, TEAM_BGR[-1])
        cv2.circle(mm, mpt, 5, (0, 0, 0), -1)
        cv2.circle(mm, mpt, 4, color, -1)
        cv2.putText(mm, str(tid % 100), (mpt[0]+4, mpt[1]-2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.26, (255, 255, 255), 1)

    # ボールをプロット
    if ball_px is not None:
        mpt = proj_to_mm(ball_px[0], ball_px[1])
        if mpt is not None:
            cv2.circle(mm, mpt, 4, (0, 0, 0), -1)
            cv2.circle(mm, mpt, 3, BALL_BGR, -1)

    # 右下に合成
    x0 = fW - MM_W - MM_PAD
    y0 = fH - MM_H - MM_PAD
    cv2.rectangle(frame, (x0-2, y0-14), (fW - MM_PAD + 2, fH - MM_PAD + 2),
                  (0, 0, 0), -1)
    cv2.putText(frame, "FULL COURT MAP", (x0, y0 - 3),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (180, 180, 180), 1)
    frame[y0:y0+MM_H, x0:x0+MM_W] = mm
    cv2.rectangle(frame, (x0, y0), (x0+MM_W, y0+MM_H), (160, 160, 160), 1)
    return frame


# ══════════════════════════════════════════════════════════════════════════════
#  HUD
# ══════════════════════════════════════════════════════════════════════════════
def draw_hud(frame, ts, n_white, n_navy, n_ref, ball_ok, pt3_r, using_orb):
    mm, ss = int(ts//60), int(ts%60)
    orb_tag = "[ORB]" if using_orb else "[ANN]"
    text = (f"t={mm}:{ss:02d}  White={n_white}  Navy={n_navy}  Ref={n_ref}"
            f"  Ball={'YES' if ball_ok else 'NO'}  3PT={pt3_r:.0f}cm  {orb_tag}")
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 30), (0,0,0), -1)
    cv2.putText(frame, text, (8, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255,255,255), 1)


# ══════════════════════════════════════════════════════════════════════════════
#  メイン
# ══════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sec",  type=float, default=300.0)
    parser.add_argument("--sam3", type=str,   default="ball_positions_sam3_300s.json")
    args = parser.parse_args()

    # SAM3ボール位置
    print(f"Loading SAM3: {args.sam3}")
    with open(args.sam3) as f:
        raw = json.load(f)
    sam3_ball = {int(k): (v[0], v[1]) if v else None for k, v in raw.items()}
    print(f"  {sum(1 for v in sam3_ball.values() if v)}/{len(sam3_ball)} frames with ball")

    cap = cv2.VideoCapture(VIDEO)
    fps = cap.get(cv2.CAP_PROP_FPS)
    W   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    VH  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_frames = min(int(args.sec * fps), int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    print(f"Video: {W}×{VH} @ {fps:.2f}fps  {n_frames} frames ({args.sec:.0f}s)")

    # アノテーション読み込み
    print("Loading annotations ...")
    ann_map = load_annotations(ANN_JSON, fps)
    print(f"  {len(ann_map)} annotation frames")

    # RANSAC 3PT半径を事前計算
    print("Pre-computing RANSAC 3PT radii ...")
    radii = precompute_ransac(ann_map, cap, fps)
    print(f"  Frames: {sorted(radii.keys())}")

    # ORBホモグラフィートラッカーを初期化
    print("Initializing ORB tracker ...")
    orb_tracker = HomographyTracker()
    for fi, (H_inv, pts) in ann_map.items():
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ret, frame_ann = cap.read()
        if ret:
            orb_tracker.add_reference(fi, frame_ann, H_inv)
    print(f"  {len(orb_tracker.refs)} reference frames cached")

    # モデル読み込み
    print("Loading models ...")
    det_model = YOLO(MODEL_DET)
    seg_model = YOLO(MODEL_SEG)
    tracker   = sv.ByteTrack(
        minimum_matching_threshold=0.8,
        minimum_consecutive_frames=1,
        lost_track_buffer=90,
    )
    team_votes = defaultdict(list)

    # 出力動画
    sec_tag  = int(args.sec)
    out_path = OUT_DIR / f"full_detection_{sec_tag}s.mp4"
    writer   = cv2.VideoWriter(str(out_path),
                               cv2.VideoWriter_fourcc(*"mp4v"),
                               fps, (W, VH))
    print(f"Output: {out_path}")

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    orb_fail_count = 0

    for fi in range(n_frames):
        ret, frame = cap.read()
        if not ret:
            break
        ts = fi / fps

        # ── ホモグラフィー (ORBトラッキング) ────────────────────────────────
        H_c2i_fallback, pts_list = get_nearest_ann(ann_map, fi)
        H_c2i   = orb_tracker.get_H_c2i(fi, frame)
        using_orb = (H_c2i is not None and H_c2i is not H_c2i_fallback)
        if H_c2i is None:
            H_c2i = H_c2i_fallback

        pt3_r = get_nearest_radius(radii, fi)

        # ── コートライン描画 ─────────────────────────────────────────────────
        if H_c2i is not None:
            draw_court(frame, H_c2i, pt3_r)

        # ── YOLO Detection + ByteTrack ───────────────────────────────────────
        det_res = det_model.predict(frame, conf=CONF_DET, verbose=False)[0]
        seg_res = seg_model.predict(frame, conf=CONF_SEG, classes=[0], verbose=False)

        player_dets, ref_bboxes = [], []
        for box in det_res.boxes:
            cls  = int(box.cls[0])
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].cpu().numpy()
            if cls == CLS_PLAYER and conf >= CONF_DET:
                player_dets.append((xyxy, conf))
            elif cls == CLS_REF and conf >= 0.3:
                ref_bboxes.append(xyxy)

        if player_dets:
            boxes_np = np.array([d[0] for d in player_dets])
            confs_np = np.array([d[1] for d in player_dets])
            sv_det   = sv.Detections(xyxy=boxes_np, confidence=confs_np,
                                      class_id=np.zeros(len(player_dets), dtype=int))
            tracks   = tracker.update_with_detections(sv_det)
        else:
            tracks = sv.Detections.empty()

        # 選手のチーム分類
        player_tracks = []   # [(tid, bbox, team)]
        for i in range(len(tracks)):
            tid  = int(tracks.tracker_id[i])
            bbox = tracks.xyxy[i]
            team = classify_team(frame, bbox)
            team_votes[tid].append(team)
            votes  = [t for t in team_votes[tid][-20:] if t in (1, 2)]
            stable = max(set(votes), key=votes.count) if votes else -1
            player_tracks.append((tid, bbox, stable))

        # ── セグメンテーション描画 ────────────────────────────────────────────
        frame = apply_seg_masks(frame, seg_res, player_tracks, {})

        # 審判はバウンディングボックスのまま
        for bbox in ref_bboxes:
            x1, y1, x2, y2 = map(int, bbox)
            cv2.rectangle(frame, (x1,y1), (x2,y2), REF_BGR, 2, cv2.LINE_AA)
            cv2.putText(frame, "REF", (x1, y1-4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, REF_BGR, 1)

        # ── SAM3 ボール描画 ──────────────────────────────────────────────────
        ball = sam3_ball.get(fi)
        if ball is not None:
            bx, by = int(ball[0]), int(ball[1])
            cv2.circle(frame, (bx, by), 14, (0,0,0),    -1)
            cv2.circle(frame, (bx, by), 12, BALL_BGR,    -1)
            cv2.circle(frame, (bx, by), 12, (255,255,255), 2)

        # ── ミニマップ ───────────────────────────────────────────────────────
        draw_minimap(frame, player_tracks, ball, H_c2i)

        # ── HUD ─────────────────────────────────────────────────────────────
        n_white = sum(1 for _, _, t in player_tracks if t == 1)
        n_navy  = sum(1 for _, _, t in player_tracks if t == 2)
        draw_hud(frame, ts, n_white, n_navy, len(ref_bboxes),
                 ball is not None, pt3_r, using_orb)

        writer.write(frame)

        if fi % int(fps * 30) == 0:
            pct = fi / n_frames * 100
            print(f"  [{pct:5.1f}%] t={ts:.0f}s  W={n_white} N={n_navy}"
                  f"  Ref={len(ref_bboxes)}  ball={'Y' if ball else 'N'}"
                  f"  orb={'OK' if using_orb else '-'}")

    cap.release()
    writer.release()
    size_mb = out_path.stat().st_size / 1e6
    print(f"\nDone: {out_path}  ({size_mb:.1f} MB)")


if __name__ == '__main__':
    main()

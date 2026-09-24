"""
最初の30秒の動画にコートグリッドをオーバーレイして出力動画を生成する

出力:
  outputs/court_detect_30s.mp4   コートグリッドオーバーレイ動画
"""

import json, os
import numpy as np
import cv2

VIDEO   = "data/videos/game_EE1swQMsXJc_720p.mp4"
ANNFILE = "outputs/annotations.json"
OUTDIR  = "outputs"
OUT_VID = os.path.join(OUTDIR, "court_detect_30s.mp4")

DURATION_S = 30     # 最初の何秒を処理するか
PROC_EVERY = 1      # フレームを何枚おきに処理するか（1=全フレーム、3=10fps相当）

# FIBA 半コート座標 → pixel（コートライン逆投影用）
SCALE = 0.45
COURT_W, COURT_H = 1500, 1400
BEV_W = int(COURT_W * SCALE)
BEV_H = int(COURT_H * SCALE)

def c2p(cx, cy):
    return (int((cx + 750) * SCALE), int((COURT_H - cy) * SCALE))

# ── アノテーション読み込み & ホモグラフィ構築 ─────────────────────
with open(ANNFILE) as f:
    data = json.load(f)

anns_by_sec = {}
for k, v in data.items():
    if ":basket" in k or not isinstance(v, list):
        continue
    sec = int(k.replace("frame_","").replace("s.jpg",""))
    # ring はホモグラフィから除外（コートライン点のみで計算）
    line_pts = [a for a in v if a["img"] is not None and a["id"] != "ring"]
    ring_ann  = next((a for a in v if a["id"] == "ring" and a["img"] is not None), None)
    if len(line_pts) < 4:
        continue
    src = np.float32([[a["img"][0], a["img"][1]] for a in line_pts])
    dst = np.float32([list(c2p(a["court"][0], a["court"][1])) for a in line_pts])
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    if H is None:
        continue
    # 再投影誤差
    proj = cv2.perspectiveTransform(src.reshape(-1,1,2), H).reshape(-1,2)
    err  = np.linalg.norm(proj - dst, axis=1).mean()
    # ring アノテーションがあればそのピクセル座標を保存
    ring_px = tuple(ring_ann["img"]) if ring_ann else None
    anns_by_sec[sec] = {"H": H, "err": err, "n": len(line_pts), "ring_px": ring_px}

sorted_secs = sorted(anns_by_sec.keys())
print(f"ホモグラフィ構築済み: {sorted_secs}")

def get_H_for_sec(t):
    """指定秒に最も近いアノテーションのHを返す（誤差<25pxを優先）"""
    best_sec = min(sorted_secs, key=lambda s: abs(s - t) + (10 if anns_by_sec[s]["err"] > 25 else 0))
    a = anns_by_sec[best_sec]
    return a["H"], best_sec, a["err"], a["ring_px"]

# ── コートライン描画ヘルパー ──────────────────────────────────────
COURT_LINES_PTS = [
    # (x1,y1,x2,y2) in FIBA
    (-750,0, 750,0),       # エンドライン
    (-750,1400, 750,1400), # センターライン
    (-750,580, 750,580),   # FTライン
    (-245,0, -245,580),    # ファーレーン
    ( 245,0,  245,580),    # ニアレーン
    (-750,0, -750,1400),   # ファーサイドライン
    ( 750,0,  750,1400),   # ニアサイドライン
]
BASKET_PX = c2p(0, 160)

def project_court_on_frame(frame, H_inv, ring_px=None):
    """コートラインを元フレームへ逆投影して描画"""
    out = frame.copy()
    h, w = frame.shape[:2]
    color_map = {
        (-750,0,750,0):    (0,255,180),   # エンドライン
        (-750,1400,750,1400): (0,200,255), # センターライン
        (-750,580,750,580): (0,200,100),  # FTライン
        (-245,0,-245,580):  (0,160,80),
        (245,0,245,580):    (0,160,80),
        (-750,0,-750,1400): (0,180,255),
        (750,0,750,1400):   (0,180,255),
    }
    for seg in COURT_LINES_PTS:
        x1,y1,x2,y2 = seg
        pts = np.float32([list(c2p(x1,y1)), list(c2p(x2,y2))]).reshape(-1,1,2)
        inv = cv2.perspectiveTransform(pts, H_inv).reshape(-1,2)
        p1 = (int(inv[0,0]), int(inv[0,1]))
        p2 = (int(inv[1,0]), int(inv[1,1]))
        if all(-200<p<2000 for p in [p1[0],p1[1],p2[0],p2[1]]):
            col = color_map.get(seg, (0,200,100))
            cv2.line(out, p1, p2, col, 2, cv2.LINE_AA)
    # バスケット: ring アノテーションがあればそのまま使用、なければホモグラフィで推定
    if ring_px is not None:
        bx, by = ring_px
    else:
        bk = np.float32([[BASKET_PX[0], BASKET_PX[1]]]).reshape(-1,1,2)
        bk_inv = cv2.perspectiveTransform(bk, H_inv).reshape(-1,2)
        bx, by = int(bk_inv[0,0]), int(bk_inv[0,1])
    if 0<=bx<w and 0<=by<h:
        cv2.circle(out, (bx,by), 12, (0,100,255), -1)
        cv2.circle(out, (bx,by), 12, (255,255,255), 2)
    return out

# ── 動画処理 ─────────────────────────────────────────────────────
cap = cv2.VideoCapture(VIDEO)
fps  = cap.get(cv2.CAP_PROP_FPS)
w    = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h    = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
total_frames = int(DURATION_S * fps)

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out_vid = cv2.VideoWriter(OUT_VID, fourcc, fps/PROC_EVERY, (w, h))

print(f"処理: {total_frames} frames ({DURATION_S}s @ {fps:.0f}fps), PROC_EVERY={PROC_EVERY}")

frame_idx = 0
cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

prev_H_src = None
while True:
    ret, frame = cap.read()
    if not ret or frame_idx >= total_frames:
        break

    if frame_idx % PROC_EVERY == 0:
        t_sec = frame_idx / fps

        H, src_sec, err, ring_px = get_H_for_sec(t_sec)
        H_inv = np.linalg.inv(H)

        # 元フレームにコートグリッドをオーバーレイ
        overlay = project_court_on_frame(frame, H_inv, ring_px)

        # ステータスラベル
        status_col = (0,220,100) if err < 15 else (0,180,255) if err < 30 else (0,100,255)
        label = f"t={t_sec:.1f}s  H from {src_sec}s  reproj={err:.1f}px"
        cv2.putText(overlay, label, (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 3)
        cv2.putText(overlay, label, (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_col, 1)
        out_vid.write(overlay)

        if frame_idx % int(fps*5) == 0:
            print(f"  {frame_idx:4d}/{total_frames}  t={t_sec:.1f}s  src={src_sec}s  err={err:.1f}px")

    frame_idx += 1

cap.release()
out_vid.release()
print(f"\n✓ {OUT_VID}")

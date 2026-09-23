"""
アノテーションからホモグラフィを計算してコート俯瞰図を生成する

出力:
  outputs/projection/  各フレームの俯瞰図 + 元画像オーバーレイ
  outputs/projection/summary.txt  再投影誤差レポート
"""

import json, os, sys
import numpy as np
import cv2

ANNOTATIONS = "outputs/annotations.json"
FRAME_DIR   = "outputs/annotation_frames"
OUTPUT_DIR  = "outputs/projection"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── FIBA 半コート寸法 (cm) ────────────────────────────────────────
# x: -750 〜 +750、y: 0 (エンドライン) 〜 1400 (センターライン)
COURT_W, COURT_H = 1500, 1400
SCALE = 0.40          # 1 cm = 0.4 px → 600 × 560 px
OUT_W  = int(COURT_W * SCALE)
OUT_H  = int(COURT_H * SCALE)

def c2p(cx, cy):
    """FIBA court (cm) → 出力画像 pixel"""
    return (int((cx + 750) * SCALE), int((COURT_H - cy) * SCALE))

def draw_court_lines(img):
    green  = (40, 180, 40)
    lgr    = (20, 100, 20)
    # コート外枠
    cv2.rectangle(img, c2p(-750, 0), c2p(750, 1400), green, 2)
    # センターライン
    cv2.line(img, c2p(-750, 1400), c2p(750, 1400), (80, 220, 80), 2)
    # FTライン
    cv2.line(img, c2p(-750, 580), c2p(750, 580), lgr, 1)
    # レーン
    cv2.line(img, c2p(-245, 0), c2p(-245, 580), lgr, 1)
    cv2.line(img, c2p( 245, 0), c2p( 245, 580), lgr, 1)
    # バスケット
    cv2.circle(img, c2p(0, 160), 8, (0, 100, 255), -1)
    cv2.circle(img, c2p(0, 160), 8, (255,255,255), 1)
    return img

def compute_H(anns):
    """img → 出力画像 pixel のホモグラフィを計算"""
    src, dst = [], []
    for a in anns:
        if a["img"] is None:
            continue
        ix, iy = a["img"]
        cx, cy = a["court"]
        src.append([ix, iy])
        dst.append(list(c2p(cx, cy)))
    if len(src) < 4:
        return None, 0, 0
    src_np = np.float32(src)
    dst_np = np.float32(dst)
    H, mask = cv2.findHomography(src_np, dst_np, cv2.RANSAC, 5.0)
    if H is None:
        return None, 0, 0
    # 再投影誤差
    proj = cv2.perspectiveTransform(src_np.reshape(-1,1,2), H).reshape(-1,2)
    errs = np.linalg.norm(proj - dst_np, axis=1)
    n_inliers = int(mask.sum()) if mask is not None else 0
    return H, errs.mean(), n_inliers

def overlay_court_on_frame(frame, H_inv):
    """
    コートの格子線ポイントを元フレームに再投影してオーバーレイ
    H_inv: 出力画像pixel → frame pixel
    """
    out = frame.copy()
    # コート点を元画像へ逆変換して描画
    court_pts = []
    for cy in range(0, 1401, 100):
        for cx in range(-750, 751, 100):
            court_pts.append(list(c2p(cx, cy)))
    pts_np = np.float32(court_pts).reshape(-1,1,2)
    frame_pts = cv2.perspectiveTransform(pts_np, H_inv).reshape(-1,2)
    for p in frame_pts:
        x, y = int(p[0]), int(p[1])
        h, w = frame.shape[:2]
        if 0 <= x < w and 0 <= y < h:
            cv2.circle(out, (x, y), 2, (0, 255, 0), -1)
    # ライン
    lines = [
        [c2p(-750,0),c2p(750,0)],
        [c2p(-750,580),c2p(750,580)],
        [c2p(-750,1400),c2p(750,1400)],
        [c2p(-245,0),c2p(-245,580)],
        [c2p(245,0),c2p(245,580)],
    ]
    for p1, p2 in lines:
        pts2d = np.float32([p1, p2]).reshape(-1,1,2)
        inv_pts = cv2.perspectiveTransform(pts2d, H_inv).reshape(-1,2)
        x1,y1 = int(inv_pts[0,0]), int(inv_pts[0,1])
        x2,y2 = int(inv_pts[1,0]), int(inv_pts[1,1])
        cv2.line(out, (x1,y1), (x2,y2), (0,220,80), 2)
    # アノテーション点も描画
    return out

def main():
    with open(ANNOTATIONS) as f:
        data = json.load(f)

    # バスケット情報を分離
    baskets = {k.replace(":basket",""):v for k,v in data.items() if ":basket" in k}
    frames_data = {k:v for k,v in data.items() if ":basket" not in k and isinstance(v, list)}

    summary_lines = ["Frame                  | pts | inliers | reproj_err(px) | status"]
    summary_lines.append("-"*70)

    for fname, anns in sorted(frames_data.items()):
        fpath = os.path.join(FRAME_DIR, fname)
        if not os.path.exists(fpath):
            continue
        valid = [a for a in anns if a["img"] is not None]
        if len(valid) < 4:
            summary_lines.append(f"{fname:<22} | {len(valid):>3} | {'N/A':>7} | {'N/A':>14} | SKIP (pts<4)")
            continue

        H, err, inliers = compute_H(anns)
        if H is None:
            summary_lines.append(f"{fname:<22} | {len(valid):>3} | {'FAIL':>7} | {'N/A':>14} | HOMOGRAPHY_FAIL")
            continue

        status = "OK" if err < 15 else "WARN"
        summary_lines.append(f"{fname:<22} | {len(valid):>3} | {inliers:>7} | {err:>14.1f} | {status}")

        frame = cv2.imread(fpath)
        if frame is None:
            continue

        # 1. 俯瞰図 (bird's eye view)
        bev = np.zeros((OUT_H, OUT_W, 3), dtype=np.uint8)
        bev[:] = (15, 35, 15)
        warped = cv2.warpPerspective(frame, H, (OUT_W, OUT_H))
        mask = np.any(warped > 0, axis=2)
        bev[mask] = warped[mask]
        draw_court_lines(bev)

        # アノテーション点を俯瞰図に描画
        colors = [(0,220,100),(0,180,255),(255,160,0),(180,0,255),
                  (0,255,220),(255,100,0),(100,255,0),(255,0,100),
                  (100,100,255),(255,220,0)]
        for i, a in enumerate(anns):
            if a["img"] is None: continue
            cx, cy = a["court"]
            px, py = c2p(cx, cy)
            col = colors[i % len(colors)]
            cv2.circle(bev, (px, py), 6, col, -1)
            cv2.circle(bev, (px, py), 6, (255,255,255), 1)

        # 2. 元画像オーバーレイ
        H_inv = np.linalg.inv(H)
        overlay = overlay_court_on_frame(frame, H_inv)

        # アノテーション点を元画像に描画
        for i, a in enumerate(anns):
            if a["img"] is None: continue
            ix, iy = a["img"]
            col = colors[i % len(colors)]
            cv2.circle(overlay, (ix, iy), 8, col, -1)
            cv2.circle(overlay, (ix, iy), 8, (255,255,255), 2)
            cv2.putText(overlay, a["id"].split("_")[0], (ix+10, iy-5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,255), 1)

        # タイトル
        h_ov, w_ov = overlay.shape[:2]
        bev_resized = cv2.resize(bev, (OUT_W*2, OUT_H*2))
        bev_h, bev_w = bev_resized.shape[:2]

        # 横に並べる（高さを合わせる）
        target_h = max(h_ov, bev_h)
        combined_left  = cv2.copyMakeBorder(overlay, 0, max(0,target_h-h_ov), 0, 0, cv2.BORDER_CONSTANT, value=(20,20,20))
        combined_right = cv2.copyMakeBorder(bev_resized, 0, max(0,target_h-bev_h), 0, 0, cv2.BORDER_CONSTANT, value=(15,35,15))
        combined = np.hstack([combined_left, combined_right])

        # タイトルバー
        basket = baskets.get(fname, "?")
        label = f"{fname}  basket={basket}  pts={len(valid)}  reproj={err:.1f}px  {status}"
        cv2.putText(combined, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220,220,220), 1)

        out_path = os.path.join(OUTPUT_DIR, fname.replace(".jpg", "_proj.jpg"))
        cv2.imwrite(out_path, combined)
        print(f"  {fname} → reproj {err:.1f}px ({inliers}/{len(valid)} inliers) [{status}]")

    # サマリー
    summary_text = "\n".join(summary_lines)
    with open(os.path.join(OUTPUT_DIR, "summary.txt"), "w") as f:
        f.write(summary_text)
    print("\n" + summary_text)
    print(f"\n→ {OUTPUT_DIR}/ に出力しました")

if __name__ == "__main__":
    main()

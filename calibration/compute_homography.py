"""
アノテーション済みキーポイントからホモグラフィー行列 H を計算する。

annotations.json 形式 (新):
  {fname: [{id, img:[x,y], court:[cx,cy]}, ...]}
  img=null のキーポイントは除外して計算。

FIBA 半コート座標系 (cm):
  原点 = エンドライン中央
  x : -750（left sideline） ～ +750（right sideline）
  y :    0（endline）     ～ 1400（center line）
"""

import cv2
import json
import numpy as np
import os

ANNOTATIONS = "outputs/annotations.json"
FRAMES_DIR  = "outputs/annotation_frames"
OUTPUT_DIR  = "outputs/homography"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def compute_H(img_pts, court_pts):
    if len(img_pts) < 4:
        return None, None
    H, mask = cv2.findHomography(img_pts, court_pts,
                                  method=cv2.RANSAC,
                                  ransacReprojThreshold=30.0)
    return H, mask


def draw_result(img, img_pts, court_pts, mask, fname):
    vis = img.copy()
    for i, (ip, cp) in enumerate(zip(img_pts, court_pts)):
        px, py = int(ip[0]), int(ip[1])
        inlier = bool(mask[i][0]) if mask is not None else True
        color  = (0, 220, 0) if inlier else (0, 0, 255)
        cv2.circle(vis, (px, py), 7, color, -1)
        cv2.circle(vis, (px, py), 8, (255, 255, 255), 1)
        cv2.putText(vis, f"({int(cp[0])},{int(cp[1])})",
                    (px+8, py-6), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1)
    n_in = int(mask.sum()) if mask is not None else len(img_pts)
    cv2.putText(vis, f"pts={len(img_pts)} inlier={n_in}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imwrite(os.path.join(OUTPUT_DIR, fname), vis)


with open(ANNOTATIONS) as f:
    data = json.load(f)

results = {}

print("Computing homography...\n")

for fname, anns in sorted(data.items()):
    if not isinstance(anns, list) or not anns:
        continue

    # img=null のキーポイントを除外して対応点を抽出
    img_pts_list   = []
    court_pts_list = []
    for kp in anns:
        if kp.get('img') is None:
            continue
        img_pts_list.append(kp['img'])
        court_pts_list.append(kp['court'])

    if len(img_pts_list) < 4:
        print(f"  [WARN] {fname}: valid KPs={len(img_pts_list)} < 4")
        continue

    img_pts   = np.float32(img_pts_list)
    court_pts = np.float32(court_pts_list)

    H, mask = compute_H(img_pts, court_pts)
    if H is None:
        print(f"  [FAIL] {fname}: findHomography failed")
        continue

    n_in = int(mask.sum()) if mask is not None else len(img_pts)

    # 再投影誤差
    proj = cv2.perspectiveTransform(img_pts.reshape(-1, 1, 2), H).reshape(-1, 2)
    err  = np.linalg.norm(proj - court_pts, axis=1)

    print(f"  {fname}: KPs={len(img_pts)}  inlier={n_in}"
          f"  reproj_err mean={err.mean():.1f}cm  max={err.max():.1f}cm")

    # inlier のみの誤差も表示
    if mask is not None:
        inlier_mask = mask.ravel().astype(bool)
        if inlier_mask.sum() >= 4:
            err_in = err[inlier_mask]
            print(f"    inlier only: mean={err_in.mean():.1f}cm  max={err_in.max():.1f}cm")

    img_path = os.path.join(FRAMES_DIR, fname)
    img = cv2.imread(img_path)
    if img is not None:
        draw_result(img, img_pts, court_pts, mask, fname)

    results[fname] = H.tolist()

H_path = os.path.join(OUTPUT_DIR, "homography.json")
with open(H_path, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\nDone: {len(results)} frames -> {H_path}")

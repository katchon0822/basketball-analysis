#!/usr/bin/env python3
"""
auto_calibrate.py — KaliCalib による自動コートホモグラフィー推定

KaliCalib (DeepSportradar 2022) の ResNet+Heatmap モデルを使って、
単一フレームから H_court_to_image を自動推定する。

使い方:
  venv/bin/python3 auto_calibrate.py --video data/videos/game_2-1.mp4
  venv/bin/python3 auto_calibrate.py --image frame.jpg --out profile.json

座標変換:
  KaliCalib : X=0→2800 (near→far cm), Y=0→1500 (left→right cm)
  我々      : cx=−750→750 (left→right cm), cy=0→2864 (near→far cm)
  変換      : their_X = cy, their_Y = cx+750  (スケール差はfindHomographyで吸収)
"""

import sys, os, cv2, json, numpy as np, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "kalicalib"))

import torch
from calib3d.points import Point3D

# ── デバイス選択 (MPS → CPU) ────────────────────────────────────────────────
def _get_device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")

DEVICE = _get_device()
print(f"[auto_calibrate] device: {DEVICE}")

# ── KaliCalib のモデルロード (getModel を MPS/CPU 対応にパッチ) ──────────────
_KALI_DIR   = Path(__file__).parent / "kalicalib"
_MODEL_PATH = _KALI_DIR / "models" / "model_challenge.pth"

def load_kali_model():
    from kalicalib.model_resnet import makeModel
    model = makeModel().to(DEVICE)
    model.load_state_dict(
        torch.load(str(_MODEL_PATH), map_location=DEVICE)
    )
    model.eval()
    print(f"[auto_calibrate] KaliCalib model loaded ({sum(p.numel() for p in model.parameters()):,} params)")
    return model

# ── 我々のコート座標系でのランドマーク ────────────────────────────────────────
# (cx_cm, cy_cm) … cx: left-right −750→+750, cy: near→far 0→FULL_Y
# KaliCalib 座標への変換: X = cy, Y = cx + 750
FIBA_LEN = 2800   # KaliCalib FIELD_LENGTH (cm)
FIBA_WID = 1500   # KaliCalib FIELD_WIDTH  (cm)

OUR_SIDELINE = 750
OUR_FULL_Y   = 2864
OUR_HALF_Y   = 1432
OUR_FT_Y     = 580
OUR_LANE_X   = 245

# フルコート主要ランドマーク (our座標)
_LANDMARKS_OUR = np.float32([
    # near half
    [-OUR_SIDELINE,  0],          # near-left corner
    [ OUR_SIDELINE,  0],          # near-right corner
    [-OUR_LANE_X,    OUR_FT_Y],   # near FT × left lane
    [ OUR_LANE_X,    OUR_FT_Y],   # near FT × right lane
    [-OUR_SIDELINE,  OUR_HALF_Y], # center × left sideline
    [ OUR_SIDELINE,  OUR_HALF_Y], # center × right sideline
    # far half (mirror)
    [-OUR_LANE_X,    OUR_FULL_Y - OUR_FT_Y],
    [ OUR_LANE_X,    OUR_FULL_Y - OUR_FT_Y],
    [-OUR_SIDELINE,  OUR_FULL_Y],
    [ OUR_SIDELINE,  OUR_FULL_Y],
])


def our_to_kali_3d(cx_cm, cy_cm, z_cm=0.0):
    """我々の (cx,cy) → KaliCalib 3D (X,Y,Z)"""
    X = cy_cm * FIBA_LEN / OUR_FULL_Y   # near→far スケール合わせ
    Y = cx_cm + OUR_SIDELINE             # centering: −750→0, +750→1500
    return float(X), float(Y), float(z_cm)


def derive_H_from_calib(calib, our_landmarks=_LANDMARKS_OUR):
    """
    Calib オブジェクトを使って our座標 → image座標 の H行列を導出する。

    1. our_landmarks を KaliCalib 3D に変換
    2. calib.project_3D_to_2D() で image座標に投影
    3. findHomography で H を計算
    """
    pts_3d = []
    for (cx, cy) in our_landmarks:
        X, Y, Z = our_to_kali_3d(cx, cy)
        pts_3d.append([X, Y, Z])
    pts_3d = np.array(pts_3d, dtype=np.float64)

    # calib3d の Point3D は shape (3, N) を期待
    pts_3d_T = Point3D(pts_3d.T)
    pts_2d   = calib.project_3D_to_2D(pts_3d_T).T   # (N, 2)

    our_pts  = our_landmarks.astype(np.float32)
    img_pts  = pts_2d.astype(np.float32)

    H, mask = cv2.findHomography(our_pts, img_pts, cv2.RANSAC, 25.0)
    inliers = int(mask.sum()) if mask is not None else 0
    return H, inliers, img_pts


def _get_field_points():
    """
    KaliCalib フィールドキーポイント (3D) をインラインで定義。
    data.datasets.viewds の getFieldPoints() と同等 (バージョン非互換を回避)。
    FIELD_LENGTH=2800, FIELD_WIDTH=1500 (cm)
    """
    FIELD_LENGTH, FIELD_WIDTH = 2800, 1500
    points = []
    u0, r_inc, u, s = 175, 30, 175, 0
    for _ in range(7):
        for i in range(13):
            points.append([i * FIELD_LENGTH / 12, FIELD_WIDTH - s, 0])
        s += u; u += r_inc
    # baskets (raised Z=-305cm = 3.05m above floor)
    bx = 120 + 15 + 45 / 2   # 157.5
    points.append([bx, FIELD_WIDTH / 2, -305])
    points.append([FIELD_LENGTH - bx, FIELD_WIDTH / 2, -305])
    return np.array(points, dtype=float)

_FIELD_POINTS_3D = _get_field_points()
_FIELD_POINTS_2D = np.expand_dims(_FIELD_POINTS_3D[:, 0:2], axis=0)


def run_kali_inference(model, frame_bgr):
    """
    1フレームで KaliCalib 推定 → Calib オブジェクトを返す。
    Returns (calib, debug_img) or (None, debug_img) if failed.
    """
    import torchvision.transforms as T
    # data モジュールを経由せず直接インポート
    from modeling.example_camera_model import compute_camera_model

    from deepsport_utilities.calib import Calib
    from calib3d.points import Point2D, Point3D

    H_px, W = frame_bgr.shape[:2]
    IMG_W, IMG_H = 960, 540
    npImg = cv2.resize(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB), (IMG_W, IMG_H))

    tf = T.Compose([
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    img_t = tf(npImg).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        heatmaps = model(img_t)

    heatmaps_cpu = heatmaps.cpu()

    # ── estimateCalibHM をインライン実装 (data モジュール不要版) ──────────────
    from modeling.example_camera_model import MEAN_H

    out      = heatmaps_cpu[0].numpy()
    nbPoints = out.shape[0] - 1 - 2

    pixelScores    = np.swapaxes(out, 0, 2)
    pixelMaxScores = np.max(pixelScores, axis=2, keepdims=True)
    pixelMax       = (pixelScores == pixelMaxScores)
    pixelMap       = np.swapaxes(pixelMax, 0, 2).astype(np.uint8)
    pixelMap       = (out > 0) * pixelMap

    srcPoints, dstPoints = [], []
    for i in range(nbPoints):
        M = cv2.moments(pixelMap[i])
        if M["m00"] == 0:
            continue
        p = np.array([M["m01"] / M["m00"], M["m10"] / M["m00"]]) * 4
        pImg = [round(p[0]), round(p[1])]
        cv2.circle(npImg, (pImg[1], pImg[0]), 5, (255, 0, 0), -1)
        srcPoints.append(_FIELD_POINTS_2D[0][i])
        dstPoints.append(p[::-1])

    calib = Calib.from_P(np.array(MEAN_H), width=W, height=H_px)
    if len(srcPoints) >= 4:
        Hest, keptPoints = cv2.findHomography(
            np.array(srcPoints), np.array(dstPoints),
            cv2.RANSAC, ransacReprojThreshold=35, maxIters=2000,
        )
        if Hest is not None:
            srcPoints3d, dstPoints2d = [], []
            for i, kept in enumerate(keptPoints):
                if kept:
                    srcPoints3d.append(np.concatenate((srcPoints[i], [0])))
                    dstPoints2d.append(dstPoints[i])
            if len(dstPoints2d) > 5:
                new_calib = compute_camera_model(dstPoints2d, srcPoints3d, (H_px, W))
                # sanity check
                pts2d_c = Point2D(np.array([[W/4, H_px/2], [3*W/4, H_px/2]]).T)
                proj3d  = new_calib.project_2D_to_3D(pts2d_c, Z=0).T
                dist    = float(np.linalg.norm(proj3d[1] - proj3d[0]))
                if 100 < dist < 1800:
                    calib = new_calib
                else:
                    print(f"[auto_calibrate] sanity fail (dist={dist:.0f}), using MEAN_H")
    else:
        print(f"[auto_calibrate] only {len(srcPoints)} keypoints detected, using MEAN_H")

    return calib, npImg


def calibrate_frame(frame_bgr, model=None):
    """
    フレームから H_court_to_image を推定。

    Returns:
        H_c2i  : np.ndarray (3,3) or None
        inliers : int
        debug   : np.ndarray (debug image)
    """
    if model is None:
        model = load_kali_model()

    calib, debug_img = run_kali_inference(model, frame_bgr)
    if calib is None:
        return None, 0, debug_img

    H_c2i, inliers, img_pts = derive_H_from_calib(calib)
    if H_c2i is None:
        return None, 0, debug_img

    # デバッグ: 推定コート線を描画
    _draw_projected_court(debug_img, H_c2i, debug_img.shape[1], debug_img.shape[0])

    return H_c2i, inliers, debug_img


def _draw_projected_court(img, H_c2i, W, H_px):
    """H_court_to_image を使ってコート線を debug_img に描画"""
    def proj(cx, cy):
        pt  = np.array([[[float(cx), float(cy)]]], dtype=np.float64)
        out = cv2.perspectiveTransform(pt, H_c2i)
        return (int(out[0,0,0]), int(out[0,0,1]))
    def seg(x1,y1,x2,y2,col=(0,255,0),t=1):
        p1,p2 = proj(x1,y1),proj(x2,y2)
        if all(-W < p[0] < 2*W and -H_px < p[1] < 2*H_px for p in (p1,p2)):
            cv2.line(img,p1,p2,col,t,cv2.LINE_AA)

    SL = OUR_SIDELINE; HY = OUR_HALF_Y; FY = OUR_FULL_Y; FT = OUR_FT_Y; LX = OUR_LANE_X
    seg(-SL,0,SL,0,(0,255,0),2)
    seg(-SL,FY,SL,FY,(0,255,0),2)
    seg(-SL,0,-SL,FY,(0,255,0),2)
    seg(SL,0,SL,FY,(0,255,0),2)
    seg(-SL,HY,SL,HY,(0,200,255),1)
    seg(-LX,0,-LX,FT,(100,200,255)); seg(LX,0,LX,FT,(100,200,255))
    seg(-LX,FT,LX,FT,(100,200,255))
    seg(-LX,FY,-LX,FY-FT,(100,200,255)); seg(LX,FY,LX,FY-FT,(100,200,255))
    seg(-LX,FY-FT,LX,FY-FT,(100,200,255))


def calibrate_video(video_path, n_frames=5, model=None):
    """
    複数フレームで推定 → inliers 最大のものを採用。
    Returns (H_c2i, best_frame_idx, inliers_count)
    """
    if model is None:
        model = load_kali_model()

    cap   = cv2.VideoCapture(str(video_path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps   = cap.get(cv2.CAP_PROP_FPS) or 30

    # 10%〜80% の範囲で n_frames 均等サンプリング
    idxs = [int(total * (0.10 + 0.70 * i / (n_frames - 1))) for i in range(n_frames)]

    best_H, best_inliers, best_fi, best_debug = None, -1, 0, None

    for fi in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ret, frame = cap.read()
        if not ret:
            continue
        print(f"[auto_calibrate] frame {fi} / {total} …", end=" ", flush=True)
        H, inliers, debug = calibrate_frame(frame, model)
        print(f"inliers={inliers}")
        if inliers > best_inliers:
            best_H, best_inliers, best_fi, best_debug = H, inliers, fi, debug

    cap.release()
    return best_H, best_fi, best_inliers, best_debug


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video",  help="動画ファイルパス")
    ap.add_argument("--image",  help="単一フレーム画像パス")
    ap.add_argument("--out",    help="出力 venue profile JSON パス")
    ap.add_argument("--profile", help="既存プロファイルに H を上書き保存するパス")
    ap.add_argument("--n_frames", type=int, default=5, help="サンプリングフレーム数")
    ap.add_argument("--debug_out", help="デバッグ画像の保存先 (省略=表示なし)")
    args = ap.parse_args()

    model = load_kali_model()

    if args.image:
        frame = cv2.imread(args.image)
        H, inliers, debug = calibrate_frame(frame, model)
        fi = 0
    elif args.video:
        H, fi, inliers, debug = calibrate_video(args.video, args.n_frames, model)
    else:
        ap.print_help(); return

    if H is None:
        print("[auto_calibrate] 推定失敗 — フレームを変えてリトライしてください")
        return

    print(f"\n[auto_calibrate] 推定完了  inliers={inliers}  frame={fi}")
    print(f"H_court_to_image =\n{H}")

    # デバッグ画像保存
    if args.debug_out and debug is not None:
        dbg_bgr = cv2.cvtColor(debug, cv2.COLOR_RGB2BGR)
        cv2.imwrite(args.debug_out, dbg_bgr)
        print(f"デバッグ画像: {args.debug_out}")

    # プロファイルへの書き込み
    target = args.profile or args.out
    if target:
        path = Path(target)
        if path.exists():
            with open(path) as f: data = json.load(f)
        else:
            data = {}
        data["H_court_to_image"] = H.tolist()
        data["kali_inliers"]     = inliers
        data["kali_frame_idx"]   = fi
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"プロファイル更新: {path}")


if __name__ == "__main__":
    main()

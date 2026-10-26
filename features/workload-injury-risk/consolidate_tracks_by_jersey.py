"""ジャージ番号OCRで、断片化したトラックIDを「選手単位」に統合できるか検証する。

workload_profiles_0_70s.json の上位トラック（移動距離が長い=サンプルが多い）について、
トラック中央時刻のコート座標(cm)を、ホモグラフィーの逆行列でピクセル座標に戻し、
その位置を中心に元映像から選手クロップを切り出してジャージ番号OCRを実行する。

同じ番号・同じチームが複数トラックで検出されれば、それらを「同一選手」として
統合し、移動距離等を合算した本当の意味での選手別負荷プロファイルを作る。

前提: features/jersey-ocr/jersey_ocr.py のOCRはタイトな番号クロップで検証済み
(5/5)。ここでの逆変換クロップは番号領域を狙い撃ちできないラフなものなので、
成功率はパイロットより下がる前提で正直に報告する。
"""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "outputs"
FRAME_DIR = OUT_DIR / "id_consolidation_frames"
FRAME_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / "features" / "jersey-ocr"))
from jersey_ocr import read_jersey_number  # noqa: E402

VIDEO = ROOT / "data/videos/game_EE1swQMsXJc_720p.mp4"
CROP_W, CROP_H = 180, 260  # 選手上半身を広めに含むクロップ（番号領域を狙い撃ちできない前提）


def load_homographies(path):
    ann = json.load(open(path))
    hs = {}
    for k, pts in ann.items():
        if ":" in k:
            continue
        valid = [p for p in pts if p.get("img") is not None]
        if len(valid) < 4:
            continue
        sec = float(k.replace("frame_", "").replace("s.jpg", ""))
        img_pts = np.float32([p["img"] for p in valid])
        crt_pts = np.float32([p["court"] for p in valid])
        H, _ = cv2.findHomography(img_pts, crt_pts, cv2.RANSAC, 5.0)
        if H is not None:
            hs[sec] = H
    return dict(sorted(hs.items()))


def nearest_H(hs, t):
    secs = list(hs.keys())
    idx = min(range(len(secs)), key=lambda i: abs(secs[i] - t))
    return hs[secs[idx]]


def court_to_px(H, cx, cy):
    H_inv = np.linalg.inv(H)
    p = cv2.perspectiveTransform(np.float32([[[cx, cy]]]), H_inv)[0][0]
    return float(p[0]), float(p[1])


def extract_frame(ts, out_path):
    cmd = ["ffmpeg", "-y", "-ss", f"{ts:.3f}", "-i", str(VIDEO), "-frames:v", "1", "-q:v", "2", str(out_path)]
    subprocess.run(cmd, capture_output=True, check=True)


def main():
    hs = load_homographies(ROOT / "outputs/annotations.json")
    wl = json.load(open(OUT_DIR / "workload_profiles_0_70s.json"))
    tracks_by_dist = sorted(wl["tracks"], key=lambda t: -t["total_distance_m"])[:24]

    d = json.load(open(ROOT / "outputs/shot_player/tracking_300s.json"))
    traj = d["trajectories"]

    results = []
    for t in tracks_by_dist:
        tid = t["track_id"]
        pts = traj[tid]
        mid = pts[len(pts) // 2]
        H = nearest_H(hs, mid["ts"])
        px, py = court_to_px(H, mid["x"], mid["y"])

        frame_path = FRAME_DIR / f"track{tid}_t{mid['ts']:.2f}.jpg"
        try:
            extract_frame(mid["ts"], frame_path)
        except subprocess.CalledProcessError as e:
            results.append({"track_id": tid, "error": f"ffmpeg failed: {e}"})
            continue

        img = cv2.imread(str(frame_path))
        if img is None:
            results.append({"track_id": tid, "error": "frame read failed"})
            continue
        h, w = img.shape[:2]
        x0 = int(max(0, px - CROP_W / 2))
        y0 = int(max(0, py - CROP_H / 2))
        x1 = int(min(w, px + CROP_W / 2))
        y1 = int(min(h, py + CROP_H / 2))
        crop = img[y0:y1, x0:x1]
        crop_path = FRAME_DIR / f"track{tid}_crop.jpg"
        cv2.imwrite(str(crop_path), crop)

        number, conf, _ = read_jersey_number(crop) if crop.size > 0 else (None, 0.0, [])
        results.append({
            "track_id": tid, "team": t["team"], "ts": round(mid["ts"], 2),
            "court_cm": [round(mid["x"], 1), round(mid["y"], 1)],
            "px_estimate": [round(px, 1), round(py, 1)],
            "jersey_number": number, "confidence": conf,
            "total_distance_m": t["total_distance_m"],
            "crop_file": str(crop_path.relative_to(ROOT)),
        })
        print(f"track {tid} (team {t['team']}): number={number} conf={conf} dist={t['total_distance_m']}m")

    # グルーピング: 同じチーム×同じ番号は同一選手とみなす
    groups = {}
    for r in results:
        if r.get("jersey_number"):
            key = (r["team"], r["jersey_number"])
            groups.setdefault(key, []).append(r)

    consolidated = []
    for (team, num), members in groups.items():
        consolidated.append({
            "team": team, "jersey_number": num,
            "track_ids": [m["track_id"] for m in members],
            "n_tracks_merged": len(members),
            "total_distance_m": round(sum(m["total_distance_m"] for m in members), 1),
        })

    out = {
        "n_tracks_attempted": len(results),
        "n_ocr_success": sum(1 for r in results if r.get("jersey_number")),
        "results": results,
        "consolidated_players": consolidated,
    }
    json.dump(out, open(OUT_DIR / "id_consolidation_result.json", "w"), ensure_ascii=False, indent=2)
    print(f"\nOCR success: {out['n_ocr_success']}/{out['n_tracks_attempted']}")
    print(f"consolidated players (>=2 tracks merged): {sum(1 for c in consolidated if c['n_tracks_merged'] >= 2)}")
    for c in consolidated:
        print(f"  team{c['team']} #{c['jersey_number']}: tracks {c['track_ids']} -> {c['total_distance_m']}m combined")


if __name__ == "__main__":
    main()

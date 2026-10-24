"""シュート検出 × 選手トラッキングの紐付け（tracking_300s.json版）。

attribute_shots.py はMcByte++の生MOT出力（ピクセル座標+bbox）を前提にしているが、
McByte++検証で使った元フレームは残っておらず、再実行はM1ローカルで約63秒/フレーム
かかるため現実的ではない（150フレームで約2.6時間）。

そこで、既存のSAM3+ByteTrackパイプライン出力(tracking_300s.json)を使う。この
トラッキングは既に実コート座標(cm)に変換済み・チーム分類済みという利点がある一方、
選手IDが断片化している（5分間で397トラック）という制約を持つ。

手法:
  1. shots_300s.json のシュート位置(px, ピクセル空間)を、annotations.jsonの
     ホモグラフィーで実コート座標(cm)に変換する
  2. シュート時刻の前後0.5秒以内に位置記録があるトラックの中から、シュート位置に
     最も近いものをシューターと推定する
  3. tracking_300s.json に既に入っているチーム分類(player_team)をそのまま使う

前提: ホモグラフィーが手動アノテーションされている0〜70秒の区間のみ対象
（他の分析と同じ既知の制約）。

出力: outputs/shots_attributed.json
"""
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "outputs"
OUT_DIR.mkdir(exist_ok=True)

CALIB_END_S = 70.0
MATCH_WINDOW_S = 0.5  # シュート時刻の前後何秒以内の選手位置を候補にするか


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


def shot_px_to_court_cm(hs, ts, px):
    H = nearest_H(hs, ts)
    p = cv2.perspectiveTransform(np.float32([[px]]), H)[0][0]
    return float(p[0]), float(p[1])


def nearest_player(traj, player_team, ts, cx, cy, window=MATCH_WINDOW_S):
    best_tid, best_d = None, 1e9
    for tid, pts in traj.items():
        for p in pts:
            if abs(p["ts"] - ts) > window:
                continue
            d = float(np.hypot(p["x"] - cx, p["y"] - cy))
            if d < best_d:
                best_d, best_tid = d, tid
    if best_tid is None:
        return None
    return {"track_id": best_tid, "team": player_team.get(best_tid), "dist_cm": round(best_d, 1)}


def main():
    hs = load_homographies(ROOT / "outputs/annotations.json")
    shots = json.load(open(ROOT / "outputs/shot_player/shots_300s.json"))
    shots = [s for s in shots if s["ts"] <= CALIB_END_S]

    d = json.load(open(ROOT / "outputs/shot_player/tracking_300s.json"))
    traj, player_team = d["trajectories"], d["player_team"]

    results = []
    for s in shots:
        cx, cy = shot_px_to_court_cm(hs, s["ts"], s["px"])
        shooter = nearest_player(traj, player_team, s["ts"], cx, cy)
        results.append({
            "ts": round(s["ts"], 2),
            "ball_court_cm": [round(cx, 1), round(cy, 1)],
            "shooter": shooter,
        })

    matched = [r for r in results if r["shooter"] is not None]
    unmatched = len(results) - len(matched)
    dists = [r["shooter"]["dist_cm"] for r in matched]

    out = {
        "window_s": [0, CALIB_END_S],
        "match_window_s": MATCH_WINDOW_S,
        "n_shots": len(results),
        "n_matched": len(matched),
        "n_unmatched": unmatched,
        "shots": results,
    }
    out_path = OUT_DIR / "shots_attributed.json"
    json.dump(out, open(out_path, "w"), ensure_ascii=False, indent=2)

    print(f"shots in 0-{CALIB_END_S}s window: {len(results)}")
    print(f"matched to a player within {MATCH_WINDOW_S}s: {len(matched)} / unmatched: {unmatched}")
    if dists:
        print(f"shooter-to-ball distance: min {min(dists):.0f}cm, median {sorted(dists)[len(dists)//2]:.0f}cm, max {max(dists):.0f}cm")
    for r in results:
        sh = r["shooter"]
        label = f"track {sh['track_id']} (team {sh['team']}, {sh['dist_cm']}cm)" if sh else "no match"
        print(f"  t={r['ts']:>6}s  ball={r['ball_court_cm']}  shooter={label}")
    print(f"saved: {out_path}")


if __name__ == "__main__":
    main()

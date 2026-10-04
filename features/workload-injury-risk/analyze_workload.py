"""選手トラッキングの実コート座標（cm）から、負荷指標（総移動距離・高強度区間・
急減速回数）を算出するフィージビリティスタディ。

怪我リスク予測・個人特性を考慮したパーソナライズモデルの土台となる特徴量設計を狙う。
本番の怪我予測モデルではない（怪我の発生ラベルが無いため学習・検証はできない）。
あくまで「この特徴量は実データから作れる」ことを示すPoC。

重要: outputs/shot_player/tracking_300s.json の x/y は pipeline/shot_player_analysis.py が
内部でホモグラフィー変換済みの実コート座標(cm, コート中心が原点)。生ピクセルではない
（ball_positions_sam3_300s.json はピクセル空間なので混同しないこと）。

前提: ホモグラフィーが手動アノテーションされている0〜70秒の区間のみ対象
（outputs/annotations.json、STATUS.mdに記載の既知の制約と同じ。70秒以降は自動補正
頼みで精度が低下するため対象外とする）。
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "outputs"
OUT_DIR.mkdir(exist_ok=True)

CALIB_END_S = 70.0

# 速度帯の閾値 (m/s) — スポーツ科学で一般的に使われる区分に準拠
SPEED_BANDS = [
    ("walk", 0.0, 2.0),
    ("jog", 2.0, 4.0),
    ("run", 4.0, 5.5),
    ("high_speed", 5.5, 999.0),
]
HARD_DECEL_THRESH_MS2 = -3.0  # m/s^2 以下を「急減速」とみなす
MAX_PLAUSIBLE_SPEED_MS = 12.0  # これを超える区間はトラッキングノイズとして除外


def smooth_xy(pts, win=5):
    """位置を移動平均で平滑化（フレーム単位のジッタが加速度計算で増幅するのを防ぐ）。"""
    xs = np.array([p["x"] for p in pts])
    ys = np.array([p["y"] for p in pts])
    if len(xs) < win:
        return xs, ys
    kernel = np.ones(win) / win
    xs_s = np.convolve(xs, kernel, mode="same")
    ys_s = np.convolve(ys, kernel, mode="same")
    # 端は平滑化窓が欠けるため元の値を残す
    half = win // 2
    xs_s[:half] = xs[:half]; xs_s[-half:] = xs[-half:]
    ys_s[:half] = ys[:half]; ys_s[-half:] = ys[-half:]
    return xs_s, ys_s


def analyze_track(pts):
    """1トラックの court cm 座標列（時刻順）から負荷指標を算出。"""
    pts = sorted(pts, key=lambda p: p["ts"])
    xs, ys = smooth_xy(pts)
    ts = [p["ts"] for p in pts]

    total_dist_cm = 0.0
    band_dist_cm = {name: 0.0 for name, _, _ in SPEED_BANDS}
    speeds = []
    n_noise_skipped = 0
    for i in range(1, len(pts)):
        dt = ts[i] - ts[i - 1]
        if dt <= 0:
            continue
        d = float(np.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1]))  # cm
        v = (d / dt) / 100.0  # m/s
        if v > MAX_PLAUSIBLE_SPEED_MS:
            n_noise_skipped += 1
            continue
        total_dist_cm += d
        for name, lo, hi in SPEED_BANDS:
            if lo <= v < hi:
                band_dist_cm[name] += d
                break
        speeds.append((ts[i], v))

    if not speeds:
        return None

    # 加速度は速度系列をさらに強めに平滑化してから算出（二階微分はノイズに弱いため、
    # 位置の平滑化だけでは不十分だった。約0.5秒窓でようやく急減速の誤検出が収まった）
    v_vals = np.array([v for _, v in speeds])
    win_a = min(15, len(v_vals)) if len(v_vals) >= 5 else len(v_vals)
    v_smooth = np.convolve(v_vals, np.ones(win_a) / win_a, mode="same") if win_a >= 5 else v_vals
    hard_decel = 0
    for i in range(1, len(speeds)):
        dt = speeds[i][0] - speeds[i - 1][0]
        if dt <= 0:
            continue
        a = (v_smooth[i] - v_smooth[i - 1]) / dt
        if a <= HARD_DECEL_THRESH_MS2:
            hard_decel += 1
    return {
        "n_points": len(pts),
        "duration_s": round(pts[-1]["ts"] - pts[0]["ts"], 2),
        "total_distance_m": round(total_dist_cm / 100.0, 1),
        "high_speed_distance_m": round(band_dist_cm["high_speed"] / 100.0, 1),
        "run_distance_m": round(band_dist_cm["run"] / 100.0, 1),
        # 最大値はトラッキングジッタに弱いため、95パーセンタイルを「ピーク速度」とする
        # （スポーツGPSトラッキングでも一般的な慣行）
        "peak_speed_ms": round(float(np.percentile(v_vals, 95)), 2),
        "mean_speed_ms": round(float(np.mean(v_vals)), 2),
        "hard_decel_count_unreliable": hard_decel,
        "n_noise_frames_skipped": n_noise_skipped,
    }


def main():
    d = json.load(open(ROOT / "outputs/shot_player/tracking_300s.json"))
    traj, player_team = d["trajectories"], d["player_team"]

    results = []
    for tid, pts in traj.items():
        sub = [p for p in pts if p["ts"] <= CALIB_END_S]
        if len(sub) < 15:
            continue
        r = analyze_track(sub)
        if r is None:
            continue
        r["track_id"] = tid
        r["team"] = player_team.get(tid)
        results.append(r)

    results.sort(key=lambda r: -r["total_distance_m"])

    out = {
        "window_s": [0, CALIB_END_S],
        "n_tracks_analyzed": len(results),
        "speed_bands_ms": {name: [lo, hi] for name, lo, hi in SPEED_BANDS},
        "hard_decel_threshold_ms2": HARD_DECEL_THRESH_MS2,
        "max_plausible_speed_ms": MAX_PLAUSIBLE_SPEED_MS,
        "tracks": results,
    }
    out_path = OUT_DIR / "workload_profiles_0_70s.json"
    json.dump(out, open(out_path, "w"), ensure_ascii=False, indent=2)

    print(f"tracks analyzed: {len(results)}")
    if results:
        dists = [r["total_distance_m"] for r in results]
        peaks = [r["peak_speed_ms"] for r in results]
        decels = [r["hard_decel_count_unreliable"] for r in results]
        print(f"distance range: {min(dists):.1f}m - {max(dists):.1f}m")
        print(f"peak speed range: {min(peaks):.1f} - {max(peaks):.1f} m/s")
        print(f"hard decel range: {min(decels)} - {max(decels)}")
        print("top 8 by distance:")
        for r in results[:8]:
            print(f"  track {r['track_id']} (team {r['team']}): {r['total_distance_m']}m, "
                  f"peak {r['peak_speed_ms']}m/s, high_speed={r['high_speed_distance_m']}m, "
                  f"hard_decel={r['hard_decel_count_unreliable']}, dur={r['duration_s']}s, "
                  f"noise_skipped={r['n_noise_frames_skipped']}")
    print(f"saved: {out_path}")


if __name__ == "__main__":
    main()

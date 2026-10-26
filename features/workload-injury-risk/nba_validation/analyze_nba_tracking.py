"""NBA公式SportVUトラッキングデータ（2015-16シーズン、25Hz）で、負荷・怪我リスク
特徴量PoCと同じ手法（速度帯別距離・95パーセンタイルのピーク速度・外れ値除去）を
検証する。

Bリーグ自前パイプラインとの最大の違い:
  - 永続的な選手ID・背番号が最初から付与されている（断片化・OCRが不要）
  - 25Hzの公式データで、座標はコート実座標（フィート）そのもの
  - 1試合フル（約48分）分のデータがある

データ: linouk23/NBA-Player-Movements (2015-16 SportVU公開データ)
対象試合: 2016-01-01 CHA at TOR (gameid 0021500492)
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
FT_TO_M = 0.3048

SPEED_BANDS = [
    ("walk", 0.0, 2.0),
    ("jog", 2.0, 4.0),
    ("run", 4.0, 5.5),
    ("high_speed", 5.5, 999.0),
]
MAX_PLAUSIBLE_SPEED_MS = 12.0


def load_game(path):
    return json.load(open(path))


def build_rosters(game):
    rosters = {}
    for side in ("home", "visitor"):
        team = game["events"][0][side]
        for p in team["players"]:
            rosters[p["playerid"]] = {
                "name": f"{p['firstname']} {p['lastname']}",
                "jersey": p["jersey"],
                "team": team["abbreviation"],
                "position": p["position"],
            }
    return rosters


def collect_trajectories(game, max_events=None):
    """player_id -> list of (wall_clock_ms, x_m, y_m), deduplicated by timestamp."""
    traj = {}
    seen_ts = {}
    events = game["events"][:max_events] if max_events else game["events"]
    for ev in events:
        for m in ev["moments"]:
            wall_ms = m[1]
            players = m[5][1:]  # skip ball (first entry)
            for team_id, pid, x_ft, y_ft, _z in players:
                if seen_ts.get(pid) == wall_ms:
                    continue
                traj.setdefault(pid, []).append((wall_ms, x_ft * FT_TO_M, y_ft * FT_TO_M))
                seen_ts[pid] = wall_ms
    for pid in traj:
        traj[pid].sort(key=lambda r: r[0])
    return traj


def smooth(vals, win=5):
    vals = np.asarray(vals, dtype=float)
    if len(vals) < win:
        return vals
    kernel = np.ones(win) / win
    sm = np.convolve(vals, kernel, mode="same")
    half = win // 2
    sm[:half] = vals[:half]
    sm[-half:] = vals[-half:]
    return sm


def analyze_player(points):
    """points: list of (ms, x_m, y_m) -> workload dict, same method as analyze_workload.py.

    重要な発見: Bリーグ分析(70秒・サンプル少)と違い、フルゲーム(数万サンプル)では
    「95パーセンタイル」が死球時間・静止時間に埋もれて実際のスプリント速度を
    大きく下回る(中央値0.6m/s、95%tile=2.8m/s程度)。サンプル密度が上がるほど
    percentile基準のピーク速度は下振れするため、99パーセンタイルも併記する。
    """
    if len(points) < 50:
        return None
    ts = np.array([p[0] / 1000.0 for p in points])
    xs = smooth([p[1] for p in points])
    ys = smooth([p[2] for p in points])

    total_dist = 0.0
    band_dist = {name: 0.0 for name, _, _ in SPEED_BANDS}
    speeds = []
    n_noise = 0
    active_s = 0.0
    for i in range(1, len(ts)):
        dt = ts[i] - ts[i - 1]
        if dt <= 0 or dt > 1.0:  # event境界のギャップはスキップ
            continue
        active_s += dt
        d = float(np.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1]))
        v = d / dt
        if v > MAX_PLAUSIBLE_SPEED_MS:
            n_noise += 1
            continue
        total_dist += d
        for name, lo, hi in SPEED_BANDS:
            if lo <= v < hi:
                band_dist[name] += d
                break
        speeds.append(v)

    if not speeds:
        return None
    return {
        "n_points": len(points),
        "total_distance_m": round(total_dist, 1),
        "high_speed_distance_m": round(band_dist["high_speed"], 1),
        "run_distance_m": round(band_dist["run"], 1),
        "peak_speed_p95_ms": round(float(np.percentile(speeds, 95)), 2),
        "peak_speed_p99_ms": round(float(np.percentile(speeds, 99)), 2),
        "mean_speed_ms": round(float(np.mean(speeds)), 2),
        "n_noise_skipped": n_noise,
        "wallclock_span_s": round(ts[-1] - ts[0], 1),
        "active_tracked_s": round(active_s, 1),
    }


def main():
    game = load_game(HERE / "0021500492.json")
    rosters = build_rosters(game)

    # 最初の約90イベント ≈ 1クォーター強、Bリーグ分析(0-70秒)よりずっと長い
    # 実データでの比較として、まず全イベント(フルゲーム)で集計する
    traj = collect_trajectories(game)

    results = []
    for pid, points in traj.items():
        info = rosters.get(pid)
        if info is None:
            continue
        r = analyze_player(points)
        if r is None:
            continue
        r.update({"player_id": pid, "name": info["name"], "jersey": info["jersey"],
                   "team": info["team"], "position": info["position"]})
        results.append(r)

    results.sort(key=lambda r: -r["total_distance_m"])

    out = {
        "game": "2016-01-01 CHA at TOR (gameid 0021500492)",
        "source": "linouk23/NBA-Player-Movements (public 2015-16 SportVU data)",
        "n_players": len(results),
        "method": "same as analyze_workload.py: speed bands, 95th-pct peak, >12m/s filtered as noise",
        "players": results,
    }
    json.dump(out, open(HERE / "nba_workload_fullgame.json", "w"), ensure_ascii=False, indent=2)

    print(f"{len(results)} players analyzed (full game)")
    print(f"{'name':20s} {'team':4s} {'#':3s} {'dist_m':>8s} {'hs_m':>7s} {'p95':>6s} {'p99':>6s} {'active_s':>9s}")
    for r in results:
        print(f"{r['name']:20s} {r['team']:4s} {r['jersey']:>3s} {r['total_distance_m']:8.1f} "
              f"{r['high_speed_distance_m']:7.1f} {r['peak_speed_p95_ms']:6.2f} {r['peak_speed_p99_ms']:6.2f} "
              f"{r['active_tracked_s']:9.1f}")


if __name__ == "__main__":
    main()

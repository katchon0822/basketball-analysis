"""ボール軌道 × 選手トラッキングからプレーの自動区切り・パターン検出を行う。

選手トラッキング(tracking_300s.json)はID断片化が激しい(397トラック/5分、
中央値3秒)ため、選手の「長時間の同一性」に依存する分析は避け、以下の
2つに絞る:

1. ボール軌道ベースのプレー区切り(デッドボール/ドリブル/パス)
   - ボール追跡は93%と高精度なため、ここが最も信頼できる特徴量
2. 短時間ウィンドウでのP&R候補検出・スペーシング指標
   - 数秒単位の局所窓であれば断片化トラックでも成立する

出力: outputs/play_patterns_300s.json, outputs/ball_speed_timeline.png
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "outputs"
OUT_DIR.mkdir(exist_ok=True)

FPS = 29.97


def load_ball(path):
    d = json.load(open(path))
    n = max(int(k) for k in d) + 1
    xy = np.full((n, 2), np.nan)
    for k, v in d.items():
        xy[int(k)] = v
    return xy


def load_trajectories(path):
    d = json.load(open(path))
    return d["trajectories"], d["player_team"], d["teams"]


# --------------------------------------------------------- 1. ボール速度・区切り


def ball_speed_series(xy, fps=FPS):
    dt = 1.0 / fps
    v = np.full(len(xy), np.nan)
    for i in range(1, len(xy)):
        if np.any(np.isnan(xy[i])) or np.any(np.isnan(xy[i - 1])):
            continue
        v[i] = np.linalg.norm(xy[i] - xy[i - 1]) / dt
    return v


def smooth(v, win=5):
    v = v.copy()
    nanmask = np.isnan(v)
    v[nanmask] = 0
    kernel = np.ones(win) / win
    sm = np.convolve(v, kernel, mode="same")
    cnt = np.convolve((~nanmask).astype(float), kernel, mode="same")
    with np.errstate(invalid="ignore", divide="ignore"):
        sm = np.where(cnt > 0, sm / np.maximum(cnt, 1e-6), np.nan)
    return sm


def segment_play(v_smooth, dead_thresh_px_s=90, min_dead_frames=12):
    """速度が閾値以下で一定フレーム継続する区間を「デッドボール」、
    それ以外を「ライブボール」として区切る。"""
    n = len(v_smooth)
    is_dead = np.where(np.isnan(v_smooth), True, v_smooth < dead_thresh_px_s)
    segments = []
    i = 0
    while i < n:
        j = i
        cur = is_dead[i]
        while j < n and is_dead[j] == cur:
            j += 1
        segments.append({"start_f": i, "end_f": j, "dead": bool(cur)})
        i = j
    # 短すぎるデッド区間はライブに吸収(ノイズ除去)
    merged = []
    for seg in segments:
        if seg["dead"] and (seg["end_f"] - seg["start_f"]) < min_dead_frames:
            seg = dict(seg, dead=False)
        if merged and merged[-1]["dead"] == seg["dead"]:
            merged[-1]["end_f"] = seg["end_f"]
        else:
            merged.append(seg)
    return merged


def classify_live_segment(v_smooth, xy, seg, fps=FPS):
    """ライブ区間をドリブル/パス/不明に分類する簡易ヒューリスティック。

    - パス: 短時間(<0.6秒)に大きな変位、速度ピークが単発
    - ドリブル: 一定時間持続し、速度に周期的な上下(バウンド)が見られる
    """
    s, e = seg["start_f"], seg["end_f"]
    dur_s = (e - s) / fps
    seg_v = v_smooth[s:e]
    seg_v = seg_v[~np.isnan(seg_v)]
    if len(seg_v) < 3:
        return "unknown", 0.0

    valid_xy = xy[s:e]
    valid_xy = valid_xy[~np.isnan(valid_xy).any(axis=1)]
    disp = float(np.linalg.norm(valid_xy[-1] - valid_xy[0])) if len(valid_xy) >= 2 else 0.0
    path_len = float(np.sum(np.linalg.norm(np.diff(valid_xy, axis=0), axis=1))) if len(valid_xy) >= 2 else 0.0
    straightness = disp / path_len if path_len > 1e-6 else 0.0

    # 周期性: 平滑化前の速度系列の自己相関でバウンド周期性を検出
    ac = np.nan
    if len(seg_v) >= 10:
        v0 = seg_v - seg_v.mean()
        ac_full = np.correlate(v0, v0, mode="full")
        ac_full = ac_full[len(ac_full) // 2 :]
        if ac_full[0] > 1e-6:
            ac_full = ac_full / ac_full[0]
            ac = float(np.max(ac_full[3:12])) if len(ac_full) > 12 else np.nan

    if dur_s < 0.6 and straightness > 0.7:
        return "pass_candidate", straightness
    if dur_s >= 0.6 and not np.isnan(ac) and ac > 0.35:
        return "dribble_candidate", ac
    return "unknown", straightness


# --------------------------------------------------------- 2. スペーシング / P&R候補


def team_positions_at(trajectories, player_team, frame_idx, fps=FPS, tol_frames=2):
    """指定フレーム付近(±tol_frames)にアクティブなトラックの位置を返す。"""
    t = frame_idx / fps
    tol = tol_frames / fps
    out = {"1": [], "2": []}
    for tid, pts in trajectories.items():
        team = player_team.get(tid)
        if team is None:
            continue
        for p in pts:
            if abs(p["ts"] - t) <= tol:
                out[str(team)].append((tid, p["x"], p["y"]))
                break
    return out


def convex_hull_area(points):
    if len(points) < 3:
        return None
    from scipy.spatial import ConvexHull

    pts = np.array([[x, y] for _, x, y in points])
    try:
        return float(ConvexHull(pts).volume)  # 2Dではvolume=面積
    except Exception:
        return None


def spacing_timeline(trajectories, player_team, n_frames, fps=FPS, step=15):
    rows = []
    for f in range(0, n_frames, step):
        pos = team_positions_at(trajectories, player_team, f, fps)
        row = {"frame": f, "t": f / fps}
        for team in ("1", "2"):
            pts = pos[team]
            row[f"team{team}_n"] = len(pts)
            row[f"team{team}_hull_px2"] = convex_hull_area(pts)
        rows.append(row)
    return rows


def pnr_candidates(trajectories, player_team, ball_xy, fps=FPS,
                    screen_dist_px=55, min_overlap_s=0.8, screen_zone_px=180):
    """同チーム2選手がボール付近で接近→分離するP&R候補を検出する。

    厳密なP&R判定ではなく、McQueen(2014)のいう「1段目のルールベース候補生成」
    に相当する。候補は目視確認が前提。
    """
    candidates = []
    ids = list(trajectories.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = trajectories[ids[i]], trajectories[ids[j]]
            if player_team.get(ids[i]) != player_team.get(ids[j]):
                continue
            ta = {round(p["ts"], 3): p for p in a}
            tb = {round(p["ts"], 3): p for p in b}
            common = sorted(set(ta) & set(tb))
            if len(common) < min_overlap_s * fps * 0.5:
                continue
            dists = []
            for t in common:
                pa, pb = ta[t], tb[t]
                d = np.hypot(pa["x"] - pb["x"], pa["y"] - pb["y"])
                dists.append((t, d))
            close = [t for t, d in dists if d < screen_dist_px]
            if not close:
                continue
            t_close = close[0]
            # ボールがその時刻に近くにあるか(スクリーンはボール周辺で起きる)
            f_close = int(round(t_close * fps))
            if f_close >= len(ball_xy) or np.any(np.isnan(ball_xy[f_close])):
                continue
            pa_close = ta[t_close]
            ball_dist = np.hypot(pa_close["x"] - ball_xy[f_close][0], pa_close["y"] - ball_xy[f_close][1])
            if ball_dist > screen_zone_px:
                continue
            # 接近後に分離するか
            after = [d for t, d in dists if t > t_close][:15]
            separated = len(after) > 0 and max(after) > screen_dist_px * 1.8
            candidates.append({
                "track_a": ids[i], "track_b": ids[j],
                "t_screen": t_close, "min_dist_px": min(d for _, d in dists),
                "ball_dist_px": float(ball_dist), "separated_after": bool(separated),
            })
    return candidates


def main():
    ball_xy = load_ball(ROOT / "ball_positions_sam3_300s.json")
    trajectories, player_team, teams = load_trajectories(ROOT / "outputs/shot_player/tracking_300s.json")

    v = ball_speed_series(ball_xy)
    v_smooth = smooth(v, win=5)
    coverage = float(np.mean(~np.isnan(ball_xy).any(axis=1)))

    segments = segment_play(v_smooth)
    for seg in segments:
        if not seg["dead"]:
            label, score = classify_live_segment(v_smooth, ball_xy, seg)
            seg["label"] = label
            seg["score"] = round(float(score), 3)
        else:
            seg["label"] = "dead_ball"
            seg["score"] = None
        seg["start_s"] = round(seg["start_f"] / FPS, 2)
        seg["end_s"] = round(seg["end_f"] / FPS, 2)
        seg["dur_s"] = round(seg["end_s"] - seg["start_s"], 2)

    live = [s for s in segments if not s["dead"]]
    label_counts = {}
    for s in live:
        label_counts[s["label"]] = label_counts.get(s["label"], 0) + 1

    spacing = spacing_timeline(trajectories, player_team, len(ball_xy))
    spacing_valid = [r for r in spacing if r["team1_hull_px2"] or r["team2_hull_px2"]]
    coverage_5v5 = np.mean([r["team1_n"] >= 3 and r["team2_n"] >= 3 for r in spacing])

    pnr = pnr_candidates(trajectories, player_team, ball_xy)

    result = {
        "ball_tracking_coverage": round(coverage, 4),
        "n_frames": len(ball_xy),
        "segments": segments,
        "live_segment_label_counts": label_counts,
        "n_dead_ball_segments": sum(1 for s in segments if s["dead"]),
        "spacing_timeline_sample_every_n_frames": 15,
        "spacing_timeline": spacing,
        "frac_frames_with_5v5_tracked": round(float(coverage_5v5), 4),
        "pnr_candidates": pnr,
        "n_pnr_candidates": len(pnr),
        "n_pnr_candidates_separated": sum(1 for c in pnr if c["separated_after"]),
    }

    out_path = OUT_DIR / "play_patterns_300s.json"
    json.dump(result, open(out_path, "w"), ensure_ascii=False, indent=2)
    print(f"ball coverage: {coverage:.1%}")
    print(f"segments: {len(segments)} (dead={result['n_dead_ball_segments']}, live={len(live)})")
    print(f"live labels: {label_counts}")
    print(f"5v5 tracked frames: {coverage_5v5:.1%}")
    print(f"P&R candidates: {len(pnr)} (separated_after={result['n_pnr_candidates_separated']})")
    print(f"saved: {out_path}")


if __name__ == "__main__":
    main()

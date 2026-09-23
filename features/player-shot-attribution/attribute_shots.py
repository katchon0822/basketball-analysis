"""シュート検出 × McByte++選手ID 紐付けモジュール。

入力:
  - McByte++ MOT出力 (frame,id,x,y,w,h,score,...)  ※クリップ基準のフレーム番号
  - shots_300s.json (ts, px)  ※動画基準の秒
  - outputs/annotations.json (2秒ごとのコート校正点, cm座標)

出力:
  - outputs/shots_attributed.json  (シュートごとの shooter_id / team / コート座標)
  - outputs/shot_chart_by_player.png  (FIBAハーフコートの選手別チャート)
  - outputs/verify_shot_*.jpg  (帰属根拠の確認画像)

使い方:
  python attribute_shots.py --mot <mot.txt> --frames <frame_dir> \
      --clip-start 26.0 --clip-fps 15 --window 26 36.5
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "outputs"

# ---------------------------------------------------------------- MOT / チーム


def load_mot(path):
    """MOT txt -> {clip_frame: [(tid, x, y, w, h), ...]}"""
    per_frame = defaultdict(list)
    for line in open(path):
        p = line.strip().split(",")
        if len(p) < 6:
            continue
        fr, tid = int(p[0]), int(float(p[1]))
        x, y, w, h = map(float, p[2:6])
        per_frame[fr].append((tid, x, y, w, h))
    return per_frame


def torso_hsv(img, box):
    """bboxの胴体部分の HSV 中央値。"""
    x, y, w, h = box
    x0, x1 = int(x + 0.25 * w), int(x + 0.75 * w)
    y0, y1 = int(y + 0.12 * h), int(y + 0.45 * h)
    x0, y0 = max(x0, 0), max(y0, 0)
    x1 = min(x1, img.shape[1] - 1)
    y1 = min(y1, img.shape[0] - 1)
    if x1 <= x0 or y1 <= y0:
        return None
    crop = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    return np.median(crop.reshape(-1, 3), axis=0)


def classify_team(hsv):
    """白 or 紺。白=明るく低彩度 / 紺=暗い or 青系高彩度。"""
    if hsv is None:
        return None
    h, s, v = hsv
    if v > 150 and s < 70:
        return "white"
    if v < 130 or (90 <= h <= 135 and s > 60):
        return "navy"
    return None


def team_map_from_mot(per_frame, frame_dir, sample_step=10):
    """全トラックIDのチームを多数決で判定。"""
    votes = defaultdict(Counter)
    for fr in sorted(per_frame):
        if fr % sample_step:
            continue
        img = cv2.imread(str(frame_dir / f"{fr:04d}.jpg"))
        if img is None:
            continue
        for tid, x, y, w, h in per_frame[fr]:
            t = classify_team(torso_hsv(img, (x, y, w, h)))
            if t:
                votes[tid][t] += 1
    return {tid: c.most_common(1)[0][0] for tid, c in votes.items() if c}


# ------------------------------------------------------------------- ボール


def detect_ball(img, near=None, radius=450):
    """HSVでオレンジ球候補を検出。near=(x,y) 付近を優先。"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (4, 110, 90), (22, 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best, best_score = None, 1e9
    for c in cnts:
        area = cv2.contourArea(c)
        if not 20 <= area <= 900:  # 720pのボールは概ね8〜30px径
            continue
        (cx, cy), r = cv2.minEnclosingCircle(c)
        fill = area / (np.pi * r * r + 1e-6)
        if fill < 0.45:  # 円形度
            continue
        if near is not None:
            d = np.hypot(cx - near[0], cy - near[1])
            if d > radius:
                continue
            score = d - 60 * fill
        else:
            score = -60 * fill
        if score < best_score:
            best, best_score = (float(cx), float(cy)), score
    return best


# ---------------------------------------------------------------- ホモグラフィ


def load_homographies(annot_path):
    """{sec: H(3x3 img->court cm)}"""
    ann = json.load(open(annot_path))
    hs = {}
    for k, pts in ann.items():
        if ":" in k or not isinstance(pts, list) or len(pts) < 4:
            continue
        sec = int(k.replace("frame_", "").replace("s.jpg", ""))
        img_pts = np.float32([p["img"] for p in pts])
        crt_pts = np.float32([p["court"] for p in pts])
        H, _ = cv2.findHomography(img_pts, crt_pts, cv2.RANSAC, 5.0)
        if H is not None:
            hs[sec] = H
    return hs


def to_court(H, px, py):
    p = cv2.perspectiveTransform(np.float32([[[px, py]]]), H)[0][0]
    return float(p[0]), float(p[1])


# ------------------------------------------------------------------- 帰属


def attribute_shot(shot, per_frame, clip_start, clip_fps):
    """検出px直下の最寄り選手をシューターと判定(近接度スコア + 信頼度)。

    このコートはボールと床のHSVがほぼ同一で色ベースの追跡が効かないため、
    シュート検出器が記録した「上昇確定時のボール位置 px」への近接で帰属する。
    リリース直後はボールがシューターの頭上にあるので、横ずれを重く・
    縦ずれ(ボールが上にある分)を軽く効かせる。
    """
    ts, (sx, sy) = shot["ts"], shot["px"]
    f_shot = round((ts - clip_start) * clip_fps) + 1
    best = None
    for f in range(max(f_shot - 6, 1), f_shot + 3):
        for tid, x, y, w, h in per_frame.get(f, []):
            head_x, head_y = x + w / 2, y
            dx = abs(sx - head_x)
            dy = head_y - sy  # 正 = ボールが頭より上(自然)
            if dy < -0.6 * h:  # ボールが足より下にある候補は除外
                continue
            score = dx + 0.5 * abs(dy - 0.6 * h)
            if best is None or score < best[0]:
                best = (score, tid, (x, y, w, h), f)
    if best is None:
        return None
    score, tid, bbox, f = best
    return dict(release_frame=f, ball=(sx, sy), shooter=tid, bbox=bbox,
                dist=round(score, 1), method="nearest",
                confidence="high" if score < 110 else "low")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mot", required=True)
    ap.add_argument("--frames", required=True)
    ap.add_argument("--clip-start", type=float, default=26.0)
    ap.add_argument("--clip-fps", type=float, default=15.0)
    ap.add_argument("--window", nargs=2, type=float, default=[26.0, 36.5])
    ap.add_argument("--shots", default=str(ROOT / "outputs/shot_player/shots_300s.json"))
    ap.add_argument("--annotations", default=str(ROOT / "outputs/annotations.json"))
    args = ap.parse_args()

    frame_dir = Path(args.frames)
    per_frame = load_mot(args.mot)
    print(f"[MOT] {len(per_frame)} frames, "
          f"{len({t for v in per_frame.values() for t, *_ in v})} ids")

    teams = team_map_from_mot(per_frame, frame_dir)
    print("[TEAM]", teams)

    hs = load_homographies(args.annotations)
    print("[H] annotated secs:", sorted(hs))

    shots = [s for s in json.load(open(args.shots))
             if args.window[0] <= s["ts"] < args.window[1]]
    print(f"[SHOTS] {len(shots)} in window {args.window}")

    results = []
    for i, shot in enumerate(shots, 1):
        att = attribute_shot(shot, per_frame, frame_dir, args.clip_start, args.clip_fps)
        rec = dict(ts=round(shot["ts"], 2), ball_px=[round(v, 1) for v in shot["px"]])
        if att:
            tid = att["shooter"]
            x, y, w, h = att["bbox"]
            feet = (x + w / 2, y + h)
            sec_near = min(hs, key=lambda s: abs(s - shot["ts"]))
            cx, cy = to_court(hs[sec_near], *feet)
            rec.update(shooter_id=tid, team=teams.get(tid, "?"),
                       release_frame=att["release_frame"], method=att["method"],
                       ball_release=[round(v, 1) for v in att["ball"]],
                       feet_px=[round(v, 1) for v in feet],
                       court_cm=[round(cx, 1), round(cy, 1)], h_sec=sec_near)
            # 検証画像
            img = cv2.imread(str(frame_dir / f"{att['release_frame']:04d}.jpg"))
            cv2.rectangle(img, (int(x), int(y)), (int(x + w), int(y + h)), (0, 220, 0), 2)
            cv2.circle(img, tuple(map(int, att["ball"])), 12, (0, 140, 255), 2)
            cv2.putText(img, f"ID {tid} ({teams.get(tid, '?')})",
                        (int(x), int(y) - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (0, 220, 0), 2)
            cv2.imwrite(str(OUT_DIR / f"verify_shot_{i}_f{att['release_frame']}.jpg"), img)
        else:
            rec.update(shooter_id=None, team=None)
        results.append(rec)
        print(f"  shot {i}: ts={rec['ts']} -> ID {rec.get('shooter_id')} "
              f"({rec.get('team')}) method={rec.get('method')} court={rec.get('court_cm')}")

    out = dict(clip=dict(start=args.clip_start, fps=args.clip_fps),
               teams={str(k): v for k, v in teams.items()}, shots=results)
    OUT_DIR.mkdir(exist_ok=True)
    json.dump(out, open(OUT_DIR / "shots_attributed.json", "w"),
              ensure_ascii=False, indent=2)
    print("[OK] ->", OUT_DIR / "shots_attributed.json")


if __name__ == "__main__":
    main()

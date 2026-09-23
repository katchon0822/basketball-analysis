"""
選手ごとのシュートチャート + チームごとトラッキングデータ生成

Pipeline:
  1. YOLO + ByteTrack で選手追跡（チーム分類 + NBA座標変換）
  2. SAM3ボール軌跡からShotDetectorでシュート検出
  3. 各シュートを最近傍選手に帰属
  4. 選手別シュートチャート / チーム別ヒートマップ / 移動距離バーチャート
"""
import cv2, json, numpy as np, argparse
from pathlib import Path
from collections import defaultdict

import supervision as sv
from ultralytics import YOLO
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Arc, Patch
from matplotlib.lines import Line2D

from court_line_accuracy import build_H_inv, key_to_frame

VIDEO      = "data/videos/game_EE1swQMsXJc_720p.mp4"
MODEL_PATH = "models/player_detector.pt"
ANN_JSON   = "outputs/annotations.json"
SAM3_BALL  = "ball_positions_sam3_300s.json"
OUT_DIR    = Path("outputs/shot_player")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CLS_PLAYER = 4
CONF       = 0.40

# コート定数 (cm)
COURT_HALF_LEN = 1432
COURT_HALF_WID = 750
BASKET_Y       = 160    # エンドラインからバスケットまで
PT3_DEFAULT    = 705


# ── ホモグラフィー構築 ────────────────────────────────────────────────────────
def load_homographies(ann_path, fps):
    with open(ann_path) as f:
        ann_data = json.load(f)
    result = {}
    for key, pts in ann_data.items():
        if not isinstance(pts, list):
            continue
        fi = key_to_frame(key, fps)
        H_inv = build_H_inv(pts)
        if H_inv is not None:
            result[fi] = (H_inv, np.linalg.inv(H_inv), pts)
    return result


def get_nearest_H(h_map, fi):
    if not h_map:
        return None, None
    closest = min(h_map.keys(), key=lambda k: abs(k - fi))
    return h_map[closest][0], h_map[closest][1]


def transform_pt(H, px, py):
    pt = np.array([[[float(px), float(py)]]], dtype=np.float64)
    out = cv2.perspectiveTransform(pt, H)
    x, y = float(out[0,0,0]), float(out[0,0,1])
    if abs(x) > COURT_HALF_WID + 100 or abs(y) > COURT_HALF_LEN + 100:
        return None
    return (x, y)


def transform_pt_loose(H, px, py):
    """コート範囲チェックなしの変換。シュートの表示用（外れ値でも位置は欲しい）。"""
    pt = np.array([[[float(px), float(py)]]], dtype=np.float64)
    out = cv2.perspectiveTransform(pt, H)
    return float(out[0, 0, 0]), float(out[0, 0, 1])


def classify_team(frame, bbox):
    x1, y1, x2, y2 = map(int, bbox)
    h = y2 - y1
    roi = frame[y1 + int(h*0.15): y1 + int(h*0.70), x1:x2]
    if roi.size == 0:
        return -1
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    t = roi.shape[0] * roi.shape[1]
    if cv2.inRange(hsv, (0,   0, 170), (180,  70, 255)).sum() / 255 / t > 0.12:
        return 1
    if cv2.inRange(hsv, (90, 60,  15), (140, 255, 170)).sum() / 255 / t > 0.07:
        return 2
    return -1


# ── シュート検出 ──────────────────────────────────────────────────────────────
class ShotDetector:
    """ボールYピクセル座標の頂点(上昇→下降の変化点)からシュートを検出する。

    SAM3ボール追跡は1〜3フレームの欠測や値の据え置きが頻発するため、
    短い欠測(<= MAX_GAP_S)は状態をリセットせずスキップし、速度は
    フレーム数ではなく経過秒で正規化する(等間隔を仮定しない)。
    """
    MAX_GAP_S = 0.5

    def __init__(self, fps, cooldown=2.0):
        self.fps       = fps
        self.cooldown  = cooldown
        self.prev_py   = None
        self.prev_ts   = None
        self.prev_vy   = 0.0
        self.last_shot = -999
        self.shots     = []

    def update(self, ball_px, H, ts):
        if ball_px is None:
            return  # 短い欠測は無視(状態はリセットしない)

        if self.prev_ts is not None and ts - self.prev_ts > self.MAX_GAP_S:
            self.prev_py = None  # 長い欠測のみ状態リセット

        py = ball_px[1]
        if self.prev_py is not None and py != self.prev_py:
            dt = max(ts - self.prev_ts, 1e-3)
            vy = (py - self.prev_py) / dt  # px/秒。負=上昇、正=下降
            # 上昇→下降の変化点 = shot apex
            if (self.prev_vy < -30 and vy > 30
                    and ts - self.last_shot > self.cooldown):
                nba = transform_pt_loose(H, ball_px[0], ball_px[1]) if H is not None else None
                self.shots.append({
                    'ts':    ts,
                    'px':    ball_px,
                    'nba_x': nba[0] if nba else None,
                    'nba_y': nba[1] if nba else None,
                })
                self.last_shot = ts
            self.prev_vy = vy

        self.prev_py = py
        self.prev_ts = ts


# ── コート描画 ────────────────────────────────────────────────────────────────
def draw_half_court(ax, flip=False, pt3_r=PT3_DEFAULT):
    L, W = COURT_HALF_LEN, COURT_HALF_WID
    bx, by = (0, BASKET_Y) if not flip else (0, 2*L - BASKET_Y)
    s = 1 if not flip else -1

    kw = dict(lw=1.2, color='#555', fill=False)

    ax.add_patch(patches.Rectangle((-W, 0), 2*W, L,
                                    lw=1.5, edgecolor='#888', facecolor='none'))
    ax.axhline(L, color='#888', lw=1)

    # ペイント
    ax.add_patch(patches.Rectangle((-245, by - s*BASKET_Y),
                                    490, s*580, **kw))
    ax.axhline(BASKET_Y + s*580 - s*BASKET_Y + (by - s*BASKET_Y) + s*580,
               xmin=0.2, xmax=0.8, color='#555', lw=0.8)  # FT line approx

    # 3PT arc
    ax.add_patch(Arc((0, by), 2*pt3_r, 2*pt3_r, theta1=0, theta2=180,
                     color='#888', lw=1.2))
    # 3PT corner straight
    cx3 = 665
    ax.plot([-cx3, -cx3], [0, by + s*300], color='#888', lw=1.2)
    ax.plot([cx3,  cx3],  [0, by + s*300], color='#888', lw=1.2)

    # バスケット
    ax.add_patch(plt.Circle((0, by), 23.75, fill=False, color='#e44', lw=1.5))

    ax.set_xlim(-W-20, W+20)
    ax.set_ylim(-30, L+30)
    ax.set_aspect('equal')
    ax.axis('off')


def scatter_shot(ax, nba_x, nba_y, made, label=None):
    color  = '#00ff88' if made else '#ff4444'
    marker = '*' if made else 'o'
    size   = 220 if made else 100
    ax.scatter(nba_x, nba_y, c=color, s=size, marker=marker,
               zorder=5, edgecolors='white', linewidths=0.7)
    if label:
        ax.annotate(label, (nba_x, nba_y), textcoords='offset points',
                    xytext=(6, 4), color='white', fontsize=7)


# ── メイン ───────────────────────────────────────────────────────────────────
def main(sec=60.0):
    sam3_raw = json.load(open(SAM3_BALL))
    sam3_ball = {int(k): (v[0], v[1]) if v else None for k, v in sam3_raw.items()}

    model   = YOLO(MODEL_PATH)
    tracker = sv.ByteTrack(minimum_matching_threshold=0.8,
                            minimum_consecutive_frames=1,
                            lost_track_buffer=90)

    cap  = cv2.VideoCapture(VIDEO)
    fps  = cap.get(cv2.CAP_PROP_FPS)
    n_frames = int(sec * fps)

    h_map = load_homographies(ANN_JSON, fps)
    shot_det   = ShotDetector(fps)
    team_votes = defaultdict(list)
    traj       = defaultdict(list)   # {tid: [(nba_x, nba_y, ts, team)]}
    px_pos     = defaultdict(list)   # {tid: [(px, py, ts)]}  pixel pos
    frame_players = {}               # {fi: [(tid, px, py, team)]}

    print(f"Processing {n_frames} frames ({sec:.0f}s) ...")
    for fi in range(n_frames):
        ret, frame = cap.read()
        if not ret:
            break
        ts = fi / fps
        H_inv, H_fwd = get_nearest_H(h_map, fi)

        # YOLO + ByteTrack
        results = model.predict(frame, conf=CONF, verbose=False)[0]
        p_dets  = [(box.xyxy[0].cpu().numpy(), float(box.conf[0]))
                   for box in results.boxes if int(box.cls[0]) == CLS_PLAYER
                   and float(box.conf[0]) >= CONF]

        if p_dets:
            boxes_np = np.array([d[0] for d in p_dets])
            confs_np = np.array([d[1] for d in p_dets])
            sv_det   = sv.Detections(xyxy=boxes_np, confidence=confs_np,
                                      class_id=np.zeros(len(p_dets), dtype=int))
            tracks   = tracker.update_with_detections(sv_det)
        else:
            tracks = sv.Detections.empty()

        frame_p = []
        for i in range(len(tracks)):
            tid  = int(tracks.tracker_id[i])
            bbox = tracks.xyxy[i]
            team = classify_team(frame, bbox)
            team_votes[tid].append(team)
            recent = team_votes[tid][-20:]
            votes  = [t for t in recent if t in (1, 2)]
            stable = max(set(votes), key=votes.count) if votes else -1

            cx = (bbox[0] + bbox[2]) / 2
            cy = bbox[3]
            px_pos[tid].append((cx, cy, ts))
            frame_p.append((tid, cx, cy, stable))

            if H_fwd is not None and stable in (1, 2):
                nba = transform_pt(H_fwd, cx, cy)
                if nba:
                    traj[tid].append((nba[0], nba[1], ts, stable))

        frame_players[fi] = frame_p

        # シュート検出
        ball_px = sam3_ball.get(fi)
        shot_det.update(ball_px, H_fwd, ts)

        if fi % int(fps * 10) == 0:
            print(f"  {fi}/{n_frames}  t={ts:.0f}s  tracks={len(tracks)}")

    cap.release()
    shots = shot_det.shots
    print(f"\nShots detected: {len(shots)}")

    # 各シュートを最近傍選手に帰属
    for s in shots:
        fi_shot = int(s['ts'] * fps)
        fi_shot = min(fi_shot, n_frames - 1)
        bpx, bpy = s['px']
        best_tid, best_dist, best_team = None, 9999, -1
        # 前後3フレームで探す
        for fi_check in range(max(0, fi_shot-3), min(n_frames, fi_shot+4)):
            for tid, cx, cy, team in frame_players.get(fi_check, []):
                d = np.hypot(cx - bpx, cy - bpy)
                if d < best_dist:
                    best_dist, best_tid, best_team = d, tid, team
        s['player_id'] = best_tid
        s['team']      = best_team
        s['made']      = False   # シュート成功判定は外部データなしで困難→手動フラグ

        mm, ss_t = int(s['ts']//60), int(s['ts']%60)
        team_name = {1:'White', 2:'Navy'}.get(best_team, '?')
        print(f"  {mm:02d}:{ss_t:02d}  P{best_tid}  {team_name}  "
              f"nba=({s['nba_x']:.0f},{s['nba_y']:.0f})  dist={best_dist:.0f}px")

    # 安定したチーム割り当て
    player_team = {}
    for tid, votes in team_votes.items():
        c = {1: votes.count(1), 2: votes.count(2)}
        best = max(c, key=c.get)
        if c[best] > len(votes) * 0.3:
            player_team[tid] = best

    team1_ids = sorted([t for t, tm in player_team.items()
                        if tm == 1 and len(traj[t]) >= 10])
    team2_ids = sorted([t for t, tm in player_team.items()
                        if tm == 2 and len(traj[t]) >= 10])
    print(f"\nWhite team: {len(team1_ids)} players  {team1_ids}")
    print(f"Navy  team: {len(team2_ids)} players  {team2_ids}")

    # ═══════════════════════════════════════════════════════
    #  1. 選手ごとシュートチャート
    # ═══════════════════════════════════════════════════════
    shots_by_player = defaultdict(list)
    for s in shots:
        if s['player_id'] is not None:
            shots_by_player[s['player_id']].append(s)
    # チームごとにまとめる
    for team_ids, team_name, t_color in [
        (team1_ids, 'White', '#88aaff'),
        (team2_ids, 'Navy',  '#ff8866'),
    ]:
        # そのチームのシュートがある選手だけ
        shooters = [(tid, shots_by_player[tid])
                    for tid in team_ids
                    if shots_by_player.get(tid)]
        # + チームの他選手で shot があるもの
        team_shots_all = [s for s in shots if s['team'] in (
            1 if team_name=='White' else 2,)]
        if not team_shots_all and not shooters:
            continue

        n_col = min(max(len(shooters), 1) + 1, 5)  # +1 for team chart
        n_row = (max(len(shooters), 1) + n_col) // n_col + 1
        n_row = max(n_row, 2)

        fig, axes = plt.subplots(n_row, n_col,
                                  figsize=(n_col * 4.5, n_row * 4),
                                  facecolor='#0d1117')
        if hasattr(axes, 'flat'):
            axes_flat = list(axes.flat)
        else:
            axes_flat = [axes]
        for ax in axes_flat:
            ax.set_facecolor('#1a1a2e')

        fig.suptitle(f'{team_name} Team — Shot Chart per Player ({int(sec)}s)',
                     color='white', fontsize=14)

        # チーム全体（最初のパネル）
        ax0 = axes_flat[0]
        draw_half_court(ax0)
        for s in team_shots_all:
            scatter_shot(ax0, s['nba_x'], s['nba_y'], s['made'])
        ax0.set_title(f'{team_name} (All)  {len(team_shots_all)} shots',
                      color='white', fontsize=10)
        ax0.set_facecolor('#1a1a2e')

        for i, (tid, s_list) in enumerate(shooters):
            if i + 1 >= len(axes_flat):
                break
            ax = axes_flat[i + 1]
            ax.set_facecolor('#1a1a2e')
            draw_half_court(ax)
            for s in s_list:
                mm = int(s['ts']//60); ss_t = int(s['ts']%60)
                scatter_shot(ax, s['nba_x'], s['nba_y'], s['made'],
                             label=f"{mm}:{ss_t:02d}")
            n_made = sum(1 for s in s_list if s['made'])
            ax.set_title(f'P{tid % 100}  {n_made}/{len(s_list)} shots',
                         color='white', fontsize=10)

        for ax in axes_flat[len(shooters)+1:]:
            ax.axis('off')

        plt.tight_layout(rect=[0, 0, 1, 0.95])
        fname = f'shot_chart_{team_name.lower()}_{int(sec)}s.png'
        fig.savefig(OUT_DIR / fname, dpi=110, bbox_inches='tight',
                    facecolor='#0d1117')
        plt.close(fig)
        print(f"Saved: {fname}")

    # ═══════════════════════════════════════════════════════
    #  2. チームごとヒートマップ
    # ═══════════════════════════════════════════════════════
    fig, axes = plt.subplots(1, 2, figsize=(18, 7), facecolor='#0d1117')
    fig.suptitle(f'Team Heatmaps — NBA Court ({int(sec)}s)', color='white', fontsize=14)

    for ax, ids, label, cmap in [
        (axes[0], team1_ids, 'White Team', 'Blues'),
        (axes[1], team2_ids, 'Navy Team',  'Oranges'),
    ]:
        ax.set_facecolor('#1a1a2e')
        ax.set_title(label, color='white', fontsize=12)
        all_pts = [(p[1], p[0]) for tid in ids for p in traj[tid]]
        if all_pts:
            xs = [p[0] for p in all_pts]
            ys = [p[1] for p in all_pts]
            hm, _, _ = np.histogram2d(xs, ys, bins=[48, 24],
                                       range=[[-COURT_HALF_LEN, COURT_HALF_LEN],
                                              [-COURT_HALF_WID, COURT_HALF_WID]])
            ax.imshow(hm.T, origin='lower', cmap=cmap, aspect='auto',
                      extent=[-COURT_HALF_LEN, COURT_HALF_LEN,
                               -COURT_HALF_WID,  COURT_HALF_WID], alpha=0.85)
        ax.add_patch(patches.Rectangle(
            (-COURT_HALF_LEN, -COURT_HALF_WID),
            2*COURT_HALF_LEN, 2*COURT_HALF_WID,
            lw=1.5, edgecolor='white', facecolor='none'))
        ax.axvline(0, color='white', lw=0.8, alpha=0.4)
        ax.tick_params(colors='white')
        ax.set_xlabel('Court Y (cm)', color='white')
        ax.set_ylabel('Court X (cm)', color='white')

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUT_DIR / f'team_heatmap_{int(sec)}s.png', dpi=110,
                bbox_inches='tight', facecolor='#0d1117')
    plt.close(fig)
    print(f"Saved: team_heatmap_{int(sec)}s.png")

    # ═══════════════════════════════════════════════════════
    #  3. 選手ごとトラジェクトリ（チームごと）
    # ═══════════════════════════════════════════════════════
    for team_ids, label, color in [
        (team1_ids, 'White', '#88aaff'),
        (team2_ids, 'Navy',  '#ff8866'),
    ]:
        if not team_ids:
            continue
        n   = len(team_ids)
        cols = min(n, 4)
        rows = (n + cols - 1) // cols

        fig, axes = plt.subplots(rows, cols, figsize=(cols*4.5, rows*4),
                                  facecolor='#0d1117')
        axes_flat = list(np.array(axes).flat) if n > 1 else [axes]
        fig.suptitle(f'{label} Team — Individual Trajectories ({int(sec)}s)',
                     color='white', fontsize=13)

        for i, tid in enumerate(team_ids):
            ax = axes_flat[i]
            ax.set_facecolor('#1a1a2e')
            pts = traj[tid]
            if pts:
                xs = [p[1] for p in pts]
                ys = [p[0] for p in pts]
                ts_arr = [p[2] for p in pts]
                sc = ax.scatter(xs, ys, c=ts_arr, cmap='plasma', s=5, alpha=0.8)
                ax.plot(xs, ys, color=color, alpha=0.25, lw=0.8)
                ax.scatter(xs[-1], ys[-1], color='white', s=50, zorder=6)
                dist = sum(np.hypot(pts[j+1][0]-pts[j][0], pts[j+1][1]-pts[j][1])
                           for j in range(len(pts)-1))
                t_on = pts[-1][2] - pts[0][2]
            else:
                dist, t_on = 0, 0

            ax.add_patch(patches.Rectangle(
                (-COURT_HALF_LEN, -COURT_HALF_WID),
                2*COURT_HALF_LEN, 2*COURT_HALF_WID,
                lw=1, edgecolor='#555', facecolor='none'))
            ax.axvline(0, color='#555', lw=0.6, alpha=0.5)
            ax.set_xlim(-COURT_HALF_LEN-20, COURT_HALF_LEN+20)
            ax.set_ylim(-COURT_HALF_WID-20, COURT_HALF_WID+20)
            ax.set_aspect('equal')
            ax.set_title(f'P{tid%100}  dist={dist:.0f}cm  {t_on:.0f}s on-court',
                         color='white', fontsize=9)
            ax.axis('off')

        for ax in axes_flat[n:]:
            ax.axis('off')

        plt.tight_layout(rect=[0, 0, 1, 0.94])
        fname = f'traj_{label.lower()}_{int(sec)}s.png'
        fig.savefig(OUT_DIR / fname, dpi=100, bbox_inches='tight',
                    facecolor='#0d1117')
        plt.close(fig)
        print(f"Saved: {fname}")

    # ═══════════════════════════════════════════════════════
    #  4. 移動距離バーチャート（全選手比較）
    # ═══════════════════════════════════════════════════════
    player_dist = {}
    for tid, pts in traj.items():
        if len(pts) < 5:
            continue
        d = sum(np.hypot(pts[j+1][0]-pts[j][0], pts[j+1][1]-pts[j][1])
                for j in range(len(pts)-1))
        player_dist[tid] = d / 100   # cm → m (概算)

    if player_dist:
        sorted_ids = sorted(player_dist, key=player_dist.get, reverse=True)
        bar_colors = ['#88aaff' if player_team.get(t)==1
                      else '#ff8866' if player_team.get(t)==2
                      else '#888' for t in sorted_ids]
        fig, ax = plt.subplots(figsize=(max(10, len(sorted_ids)*0.9), 5),
                                facecolor='#0d1117')
        ax.set_facecolor('#1a1a2e')
        bars = ax.bar([f'P{t%100}' for t in sorted_ids],
                      [player_dist[t] for t in sorted_ids],
                      color=bar_colors, edgecolor='#333', width=0.65)
        for bar, val in zip(bars, [player_dist[t] for t in sorted_ids]):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.5,
                    f'{val:.0f}m', ha='center', color='white', fontsize=9)
        ax.set_ylabel('Distance (m, approx)', color='white')
        ax.set_title(f'Distance Run per Player ({int(sec)}s)  '
                     f'Blue=White Team  Orange=Navy Team',
                     color='white', fontsize=12)
        ax.tick_params(colors='white')
        for sp in ax.spines.values():
            sp.set_color('#444')
        legend = [Patch(facecolor='#88aaff', label='White Team'),
                  Patch(facecolor='#ff8866', label='Navy Team')]
        ax.legend(handles=legend, facecolor='#1a1a2e', labelcolor='white')
        plt.tight_layout()
        fig.savefig(OUT_DIR / f'distance_{int(sec)}s.png', dpi=110,
                    bbox_inches='tight', facecolor='#0d1117')
        plt.close(fig)
        print(f"Saved: distance_{int(sec)}s.png")

    # ═══════════════════════════════════════════════════════
    #  5. トラッキングデータ JSON 保存
    # ═══════════════════════════════════════════════════════
    tracking_out = {
        'meta': {'sec': sec, 'fps': fps, 'n_frames': n_frames},
        'teams': {
            'white': team1_ids,
            'navy':  team2_ids,
        },
        'player_team': {str(k): v for k, v in player_team.items()},
        'trajectories': {
            str(tid): [{'x': p[0], 'y': p[1], 'ts': p[2], 'team': p[3]}
                       for p in pts]
            for tid, pts in traj.items() if len(pts) >= 5
        },
        'shots': shots,
    }
    json_path = OUT_DIR / f'tracking_{int(sec)}s.json'
    with open(json_path, 'w') as f:
        json.dump(tracking_out, f)
    print(f"Saved: {json_path}")
    print(f"\nAll outputs in: {OUT_DIR}/")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--sec', type=float, default=60.0)
    args = parser.parse_args()
    main(args.sec)

"""
SAM3ボール軌跡からシュートを検出して可視化
- コート座標への変換は行わない（ホモグラフィー不要）
- 検出されたシュートの開始ピクセル座標をフレーム上に重ねて表示
"""
import cv2, json, numpy as np
from pathlib import Path
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

import argparse

VIDEO     = "data/videos/game_EE1swQMsXJc_720p.mp4"
SAM3_BALL = "ball_positions_sam3_60s.json"   # --sam3 で上書き可
TRACKING  = "outputs/shot_player/tracking_60s.json"
OUT_DIR   = Path("outputs/shot_player")
OUT_DIR.mkdir(parents=True, exist_ok=True)


class ShotDetector:
    """SAM3の3フレーム重複に対応したシュート検出器（放物線フィット）"""

    def __init__(self, window_sec=1.2, cooldown=2.5):
        self.window_sec = window_sec
        self.cooldown   = cooldown
        self.unique_pos = []
        self.last_shot  = -999
        self.shots      = []
        self._prev_pos  = None

    def update(self, ball_px, fi, ts):
        if ball_px is None:
            return
        px, py = float(ball_px[0]), float(ball_px[1])

        # 重複除去
        if self._prev_pos is not None:
            if abs(px - self._prev_pos[0]) < 0.5 and abs(py - self._prev_pos[1]) < 0.5:
                return
        self._prev_pos = (px, py)
        self.unique_pos.append((ts, px, py))

        cutoff = ts - self.window_sec
        self.unique_pos = [(t, x, y) for t, x, y in self.unique_pos if t >= cutoff]

        if len(self.unique_pos) < 5:
            return
        if ts - self.last_shot < self.cooldown:
            return

        pts    = self.unique_pos
        ts_arr = np.array([p[0] for p in pts])
        xs_arr = np.array([p[1] for p in pts])
        ys_arr = np.array([p[2] for p in pts])

        dur = ts_arr[-1] - ts_arr[0]
        if dur < 0.25 or dur > 2.5:
            return
        if ys_arr.max() - ys_arr.min() < 60:
            return

        # 前半で上昇（y減少）しているかチェック
        mid = len(pts) // 2
        if np.mean(np.diff(ys_arr[:mid+1])) >= 0:
            return

        # 放物線フィット（t vs y）
        try:
            coeffs = np.polyfit(ts_arr, ys_arr, 2)
        except Exception:
            return
        if coeffs[0] <= 0:
            return

        y_pred = np.polyval(coeffs, ts_arr)
        ss_res = np.sum((ys_arr - y_pred) ** 2)
        ss_tot = np.sum((ys_arr - ys_arr.mean()) ** 2)
        if ss_tot < 1 or (1 - ss_res / ss_tot) < 0.70:
            return

        self.shots.append({
            'ts':      float(ts_arr[0]),
            'fi':      fi,
            'px':      (float(xs_arr[0]), float(ys_arr[0])),
            'n_pts':   len(pts),
            'dur':     dur,
            'y_range': float(ys_arr.max() - ys_arr.min()),
        })
        self.last_shot = ts
        print(f"  Shot t={ts_arr[0]:.2f}s  px=({xs_arr[0]:.0f},{ys_arr[0]:.0f})"
              f"  n={len(pts)}  dur={dur:.2f}s  Δy={ys_arr.max()-ys_arr.min():.0f}px")


def get_frame(cap, fi):
    cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
    ret, frame = cap.read()
    return frame if ret else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sam3", default=SAM3_BALL)
    parser.add_argument("--tag",  default=None, help="出力ファイル名のタグ (例: 300s)")
    args = parser.parse_args()

    sam3_path = args.sam3
    tag = args.tag or Path(sam3_path).stem.split("_")[-1]  # e.g. "300s"

    print(f"Loading SAM3 ball data: {sam3_path}")
    with open(sam3_path) as f:
        ball_raw = json.load(f)
    ball_data = {int(k): v for k, v in ball_raw.items()}

    print("Loading player tracking data ...")
    with open(TRACKING) as f:
        tracking = json.load(f)
    player_team  = {int(k): v for k, v in tracking.get('player_team', {}).items()}
    trajectories = {int(k): v for k, v in tracking.get('trajectories', {}).items()}

    team1_ids = sorted([t for t, tm in player_team.items()
                        if tm == 1 and len(trajectories.get(t, [])) >= 10])
    team2_ids = sorted([t for t, tm in player_team.items()
                        if tm == 2 and len(trajectories.get(t, [])) >= 10])

    cap = cv2.VideoCapture(VIDEO)
    fps = cap.get(cv2.CAP_PROP_FPS)

    # ── シュート検出 ──────────────────────────────────────────────────────────
    print("\nRunning shot detection ...")
    detector = ShotDetector(window_sec=1.2, cooldown=2.5)
    for fi in sorted(ball_data.keys()):
        detector.update(ball_data[fi], fi, fi / fps)

    shots = detector.shots
    print(f"Total shots detected: {len(shots)}")

    # ── 選手帰属（ピクセル距離で最近傍） ─────────────────────────────────────
    # tracking_60s.json の trajectories は court座標なので使えない
    # → 各フレームでYOLO再検出は重いので省略し player_id は未設定
    # (tracking.json の pixel座標があれば使えるがここでは省略)

    # ── シュートチャート: 動画フレームにプロット ─────────────────────────────
    n = len(shots)
    if n == 0:
        print("No shots detected.")
        cap.release()
        return

    # グリッドレイアウト
    n_col = min(n, 4)
    n_row = (n + n_col - 1) // n_col

    fig, axes = plt.subplots(n_row, n_col,
                              figsize=(n_col * 5, n_row * 3.5),
                              facecolor='#0d1117')
    axes_flat = list(np.array(axes).flat) if n > 1 else [axes]
    for ax in axes_flat:
        ax.set_facecolor('#0d1117')

    fig.suptitle(f'Shot Detection — Video Frame View (60s)\n'
                 f'Ball trajectory apex in image coordinates',
                 color='white', fontsize=13)

    TEAM_COLORS = {1: '#88aaff', 2: '#ff8866', -1: '#aaaaaa'}

    for idx, s in enumerate(shots):
        ax = axes_flat[idx]
        fi = int(s['ts'] * fps)

        # フレームを取得して背景に
        frame = get_frame(cap, fi)
        if frame is not None:
            ax.imshow(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        else:
            ax.set_facecolor('#111')

        px, py = s['px']
        team   = s.get('team', -1)
        color  = TEAM_COLORS.get(team, '#aaaaaa')

        # シュート位置をプロット
        ax.scatter(px, py, s=300, c=color, marker='o',
                   edgecolors='white', linewidths=1.5, zorder=5)
        ax.scatter(px, py, s=1200, c=color, marker='o',
                   alpha=0.25, zorder=4)

        mm, ss = int(s['ts']//60), int(s['ts']%60)
        team_name = {1:'White', 2:'Navy'}.get(team, '?')
        ax.set_title(f't={mm}:{ss:02d}  {team_name}\n'
                     f'Δy={s["y_range"]:.0f}px  n={s["n_pts"]}pts',
                     color='white', fontsize=9, pad=4)
        ax.axis('off')

    for ax in axes_flat[n:]:
        ax.axis('off')

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    out_path = OUT_DIR / f'shot_chart_frame_{tag}.png'
    fig.savefig(out_path, dpi=110, bbox_inches='tight', facecolor='#0d1117')
    plt.close(fig)
    print(f"Saved: {out_path}")

    # ── 全体サムネ（ボール軌跡を1枚にまとめる） ─────────────────────────────
    # 代表フレーム（中間）を背景にして全シュート位置をプロット
    mid_fi = int(fps * 30)  # 30秒付近のフレーム
    frame_bg = get_frame(cap, mid_fi)
    cap.release()

    if frame_bg is not None:
        fig, ax = plt.subplots(figsize=(12, 7), facecolor='#0d1117')
        ax.imshow(cv2.cvtColor(frame_bg, cv2.COLOR_BGR2RGB))
        ax.set_title('All Shots — Image Space (60s)', color='white', fontsize=13, pad=8)

        for s in shots:
            px, py = s['px']
            team   = s.get('team', -1)
            color  = TEAM_COLORS.get(team, '#aaaaaa')
            mm, ss = int(s['ts']//60), int(s['ts']%60)
            ax.scatter(px, py, s=200, c=color, marker='o',
                       edgecolors='white', linewidths=1.5, zorder=5)
            ax.annotate(f"{mm}:{ss:02d}", (px, py),
                        textcoords='offset points', xytext=(8, 4),
                        color='white', fontsize=8,
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='#000', alpha=0.5))

        from matplotlib.lines import Line2D
        legend = [
            Line2D([0],[0], marker='o', color='#88aaff', lw=0, markersize=9, label='White Team'),
            Line2D([0],[0], marker='o', color='#ff8866', lw=0, markersize=9, label='Navy Team'),
        ]
        ax.legend(handles=legend, facecolor='#1a1a2e', labelcolor='white',
                  fontsize=10, loc='upper left')
        ax.axis('off')
        plt.tight_layout()
        out2 = OUT_DIR / f'shot_chart_all_{tag}.png'
        fig.savefig(out2, dpi=110, bbox_inches='tight', facecolor='#0d1117')
        plt.close(fig)
        print(f"Saved: {out2}")

    # ── JSON保存 ─────────────────────────────────────────────────────────────
    shots_out = [{'ts': s['ts'], 'px': list(s['px']),
                  'team': s.get('team', -1), 'y_range': s['y_range']}
                 for s in shots]
    with open(OUT_DIR / f'shots_{tag}.json', 'w') as f:
        json.dump(shots_out, f, indent=2)
    print(f"Saved: shots_{tag}.json ({len(shots_out)} shots)")

    print(f"\n=== {len(shots)} shots detected ({tag}) ===")
    for s in shots:
        mm, ss = int(s['ts']//60), int(s['ts']%60)
        print(f"  {mm:02d}:{ss:02d}  px=({s['px'][0]:.0f},{s['px'][1]:.0f})"
              f"  Δy={s['y_range']:.0f}px")


if __name__ == '__main__':
    main()

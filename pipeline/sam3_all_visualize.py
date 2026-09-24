"""
SAM3一本勝負の結果を動画に可視化

Usage:
  python sam3_all_visualize.py --json sam3_all_objects_60s.json
"""

import cv2
import json
import numpy as np
import argparse
import subprocess
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

VIDEO   = "data/videos/game_EE1swQMsXJc_720p.mp4"
OUT_DIR = Path("outputs/sam3_all")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 描画色
C_BALL   = (0, 140, 255)    # オレンジ
C_HOOP   = (0, 255, 0)      # 緑
C_PLAYER = (255, 220, 50)   # 黄色
C_TEXT   = (255, 255, 255)  # 白


def draw_frame(frame, data):
    out = frame.copy()

    # 選手
    for i, p in enumerate(data.get('players', [])):
        x1, y1, x2, y2 = p['bbox']
        score = p.get('score', 0)
        cv2.rectangle(out, (x1, y1), (x2, y2), C_PLAYER, 2)
        cv2.putText(out, f"P{i+1} {score:.2f}", (x1, max(0, y1-6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 3)
        cv2.putText(out, f"P{i+1} {score:.2f}", (x1, max(0, y1-6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, C_PLAYER, 1)

    # ゴール
    if data.get('hoop'):
        hx, hy = int(data['hoop'][0]), int(data['hoop'][1])
        cv2.circle(out, (hx, hy), 22, C_HOOP, 3)
        cv2.putText(out, 'HOOP', (hx+24, hy+6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,0), 3)
        cv2.putText(out, 'HOOP', (hx+24, hy+6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, C_HOOP, 1)

    # ボール
    if data.get('ball'):
        bx, by = int(data['ball'][0]), int(data['ball'][1])
        cv2.circle(out, (bx, by), 14, C_BALL, -1)
        cv2.circle(out, (bx, by), 14, C_TEXT, 2)
        cv2.putText(out, 'BALL', (bx+16, by+6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,0), 3)
        cv2.putText(out, 'BALL', (bx+16, by+6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, C_BALL, 1)

    return out


def make_video(all_results, n_frames, fps, W, H, out_path):
    cap = cv2.VideoCapture(VIDEO)
    tmp = str(out_path).replace('.mp4', '_tmp.mp4')
    writer = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*'mp4v'), fps, (W, H))

    for fi in range(n_frames):
        ret, frame = cap.read()
        if not ret:
            break
        data = all_results.get(str(fi), {})
        out = draw_frame(frame, data)

        n_p = len(data.get('players', []))
        has_ball = '✓' if data.get('ball') else '-'
        has_hoop = '✓' if data.get('hoop') else '-'
        t = fi / fps
        hud = f"SAM3  t={t:.1f}s  Ball:{has_ball}  Hoop:{has_hoop}  Players:{n_p}"
        cv2.putText(out, hud, (10, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0,0,0), 3)
        cv2.putText(out, hud, (10, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, C_TEXT, 1)
        writer.write(out)

    cap.release()
    writer.release()
    subprocess.run(['ffmpeg', '-y', '-i', tmp,
                    '-vcodec', 'libx264', '-pix_fmt', 'yuv420p',
                    '-crf', '23', '-movflags', '+faststart', str(out_path)],
                   capture_output=True)
    Path(tmp).unlink(missing_ok=True)
    print(f'動画: {out_path}')


def make_dashboard(all_results, n_frames, fps, out_path):
    frames_with_data = {int(k): v for k, v in all_results.items()}

    ball_xs, ball_ys, ball_ts = [], [], []
    hoop_xs, hoop_ys = [], []
    player_counts = []

    for fi in range(n_frames):
        d = frames_with_data.get(fi, {})
        if d.get('ball'):
            ball_xs.append(d['ball'][0])
            ball_ys.append(d['ball'][1])
            ball_ts.append(fi / fps)
        if d.get('hoop'):
            hoop_xs.append(d['hoop'][0])
            hoop_ys.append(d['hoop'][1])
        player_counts.append(len(d.get('players', [])))

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), facecolor='#0d1117')
    fig.suptitle('SAM3 One-Model Detection Dashboard (60s)', color='white', fontsize=15)

    # 1. ボール軌跡
    ax = axes[0, 0]
    ax.set_facecolor('#1a1a2e')
    ax.set_title('Ball Trajectory', color='white')
    if ball_xs:
        sc = ax.scatter(ball_xs, ball_ys, c=ball_ts, cmap='plasma', s=4, alpha=0.8)
        plt.colorbar(sc, ax=ax).ax.yaxis.label.set_color('white')
    if hoop_xs:
        ax.scatter(np.mean(hoop_xs), np.mean(hoop_ys), c='lime', s=200,
                   marker='*', zorder=5, label='Hoop')
        ax.legend(facecolor='#1a1a2e', labelcolor='white')
    ax.set_xlim(0, 1280); ax.set_ylim(720, 0)
    ax.tick_params(colors='white')
    for sp in ax.spines.values(): sp.set_color('#444')

    # 2. ボールヒートマップ
    ax = axes[0, 1]
    ax.set_facecolor('#1a1a2e')
    ax.set_title('Ball Heatmap', color='white')
    if ball_xs:
        hm, xe, ye = np.histogram2d(ball_xs, ball_ys, bins=[32, 18],
                                     range=[[0,1280],[0,720]])
        ax.imshow(hm.T, origin='upper', cmap='hot', aspect='auto',
                  extent=[0, 1280, 720, 0])
    ax.tick_params(colors='white')

    # 3. 選手検出数の時系列
    ax = axes[1, 0]
    ax.set_facecolor('#1a1a2e')
    ax.set_title('Player Count Over Time', color='white')
    ts_all = [fi / fps for fi in range(len(player_counts))]
    ax.fill_between(ts_all, player_counts, alpha=0.6, color='#ffaa00')
    ax.plot(ts_all, player_counts, color='#ffaa00', lw=0.8)
    ax.set_xlabel('Time (s)', color='white'); ax.set_ylabel('Players', color='white')
    ax.set_xlim(0, max(ts_all)); ax.tick_params(colors='white')
    for sp in ax.spines.values(): sp.set_color('#444')

    # 4. 検出率まとめ
    ax = axes[1, 1]
    ax.set_facecolor('#1a1a2e')
    ax.set_title('Detection Summary', color='white')
    n_ball_det = len(ball_xs)
    n_hoop_det = len(hoop_xs)
    n_player_det = sum(1 for c in player_counts if c > 0)
    labels = ['Ball', 'Hoop', 'Players\n(any)']
    rates = [100*n_ball_det/n_frames, 100*n_hoop_det/n_frames, 100*n_player_det/n_frames]
    colors = ['#ff8c00', '#00ff00', '#ffd700']
    bars = ax.bar(labels, rates, color=colors, edgecolor='#444', width=0.5)
    ax.set_ylim(0, 110); ax.axhline(100, color='white', ls='--', lw=0.8, alpha=0.4)
    ax.set_ylabel('Detection Rate (%)', color='white'); ax.tick_params(colors='white')
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1,
                f'{rate:.1f}%', ha='center', va='bottom', color='white', fontsize=12)
    for sp in ax.spines.values(): sp.set_color('#444')

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(out_path, dpi=120, bbox_inches='tight', facecolor='#0d1117')
    print(f'ダッシュボード: {out_path}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', required=True)
    parser.add_argument('--no-video', action='store_true')
    args = parser.parse_args()

    all_results = json.load(open(args.json))
    n_frames = len(all_results)

    cap = cv2.VideoCapture(VIDEO)
    fps = cap.get(cv2.CAP_PROP_FPS)
    W   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    sec = int(n_frames / fps)
    print(f'フレーム数: {n_frames} ({sec}秒)')

    # 統計
    n_ball   = sum(1 for v in all_results.values() if v.get('ball'))
    n_hoop   = sum(1 for v in all_results.values() if v.get('hoop'))
    n_player = sum(1 for v in all_results.values() if v.get('players'))
    print(f'ボール検出率 : {100*n_ball/n_frames:.1f}%')
    print(f'ゴール検出率 : {100*n_hoop/n_frames:.1f}%')
    print(f'選手検出率   : {100*n_player/n_frames:.1f}%')

    make_dashboard(all_results, n_frames, fps,
                   OUT_DIR / f'sam3_all_dashboard_{sec}s.png')

    if not args.no_video:
        make_video(all_results, n_frames, fps, W, H,
                   OUT_DIR / f'sam3_all_{sec}s.mp4')


if __name__ == '__main__':
    main()

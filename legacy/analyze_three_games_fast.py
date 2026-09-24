#!/usr/bin/env python3
"""
3試合のYouTube動画から高速でシュートチャートとPlay-by-Playを生成

使い方:
    python analyze_three_games_fast.py
"""

import cv2
import numpy as np
from pathlib import Path
import pandas as pd
from ultralytics import YOLO
from tqdm import tqdm
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from collections import defaultdict
import json
from datetime import datetime

# 日本語フォント設定
plt.rcParams['font.family'] = 'Hiragino Sans'
plt.rcParams['font.size'] = 10

class FastThreeGameAnalyzer:
    def __init__(self):
        self.output_dir = Path("outputs/three_games")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # YOLO モデル読み込み
        print("YOLOv8モデル読み込み中...")
        self.model = YOLO('yolov8n.pt')  # nanoモデル（高速）

        # ゴール位置（想定）
        self.goal_top = (470, 50)      # トップゴール（x, y）
        self.goal_bottom = (470, 670)  # ボトムゴール

        # シュート検出パラメータ
        self.shot_threshold = 80  # ゴールとの距離閾値（ピクセル）
        self.time_window = 3.0    # シュート判定の時間窓（秒）

    def analyze_game_fast(self, video_path: str, game_name: str):
        """1試合を高速分析（10フレームに1回サンプリング）"""
        print(f"\n{'='*80}")
        print(f"試合分析開始: {game_name}")
        print(f"動画: {video_path}")
        print(f"{'='*80}\n")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"❌ 動画が開けません: {video_path}")
            return None

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        print(f"📊 動画情報:")
        print(f"   FPS: {fps:.2f}")
        print(f"   総フレーム数: {total_frames}")
        print(f"   長さ: {duration/60:.1f}分\n")

        # ボール検出（高速モード）
        shots = self.detect_shots_fast(cap, fps, total_frames)
        cap.release()

        print(f"\n✅ 検出完了: {len(shots)}本のシュート\n")

        # 結果保存
        game_data = {
            'game_name': game_name,
            'video_path': video_path,
            'fps': fps,
            'duration': duration,
            'shots': shots,
            'timestamp': datetime.now().isoformat()
        }

        return game_data

    def detect_shots_fast(self, cap, fps, total_frames):
        """ボールを高速検出してシュートを判定（10フレームに1回）"""
        shots = []
        ball_positions = []

        # フレームサンプリング（10フレームに1回 = 約3fps相当）
        sample_interval = 10
        sample_frames = list(range(0, total_frames, sample_interval))

        print(f"🔍 ボール検出中... ({len(sample_frames)}フレーム、約{len(sample_frames)/(total_frames/fps):.1f}fps)")

        for frame_idx in tqdm(sample_frames, desc="検出中"):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                continue

            # YOLO検出
            results = self.model(frame, classes=[32], verbose=False, conf=0.4)  # 信頼度40%以上

            # ボール検出
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2
                    ball_positions.append((frame_idx, cx, cy, conf))

        print(f"   検出したボール: {len(ball_positions)}個")

        # シュート判定
        print(f"\n🏀 シュート判定中...")
        for i, (frame, x, y, conf) in enumerate(ball_positions):
            # トップゴールとの距離
            dist_top = np.sqrt((x - self.goal_top[0])**2 + (y - self.goal_top[1])**2)
            # ボトムゴールとの距離
            dist_bottom = np.sqrt((x - self.goal_bottom[0])**2 + (y - self.goal_bottom[1])**2)

            # ゴールに近い場合はシュートとみなす
            if dist_top < self.shot_threshold:
                time_sec = frame / fps
                shots.append({
                    'frame': frame,
                    'time': time_sec,
                    'x': float(x),
                    'y': float(y),
                    'goal': 'top',
                    'confidence': float(conf),
                    'distance': float(dist_top)
                })
            elif dist_bottom < self.shot_threshold:
                time_sec = frame / fps
                shots.append({
                    'frame': frame,
                    'time': time_sec,
                    'x': float(x),
                    'y': float(y),
                    'goal': 'bottom',
                    'confidence': float(conf),
                    'distance': float(dist_bottom)
                })

        # 重複除去（時間が近いシュートを統合）
        shots = self.merge_duplicate_shots(shots)

        return shots

    def merge_duplicate_shots(self, shots):
        """時間が近いシュートを統合"""
        if not shots:
            return []

        shots_sorted = sorted(shots, key=lambda s: s['time'])
        merged = [shots_sorted[0]]

        for shot in shots_sorted[1:]:
            if shot['time'] - merged[-1]['time'] > self.time_window:
                merged.append(shot)

        return merged

    def create_shot_chart(self, game_data):
        """シュートチャート作成"""
        game_name = game_data['game_name']
        shots = game_data['shots']

        if not shots:
            print(f"⚠️ {game_name}: シュートが検出されませんでした")
            return

        fig, ax = plt.subplots(figsize=(10, 12))

        # コート描画（簡易版）
        self.draw_simple_court(ax)

        # シュートプロット
        top_shots = [s for s in shots if s['goal'] == 'top']
        bottom_shots = [s for s in shots if s['goal'] == 'bottom']

        if top_shots:
            top_x = [s['x'] for s in top_shots]
            top_y = [s['y'] for s in top_shots]
            ax.scatter(top_x, top_y, c='red', s=100, alpha=0.6,
                      edgecolors='darkred', linewidths=2, label=f'トップゴール ({len(top_shots)}本)')

        if bottom_shots:
            bottom_x = [s['x'] for s in bottom_shots]
            bottom_y = [s['y'] for s in bottom_shots]
            ax.scatter(bottom_x, bottom_y, c='blue', s=100, alpha=0.6,
                      edgecolors='darkblue', linewidths=2, label=f'ボトムゴール ({len(bottom_shots)}本)')

        # タイトル・ラベル
        ax.set_title(f'{game_name} - シュートチャート\n総シュート数: {len(shots)}本',
                    fontsize=16, fontweight='bold', pad=20)
        ax.legend(loc='upper right', fontsize=12)
        ax.set_xlim(0, 940)
        ax.set_ylim(720, 0)  # Y軸反転
        ax.axis('off')

        # 保存
        output_path = self.output_dir / f"{game_name}_shot_chart.png"
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        print(f"✅ シュートチャート保存: {output_path}")

    def draw_simple_court(self, ax):
        """簡易コート描画"""
        # 背景
        ax.set_facecolor('#f0f0f0')

        # アウトライン
        court = patches.Rectangle((50, 0), 840, 720,
                                  linewidth=3, edgecolor='black', facecolor='white')
        ax.add_patch(court)

        # センターライン
        ax.plot([50, 890], [360, 360], 'k-', linewidth=2)

        # トップゴール
        top_goal = patches.Rectangle((420, 0), 100, 50,
                                     linewidth=2, edgecolor='orange',
                                     facecolor='lightcoral', alpha=0.5)
        ax.add_patch(top_goal)
        ax.text(470, 25, 'TOP', ha='center', va='center',
               fontsize=14, fontweight='bold')

        # ボトムゴール
        bottom_goal = patches.Rectangle((420, 670), 100, 50,
                                        linewidth=2, edgecolor='orange',
                                        facecolor='lightblue', alpha=0.5)
        ax.add_patch(bottom_goal)
        ax.text(470, 695, 'BOTTOM', ha='center', va='center',
               fontsize=14, fontweight='bold')

        # 3Pライン（簡易）
        arc_top = patches.Arc((470, 50), 400, 400, theta1=180, theta2=0,
                             linewidth=2, edgecolor='green', linestyle='--')
        arc_bottom = patches.Arc((470, 670), 400, 400, theta1=0, theta2=180,
                                linewidth=2, edgecolor='green', linestyle='--')
        ax.add_patch(arc_top)
        ax.add_patch(arc_bottom)

    def create_play_by_play(self, game_data):
        """Play-by-Play CSV作成"""
        game_name = game_data['game_name']
        shots = game_data['shots']

        if not shots:
            print(f"⚠️ {game_name}: シュートが検出されませんでした")
            return

        # データフレーム作成
        pbp_data = []
        for i, shot in enumerate(shots, 1):
            time_min = int(shot['time'] // 60)
            time_sec = int(shot['time'] % 60)

            pbp_data.append({
                'No': i,
                '時刻': f"{time_min:02d}:{time_sec:02d}",
                '時刻(秒)': shot['time'],
                'ゴール': 'トップ' if shot['goal'] == 'top' else 'ボトム',
                'X座標': shot['x'],
                'Y座標': shot['y'],
                '信頼度': shot['confidence'],
                'ゴールまでの距離': shot['distance']
            })

        df = pd.DataFrame(pbp_data)

        # CSV保存
        output_path = self.output_dir / f"{game_name}_play_by_play.csv"
        df.to_csv(output_path, index=False, encoding='utf-8-sig')

        print(f"✅ Play-by-Play保存: {output_path}")
        print(f"\n【{game_name} Play-by-Play サンプル】")
        print(df.head(10).to_string(index=False))
        print(f"... (全{len(df)}行)\n")

        return df

    def create_summary_report(self, all_games_data):
        """3試合の統計サマリーレポート"""
        print(f"\n{'='*80}")
        print("📊 3試合統計サマリー作成中...")
        print(f"{'='*80}\n")

        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("3試合分析レポート")
        report_lines.append(f"作成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 80)
        report_lines.append("")

        total_shots = 0

        for game_data in all_games_data:
            game_name = game_data['game_name']
            shots = game_data['shots']
            duration = game_data['duration']

            top_shots = [s for s in shots if s['goal'] == 'top']
            bottom_shots = [s for s in shots if s['goal'] == 'bottom']

            total_shots += len(shots)

            report_lines.append(f"【{game_name}】")
            report_lines.append(f"  試合時間: {duration/60:.1f}分")
            report_lines.append(f"  総シュート数: {len(shots)}本")
            report_lines.append(f"    - トップゴール: {len(top_shots)}本")
            report_lines.append(f"    - ボトムゴール: {len(bottom_shots)}本")

            if shots:
                avg_conf = np.mean([s['confidence'] for s in shots])
                report_lines.append(f"  平均信頼度: {avg_conf:.2%}")

                shot_rate = len(shots) / (duration / 60)  # シュート/分
                report_lines.append(f"  シュートレート: {shot_rate:.1f}本/分")

            report_lines.append("")

        # 総合統計
        report_lines.append("=" * 80)
        report_lines.append("【総合統計】")
        report_lines.append(f"  分析試合数: {len(all_games_data)}試合")
        report_lines.append(f"  総シュート数: {total_shots}本")
        if len(all_games_data) > 0:
            report_lines.append(f"  試合平均: {total_shots/len(all_games_data):.1f}本/試合")
        report_lines.append("=" * 80)

        # ファイル保存
        report_text = "\n".join(report_lines)
        output_path = self.output_dir / "summary_report.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)

        print(report_text)
        print(f"\n✅ サマリーレポート保存: {output_path}")

        return report_text

    def run_analysis(self):
        """3試合を一括分析"""
        games = [
            ("data/videos/game_2-1.mp4", "試合2-1"),
            ("data/videos/game_2-2.mp4", "試合2-2"),
            ("data/videos/game_2-3.mp4", "試合2-3"),
        ]

        all_games_data = []

        for video_path, game_name in games:
            if not Path(video_path).exists():
                print(f"⚠️ 動画が見つかりません: {video_path}")
                continue

            # 試合分析
            game_data = self.analyze_game_fast(video_path, game_name)
            if game_data:
                all_games_data.append(game_data)

                # シュートチャート生成
                self.create_shot_chart(game_data)

                # Play-by-Play生成
                self.create_play_by_play(game_data)

        # 統計サマリー
        if all_games_data:
            self.create_summary_report(all_games_data)

            # 全試合データをJSON保存
            json_path = self.output_dir / "all_games_data.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(all_games_data, f, indent=2, ensure_ascii=False)
            print(f"\n✅ 全試合データ保存: {json_path}")

        print(f"\n{'='*80}")
        print("🎉 3試合の分析が完了しました！")
        print(f"{'='*80}")
        print(f"\n📂 出力ディレクトリ: {self.output_dir}")
        print("\n生成されたファイル:")
        for file in sorted(self.output_dir.iterdir()):
            if file.name != 'analysis.log':
                print(f"  - {file.name}")


def main():
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║        3試合高速自動分析システム                           ║
    ║   シュートチャート + Play-by-Play 一括生成                 ║
    ║   (10フレームに1回サンプリング = 約10倍高速)               ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    analyzer = FastThreeGameAnalyzer()
    analyzer.run_analysis()


if __name__ == "__main__":
    main()

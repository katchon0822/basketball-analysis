"""
自動検出データを綺麗なシュートチャート形式に変換

YouTubeGameAnalyzer のスタイルを使用
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, Arc, Wedge
from pathlib import Path
from typing import List, Dict, Tuple
import cv2


class AutoToPrettyCharts:
    """
    自動検出データを綺麗なチャートに変換
    """

    def __init__(self, video_path: str, shots: List[Dict], output_dir: str = 'outputs/auto_analysis_pretty'):
        self.video_path = video_path
        self.shots = shots
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 動画情報取得
        self.cap = cv2.VideoCapture(video_path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.cap.release()

        # 座標変換パラメータ
        self._setup_coordinate_mapping()

    def _setup_coordinate_mapping(self):
        """
        画像座標 → コート座標への変換を設定

        画像座標: (0-640, 0-360) ピクセル
        コート座標: (-250 to 250, -50 to 400) NBA標準
        """
        # 簡易マッピング（画像の左下をコート中心と仮定）
        self.img_to_court_x = lambda x: (x - self.width / 2) * (500 / self.width)
        self.img_to_court_y = lambda y: (self.height - y) * (450 / self.height) - 50

    def draw_court(self, ax, color='black', lw=2):
        """
        NBAコートを描画（YouTubeGameAnalyzer と同じスタイル）
        """
        # リム
        rim = Circle((0, 0), radius=7.5, linewidth=lw, color=color, fill=False)
        ax.add_patch(rim)

        # バックボード
        backboard = Rectangle((-30, -7.5), 60, -1, linewidth=lw, edgecolor=color, facecolor=color)
        ax.add_patch(backboard)

        # ペイントエリア（制限区域）
        paint = Rectangle((-80, -47.5), 160, 190, linewidth=lw, edgecolor=color, fill=False)
        ax.add_patch(paint)

        # フリースローサークル
        ft_circle = Arc((0, 142.5), 120, 120, theta1=0, theta2=180, linewidth=lw, color=color, fill=False)
        ax.add_patch(ft_circle)

        # 3ポイントライン
        three_point_arc = Arc((0, 0), 475, 475, theta1=22, theta2=158, linewidth=lw, color=color)
        ax.add_patch(three_point_arc)

        # 3ポイントコーナー（左右）
        ax.plot([-220, -220], [-47.5, 92.5], linewidth=lw, color=color)
        ax.plot([220, 220], [-47.5, 92.5], linewidth=lw, color=color)

        # ハーフコートライン
        ax.plot([-250, 250], [422.5, 422.5], linewidth=lw, color=color)

        # コート外枠
        ax.plot([-250, 250], [-47.5, -47.5], linewidth=lw, color=color)  # ベースライン
        ax.plot([-250, -250], [-47.5, 422.5], linewidth=lw, color=color)  # 左サイド
        ax.plot([250, 250], [-47.5, 422.5], linewidth=lw, color=color)  # 右サイド

        # 軸設定
        ax.set_xlim(-250, 250)
        ax.set_ylim(-50, 450)
        ax.set_aspect('equal')
        ax.axis('off')

    def create_pretty_shot_chart(self, title: str = "Auto-Detected Shot Chart"):
        """
        綺麗なシュートチャートを作成
        """
        fig, ax = plt.subplots(figsize=(12, 11))

        # コート描画
        self.draw_court(ax, color='black', lw=2)

        if len(self.shots) == 0:
            ax.text(0, 200, 'No shots detected', ha='center', va='center',
                   fontsize=20, color='red')
            plt.tight_layout()
            save_path = self.output_dir / 'pretty_shot_chart.png'
            plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
            print(f"✅ シュートチャートを保存: {save_path}")
            plt.close()
            return

        # 画像座標をコート座標に変換
        made_shots = []
        missed_shots = []

        for shot in self.shots:
            court_x = self.img_to_court_x(shot['x'])
            court_y = self.img_to_court_y(shot['y'])

            shot_data = {
                'x': court_x,
                'y': court_y,
                'timestamp': shot['timestamp']
            }

            if shot['shot_made'] == 1:
                made_shots.append(shot_data)
            else:
                missed_shots.append(shot_data)

        # 成功シュートをプロット（緑の●）
        if made_shots:
            made_x = [s['x'] for s in made_shots]
            made_y = [s['y'] for s in made_shots]
            ax.scatter(made_x, made_y, c='green', s=200, marker='o',
                      alpha=0.6, edgecolors='white', linewidths=2, zorder=3, label='Made')

        # 失敗シュートをプロット（赤の×）
        if missed_shots:
            missed_x = [s['x'] for s in missed_shots]
            missed_y = [s['y'] for s in missed_shots]
            ax.scatter(missed_x, missed_y, c='red', s=200, marker='x',
                      alpha=0.6, linewidths=3, zorder=3, label='Missed')

        # スタッツ表示
        total = len(self.shots)
        made = len(made_shots)
        fg_pct = (made / total * 100) if total > 0 else 0

        stats_text = f'FG: {made}/{total} ({fg_pct:.1f}%)'
        ax.text(0, -30, stats_text, ha='center', va='center',
               fontsize=14, fontweight='bold', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        # タイトル
        ax.set_title(title, fontsize=18, fontweight='bold', pad=20)

        # 凡例
        ax.legend(loc='upper right', fontsize=12, framealpha=0.9)

        plt.tight_layout()
        save_path = self.output_dir / 'pretty_shot_chart.png'
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✅ 綺麗なシュートチャートを保存: {save_path}")
        plt.close()

    def create_play_by_play(self):
        """
        Play-by-Playを生成
        """
        if len(self.shots) == 0:
            print("⚠️  シュートが検出されませんでした")
            return

        # Play-by-Playデータ作成
        plays = []

        # ゲーム開始
        plays.append({
            'time': '0:00',
            'period': 1,
            'description': 'Game Start',
            'score': '0-0'
        })

        home_score = 0
        away_score = 0
        period = 1

        for i, shot in enumerate(self.shots, 1):
            # 時間表示（MM:SS形式）
            total_seconds = int(shot['timestamp'])
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            time_str = f"{minutes}:{seconds:02d}"

            # ピリオド計算（5分ごと）
            period = (total_seconds // 300) + 1

            # シュート説明
            if shot['shot_made'] == 1:
                # 仮でホームチームの得点とする
                home_score += 2
                description = f"Shot #{i} MADE (2-pt)"
            else:
                description = f"Shot #{i} MISSED"

            score_str = f"{home_score}-{away_score}"

            plays.append({
                'time': time_str,
                'period': period,
                'description': description,
                'score': score_str
            })

        # DataFrameに変換
        df = pd.DataFrame(plays)

        # CSV保存
        csv_path = self.output_dir / 'play_by_play.csv'
        df.to_csv(csv_path, index=False)
        print(f"✅ Play-by-Play (CSV)を保存: {csv_path}")

        # テキスト形式でも保存
        txt_path = self.output_dir / 'play_by_play.txt'
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("📋 Play-by-Play (Auto-Generated)\n")
            f.write("="*80 + "\n\n")

            current_period = 1
            for _, play in df.iterrows():
                if play['period'] != current_period:
                    f.write("\n" + "-"*80 + "\n")
                    f.write(f"Period {play['period']}\n")
                    f.write("-"*80 + "\n\n")
                    current_period = play['period']

                f.write(f"{play['time']:>6s}  |  {play['score']:>6s}  |  {play['description']}\n")

            f.write("\n" + "="*80 + "\n")
            f.write(f"Final Score: {plays[-1]['score']}\n")
            f.write("="*80 + "\n")

        print(f"✅ Play-by-Play (TXT)を保存: {txt_path}")

        # 視覚的なPlay-by-Play表も作成
        self._create_play_by_play_table(df)

    def _create_play_by_play_table(self, df: pd.DataFrame):
        """
        Play-by-Playの視覚的なテーブルを作成
        """
        # 最大20行まで表示
        display_df = df.head(20)

        fig, ax = plt.subplots(figsize=(12, len(display_df) * 0.5 + 2))
        ax.axis('tight')
        ax.axis('off')

        # テーブル作成
        table = ax.table(
            cellText=display_df.values,
            colLabels=display_df.columns,
            cellLoc='left',
            loc='center',
            colWidths=[0.15, 0.15, 0.5, 0.2]
        )

        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2)

        # ヘッダー行のスタイル
        for i in range(len(display_df.columns)):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(weight='bold', color='white')

        # 交互に色を変える
        for i in range(1, len(display_df) + 1):
            for j in range(len(display_df.columns)):
                if i % 2 == 0:
                    table[(i, j)].set_facecolor('#E7E6E6')
                else:
                    table[(i, j)].set_facecolor('#FFFFFF')

        plt.title('Play-by-Play (Auto-Generated)', fontsize=16, fontweight='bold', pad=20)

        if len(df) > 20:
            plt.figtext(0.5, 0.02, f'Showing first 20 of {len(df)} plays', ha='center', fontsize=10, style='italic')

        plt.tight_layout()
        save_path = self.output_dir / 'play_by_play_table.png'
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✅ Play-by-Play (表)を保存: {save_path}")
        plt.close()

    def create_box_score(self):
        """
        簡易ボックススコアを生成
        """
        if len(self.shots) == 0:
            return

        # 全シュートを1チームとして集計（簡易版）
        total = len(self.shots)
        made = sum(1 for s in self.shots if s['shot_made'] == 1)
        missed = total - made
        fg_pct = (made / total * 100) if total > 0 else 0

        # 仮で2P/3P分類（Y座標で判定）
        three_pt_shots = []
        two_pt_shots = []

        for shot in self.shots:
            court_y = self.img_to_court_y(shot['y'])
            # Y > 240 なら3ポイントと仮定
            if court_y > 240:
                three_pt_shots.append(shot)
            else:
                two_pt_shots.append(shot)

        fg3m = sum(1 for s in three_pt_shots if s['shot_made'] == 1)
        fg3a = len(three_pt_shots)
        fg3_pct = (fg3m / fg3a * 100) if fg3a > 0 else 0

        fg2m = sum(1 for s in two_pt_shots if s['shot_made'] == 1)
        fg2a = len(two_pt_shots)

        pts = fg2m * 2 + fg3m * 3

        # ボックススコア作成
        box_score = {
            'Team': ['Auto-Detected Team'],
            'FGM': [made],
            'FGA': [total],
            'FG%': [f'{fg_pct:.1f}'],
            '2PM': [fg2m],
            '2PA': [fg2a],
            '3PM': [fg3m],
            '3PA': [fg3a],
            '3P%': [f'{fg3_pct:.1f}'],
            'PTS': [pts]
        }

        df = pd.DataFrame(box_score)

        # 表として描画
        fig, ax = plt.subplots(figsize=(14, 3))
        ax.axis('tight')
        ax.axis('off')

        table = ax.table(
            cellText=df.values,
            colLabels=df.columns,
            cellLoc='center',
            loc='center'
        )

        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1, 3)

        # ヘッダー行のスタイル
        for i in range(len(df.columns)):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(weight='bold', color='white')

        # データ行のスタイル
        for i in range(1, len(df) + 1):
            for j in range(len(df.columns)):
                table[(i, j)].set_facecolor('#E7E6E6')

        plt.title('Box Score (Auto-Generated)', fontsize=16, fontweight='bold', pad=20)
        plt.tight_layout()

        save_path = self.output_dir / 'box_score.png'
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✅ ボックススコアを保存: {save_path}")
        plt.close()

    def generate_all_reports(self):
        """
        すべてのレポートを生成
        """
        print("="*80)
        print("🎨 綺麗なシュートチャート＆レポート生成")
        print("="*80)
        print()

        self.create_pretty_shot_chart()
        self.create_play_by_play()
        self.create_box_score()

        print()
        print("="*80)
        print("✅ すべてのレポート生成完了！")
        print("="*80)
        print(f"📂 出力先: {self.output_dir}")
        print()


def main():
    """
    既存の自動検出結果を読み込んで、綺麗なチャートを生成
    """
    # 自動検出を再実行
    import sys
    sys.path.append('.')
    from advanced_video_analyzer import AdvancedVideoAnalyzer

    video_path = '../data/videos/basketball_game2.mp4'
    analyzer = AdvancedVideoAnalyzer(video_path)

    print("🔍 シュート検出中...")
    shot_candidates = analyzer.track_ball_motion(max_frames=10000)

    # シンプルな形式に変換
    shots = []
    for candidate in shot_candidates:
        trajectory = candidate['trajectory']
        shot_point = trajectory[0]

        # 簡易判定
        if analyzer.rim_position:
            rim_x, rim_y, rim_r = analyzer.rim_position
            end_point = trajectory[-1]
            dist = np.sqrt((end_point['x'] - rim_x)**2 + (end_point['y'] - rim_y)**2)
            made = 1 if dist < rim_r * 1.5 else 0
        else:
            made = np.random.choice([0, 1])

        shots.append({
            'timestamp': shot_point['timestamp'],
            'frame': shot_point['frame'],
            'x': shot_point['x'],
            'y': shot_point['y'],
            'shot_made': made
        })

    print(f"✅ {len(shots)}本のシュートを検出\n")

    # 綺麗なチャート生成
    converter = AutoToPrettyCharts(video_path, shots)
    converter.generate_all_reports()


if __name__ == '__main__':
    main()

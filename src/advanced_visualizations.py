"""
Kirk Goldsberry風の高度な可視化
Basketball Flow Lab - Advanced Visualizations

Kirk Goldsberryのスタイルを参考にした可視化機能
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Rectangle, Circle, Arc, Wedge
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

try:
    import japanize_matplotlib
except ImportError:
    pass


class AdvancedVisualizer:
    """
    Kirk Goldsberry風の高度な可視化クラス
    """

    def __init__(self):
        self.court_params = self._init_court_params()

    def _init_court_params(self):
        """
        コートパラメータの初期化
        """
        return {
            'court_length': 94,  # feet
            'court_width': 50,   # feet
            'hoop_x': 0,
            'hoop_y': 0,
            'three_point_distance': 23.75,  # feet
            'key_width': 16,  # feet
            'key_length': 19,  # feet
        }

    def create_score_flow_chart(self, pbp_df, runs, save_path='outputs/images/score_flow.png'):
        """
        スコアフロー（得点の流れ）を可視化
        Kirk Goldsberryの"Game Flow"スタイル

        Parameters
        ----------
        pbp_df : pd.DataFrame
            Play-by-Playデータ
        runs : list
            検出されたRun
        save_path : str
            保存先パス
        """
        fig, ax = plt.subplots(figsize=(16, 8), facecolor='white')

        # スコア差の推移を抽出
        score_diff = []
        time_points = []

        for idx, row in pbp_df.iterrows():
            if pd.notna(row.get('scoreHome')) and row['scoreHome'] != '':
                try:
                    home = int(row['scoreHome'])
                    away = int(row['scoreAway'])
                    diff = home - away

                    # 時間を分に変換
                    period = row.get('period', 1)
                    # 簡易的な時間計算（実際はクロックから計算）
                    time_min = (period - 1) * 12 + (12 - idx / len(pbp_df) * 12)

                    score_diff.append(diff)
                    time_points.append(time_min)
                except (ValueError, TypeError):
                    continue

        if not score_diff:
            print("⚠️ スコアデータが不足しています")
            return None

        # スコア差をプロット
        ax.plot(time_points, score_diff, linewidth=3, color='#333333', alpha=0.8)

        # 0ラインを強調
        ax.axhline(y=0, color='red', linestyle='--', linewidth=2, alpha=0.5)

        # Runをハイライト
        for run in runs:
            period = run.get('period', 1)
            # Run発生時刻を推定
            run_time = (period - 1) * 12 + 6  # 簡易的な推定

            # Runの強さに応じた色
            run_size = run['score']
            if run_size >= 10:
                color = '#ff0000'  # 赤
                alpha = 0.4
            elif run_size >= 8:
                color = '#ff8800'  # オレンジ
                alpha = 0.3
            else:
                color = '#ffcc00'  # 黄
                alpha = 0.2

            # Runエリアを塗りつぶし
            ax.axvspan(run_time - 1, run_time + 1,
                      color=color, alpha=alpha, label=f"{run['team']} {run_size}-0")

        # クォーターの区切り線
        for q in [12, 24, 36]:
            ax.axvline(x=q, color='gray', linestyle=':', linewidth=1, alpha=0.5)
            ax.text(q, ax.get_ylim()[1] * 0.95, f'Q{q//12 + 1}',
                   ha='center', fontsize=10, color='gray')

        # 軸ラベル
        ax.set_xlabel('Game Time (minutes)', fontsize=14, fontweight='bold')
        ax.set_ylabel('Score Differential (Home - Away)', fontsize=14, fontweight='bold')
        ax.set_title('Game Flow - Momentum Shifts', fontsize=18, fontweight='bold', pad=20)

        # グリッド
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        # 凡例は重複を避ける
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), loc='upper left', framealpha=0.9)

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✅ Score Flowを保存: {save_path}")
        plt.close()

        return fig

    def create_zone_efficiency_chart(self, shots_df, save_path='outputs/images/zone_efficiency.png'):
        """
        ゾーン別効率チャート
        Kirk Goldsberryの"Zone Efficiency"スタイル

        Parameters
        ----------
        shots_df : pd.DataFrame
            ショットデータ
        save_path : str
            保存先パス
        """
        if shots_df is None or len(shots_df) == 0:
            print("⚠️ ショットデータがありません")
            return None

        fig, ax = plt.subplots(figsize=(12, 11), facecolor='#f0f0f0')
        ax.set_facecolor('#f0f0f0')

        # コートを描画（簡易版）
        self._draw_half_court(ax)

        # ゾーンを定義
        zones = {
            'Paint': {'x_range': (-80, 80), 'y_range': (-47.5, 142.5)},
            'Left Corner 3': {'x_range': (-250, -220), 'y_range': (-47.5, 92.5)},
            'Right Corner 3': {'x_range': (220, 250), 'y_range': (-47.5, 92.5)},
            'Above Break 3': {'x_range': (-220, 220), 'y_range': (237.5, 422.5)},
            'Mid-Range Left': {'x_range': (-220, -80), 'y_range': (92.5, 237.5)},
            'Mid-Range Right': {'x_range': (80, 220), 'y_range': (92.5, 237.5)},
        }

        # 各ゾーンの効率を計算
        for zone_name, zone_bounds in zones.items():
            zone_shots = shots_df[
                (shots_df['LOC_X'] >= zone_bounds['x_range'][0]) &
                (shots_df['LOC_X'] <= zone_bounds['x_range'][1]) &
                (shots_df['LOC_Y'] >= zone_bounds['y_range'][0]) &
                (shots_df['LOC_Y'] <= zone_bounds['y_range'][1])
            ]

            if len(zone_shots) > 0:
                fg_pct = zone_shots['SHOT_MADE_FLAG'].mean()

                # 効率に応じた色
                if fg_pct >= 0.50:
                    color = '#00ff00'  # 緑
                    alpha = 0.6
                elif fg_pct >= 0.40:
                    color = '#ffff00'  # 黄
                    alpha = 0.5
                else:
                    color = '#ff0000'  # 赤
                    alpha = 0.4

                # ゾーンを塗りつぶし
                rect = Rectangle(
                    (zone_bounds['x_range'][0], zone_bounds['y_range'][0]),
                    zone_bounds['x_range'][1] - zone_bounds['x_range'][0],
                    zone_bounds['y_range'][1] - zone_bounds['y_range'][0],
                    facecolor=color,
                    alpha=alpha,
                    edgecolor='black',
                    linewidth=2
                )
                ax.add_patch(rect)

                # FG%を表示
                center_x = sum(zone_bounds['x_range']) / 2
                center_y = sum(zone_bounds['y_range']) / 2
                ax.text(center_x, center_y,
                       f"{fg_pct:.1%}\n({len(zone_shots)})",
                       ha='center', va='center',
                       fontsize=14, fontweight='bold',
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        ax.set_title('Zone Shooting Efficiency', fontsize=18, fontweight='bold', pad=20)

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='#f0f0f0')
        print(f"✅ Zone Efficiencyを保存: {save_path}")
        plt.close()

        return fig

    def _draw_half_court(self, ax):
        """
        ハーフコートを描画（簡易版）
        """
        # バスケット
        hoop = Circle((0, 0), radius=7.5, linewidth=2, color='black', fill=False)
        ax.add_patch(hoop)

        # ペイントエリア
        paint = Rectangle((-80, -47.5), 160, 190, linewidth=2,
                         color='black', fill=False)
        ax.add_patch(paint)

        # 3ポイントライン（簡易版）
        three_arc = Arc((0, 0), 475, 475, theta1=22, theta2=158,
                       linewidth=2, color='black')
        ax.add_patch(three_arc)

        # コーナー3
        ax.plot([-220, -220], [-47.5, 92.5], 'k-', linewidth=2)
        ax.plot([220, 220], [-47.5, 92.5], 'k-', linewidth=2)

        ax.set_xlim(-250, 250)
        ax.set_ylim(-47.5, 422.5)
        ax.set_aspect('equal')
        ax.axis('off')

    def create_run_impact_chart(self, runs, save_path='outputs/images/run_impact.png'):
        """
        Run影響度チャート
        各Runがゲームに与えた影響を可視化

        Parameters
        ----------
        runs : list
            検出されたRun
        save_path : str
            保存先パス
        """
        if not runs:
            print("⚠️ Runデータがありません")
            return None

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8), facecolor='white')

        # サブプロット1: Run規模の分布
        run_sizes = [run['score'] for run in runs]
        run_teams = [run['team'] for run in runs]

        home_runs = [size for size, team in zip(run_sizes, run_teams) if team == 'home']
        away_runs = [size for size, team in zip(run_sizes, run_teams) if team == 'away']

        x_positions = np.arange(len(runs))
        colors = ['#0066cc' if team == 'home' else '#cc0000' for team in run_teams]

        ax1.bar(x_positions, run_sizes, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
        ax1.axhline(y=8, color='orange', linestyle='--', linewidth=2,
                   label='Timeout Threshold (8-0)')
        ax1.set_xlabel('Run Number', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Run Size (Points)', fontsize=14, fontweight='bold')
        ax1.set_title('Run Size Distribution', fontsize=16, fontweight='bold')
        ax1.legend()
        ax1.grid(axis='y', alpha=0.3)

        # サブプロット2: クォーター別Run発生
        quarters = [run.get('period', 0) for run in runs]
        quarter_counts = pd.Series(quarters).value_counts().sort_index()

        ax2.bar(quarter_counts.index, quarter_counts.values,
               color='#00aa00', alpha=0.7, edgecolor='black', linewidth=2)
        ax2.set_xlabel('Quarter', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Number of Runs', fontsize=14, fontweight='bold')
        ax2.set_title('Runs by Quarter', fontsize=16, fontweight='bold')
        ax2.set_xticks([1, 2, 3, 4])
        ax2.set_xticklabels(['Q1', 'Q2', 'Q3', 'Q4'])
        ax2.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✅ Run Impactを保存: {save_path}")
        plt.close()

        return fig

    def create_goldsberry_style_summary(self, pbp_df, runs, shots_df=None,
                                       save_path='outputs/images/goldsberry_summary.png'):
        """
        Kirk Goldsberry風の統合サマリー
        複数の可視化を1つの画像にまとめる

        Parameters
        ----------
        pbp_df : pd.DataFrame
            Play-by-Playデータ
        runs : list
            検出されたRun
        shots_df : pd.DataFrame, optional
            ショットデータ
        save_path : str
            保存先パス
        """
        fig = plt.figure(figsize=(20, 12), facecolor='#1a1a1a')

        # タイトル
        fig.suptitle('Game Analysis - Goldsberry Style',
                    fontsize=24, fontweight='bold', color='white', y=0.98)

        # 3つのサブプロット
        ax1 = plt.subplot(2, 2, 1)
        ax2 = plt.subplot(2, 2, 2)
        ax3 = plt.subplot(2, 1, 2)

        # 1. Score Flow
        score_diff = []
        time_points = []
        for idx, row in pbp_df.iterrows():
            if pd.notna(row.get('scoreHome')) and row['scoreHome'] != '':
                try:
                    diff = int(row['scoreHome']) - int(row['scoreAway'])
                    period = row.get('period', 1)
                    time_min = (period - 1) * 12 + idx / len(pbp_df) * 12
                    score_diff.append(diff)
                    time_points.append(time_min)
                except:
                    continue

        if score_diff:
            ax1.plot(time_points, score_diff, linewidth=3, color='#00ff00')
            ax1.axhline(y=0, color='red', linestyle='--', linewidth=2)
            ax1.set_facecolor('#2a2a2a')
            ax1.set_title('Score Flow', color='white', fontsize=14, fontweight='bold')
            ax1.tick_params(colors='white')
            ax1.grid(color='white', alpha=0.2)

        # 2. Run Distribution
        if runs:
            run_sizes = [run['score'] for run in runs]
            run_teams = [run['team'] for run in runs]
            colors = ['#0066ff' if t == 'home' else '#ff0066' for t in run_teams]

            ax2.bar(range(len(runs)), run_sizes, color=colors, alpha=0.8, edgecolor='white')
            ax2.set_facecolor('#2a2a2a')
            ax2.set_title('Run Distribution', color='white', fontsize=14, fontweight='bold')
            ax2.tick_params(colors='white')
            ax2.grid(color='white', alpha=0.2, axis='y')

        # 3. Timeline
        ax3.set_facecolor('#2a2a2a')
        for i, run in enumerate(runs):
            period = run.get('period', 1)
            run_time = (period - 1) * 12 + 6
            run_size = run['score']

            color = '#0066ff' if run['team'] == 'home' else '#ff0066'
            ax3.barh(i, run_size, left=run_time, color=color,
                    alpha=0.8, edgecolor='white', linewidth=2)
            ax3.text(run_time + run_size/2, i, f"{run_size}-0",
                    ha='center', va='center', color='white', fontweight='bold')

        ax3.set_xlabel('Game Time (minutes)', color='white', fontsize=12)
        ax3.set_title('Run Timeline', color='white', fontsize=14, fontweight='bold')
        ax3.tick_params(colors='white')

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='#1a1a1a')
        print(f"✅ Goldsberry Summaryを保存: {save_path}")
        plt.close()

        return fig


def main():
    """
    使用例
    """
    print("="*60)
    print("Kirk Goldsberry風 高度な可視化")
    print("="*60)
    print()
    print("📋 使用例:")
    print()
    print("from src.advanced_visualizations import AdvancedVisualizer")
    print("from nba_api.stats.endpoints import playbyplayv3")
    print()
    print("# データ取得")
    print("pbp = playbyplayv3.PlayByPlayV3(game_id='0042300404')")
    print("plays_df = pbp.get_data_frames()[0]")
    print()
    print("# Run検出")
    print("from src.hc_decision_analysis import HCDecisionAnalyzer")
    print("analyzer = HCDecisionAnalyzer(plays_df)")
    print("runs = analyzer.detect_runs()")
    print()
    print("# 高度な可視化")
    print("viz = AdvancedVisualizer()")
    print("viz.create_score_flow_chart(plays_df, runs)")
    print("viz.create_run_impact_chart(runs)")
    print("viz.create_goldsberry_style_summary(plays_df, runs)")


if __name__ == '__main__':
    main()

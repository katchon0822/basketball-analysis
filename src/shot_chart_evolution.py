"""
選手の年度別ショットチャート進化
Basketball Flow Lab - Shot Chart Evolution

シンプルで見やすい年度比較
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, Arc
import seaborn as sns
from nba_api.stats.endpoints import shotchartdetail
import time
import warnings
warnings.filterwarnings('ignore')


class ShotChartEvolution:
    """
    選手の年度別ショットチャート進化を可視化
    """

    def __init__(self, player_id, player_name):
        self.player_id = player_id
        self.player_name = player_name
        self.all_shots = {}

    def draw_simple_court(self, ax, color='black', lw=1.5):
        """
        シンプルなコート描画
        """
        # リム
        hoop = Circle((0, 0), radius=7.5, linewidth=lw, color=color, fill=False)
        ax.add_patch(hoop)

        # バックボード
        ax.plot([-30, 30], [-7.5, -7.5], color=color, linewidth=lw)

        # ペイント
        paint = Rectangle((-80, -47.5), 160, 190, linewidth=lw,
                         color=color, fill=False)
        ax.add_patch(paint)

        # フリースローサークル
        top_ft = Arc((0, 142.5), 120, 120, theta1=0, theta2=180,
                    linewidth=lw, color=color, fill=False)
        ax.add_patch(top_ft)

        # 3Pライン
        three_arc = Arc((0, 0), 475, 475, theta1=22, theta2=158,
                       linewidth=lw, color=color)
        ax.add_patch(three_arc)

        # コーナー3
        ax.plot([-220, -220], [-47.5, 92.5], color=color, linewidth=lw)
        ax.plot([220, 220], [-47.5, 92.5], color=color, linewidth=lw)

        ax.set_xlim(-250, 250)
        ax.set_ylim(-47.5, 422.5)
        ax.set_aspect('equal')
        ax.axis('off')

        return ax

    def fetch_season_data(self, season):
        """
        特定シーズンのデータ取得
        """
        print(f"  📥 {season}シーズンのデータ取得中...")

        try:
            time.sleep(1.5)  # API rate limit

            shot_chart = shotchartdetail.ShotChartDetail(
                team_id=0,
                player_id=self.player_id,
                season_nullable=season,
                season_type_all_star='Regular Season',
                context_measure_simple='FGA'
            )

            shots = shot_chart.get_data_frames()[0]
            self.all_shots[season] = shots

            made = shots[shots['SHOT_MADE_FLAG'] == 1]
            fg_pct = len(made) / len(shots) * 100 if len(shots) > 0 else 0

            print(f"  ✅ {len(shots)}本取得 (FG: {fg_pct:.1f}%)")

            return shots

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return pd.DataFrame()

    def create_evolution_chart(self, seasons, save_path='outputs/images/shot_evolution.png'):
        """
        年度別ショットチャート比較図を作成

        Parameters
        ----------
        seasons : list
            シーズンのリスト（例: ['2019-20', '2020-21', ...]）
        save_path : str
            保存先
        """
        print(f"\n🎬 {self.player_name} 年度別ショットチャート作成中...")
        print(f"   対象シーズン: {', '.join(seasons)}")

        # データ取得
        for season in seasons:
            self.fetch_season_data(season)

        # データがあるシーズンのみ
        valid_seasons = [s for s in seasons if s in self.all_shots and len(self.all_shots[s]) > 0]

        if not valid_seasons:
            print("❌ データが取得できませんでした")
            return

        print(f"\n📊 {len(valid_seasons)}シーズンのチャートを作成")

        # サブプロット作成
        n_seasons = len(valid_seasons)
        cols = min(3, n_seasons)
        rows = (n_seasons + cols - 1) // cols

        fig, axes = plt.subplots(rows, cols, figsize=(6*cols, 6*rows),
                                facecolor='white')

        if n_seasons == 1:
            axes = [axes]
        else:
            axes = axes.flatten() if n_seasons > 1 else [axes]

        for idx, season in enumerate(valid_seasons):
            ax = axes[idx]
            shots = self.all_shots[season]

            # コート描画
            self.draw_simple_court(ax, color='black', lw=1.5)

            # ショット描画
            made = shots[shots['SHOT_MADE_FLAG'] == 1]
            missed = shots[shots['SHOT_MADE_FLAG'] == 0]

            # 失敗（薄い赤）
            ax.scatter(missed['LOC_X'], missed['LOC_Y'],
                      c='#FF6B6B', alpha=0.3, s=30, marker='x',
                      linewidths=1)

            # 成功（濃い緑）
            ax.scatter(made['LOC_X'], made['LOC_Y'],
                      c='#51CF66', alpha=0.6, s=60,
                      edgecolors='#37B24D', linewidths=1.5)

            # タイトル
            fg_pct = len(made) / len(shots) * 100
            three_pt = shots[shots['SHOT_TYPE'] == '3PT Field Goal']
            three_made = three_pt[three_pt['SHOT_MADE_FLAG'] == 1]
            three_pct = len(three_made) / len(three_pt) * 100 if len(three_pt) > 0 else 0

            title_text = f"{season}\n"
            title_text += f"FG: {fg_pct:.1f}% ({len(made)}/{len(shots)})\n"
            title_text += f"3P: {three_pct:.1f}% ({len(three_made)}/{len(three_pt)})"

            ax.set_title(title_text, fontsize=12, fontweight='bold', pad=10)

        # 余ったサブプロットを非表示
        for idx in range(len(valid_seasons), len(axes)):
            axes[idx].axis('off')

        # 全体タイトル
        fig.suptitle(f"{self.player_name} - Shot Chart Evolution",
                    fontsize=18, fontweight='bold', y=0.98)

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"\n✅ 年度別ショットチャートを保存: {save_path}")
        plt.close()

        return fig

    def create_heatmap_comparison(self, seasons, save_path='outputs/images/shot_heatmap_evolution.png'):
        """
        ヒートマップ形式の年度比較（シンプル＆綺麗）
        """
        print(f"\n🔥 ヒートマップ比較作成中...")

        valid_seasons = [s for s in seasons if s in self.all_shots and len(self.all_shots[s]) > 0]

        if not valid_seasons:
            print("❌ データがありません")
            return

        n_seasons = len(valid_seasons)
        cols = min(3, n_seasons)
        rows = (n_seasons + cols - 1) // cols

        fig, axes = plt.subplots(rows, cols, figsize=(6*cols, 6*rows),
                                facecolor='white')

        if n_seasons == 1:
            axes = [axes]
        else:
            axes = axes.flatten() if n_seasons > 1 else [axes]

        for idx, season in enumerate(valid_seasons):
            ax = axes[idx]
            shots = self.all_shots[season]

            # コート描画（黒線）
            self.draw_simple_court(ax, color='black', lw=1.5)

            # 成功/失敗で分ける
            made = shots[shots['SHOT_MADE_FLAG'] == 1]
            missed = shots[shots['SHOT_MADE_FLAG'] == 0]

            # より綺麗な色使い
            # 失敗 - 薄いグレー
            ax.scatter(missed['LOC_X'], missed['LOC_Y'],
                      c='#CCCCCC', alpha=0.25, s=25, marker='o',
                      edgecolors='none')

            # 成功 - 青のグラデーション（濃淡で頻度表現）
            from matplotlib.colors import LinearSegmentedColormap

            # カスタムカラーマップ（薄い青→濃い青）
            colors = ['#E3F2FD', '#64B5F6', '#1976D2', '#0D47A1']
            n_bins = 100
            cmap = LinearSegmentedColormap.from_list('blue_gradient', colors, N=n_bins)

            # ヒートマップ（成功ショットのみ）
            if len(made) > 0:
                hexbin = ax.hexbin(
                    made['LOC_X'], made['LOC_Y'],
                    gridsize=18, cmap=cmap, alpha=0.7,
                    edgecolors='white', linewidths=0.3,
                    mincnt=1
                )

            # タイトル（統計情報付き）
            total = len(shots)
            fg_pct = len(made) / total * 100 if total > 0 else 0

            title_text = f"{season}\n{fg_pct:.1f}% ({len(made)}/{total}本)"
            ax.set_title(title_text, fontsize=13, fontweight='bold', pad=10)

        # 余ったサブプロットを非表示
        for idx in range(len(valid_seasons), len(axes)):
            axes[idx].axis('off')

        fig.suptitle(f"{self.player_name} - Shot Heatmap Evolution",
                    fontsize=18, fontweight='bold', y=0.98)

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✅ ヒートマップを保存: {save_path}")
        plt.close()

        return fig


def main():
    print("="*80)
    print("Shot Chart Evolution - 年度別進化可視化")
    print("="*80)
    print()
    print("使用例:")
    print()
    print("from src.shot_chart_evolution import ShotChartEvolution")
    print()
    print("# 八村塁選手")
    print("evolution = ShotChartEvolution(player_id=1629060, player_name='Rui Hachimura')")
    print("evolution.create_evolution_chart(['2019-20', '2020-21', '2021-22', '2022-23', '2023-24', '2024-25'])")


if __name__ == '__main__':
    main()

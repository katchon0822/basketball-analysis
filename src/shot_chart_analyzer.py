"""
Kirk Goldsberry型Shot Chart分析
Basketball Flow Lab - Shot Chart Analysis

Kirk Goldsberryの手法を参考にした空間分析
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Circle, Rectangle, Arc
import seaborn as sns
from nba_api.stats.endpoints import shotchartdetail
import time
import warnings
warnings.filterwarnings('ignore')

try:
    import japanize_matplotlib
except ImportError:
    pass


class ShotChartAnalyzer:
    """
    Kirk Goldsberry型のShot Chart分析クラス
    """

    def __init__(self, team_id=None, player_id=None, season='2023-24'):
        """
        Parameters
        ----------
        team_id : int, optional
            チームID
        player_id : int, optional
            選手ID
        season : str
            シーズン（例: '2023-24'）
        """
        self.team_id = team_id
        self.player_id = player_id
        self.season = season
        self.shots_df = None

    def fetch_shot_data(self, game_id=None):
        """
        Shot dataを取得

        Parameters
        ----------
        game_id : str, optional
            特定の試合ID

        Returns
        -------
        pd.DataFrame
            Shot data
        """
        print(f"🏀 Fetching shot data...")

        try:
            time.sleep(1)  # API rate limit対策

            shot_chart = shotchartdetail.ShotChartDetail(
                team_id=self.team_id or 0,
                player_id=self.player_id or 0,
                season_nullable=self.season,
                season_type_all_star='Regular Season',
                context_measure_simple='FGA',
                game_id_nullable=game_id or ''
            )

            shots = shot_chart.get_data_frames()[0]
            self.shots_df = shots

            print(f"✅ {len(shots)}本のショットデータを取得")
            return shots

        except Exception as e:
            print(f"❌ Error fetching shot data: {e}")
            return pd.DataFrame()

    def draw_court(self, ax=None, color='black', lw=2, outer_lines=False):
        """
        NBAコートを描画（Kirk Goldsberry style）

        Parameters
        ----------
        ax : matplotlib.axes.Axes, optional
            描画対象のaxes
        color : str
            線の色
        lw : float
            線の太さ
        outer_lines : bool
            外枠を描画するか

        Returns
        -------
        matplotlib.axes.Axes
        """
        if ax is None:
            ax = plt.gca()

        # コートの寸法（単位: feet、NBA公式）
        # 1 foot = 0.3048 meters
        # コート座標は10分の1インチ単位

        # バスケット（リムの中心は原点）
        hoop = Circle((0, 0), radius=7.5, linewidth=lw, color=color, fill=False)
        ax.add_patch(hoop)

        # バックボード
        backboard = Rectangle((-30, -7.5), 60, -1, linewidth=lw, color=color)
        ax.add_patch(backboard)

        # ペイントエリア（制限区域）
        outer_box = Rectangle((-80, -47.5), 160, 190, linewidth=lw, color=color, fill=False)
        ax.add_patch(outer_box)

        inner_box = Rectangle((-60, -47.5), 120, 190, linewidth=lw, color=color, fill=False)
        ax.add_patch(inner_box)

        # フリースローサークル
        top_free_throw = Arc((0, 142.5), 120, 120, theta1=0, theta2=180,
                            linewidth=lw, color=color, fill=False)
        ax.add_patch(top_free_throw)

        bottom_free_throw = Arc((0, 142.5), 120, 120, theta1=180, theta2=0,
                               linewidth=lw, color=color, fill=False, linestyle='dashed')
        ax.add_patch(bottom_free_throw)

        # 3ポイントライン
        corner_three_a = Rectangle((-220, -47.5), 0, 140, linewidth=lw, color=color)
        corner_three_b = Rectangle((220, -47.5), 0, 140, linewidth=lw, color=color)
        ax.add_patch(corner_three_a)
        ax.add_patch(corner_three_b)

        three_arc = Arc((0, 0), 475, 475, theta1=22, theta2=158,
                       linewidth=lw, color=color)
        ax.add_patch(three_arc)

        # センターサークル
        center_outer_arc = Arc((0, 422.5), 120, 120, theta1=180, theta2=0,
                              linewidth=lw, color=color)
        ax.add_patch(center_outer_arc)

        # コート外枠
        if outer_lines:
            outer_lines_rect = Rectangle((-250, -47.5), 500, 470,
                                        linewidth=lw, color=color, fill=False)
            ax.add_patch(outer_lines_rect)

        # 軸の設定
        ax.set_xlim(-250, 250)
        ax.set_ylim(-47.5, 422.5)
        ax.set_aspect('equal')
        ax.axis('off')

        return ax

    def create_shot_chart(self, title='Shot Chart', save_path='outputs/images/shot_chart.png'):
        """
        Kirk Goldsberry型のShot Chartを作成

        Parameters
        ----------
        title : str
            グラフタイトル
        save_path : str
            保存先パス

        Returns
        -------
        matplotlib.figure.Figure
        """
        if self.shots_df is None or len(self.shots_df) == 0:
            print("❌ Shot dataがありません。先にfetch_shot_data()を実行してください。")
            return None

        fig, ax = plt.subplots(figsize=(12, 11))

        # コートを描画
        self.draw_court(ax, color='black', lw=2)

        # ショットをプロット
        # 成功/失敗で色分け
        made_shots = self.shots_df[self.shots_df['SHOT_MADE_FLAG'] == 1]
        missed_shots = self.shots_df[self.shots_df['SHOT_MADE_FLAG'] == 0]

        # 失敗ショット（赤）
        ax.scatter(missed_shots['LOC_X'], missed_shots['LOC_Y'],
                  c='red', alpha=0.3, s=50, marker='x', linewidths=1.5,
                  label=f'Missed ({len(missed_shots)})')

        # 成功ショット（緑）
        ax.scatter(made_shots['LOC_X'], made_shots['LOC_Y'],
                  c='green', alpha=0.5, s=100, edgecolors='darkgreen',
                  linewidths=1.5, label=f'Made ({len(made_shots)})')

        # 統計情報を追加
        fg_pct = len(made_shots) / len(self.shots_df) * 100 if len(self.shots_df) > 0 else 0
        stats_text = f"FG%: {fg_pct:.1f}% ({len(made_shots)}/{len(self.shots_df)})"

        ax.text(0, -20, stats_text, ha='center', va='top',
               fontsize=14, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.legend(loc='upper right', framealpha=0.9)

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✅ Shot Chartを保存: {save_path}")

        return fig

    def create_hexbin_shot_chart(self, title='Shot Frequency Hexbin',
                                 save_path='outputs/images/shot_hexbin.png'):
        """
        Hexbin形式のShot Chart（ヒートマップ）

        Parameters
        ----------
        title : str
            グラフタイトル
        save_path : str
            保存先パス
        """
        if self.shots_df is None or len(self.shots_df) == 0:
            print("❌ Shot dataがありません")
            return None

        fig, ax = plt.subplots(figsize=(12, 11))

        # コートを描画
        self.draw_court(ax, color='white', lw=2)

        # Hexbinでショット頻度を可視化
        hexbin = ax.hexbin(
            self.shots_df['LOC_X'],
            self.shots_df['LOC_Y'],
            gridsize=25,
            cmap='YlOrRd',
            alpha=0.8,
            edgecolors='black',
            linewidths=0.5
        )

        # カラーバー
        cbar = plt.colorbar(hexbin, ax=ax)
        cbar.set_label('Shot Frequency', fontsize=12)

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_facecolor('#f0f0f0')

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✅ Hexbin Shot Chartを保存: {save_path}")

        return fig

    def analyze_shooting_zones(self):
        """
        ゾーン別のシューティング効率を分析

        Returns
        -------
        pd.DataFrame
            ゾーン別統計
        """
        if self.shots_df is None:
            return pd.DataFrame()

        zones = self.shots_df.groupby('SHOT_ZONE_BASIC').agg({
            'SHOT_MADE_FLAG': ['sum', 'count', 'mean']
        }).round(3)

        zones.columns = ['Made', 'Attempts', 'FG%']
        zones = zones.sort_values('FG%', ascending=False)

        print("\n📊 ゾーン別シューティング効率:")
        print(zones)

        return zones

    def create_goldsberry_style_chart(self, title='Shot Chart - Goldsberry Style',
                                      save_path='outputs/images/goldsberry_shot_chart.png'):
        """
        Kirk Goldsberry風のスタイリッシュなShot Chart

        Parameters
        ----------
        title : str
            タイトル
        save_path : str
            保存先
        """
        if self.shots_df is None or len(self.shots_df) == 0:
            print("❌ Shot dataがありません")
            return None

        # 背景を黒にしてGoldsberry風に
        fig, ax = plt.subplots(figsize=(12, 11), facecolor='#1a1a1a')
        ax.set_facecolor('#1a1a1a')

        # コートを描画（白線）
        self.draw_court(ax, color='white', lw=1.5)

        # ショットを効率でカラーマップ
        # 成功率が高いエリアを明るく表示
        made_shots = self.shots_df[self.shots_df['SHOT_MADE_FLAG'] == 1]
        missed_shots = self.shots_df[self.shots_df['SHOT_MADE_FLAG'] == 0]

        # 失敗ショット（薄い赤）
        ax.scatter(missed_shots['LOC_X'], missed_shots['LOC_Y'],
                  c='#ff4444', alpha=0.15, s=80, edgecolors='none')

        # 成功ショット（明るい緑）
        ax.scatter(made_shots['LOC_X'], made_shots['LOC_Y'],
                  c='#00ff00', alpha=0.6, s=120, edgecolors='#00cc00',
                  linewidths=2)

        # タイトル（白）
        ax.set_title(title, fontsize=18, fontweight='bold', color='white', pad=20)

        # 統計情報
        fg_pct = len(made_shots) / len(self.shots_df) * 100 if len(self.shots_df) > 0 else 0
        stats_text = f"FG: {len(made_shots)}/{len(self.shots_df)} ({fg_pct:.1f}%)"

        ax.text(0, -30, stats_text, ha='center', va='top',
               fontsize=16, fontweight='bold', color='white',
               bbox=dict(boxstyle='round', facecolor='#333333', alpha=0.8,
                        edgecolor='white', linewidth=2))

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='#1a1a1a')
        print(f"✅ Goldsberry風Shot Chartを保存: {save_path}")
        plt.close()

        return fig


def main():
    """
    サンプル実行
    """
    print("=" * 60)
    print("Kirk Goldsberry型 Shot Chart分析")
    print("=" * 60)
    print()

    print("📋 使用例:")
    print()
    print("from src.shot_chart_analyzer import ShotChartAnalyzer")
    print()
    print("# 選手IDを指定（例: LeBron James = 2544）")
    print("analyzer = ShotChartAnalyzer(player_id=2544, season='2023-24')")
    print()
    print("# データ取得")
    print("analyzer.fetch_shot_data()")
    print()
    print("# Shot Chart作成")
    print("analyzer.create_shot_chart(title='LeBron James Shot Chart')")
    print("analyzer.create_goldsberry_style_chart()")
    print("analyzer.create_hexbin_shot_chart()")
    print()
    print("# ゾーン別分析")
    print("zones = analyzer.analyze_shooting_zones()")


if __name__ == '__main__':
    main()

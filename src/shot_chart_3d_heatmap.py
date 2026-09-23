"""
3D Shot Heatmap
Basketball Flow Lab - 3Dヒートマップ可視化

高さ = 試投数（アテンプト）
色 = 成功率（FG%）
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import animation
from matplotlib.patches import Circle, Rectangle, Arc
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns
from nba_api.stats.endpoints import shotchartdetail
import time
import warnings
warnings.filterwarnings('ignore')


class ShotChart3DHeatmap:
    """
    3Dヒートマップ: 高さ=試投数、色=成功率
    """

    def __init__(self, player_id, player_name, season='2024-25'):
        self.player_id = player_id
        self.player_name = player_name
        self.season = season
        self.shots_df = None

    def fetch_shot_data(self):
        """Shot dataを取得"""
        print(f"🏀 Fetching shot data for {self.player_name}...")

        try:
            time.sleep(1)

            shot_chart = shotchartdetail.ShotChartDetail(
                team_id=0,
                player_id=self.player_id,
                season_nullable=self.season,
                season_type_all_star='Regular Season',
                context_measure_simple='FGA'
            )

            shots = shot_chart.get_data_frames()[0]
            self.shots_df = shots

            print(f"✅ {len(shots)}本のショットデータを取得")
            return shots

        except Exception as e:
            print(f"❌ Error: {e}")
            return pd.DataFrame()

    def draw_simple_court_3d(self, ax):
        """
        シンプルな3Dコート描画
        """
        # リム
        theta = np.linspace(0, 2*np.pi, 100)
        rim_x = 7.5 * np.cos(theta)
        rim_y = 7.5 * np.sin(theta)
        rim_z = np.zeros_like(rim_x)

        ax.plot(rim_x, rim_y, rim_z, color='black', linewidth=2)

        # 3Pライン
        three_arc_theta = np.linspace(np.radians(22), np.radians(158), 100)
        three_arc_x = 237.5 * np.cos(three_arc_theta)
        three_arc_y = 237.5 * np.sin(three_arc_theta)
        three_arc_z = np.zeros_like(three_arc_x)

        ax.plot(three_arc_x, three_arc_y, three_arc_z, color='black', linewidth=1.5, alpha=0.5)

        # コーナー3
        ax.plot([-220, -220], [-47.5, 92.5], [0, 0], color='black', linewidth=1.5, alpha=0.5)
        ax.plot([220, 220], [-47.5, 92.5], [0, 0], color='black', linewidth=1.5, alpha=0.5)

        # ペイント
        paint_x = [-80, 80, 80, -80, -80]
        paint_y = [-47.5, -47.5, 142.5, 142.5, -47.5]
        paint_z = [0, 0, 0, 0, 0]
        ax.plot(paint_x, paint_y, paint_z, color='black', linewidth=1.5, alpha=0.5)

        return ax

    def create_3d_heatmap(self, save_path='outputs/images/shot_3d_heatmap.png',
                         grid_size=15, hide_axes=False):
        """
        3Dヒートマップ作成

        高さ = 試投数
        色 = 成功率

        Parameters
        ----------
        save_path : str
            保存先
        grid_size : int
            グリッドの細かさ
        hide_axes : bool
            軸を非表示にするか
        """
        if self.shots_df is None or len(self.shots_df) == 0:
            print("❌ Shot dataがありません")
            return

        print(f"\n🎨 3Dヒートマップ作成中...")
        print(f"   高さ = 試投数")
        print(f"   色 = 成功率")

        # グリッド作成
        x_bins = np.linspace(-250, 250, grid_size)
        y_bins = np.linspace(-50, 400, grid_size)

        # 各グリッドの統計を計算
        grid_stats = {}

        for i in range(len(x_bins) - 1):
            for j in range(len(y_bins) - 1):
                x_min, x_max = x_bins[i], x_bins[i+1]
                y_min, y_max = y_bins[j], y_bins[j+1]

                # このグリッド内のショット
                mask = (
                    (self.shots_df['LOC_X'] >= x_min) &
                    (self.shots_df['LOC_X'] < x_max) &
                    (self.shots_df['LOC_Y'] >= y_min) &
                    (self.shots_df['LOC_Y'] < y_max)
                )

                shots_in_grid = self.shots_df[mask]

                if len(shots_in_grid) > 0:
                    attempts = len(shots_in_grid)
                    makes = shots_in_grid['SHOT_MADE_FLAG'].sum()
                    fg_pct = makes / attempts

                    grid_stats[(i, j)] = {
                        'x_center': (x_min + x_max) / 2,
                        'y_center': (y_min + y_max) / 2,
                        'attempts': attempts,
                        'fg_pct': fg_pct
                    }

        if not grid_stats:
            print("❌ グリッドにデータがありません")
            return

        print(f"✅ {len(grid_stats)}個のグリッドにデータあり")

        # 3Dプロット
        fig = plt.figure(figsize=(14, 10), facecolor='white')
        ax = fig.add_subplot(111, projection='3d', facecolor='white')

        # コート描画
        self.draw_simple_court_3d(ax)

        # カラーマップ（赤→黄→緑）
        # 低確率=赤、中間=黄、高確率=緑
        colors = ['#D32F2F', '#FFA726', '#FFD54F', '#66BB6A', '#2E7D32']
        cmap = LinearSegmentedColormap.from_list('fg_pct', colors, N=256)

        # 3Dバーを描画
        for (i, j), stats in grid_stats.items():
            x = stats['x_center']
            y = stats['y_center']
            attempts = stats['attempts']
            fg_pct = stats['fg_pct']

            # 高さ = 試投数
            height = attempts

            # 色 = 成功率
            color = cmap(fg_pct)

            # バーの幅
            dx = dy = (x_bins[1] - x_bins[0]) * 0.8

            # 3Dバー描画
            ax.bar3d(x - dx/2, y - dy/2, 0, dx, dy, height,
                    color=color, alpha=0.8, edgecolor='white', linewidth=0.5)

        # 軸設定
        ax.set_xlim(-260, 260)
        ax.set_ylim(-60, 410)
        ax.set_zlim(0, max([s['attempts'] for s in grid_stats.values()]) * 1.2)

        if hide_axes:
            # 軸を完全に非表示
            ax.set_xlabel('')
            ax.set_ylabel('')
            ax.set_zlabel('')
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_zticks([])
            ax.xaxis.pane.fill = False
            ax.yaxis.pane.fill = False
            ax.zaxis.pane.fill = False
            ax.xaxis.pane.set_edgecolor('none')
            ax.yaxis.pane.set_edgecolor('none')
            ax.zaxis.pane.set_edgecolor('none')
            ax.grid(False)
        else:
            ax.set_xlabel('Court Width', fontsize=10)
            ax.set_ylabel('Court Length', fontsize=10)
            ax.set_zlabel('Attempts', fontsize=10)

        # タイトル
        made = self.shots_df[self.shots_df['SHOT_MADE_FLAG'] == 1]
        total_fg = len(made) / len(self.shots_df) * 100

        title = f"{self.player_name} - 3D Shot Heatmap ({self.season})\n"
        title += f"Height = Attempts | Color = FG% | Total: {total_fg:.1f}% ({len(made)}/{len(self.shots_df)})"

        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

        # カメラアングル
        ax.view_init(elev=30, azim=45)

        # カラーバー
        sm = cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=0, vmax=1))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.5, aspect=10)
        cbar.set_label('FG%', rotation=270, labelpad=15, fontsize=10)

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✅ 3Dヒートマップを保存: {save_path}")
        plt.close()

        return fig

    def create_rotating_3d_video(self, save_path='outputs/videos/shot_3d_heatmap.mp4',
                                fps=30, duration=15, grid_size=15):
        """
        回転する3Dヒートマップ動画

        Parameters
        ----------
        save_path : str
            保存先
        fps : int
            フレームレート
        duration : int
            動画の長さ（秒）
        grid_size : int
            グリッドサイズ
        """
        if self.shots_df is None or len(self.shots_df) == 0:
            print("❌ Shot dataがありません")
            return

        print(f"\n🎬 3Dヒートマップ動画作成中...")
        print(f"   動画の長さ: {duration}秒")

        # グリッド統計計算（静止画と同じ）
        x_bins = np.linspace(-250, 250, grid_size)
        y_bins = np.linspace(-50, 400, grid_size)

        grid_stats = {}

        for i in range(len(x_bins) - 1):
            for j in range(len(y_bins) - 1):
                x_min, x_max = x_bins[i], x_bins[i+1]
                y_min, y_max = y_bins[j], y_bins[j+1]

                mask = (
                    (self.shots_df['LOC_X'] >= x_min) &
                    (self.shots_df['LOC_X'] < x_max) &
                    (self.shots_df['LOC_Y'] >= y_min) &
                    (self.shots_df['LOC_Y'] < y_max)
                )

                shots_in_grid = self.shots_df[mask]

                if len(shots_in_grid) > 0:
                    attempts = len(shots_in_grid)
                    makes = shots_in_grid['SHOT_MADE_FLAG'].sum()
                    fg_pct = makes / attempts

                    grid_stats[(i, j)] = {
                        'x_center': (x_min + x_max) / 2,
                        'y_center': (y_min + y_max) / 2,
                        'attempts': attempts,
                        'fg_pct': fg_pct
                    }

        if not grid_stats:
            print("❌ グリッドにデータがありません")
            return

        # カラーマップ
        colors = ['#D32F2F', '#FFA726', '#FFD54F', '#66BB6A', '#2E7D32']
        cmap = LinearSegmentedColormap.from_list('fg_pct', colors, N=256)

        # アニメーション設定
        fig = plt.figure(figsize=(14, 10), facecolor='white')
        ax = fig.add_subplot(111, projection='3d', facecolor='white')

        made = self.shots_df[self.shots_df['SHOT_MADE_FLAG'] == 1]
        total_fg = len(made) / len(self.shots_df) * 100

        title = ax.text2D(0.5, 0.95,
                         f"{self.player_name} - 3D Shot Heatmap ({self.season})\n" +
                         f"Height = Attempts | Color = FG% | Total: {total_fg:.1f}%",
                         transform=ax.transAxes, fontsize=14, fontweight='bold',
                         ha='center')

        total_frames = fps * duration
        max_height = max([s['attempts'] for s in grid_stats.values()]) * 1.2

        def init():
            return []

        def animate(frame):
            ax.cla()
            self.draw_simple_court_3d(ax)

            # カメラ回転
            angle = (frame / total_frames) * 360
            ax.view_init(elev=25, azim=angle)

            # 3Dバー描画
            for (i, j), stats in grid_stats.items():
                x = stats['x_center']
                y = stats['y_center']
                attempts = stats['attempts']
                fg_pct = stats['fg_pct']

                height = attempts
                color = cmap(fg_pct)

                dx = dy = (x_bins[1] - x_bins[0]) * 0.8

                ax.bar3d(x - dx/2, y - dy/2, 0, dx, dy, height,
                        color=color, alpha=0.8, edgecolor='white', linewidth=0.5)

            ax.set_xlim(-260, 260)
            ax.set_ylim(-60, 410)
            ax.set_zlim(0, max_height)

            ax.set_xlabel('Court Width', fontsize=10)
            ax.set_ylabel('Court Length', fontsize=10)
            ax.set_zlabel('Attempts', fontsize=10)

            return []

        anim = animation.FuncAnimation(
            fig, animate, init_func=init,
            frames=total_frames, interval=1000//fps,
            blit=False
        )

        # 保存
        import os
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        print(f"\n💾 動画を保存中...")
        try:
            anim.save(save_path, writer='ffmpeg', fps=fps, dpi=150,
                     extra_args=['-vcodec', 'libx264', '-pix_fmt', 'yuv420p'])
            print(f"✅ 3Dヒートマップ動画を保存: {save_path}")
        except Exception as e:
            print(f"❌ MP4保存エラー: {e}")

        plt.close()
        return anim


    def create_multi_season_comparison(self, seasons, save_path='outputs/images/heatmap_evolution_3d.png',
                                      grid_size=12):
        """
        複数シーズンの3Dヒートマップ比較

        Parameters
        ----------
        seasons : list
            シーズンのリスト
        save_path : str
            保存先
        grid_size : int
            グリッドサイズ
        """
        print(f"\n🎨 年度別3Dヒートマップ比較作成中...")
        print(f"   対象シーズン: {', '.join(seasons)}")

        # 各シーズンのデータを取得
        all_season_data = {}

        for season in seasons:
            print(f"\n  📥 {season}シーズンのデータ取得中...")
            time.sleep(1.5)

            try:
                shot_chart = shotchartdetail.ShotChartDetail(
                    team_id=0,
                    player_id=self.player_id,
                    season_nullable=season,
                    season_type_all_star='Regular Season',
                    context_measure_simple='FGA'
                )

                shots = shot_chart.get_data_frames()[0]

                if len(shots) > 0:
                    all_season_data[season] = shots
                    made = shots[shots['SHOT_MADE_FLAG'] == 1]
                    print(f"  ✅ {len(shots)}本取得 (FG: {len(made)/len(shots)*100:.1f}%)")
                else:
                    print(f"  ⚠️  データなし")

            except Exception as e:
                print(f"  ❌ Error: {e}")

        if not all_season_data:
            print("❌ データが取得できませんでした")
            return

        # サブプロット作成
        n_seasons = len(all_season_data)
        cols = min(3, n_seasons)
        rows = (n_seasons + cols - 1) // cols

        fig = plt.figure(figsize=(6*cols, 6*rows), facecolor='white')

        # カラーマップ
        colors = ['#D32F2F', '#FFA726', '#FFD54F', '#66BB6A', '#2E7D32']
        cmap = LinearSegmentedColormap.from_list('fg_pct', colors, N=256)

        for idx, (season, shots_df) in enumerate(all_season_data.items(), 1):
            ax = fig.add_subplot(rows, cols, idx, projection='3d', facecolor='white')

            # グリッド統計計算
            x_bins = np.linspace(-250, 250, grid_size)
            y_bins = np.linspace(-50, 400, grid_size)

            grid_stats = {}

            for i in range(len(x_bins) - 1):
                for j in range(len(y_bins) - 1):
                    x_min, x_max = x_bins[i], x_bins[i+1]
                    y_min, y_max = y_bins[j], y_bins[j+1]

                    mask = (
                        (shots_df['LOC_X'] >= x_min) &
                        (shots_df['LOC_X'] < x_max) &
                        (shots_df['LOC_Y'] >= y_min) &
                        (shots_df['LOC_Y'] < y_max)
                    )

                    shots_in_grid = shots_df[mask]

                    if len(shots_in_grid) > 0:
                        attempts = len(shots_in_grid)
                        makes = shots_in_grid['SHOT_MADE_FLAG'].sum()
                        fg_pct = makes / attempts

                        grid_stats[(i, j)] = {
                            'x_center': (x_min + x_max) / 2,
                            'y_center': (y_min + y_max) / 2,
                            'attempts': attempts,
                            'fg_pct': fg_pct
                        }

            # コート描画
            self.draw_simple_court_3d(ax)

            # 3Dバー描画
            if grid_stats:
                for (i, j), stats in grid_stats.items():
                    x = stats['x_center']
                    y = stats['y_center']
                    attempts = stats['attempts']
                    fg_pct = stats['fg_pct']

                    height = attempts
                    color = cmap(fg_pct)

                    dx = dy = (x_bins[1] - x_bins[0]) * 0.8

                    ax.bar3d(x - dx/2, y - dy/2, 0, dx, dy, height,
                            color=color, alpha=0.8, edgecolor='white', linewidth=0.5)

            # 軸設定（軸なし）
            ax.set_xlim(-260, 260)
            ax.set_ylim(-60, 410)
            if grid_stats:
                ax.set_zlim(0, max([s['attempts'] for s in grid_stats.values()]) * 1.2)

            # 軸を完全に非表示
            ax.set_xlabel('')
            ax.set_ylabel('')
            ax.set_zlabel('')
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_zticks([])
            ax.xaxis.pane.fill = False
            ax.yaxis.pane.fill = False
            ax.zaxis.pane.fill = False
            ax.xaxis.pane.set_edgecolor('none')
            ax.yaxis.pane.set_edgecolor('none')
            ax.zaxis.pane.set_edgecolor('none')
            ax.grid(False)

            # カメラアングル
            ax.view_init(elev=30, azim=45)

            # タイトル
            made = shots_df[shots_df['SHOT_MADE_FLAG'] == 1]
            fg_pct = len(made) / len(shots_df) * 100

            title = f"{season}\nFG: {fg_pct:.1f}% ({len(made)}/{len(shots_df)})"
            ax.set_title(title, fontsize=13, fontweight='bold', pad=10)

        # 全体タイトル
        fig.suptitle(f"{self.player_name} - 3D Heatmap Evolution",
                    fontsize=18, fontweight='bold', y=0.98)

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"\n✅ 年度別3Dヒートマップを保存: {save_path}")
        plt.close()

        return fig


def main():
    print("="*80)
    print("3D Shot Heatmap - 高さ=試投数、色=成功率")
    print("="*80)
    print()
    print("使用例:")
    print()
    print("from src.shot_chart_3d_heatmap import ShotChart3DHeatmap")
    print()
    print("heatmap = ShotChart3DHeatmap(player_id=1629060, player_name='Rui Hachimura')")
    print("heatmap.fetch_shot_data()")
    print("heatmap.create_3d_heatmap()")
    print("heatmap.create_rotating_3d_video()")


if __name__ == '__main__':
    main()

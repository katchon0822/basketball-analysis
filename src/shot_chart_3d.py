"""
3D Shot Chart Animator
Basketball Flow Lab - 3D Shot Visualization

Stephen Curryなど注目選手の3Dショットチャートをアニメーション動画として生成
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import animation
from matplotlib.patches import Circle, Rectangle, Arc, FancyBboxPatch
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import seaborn as sns
from nba_api.stats.endpoints import shotchartdetail
import time
import warnings
warnings.filterwarnings('ignore')


class ShotChart3DAnimator:
    """
    3D Shot Chartアニメーター
    """

    def __init__(self, player_id, player_name, season='2024-25'):
        """
        Parameters
        ----------
        player_id : int
            選手ID
        player_name : str
            選手名
        season : str
            シーズン
        """
        self.player_id = player_id
        self.player_name = player_name
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
        print(f"🏀 Fetching shot data for {self.player_name}...")

        try:
            time.sleep(1)

            shot_chart = shotchartdetail.ShotChartDetail(
                team_id=0,
                player_id=self.player_id,
                season_nullable=self.season,
                season_type_all_star='Regular Season',
                context_measure_simple='FGA',
                game_id_nullable=game_id or ''
            )

            shots = shot_chart.get_data_frames()[0]
            self.shots_df = shots

            print(f"✅ {len(shots)}本のショットデータを取得")

            # Z軸（高さ）を推定
            # ショット距離に基づいて弧の高さを計算
            if 'SHOT_DISTANCE' in shots.columns:
                # 距離が遠いほど高く打ち上げる
                shots['SHOT_HEIGHT'] = shots['SHOT_DISTANCE'].apply(
                    lambda d: min(15 + d * 0.5, 35)  # 最大35feet
                )
            else:
                shots['SHOT_HEIGHT'] = 20  # デフォルト

            return shots

        except Exception as e:
            print(f"❌ Error fetching shot data: {e}")
            return pd.DataFrame()

    def draw_3d_court(self, ax):
        """
        3Dコートを描画

        Parameters
        ----------
        ax : matplotlib Axes3D
            3D axes
        """
        # リム（原点）
        theta = np.linspace(0, 2*np.pi, 100)
        rim_x = 7.5 * np.cos(theta)
        rim_y = 7.5 * np.sin(theta)
        rim_z = np.zeros_like(rim_x) + 10  # リムの高さ10feet

        ax.plot(rim_x, rim_y, rim_z, color='orange', linewidth=3, label='Rim')

        # バックボード
        backboard_x = [-30, 30, 30, -30, -30]
        backboard_y = [-7.5, -7.5, -7.5, -7.5, -7.5]
        backboard_z = [0, 0, 15, 15, 0]
        ax.plot(backboard_x, backboard_y, backboard_z, color='white', linewidth=2)

        # 3ポイントライン（地面）
        three_point_arc_theta = np.linspace(np.radians(22), np.radians(158), 100)
        three_arc_x = 237.5 * np.cos(three_point_arc_theta)
        three_arc_y = 237.5 * np.sin(three_point_arc_theta)
        three_arc_z = np.zeros_like(three_arc_x)

        ax.plot(three_arc_x, three_arc_y, three_arc_z, color='white', linewidth=2, alpha=0.6)

        # コーナー3
        ax.plot([-220, -220], [-47.5, 92.5], [0, 0], color='white', linewidth=2, alpha=0.6)
        ax.plot([220, 220], [-47.5, 92.5], [0, 0], color='white', linewidth=2, alpha=0.6)

        # ペイントエリア
        paint_x = [-80, 80, 80, -80, -80]
        paint_y = [-47.5, -47.5, 142.5, 142.5, -47.5]
        paint_z = [0, 0, 0, 0, 0]
        ax.plot(paint_x, paint_y, paint_z, color='white', linewidth=1.5, alpha=0.4)

        # 軸設定
        ax.set_xlim(-250, 250)
        ax.set_ylim(-50, 400)
        ax.set_zlim(0, 50)

        ax.set_xlabel('X (feet)', color='white')
        ax.set_ylabel('Y (feet)', color='white')
        ax.set_zlabel('Height (feet)', color='white')

        # 背景を暗く
        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False
        ax.xaxis.pane.set_edgecolor('gray')
        ax.yaxis.pane.set_edgecolor('gray')
        ax.zaxis.pane.set_edgecolor('gray')
        ax.grid(True, alpha=0.2)

        return ax

    def create_3d_animation(self, save_path='outputs/videos/shot_chart_3d.mp4',
                           fps=30, duration=10):
        """
        3D Shot Chartアニメーションを作成

        Parameters
        ----------
        save_path : str
            保存先パス
        fps : int
            フレームレート
        duration : int
            動画の長さ（秒）

        Returns
        -------
        matplotlib.animation.FuncAnimation
        """
        if self.shots_df is None or len(self.shots_df) == 0:
            print("❌ Shot dataがありません")
            return None

        print(f"\n🎬 3Dアニメーション作成中...")
        print(f"   フレームレート: {fps} fps")
        print(f"   動画の長さ: {duration}秒")

        # 成功/失敗で分類
        made_shots = self.shots_df[self.shots_df['SHOT_MADE_FLAG'] == 1].copy()
        missed_shots = self.shots_df[self.shots_df['SHOT_MADE_FLAG'] == 0].copy()

        fig = plt.figure(figsize=(14, 10), facecolor='black')
        ax = fig.add_subplot(111, projection='3d', facecolor='black')

        # コート描画
        self.draw_3d_court(ax)

        # タイトル
        title = ax.text2D(0.5, 0.95, f"{self.player_name} - 3D Shot Chart",
                         transform=ax.transAxes, fontsize=18, fontweight='bold',
                         color='white', ha='center')

        # 統計情報
        fg_pct = len(made_shots) / len(self.shots_df) * 100
        stats = ax.text2D(0.5, 0.90,
                         f"FG: {len(made_shots)}/{len(self.shots_df)} ({fg_pct:.1f}%)",
                         transform=ax.transAxes, fontsize=14,
                         color='white', ha='center')

        # アニメーション用の空のプロット
        made_scatter = ax.scatter([], [], [], c='lime', s=100, alpha=0.8,
                                 edgecolors='green', linewidths=2, label='Made')
        missed_scatter = ax.scatter([], [], [], c='red', s=50, alpha=0.4,
                                   marker='x', linewidths=2, label='Missed')

        ax.legend(loc='upper left', fontsize=12, facecolor='black',
                 edgecolor='white', labelcolor='white')

        # アニメーション関数
        total_frames = fps * duration
        shots_per_frame = max(1, len(self.shots_df) // total_frames)

        def init():
            """初期化"""
            made_scatter._offsets3d = ([], [], [])
            missed_scatter._offsets3d = ([], [], [])
            return made_scatter, missed_scatter

        def animate(frame):
            """各フレームの更新"""
            # 回転
            angle = frame * 360 / total_frames
            ax.view_init(elev=20, azim=angle)

            # ショットを徐々に追加
            num_shots = min(len(self.shots_df), (frame + 1) * shots_per_frame)

            current_made = made_shots.head(num_shots)
            current_missed = missed_shots.head(num_shots)

            # 更新
            if len(current_made) > 0:
                made_scatter._offsets3d = (
                    current_made['LOC_X'].values,
                    current_made['LOC_Y'].values,
                    current_made['SHOT_HEIGHT'].values
                )

            if len(current_missed) > 0:
                missed_scatter._offsets3d = (
                    current_missed['LOC_X'].values,
                    current_missed['LOC_Y'].values,
                    current_missed['SHOT_HEIGHT'].values
                )

            # 進捗表示
            progress = ax.text2D(0.5, 0.05, f"Shots: {num_shots}/{len(self.shots_df)}",
                               transform=ax.transAxes, fontsize=12,
                               color='cyan', ha='center')

            return made_scatter, missed_scatter, progress

        # アニメーション生成
        anim = animation.FuncAnimation(
            fig, animate, init_func=init,
            frames=total_frames, interval=1000/fps,
            blit=False
        )

        # 保存
        import os
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        print(f"\n💾 動画を保存中（これには数分かかります）...")
        try:
            # MP4として保存（ffmpegが必要）
            anim.save(save_path, writer='ffmpeg', fps=fps, dpi=150,
                     extra_args=['-vcodec', 'libx264'])
            print(f"✅ 3D Shot Chart動画を保存: {save_path}")
        except Exception as e:
            print(f"❌ MP4保存エラー: {e}")
            print("⚠️  GIFとして保存を試みます...")
            gif_path = save_path.replace('.mp4', '.gif')
            anim.save(gif_path, writer='pillow', fps=fps//2)
            print(f"✅ GIFとして保存: {gif_path}")

        plt.close()
        return anim

    def create_trajectory_animation(self, save_path='outputs/videos/shot_trajectory.mp4',
                                   num_shots=10, fps=30):
        """
        ショット軌跡アニメーション

        Parameters
        ----------
        save_path : str
            保存先
        num_shots : int
            描画するショット数
        fps : int
            フレームレート
        """
        if self.shots_df is None or len(self.shots_df) == 0:
            print("❌ Shot dataがありません")
            return None

        print(f"\n🎬 ショット軌跡アニメーション作成中...")

        # ランダムに選択
        selected_shots = self.shots_df.sample(min(num_shots, len(self.shots_df)))

        fig = plt.figure(figsize=(14, 10), facecolor='black')
        ax = fig.add_subplot(111, projection='3d', facecolor='black')

        self.draw_3d_court(ax)

        # タイトル
        title = ax.text2D(0.5, 0.95, f"{self.player_name} - Shot Trajectories",
                         transform=ax.transAxes, fontsize=18, fontweight='bold',
                         color='white', ha='center')

        def init():
            return []

        def animate(frame):
            ax.cla()
            self.draw_3d_court(ax)

            # 各ショットの軌跡を描画
            for idx, shot in selected_shots.iterrows():
                x_start = shot['LOC_X']
                y_start = shot['LOC_Y']
                x_end = 0  # リム中心
                y_end = 0

                # 放物線軌跡
                t = np.linspace(0, 1, 50)
                x_traj = x_start + (x_end - x_start) * t
                y_traj = y_start + (y_end - y_start) * t
                z_traj = shot['SHOT_HEIGHT'] * np.sin(np.pi * t)  # 放物線

                # 徐々に表示
                progress = min(1.0, frame / 60)
                visible_points = int(len(t) * progress)

                if visible_points > 0:
                    color = 'lime' if shot['SHOT_MADE_FLAG'] == 1 else 'red'
                    ax.plot(x_traj[:visible_points],
                           y_traj[:visible_points],
                           z_traj[:visible_points],
                           color=color, linewidth=2, alpha=0.7)

            # 回転
            angle = frame * 2
            ax.view_init(elev=25, azim=angle)

            return []

        anim = animation.FuncAnimation(
            fig, animate, init_func=init,
            frames=180, interval=1000//fps, blit=False
        )

        # 保存
        import os
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        print(f"\n💾 軌跡動画を保存中...")
        try:
            anim.save(save_path, writer='ffmpeg', fps=fps, dpi=150,
                     extra_args=['-vcodec', 'libx264'])
            print(f"✅ ショット軌跡動画を保存: {save_path}")
        except Exception as e:
            print(f"❌ MP4保存エラー: {e}")
            gif_path = save_path.replace('.mp4', '.gif')
            anim.save(gif_path, writer='pillow', fps=fps//2)
            print(f"✅ GIFとして保存: {gif_path}")

        plt.close()
        return anim


def main():
    """
    サンプル実行
    """
    print("="*80)
    print("3D Shot Chart Animator")
    print("="*80)
    print()
    print("使用例:")
    print()
    print("from src.shot_chart_3d import ShotChart3DAnimator")
    print()
    print("# Stephen Curry")
    print("animator = ShotChart3DAnimator(player_id=201939, player_name='Stephen Curry')")
    print("animator.fetch_shot_data()")
    print("animator.create_3d_animation()")
    print("animator.create_trajectory_animation()")


if __name__ == '__main__':
    main()

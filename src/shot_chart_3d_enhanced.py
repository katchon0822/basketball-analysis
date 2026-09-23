"""
3D Shot Chart Animator - Enhanced Version
Basketball Flow Lab - リッチな3D可視化

改良点:
- 時系列順にシュートを表示
- ボールをリアルな球体で表現
- グラデーション効果
- より滑らかなアニメーション
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import animation
from matplotlib.patches import Circle, Rectangle, Arc
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import seaborn as sns
from nba_api.stats.endpoints import shotchartdetail
import time
import warnings
warnings.filterwarnings('ignore')


class EnhancedShotChart3D:
    """
    時系列順 + リッチなボール表現の3D Shot Chart
    """

    def __init__(self, player_id, player_name, season='2024-25'):
        self.player_id = player_id
        self.player_name = player_name
        self.season = season
        self.shots_df = None

    def fetch_shot_data(self, game_id=None):
        """Shot dataを取得"""
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

            # 時系列順にソート（ゲームID、ピリオド、時間）
            if 'GAME_ID' in shots.columns:
                shots = shots.sort_values(['GAME_ID', 'PERIOD', 'MINUTES_REMAINING', 'SECONDS_REMAINING'],
                                         ascending=[True, True, False, False])

            self.shots_df = shots

            print(f"✅ {len(shots)}本のショットデータを取得")

            # Z軸（高さ）を推定
            if 'SHOT_DISTANCE' in shots.columns:
                shots['SHOT_HEIGHT'] = shots['SHOT_DISTANCE'].apply(
                    lambda d: min(15 + d * 0.6, 40)  # より高い弧
                )
            else:
                shots['SHOT_HEIGHT'] = 20

            return shots

        except Exception as e:
            print(f"❌ Error: {e}")
            return pd.DataFrame()

    def draw_3d_court_enhanced(self, ax):
        """
        強化された3Dコート描画
        """
        # リム（オレンジ色の3D円）
        theta = np.linspace(0, 2*np.pi, 100)
        rim_x = 7.5 * np.cos(theta)
        rim_y = 7.5 * np.sin(theta)
        rim_z = np.zeros_like(rim_x) + 10

        ax.plot(rim_x, rim_y, rim_z, color='#FF6B35', linewidth=4, label='Rim')

        # リムの影（地面）
        ax.plot(rim_x, rim_y, np.zeros_like(rim_x), color='orange',
                linewidth=2, alpha=0.3, linestyle='--')

        # バックボード（ガラス風）
        backboard_x = [-30, 30, 30, -30, -30]
        backboard_y = [-7.5, -7.5, -7.5, -7.5, -7.5]
        backboard_z = [0, 0, 15, 15, 0]

        # ガラスの反射効果
        verts = [list(zip(backboard_x[:4], backboard_y[:4], backboard_z[:4]))]
        backboard_poly = Poly3DCollection(verts, alpha=0.3, facecolor='cyan',
                                         edgecolor='white', linewidth=2)
        ax.add_collection3d(backboard_poly)

        # 3ポイントライン（地面、明るく）
        three_point_arc_theta = np.linspace(np.radians(22), np.radians(158), 100)
        three_arc_x = 237.5 * np.cos(three_point_arc_theta)
        three_arc_y = 237.5 * np.sin(three_point_arc_theta)
        three_arc_z = np.zeros_like(three_arc_x)

        ax.plot(three_arc_x, three_arc_y, three_arc_z, color='#00D9FF',
                linewidth=3, alpha=0.8, label='3PT Line')

        # コーナー3
        ax.plot([-220, -220], [-47.5, 92.5], [0, 0], color='#00D9FF',
                linewidth=3, alpha=0.8)
        ax.plot([220, 220], [-47.5, 92.5], [0, 0], color='#00D9FF',
                linewidth=3, alpha=0.8)

        # ペイントエリア（黄色系）
        paint_x = [-80, 80, 80, -80, -80]
        paint_y = [-47.5, -47.5, 142.5, 142.5, -47.5]
        paint_z = [0, 0, 0, 0, 0]
        ax.plot(paint_x, paint_y, paint_z, color='#FFD700',
                linewidth=2, alpha=0.6)

        # フリースローライン
        ax.plot([-60, 60], [142.5, 142.5], [0, 0], color='white',
                linewidth=2, alpha=0.5)

        # 軸設定
        ax.set_xlim(-250, 250)
        ax.set_ylim(-50, 400)
        ax.set_zlim(0, 50)

        ax.set_xlabel('', color='white')
        ax.set_ylabel('', color='white')
        ax.set_zlabel('', color='white')

        # グリッドとパネルの設定
        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False
        ax.xaxis.pane.set_edgecolor('gray')
        ax.yaxis.pane.set_edgecolor('gray')
        ax.zaxis.pane.set_edgecolor('gray')
        ax.grid(True, alpha=0.2, color='gray')

        # 軸の目盛りを非表示
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_zticks([])

        return ax

    def draw_basketball(self, ax, x, y, z, radius=5, color='orange', alpha=1.0):
        """
        リアルなバスケットボールを描画（球体）

        Parameters
        ----------
        ax : Axes3D
        x, y, z : float
            位置
        radius : float
            半径
        color : str
            色
        alpha : float
            透明度
        """
        # 球体のメッシュ
        u = np.linspace(0, 2 * np.pi, 20)
        v = np.linspace(0, np.pi, 20)

        sphere_x = x + radius * np.outer(np.cos(u), np.sin(v))
        sphere_y = y + radius * np.outer(np.sin(u), np.sin(v))
        sphere_z = z + radius * np.outer(np.ones(np.size(u)), np.cos(v))

        return ax.plot_surface(sphere_x, sphere_y, sphere_z,
                              color=color, alpha=alpha, shade=True)

    def create_chronological_trajectory_animation(self,
                                                  save_path='outputs/videos/curry_chronological_3d.mp4',
                                                  num_shots=30, fps=30, duration=20):
        """
        時系列順にショット軌跡を表示するアニメーション

        Parameters
        ----------
        save_path : str
            保存先
        num_shots : int
            表示するショット数
        fps : int
            フレームレート
        duration : int
            動画の長さ（秒）
        """
        if self.shots_df is None or len(self.shots_df) == 0:
            print("❌ Shot dataがありません")
            return None

        print(f"\n🎬 時系列順3Dアニメーション作成中...")
        print(f"   ショット数: {num_shots}本")
        print(f"   フレームレート: {fps} fps")
        print(f"   動画の長さ: {duration}秒")

        # 時系列順に選択（既にソート済み）
        selected_shots = self.shots_df.head(num_shots).copy()
        selected_shots['shot_index'] = range(len(selected_shots))

        fig = plt.figure(figsize=(16, 10), facecolor='#0a0a0a')
        ax = fig.add_subplot(111, projection='3d', facecolor='#0a0a0a')

        # タイトル
        title = ax.text2D(0.5, 0.95, f"{self.player_name} - Chronological Shot Chart",
                         transform=ax.transAxes, fontsize=20, fontweight='bold',
                         color='white', ha='center')

        # 統計情報
        made = self.shots_df[self.shots_df['SHOT_MADE_FLAG'] == 1]
        stats_text = f"FG: {len(made)}/{len(self.shots_df)} ({len(made)/len(self.shots_df)*100:.1f}%)"
        stats = ax.text2D(0.5, 0.90, stats_text,
                         transform=ax.transAxes, fontsize=16,
                         color='cyan', ha='center')

        # 進捗表示用
        progress_text = ax.text2D(0.5, 0.05, "",
                                 transform=ax.transAxes, fontsize=14,
                                 color='lime', ha='center')

        total_frames = fps * duration
        trajectory_points = 50  # 各軌跡の点数

        def init():
            """初期化"""
            return []

        def animate(frame):
            """各フレームの更新"""
            ax.cla()
            self.draw_3d_court_enhanced(ax)

            # カメラの回転
            angle = 45 + (frame / total_frames) * 180  # 45度から225度まで
            ax.view_init(elev=25, azim=angle)

            # 現在表示すべきショット数
            shots_to_show = int((frame / total_frames) * num_shots)

            for idx, shot in selected_shots.head(shots_to_show).iterrows():
                x_start = shot['LOC_X']
                y_start = shot['LOC_Y']
                x_end = 0
                y_end = 0

                # 放物線軌跡
                t = np.linspace(0, 1, trajectory_points)
                x_traj = x_start + (x_end - x_start) * t
                y_traj = y_start + (y_end - y_start) * t
                z_traj = shot['SHOT_HEIGHT'] * np.sin(np.pi * t)

                # 色とアルファ値（新しいショットほど明るく）
                shot_age = (shots_to_show - shot['shot_index']) / shots_to_show
                alpha = 0.3 + 0.7 * (1 - shot_age)  # 古いショットは薄く

                color = '#00FF00' if shot['SHOT_MADE_FLAG'] == 1 else '#FF4444'

                # 軌跡を描画
                ax.plot(x_traj, y_traj, z_traj,
                       color=color, linewidth=2.5, alpha=alpha)

                # 最新のショットにはボールを描画
                if shot['shot_index'] == shots_to_show - 1:
                    # ボールの現在位置（アニメーション中）
                    ball_progress = (frame % (total_frames // num_shots)) / (total_frames // num_shots)
                    ball_idx = int(ball_progress * trajectory_points)
                    ball_idx = min(ball_idx, trajectory_points - 1)

                    ball_x = x_traj[ball_idx]
                    ball_y = y_traj[ball_idx]
                    ball_z = z_traj[ball_idx]

                    # リアルなバスケットボール
                    self.draw_basketball(ax, ball_x, ball_y, ball_z,
                                       radius=8, color='#FF8C00', alpha=0.9)

                    # ボールの影
                    ax.scatter([ball_x], [ball_y], [0],
                             c='gray', s=100, alpha=0.3, marker='o')

            # 進捗更新
            progress_text.set_text(f"Shot {shots_to_show}/{num_shots}")
            title.set_text(f"{self.player_name} - Chronological Shot Chart")

            return []

        # アニメーション生成
        anim = animation.FuncAnimation(
            fig, animate, init_func=init,
            frames=total_frames, interval=1000//fps,
            blit=False
        )

        # 保存
        import os
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        print(f"\n💾 動画を保存中（数分かかります）...")
        try:
            anim.save(save_path, writer='ffmpeg', fps=fps, dpi=150,
                     extra_args=['-vcodec', 'libx264', '-pix_fmt', 'yuv420p'])
            print(f"✅ 時系列3D動画を保存: {save_path}")
        except Exception as e:
            print(f"❌ MP4保存エラー: {e}")
            gif_path = save_path.replace('.mp4', '.gif')
            anim.save(gif_path, writer='pillow', fps=fps//2)
            print(f"✅ GIFとして保存: {gif_path}")

        plt.close()
        return anim


def main():
    print("="*80)
    print("Enhanced 3D Shot Chart - 時系列 + リッチなボール表現")
    print("="*80)
    print()
    print("使用例:")
    print()
    print("from src.shot_chart_3d_enhanced import EnhancedShotChart3D")
    print()
    print("animator = EnhancedShotChart3D(player_id=201939, player_name='Stephen Curry')")
    print("animator.fetch_shot_data()")
    print("animator.create_chronological_trajectory_animation(num_shots=30)")


if __name__ == '__main__':
    main()

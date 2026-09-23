"""
3D Shot Chart - Ultra Realistic Court & Rim
Basketball Flow Lab - 超リアルなコートとゴール

改良点:
- ボールなし（軌跡のみ）
- リアルな木製コート
- 立体的なゴールとネット
- リアルなバックボード
- 詳細なコートライン
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


class RealisticShotChart3D:
    """
    超リアルなコート・ゴール表現の3D Shot Chart
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

            # 時系列順にソート
            if 'GAME_ID' in shots.columns:
                shots = shots.sort_values(['GAME_ID', 'PERIOD', 'MINUTES_REMAINING', 'SECONDS_REMAINING'],
                                         ascending=[True, True, False, False])

            self.shots_df = shots
            print(f"✅ {len(shots)}本のショットデータを取得")

            # Z軸（高さ）を推定
            if 'SHOT_DISTANCE' in shots.columns:
                shots['SHOT_HEIGHT'] = shots['SHOT_DISTANCE'].apply(
                    lambda d: min(15 + d * 0.6, 40)
                )
            else:
                shots['SHOT_HEIGHT'] = 20

            return shots

        except Exception as e:
            print(f"❌ Error: {e}")
            return pd.DataFrame()

    def draw_realistic_court(self, ax):
        """
        超リアルな3Dコート描画
        """
        # === コートフロア（木製テクスチャ風） ===
        court_x = [-250, 250, 250, -250]
        court_y = [-50, -50, 400, 400]
        court_z = [0, 0, 0, 0]

        verts = [list(zip(court_x, court_y, court_z))]
        court_floor = Poly3DCollection(verts, alpha=0.95,
                                      facecolor='#C19A6B',  # 木製色
                                      edgecolor='#8B7355', linewidth=2)
        ax.add_collection3d(court_floor)

        # === リアルなゴール（リム + ネット + バックボード） ===

        # 1. バックボード（透明なガラス + 赤い枠）
        backboard_width = 72  # 6フィート = 72インチ
        backboard_height = 42  # 3.5フィート
        backboard_x = [-backboard_width/2, backboard_width/2,
                      backboard_width/2, -backboard_width/2, -backboard_width/2]
        backboard_y = [-7.5, -7.5, -7.5, -7.5, -7.5]
        backboard_z = [10 - backboard_height/2, 10 - backboard_height/2,
                      10 + backboard_height/2, 10 + backboard_height/2,
                      10 - backboard_height/2]

        # ガラス本体
        bb_verts = [list(zip(backboard_x[:4], backboard_y[:4], backboard_z[:4]))]
        backboard_glass = Poly3DCollection(bb_verts, alpha=0.2,
                                          facecolor='cyan', edgecolor='none')
        ax.add_collection3d(backboard_glass)

        # 赤い枠
        ax.plot(backboard_x, backboard_y, backboard_z, color='#E03C31',
                linewidth=4)

        # 内側の四角（リム周辺のターゲット）
        target_w = 24
        target_h = 18
        target_x = [-target_w/2, target_w/2, target_w/2, -target_w/2, -target_w/2]
        target_y = [-7.5, -7.5, -7.5, -7.5, -7.5]
        target_z = [10 - target_h/2, 10 - target_h/2, 10 + target_h/2,
                   10 + target_h/2, 10 - target_h/2]
        ax.plot(target_x, target_y, target_z, color='white', linewidth=2)

        # 2. リム（18インチ直径のオレンジ色の輪）
        theta = np.linspace(0, 2*np.pi, 100)
        rim_radius = 9  # 18インチ直径 = 9インチ半径
        rim_x = rim_radius * np.cos(theta)
        rim_y = rim_radius * np.sin(theta)
        rim_z = np.zeros_like(rim_x) + 10  # 10フィート高

        ax.plot(rim_x, rim_y, rim_z, color='#FF6B35', linewidth=5, zorder=10)

        # リムの厚み（3D効果）
        rim_z_bottom = rim_z - 0.5
        ax.plot(rim_x, rim_y, rim_z_bottom, color='#CC5020', linewidth=4,
                alpha=0.8)

        # 3. ネット（ワイヤーフレーム）
        net_depth = 15  # ネットの長さ
        num_segments = 10

        for i in range(8):  # 8本の縦線
            angle = i * np.pi / 4
            net_x_top = rim_radius * np.cos(angle)
            net_y_top = rim_radius * np.sin(angle)
            net_x_bottom = (rim_radius * 0.5) * np.cos(angle)
            net_y_bottom = (rim_radius * 0.5) * np.sin(angle)

            net_x = np.linspace(net_x_top, net_x_bottom, num_segments)
            net_y = np.linspace(net_y_top, net_y_bottom, num_segments)
            net_z = np.linspace(10, 10 - net_depth, num_segments)

            ax.plot(net_x, net_y, net_z, color='white', linewidth=1,
                   alpha=0.6)

        # === コートライン（白線） ===

        # 3ポイントライン
        three_arc_theta = np.linspace(np.radians(22), np.radians(158), 150)
        three_arc_x = 237.5 * np.cos(three_arc_theta)
        three_arc_y = 237.5 * np.sin(three_arc_theta)
        three_arc_z = np.zeros_like(three_arc_x) + 0.5  # 少し浮かせる

        ax.plot(three_arc_x, three_arc_y, three_arc_z, color='white',
                linewidth=3, alpha=0.95)

        # コーナー3
        ax.plot([-220, -220], [-47.5, 92.5], [0.5, 0.5], color='white',
                linewidth=3, alpha=0.95)
        ax.plot([220, 220], [-47.5, 92.5], [0.5, 0.5], color='white',
                linewidth=3, alpha=0.95)

        # ペイントエリア（キーエリア）
        # アウター
        outer_box_x = [-80, 80, 80, -80, -80]
        outer_box_y = [-47.5, -47.5, 142.5, 142.5, -47.5]
        outer_box_z = [0.5, 0.5, 0.5, 0.5, 0.5]
        ax.plot(outer_box_x, outer_box_y, outer_box_z, color='white',
                linewidth=2.5, alpha=0.9)

        # インナー
        inner_box_x = [-60, 60, 60, -60, -60]
        inner_box_y = [-47.5, -47.5, 142.5, 142.5, -47.5]
        inner_box_z = [0.5, 0.5, 0.5, 0.5, 0.5]
        ax.plot(inner_box_x, inner_box_y, inner_box_z, color='white',
                linewidth=2.5, alpha=0.9)

        # フリースローサークル
        ft_theta = np.linspace(0, np.pi, 100)
        ft_x = 60 * np.cos(ft_theta)
        ft_y = 142.5 + 60 * np.sin(ft_theta)
        ft_z = np.zeros_like(ft_x) + 0.5
        ax.plot(ft_x, ft_y, ft_z, color='white', linewidth=2.5, alpha=0.9)

        # 破線（下半円）
        ft_theta_dash = np.linspace(np.pi, 2*np.pi, 100)
        ft_x_dash = 60 * np.cos(ft_theta_dash)
        ft_y_dash = 142.5 + 60 * np.sin(ft_theta_dash)
        ft_z_dash = np.zeros_like(ft_x_dash) + 0.5
        ax.plot(ft_x_dash, ft_y_dash, ft_z_dash, color='white',
                linewidth=2, alpha=0.7, linestyle='--')

        # === 軸設定 ===
        ax.set_xlim(-260, 260)
        ax.set_ylim(-60, 410)
        ax.set_zlim(0, 50)

        ax.set_xlabel('', color='white')
        ax.set_ylabel('', color='white')
        ax.set_zlabel('', color='white')

        # 背景設定
        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False
        ax.xaxis.pane.set_edgecolor('#333333')
        ax.yaxis.pane.set_edgecolor('#333333')
        ax.zaxis.pane.set_edgecolor('#333333')
        ax.grid(False)

        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_zticks([])

        return ax

    def create_realistic_animation(self,
                                   save_path='outputs/videos/realistic_3d.mp4',
                                   num_shots=40, fps=30, duration=20):
        """
        超リアルなコートでの3D動画作成
        """
        if self.shots_df is None or len(self.shots_df) == 0:
            print("❌ Shot dataがありません")
            return None

        print(f"\n🎬 Ultra Realistic 3D動画作成中...")
        print(f"   特徴: 木製コート + リアルなゴール + ネット")
        print(f"   ショット数: {num_shots}本")
        print(f"   動画の長さ: {duration}秒")

        selected_shots = self.shots_df.head(num_shots).copy()
        selected_shots['shot_index'] = range(len(selected_shots))

        fig = plt.figure(figsize=(16, 10), facecolor='#1a1a1a')
        ax = fig.add_subplot(111, projection='3d', facecolor='#1a1a1a')

        # タイトル
        title = ax.text2D(0.5, 0.95, f"{self.player_name} - Ultra Realistic Shot Chart",
                         transform=ax.transAxes, fontsize=20, fontweight='bold',
                         color='white', ha='center')

        # 統計
        made = self.shots_df[self.shots_df['SHOT_MADE_FLAG'] == 1]
        stats_text = f"FG: {len(made)}/{len(self.shots_df)} ({len(made)/len(self.shots_df)*100:.1f}%)"
        stats = ax.text2D(0.5, 0.90, stats_text,
                         transform=ax.transAxes, fontsize=16,
                         color='#FFD700', ha='center')

        progress_text = ax.text2D(0.5, 0.05, "",
                                 transform=ax.transAxes, fontsize=14,
                                 color='lime', ha='center')

        total_frames = fps * duration
        trajectory_points = 50

        def init():
            return []

        def animate(frame):
            ax.cla()
            self.draw_realistic_court(ax)

            # カメラ回転
            angle = 45 + (frame / total_frames) * 180
            ax.view_init(elev=25, azim=angle)

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

                # グラデーション
                shot_age = (shots_to_show - shot['shot_index']) / shots_to_show
                alpha = 0.3 + 0.7 * (1 - shot_age)

                color = '#00FF41' if shot['SHOT_MADE_FLAG'] == 1 else '#FF073A'

                # 軌跡描画（ボールなし）
                ax.plot(x_traj, y_traj, z_traj,
                       color=color, linewidth=3, alpha=alpha)

            # 進捗更新
            progress_text.set_text(f"Shot {shots_to_show}/{num_shots}")

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

        print(f"\n💾 動画を保存中...")
        try:
            anim.save(save_path, writer='ffmpeg', fps=fps, dpi=150,
                     extra_args=['-vcodec', 'libx264', '-pix_fmt', 'yuv420p'])
            print(f"✅ Ultra Realistic 3D動画を保存: {save_path}")
        except Exception as e:
            print(f"❌ MP4保存エラー: {e}")

        plt.close()
        return anim


def main():
    print("="*80)
    print("Ultra Realistic 3D Shot Chart")
    print("木製コート + リアルなゴール + ネット")
    print("="*80)


if __name__ == '__main__':
    main()

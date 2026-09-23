"""
YouTube動画からの手動データ分析
Shot Chart、Box Score、Play-by-Playの生成
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import Circle, Rectangle, Arc
import seaborn as sns
import numpy as np

class YouTubeGameAnalyzer:
    """
    YouTube動画から手動で記録したデータを分析・可視化
    """

    def __init__(self, game_name="YouTube Game"):
        self.game_name = game_name
        self.shot_data = None
        self.box_score = None
        self.play_by_play = None

        # 日本語フォント設定
        plt.rcParams['font.sans-serif'] = ['Hiragino Sans', 'Yu Gothic', 'Meirio', 'IPAexGothic']
        plt.rcParams['axes.unicode_minus'] = False

    def load_shot_data(self, csv_path):
        """
        Shot Dataを読み込み

        CSVフォーマット:
        period, clock, team, player_name, shot_type, shot_distance, loc_x, loc_y, shot_made, points
        """
        self.shot_data = pd.read_csv(csv_path)
        print(f"✅ Shot Data読み込み: {len(self.shot_data)}本のショット")
        return self.shot_data

    def load_box_score(self, csv_path):
        """
        Box Scoreを読み込み

        CSVフォーマット:
        team, player_name, minutes, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct,
        ftm, fta, ft_pct, oreb, dreb, reb, ast, stl, blk, tov, pf, pts
        """
        self.box_score = pd.read_csv(csv_path)
        print(f"✅ Box Score読み込み: {len(self.box_score)}選手")
        return self.box_score

    def load_play_by_play(self, csv_path):
        """
        Play-by-Playを読み込み

        CSVフォーマット:
        period, clock, home_score, away_score, team, player_name, action_type, description
        """
        self.play_by_play = pd.read_csv(csv_path)
        print(f"✅ Play-by-Play読み込み: {len(self.play_by_play)}プレー")
        return self.play_by_play

    def draw_court(self, ax, color='black', lw=2):
        """
        バスケットコートを描画
        """
        # リム
        hoop = Circle((0, 0), radius=7.5, linewidth=lw, color=color, fill=False)
        ax.add_patch(hoop)

        # バックボード
        ax.plot([-30, 30], [-7.5, -7.5], color=color, linewidth=lw)

        # ペイント
        paint = Rectangle((-80, -47.5), 160, 190, linewidth=lw, color=color, fill=False)
        ax.add_patch(paint)

        # フリースローサークル
        top_ft = Arc((0, 142.5), 120, 120, theta1=0, theta2=180, linewidth=lw, color=color, fill=False)
        ax.add_patch(top_ft)

        # 3Pライン
        three_arc = Arc((0, 0), 475, 475, theta1=22, theta2=158, linewidth=lw, color=color)
        ax.add_patch(three_arc)

        # コーナー3P
        ax.plot([-220, -220], [-47.5, 92.5], color=color, linewidth=lw)
        ax.plot([220, 220], [-47.5, 92.5], color=color, linewidth=lw)

        ax.set_xlim(-250, 250)
        ax.set_ylim(-47.5, 422.5)
        ax.set_aspect('equal')
        ax.axis('off')

    def create_shot_chart(self, team=None, player=None, save_path='outputs/youtube_shots/shot_chart.png'):
        """
        Shot Chart作成

        Parameters
        ----------
        team : str, optional
            チーム名でフィルタ ('HOME', 'AWAY', None=全体)
        player : str, optional
            選手名でフィルタ
        save_path : str
            保存先パス
        """
        if self.shot_data is None:
            print("❌ Shot Dataが読み込まれていません")
            return

        # フィルタリング
        shots = self.shot_data.copy()
        if team:
            shots = shots[shots['team'] == team]
        if player:
            shots = shots[shots['player_name'] == player]

        if len(shots) == 0:
            print("❌ 該当するショットがありません")
            return

        # Figure作成
        fig, ax = plt.subplots(figsize=(12, 11), facecolor='white')

        # コート描画
        self.draw_court(ax)

        # ショット描画
        made = shots[shots['shot_made'] == 1]
        missed = shots[shots['shot_made'] == 0]

        # 失敗（赤×）
        ax.scatter(missed['loc_x'], missed['loc_y'],
                  c='#FF6B6B', alpha=0.4, s=80, marker='x', linewidths=2, label='Missed')

        # 成功（緑●）
        ax.scatter(made['loc_x'], made['loc_y'],
                  c='#51CF66', alpha=0.7, s=120, edgecolors='#37B24D', linewidths=2, label='Made')

        # タイトル
        title = self.game_name
        if team:
            title += f" - {team}"
        if player:
            title += f" - {player}"

        # 統計情報
        total = len(shots)
        made_count = len(made)
        fg_pct = (made_count / total * 100) if total > 0 else 0

        # 3Pショット統計
        three_pt = shots[shots['shot_type'].str.contains('3PT|3-PT|3pt|3-pt', case=False, na=False)]
        three_made = three_pt[three_pt['shot_made'] == 1]
        three_pct = (len(three_made) / len(three_pt) * 100) if len(three_pt) > 0 else 0

        stats_text = f"FG: {fg_pct:.1f}% ({made_count}/{total})\n"
        stats_text += f"3P: {three_pct:.1f}% ({len(three_made)}/{len(three_pt)})"

        ax.set_title(f"{title}\n{stats_text}", fontsize=16, fontweight='bold', pad=20)
        ax.legend(loc='upper right', fontsize=12)

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"\n✅ Shot Chartを保存: {save_path}")
        plt.close()

        return fig

    def create_box_score_table(self, save_path='outputs/youtube_shots/box_score.png'):
        """
        Box Scoreテーブルを画像として生成
        """
        if self.box_score is None:
            print("❌ Box Scoreが読み込まれていません")
            return

        # Figure作成
        fig, axes = plt.subplots(2, 1, figsize=(16, 10), facecolor='white')

        # HOMEチーム
        home_box = self.box_score[self.box_score['team'] == 'HOME']
        if len(home_box) > 0:
            ax1 = axes[0]
            ax1.axis('tight')
            ax1.axis('off')

            # カラム選択
            columns = ['player_name', 'minutes', 'pts', 'reb', 'ast', 'fgm', 'fga', 'fg_pct',
                      'fg3m', 'fg3a', 'fg3_pct', 'ftm', 'fta', 'ft_pct', 'stl', 'blk', 'tov', 'pf']

            table_data = home_box[columns].values

            table1 = ax1.table(cellText=table_data, colLabels=columns,
                             loc='center', cellLoc='center')
            table1.auto_set_font_size(False)
            table1.set_fontsize(9)
            table1.scale(1, 2)

            # ヘッダーのスタイル
            for i in range(len(columns)):
                table1[(0, i)].set_facecolor('#4CAF50')
                table1[(0, i)].set_text_props(weight='bold', color='white')

            ax1.set_title('HOME TEAM', fontsize=16, fontweight='bold', pad=10)

        # AWAYチーム
        away_box = self.box_score[self.box_score['team'] == 'AWAY']
        if len(away_box) > 0:
            ax2 = axes[1]
            ax2.axis('tight')
            ax2.axis('off')

            table_data = away_box[columns].values

            table2 = ax2.table(cellText=table_data, colLabels=columns,
                             loc='center', cellLoc='center')
            table2.auto_set_font_size(False)
            table2.set_fontsize(9)
            table2.scale(1, 2)

            # ヘッダーのスタイル
            for i in range(len(columns)):
                table2[(0, i)].set_facecolor('#2196F3')
                table2[(0, i)].set_text_props(weight='bold', color='white')

            ax2.set_title('AWAY TEAM', fontsize=16, fontweight='bold', pad=10)

        plt.suptitle(f'{self.game_name} - Box Score', fontsize=18, fontweight='bold', y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✅ Box Scoreを保存: {save_path}")
        plt.close()

        return fig

    def create_score_flow(self, save_path='outputs/youtube_shots/score_flow.png'):
        """
        スコア推移グラフを作成
        """
        if self.play_by_play is None:
            print("❌ Play-by-Playが読み込まれていません")
            return

        pbp = self.play_by_play.copy()

        # Figure作成
        fig, ax = plt.subplots(figsize=(16, 8), facecolor='white')

        # プレー番号（X軸）
        pbp['play_num'] = range(len(pbp))

        # スコア推移
        ax.plot(pbp['play_num'], pbp['home_score'],
               color='#4CAF50', linewidth=3, label='HOME', marker='o', markersize=4)
        ax.plot(pbp['play_num'], pbp['away_score'],
               color='#2196F3', linewidth=3, label='AWAY', marker='o', markersize=4)

        # クォーター区切り線
        quarters = pbp.groupby('period')['play_num'].min()
        for q, play_num in quarters.items():
            if q > 1:
                ax.axvline(x=play_num, color='gray', linestyle='--', alpha=0.5)
                ax.text(play_num, ax.get_ylim()[1], f'Q{q}',
                       ha='left', va='top', fontsize=10, fontweight='bold')

        ax.set_xlabel('Play Number', fontsize=14)
        ax.set_ylabel('Score', fontsize=14)
        ax.set_title(f'{self.game_name} - Score Flow', fontsize=18, fontweight='bold', pad=20)
        ax.legend(loc='upper left', fontsize=14)
        ax.grid(alpha=0.3, linestyle='--')

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✅ Score Flowを保存: {save_path}")
        plt.close()

        return fig

    def create_player_stats_summary(self, save_path='outputs/youtube_shots/player_stats.png'):
        """
        選手別統計サマリー
        """
        if self.box_score is None:
            print("❌ Box Scoreが読み込まれていません")
            return

        # 上位5選手（得点順）
        top_scorers = self.box_score.nlargest(5, 'pts')

        fig, axes = plt.subplots(2, 2, figsize=(16, 12), facecolor='white')

        # 1. 得点ランキング
        ax1 = axes[0, 0]
        colors = ['#4CAF50' if t == 'HOME' else '#2196F3' for t in top_scorers['team']]
        ax1.barh(top_scorers['player_name'], top_scorers['pts'], color=colors, alpha=0.8)
        ax1.set_xlabel('Points', fontsize=12)
        ax1.set_title('Top 5 Scorers', fontsize=14, fontweight='bold')
        ax1.grid(axis='x', alpha=0.3)

        # 2. アシストランキング
        ax2 = axes[0, 1]
        top_assists = self.box_score.nlargest(5, 'ast')
        colors = ['#4CAF50' if t == 'HOME' else '#2196F3' for t in top_assists['team']]
        ax2.barh(top_assists['player_name'], top_assists['ast'], color=colors, alpha=0.8)
        ax2.set_xlabel('Assists', fontsize=12)
        ax2.set_title('Top 5 Assists', fontsize=14, fontweight='bold')
        ax2.grid(axis='x', alpha=0.3)

        # 3. リバウンドランキング
        ax3 = axes[1, 0]
        top_rebounds = self.box_score.nlargest(5, 'reb')
        colors = ['#4CAF50' if t == 'HOME' else '#2196F3' for t in top_rebounds['team']]
        ax3.barh(top_rebounds['player_name'], top_rebounds['reb'], color=colors, alpha=0.8)
        ax3.set_xlabel('Rebounds', fontsize=12)
        ax3.set_title('Top 5 Rebounds', fontsize=14, fontweight='bold')
        ax3.grid(axis='x', alpha=0.3)

        # 4. FG%ランキング（最低5本試投）
        ax4 = axes[1, 1]
        qualified = self.box_score[self.box_score['fga'] >= 5]
        if len(qualified) > 0:
            top_fg = qualified.nlargest(5, 'fg_pct')
            colors = ['#4CAF50' if t == 'HOME' else '#2196F3' for t in top_fg['team']]
            ax4.barh(top_fg['player_name'], top_fg['fg_pct'], color=colors, alpha=0.8)
            ax4.set_xlabel('FG%', fontsize=12)
            ax4.set_title('Top 5 FG% (min 5 FGA)', fontsize=14, fontweight='bold')
            ax4.grid(axis='x', alpha=0.3)

        plt.suptitle(f'{self.game_name} - Player Statistics', fontsize=18, fontweight='bold', y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✅ Player Statsを保存: {save_path}")
        plt.close()

        return fig

    def generate_all_reports(self, output_dir='outputs/youtube_shots'):
        """
        すべてのレポートを一括生成
        """
        print("="*80)
        print(f"🏀 {self.game_name} - 分析レポート生成")
        print("="*80)
        print()

        # Shot Chart
        if self.shot_data is not None:
            self.create_shot_chart(save_path=f'{output_dir}/shot_chart_all.png')
            self.create_shot_chart(team='HOME', save_path=f'{output_dir}/shot_chart_home.png')
            self.create_shot_chart(team='AWAY', save_path=f'{output_dir}/shot_chart_away.png')

        # Box Score
        if self.box_score is not None:
            self.create_box_score_table(save_path=f'{output_dir}/box_score.png')
            self.create_player_stats_summary(save_path=f'{output_dir}/player_stats.png')

        # Score Flow
        if self.play_by_play is not None:
            self.create_score_flow(save_path=f'{output_dir}/score_flow.png')

        print()
        print("="*80)
        print("✨ すべてのレポート生成完了")
        print("="*80)
        print()
        print(f"📂 出力先: {output_dir}/")
        print()
        print("生成されたファイル:")
        print("  - shot_chart_all.png     (全体のShot Chart)")
        print("  - shot_chart_home.png    (HOMEチームのShot Chart)")
        print("  - shot_chart_away.png    (AWAYチームのShot Chart)")
        print("  - box_score.png          (Box Score)")
        print("  - player_stats.png       (選手統計)")
        print("  - score_flow.png         (スコア推移)")


def main():
    """
    使用例
    """
    print("="*80)
    print("YouTube Game Analyzer - 使用例")
    print("="*80)
    print()
    print("# アナライザー作成")
    print("analyzer = YouTubeGameAnalyzer(game_name='YouTube Game Example')")
    print()
    print("# データ読み込み")
    print("analyzer.load_shot_data('data/templates/shot_data_template.csv')")
    print("analyzer.load_box_score('data/templates/box_score_template.csv')")
    print("analyzer.load_play_by_play('data/templates/play_by_play_template.csv')")
    print()
    print("# レポート生成")
    print("analyzer.generate_all_reports()")
    print()


if __name__ == '__main__':
    main()

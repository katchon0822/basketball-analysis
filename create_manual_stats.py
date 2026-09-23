#!/usr/bin/env python3
"""
手動でPlay-by-Playスタッツを作成するツール

動画を見ながらシュートタイミングを記録して、
後からPlay-by-Playとシュートチャートを生成
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path
import json
from datetime import datetime

# 日本語フォント
plt.rcParams['font.family'] = 'Hiragino Sans'
plt.rcParams['font.size'] = 10

class ManualStatsCreator:
    def __init__(self):
        self.output_dir = Path("outputs/three_games_manual")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_sample_data(self):
        """サンプルデータ作成（手動入力のテンプレート）"""

        # 試合2-1のサンプル
        game1_shots = [
            {'time': 60, 'team': 'A', 'x': 470, 'y': 55, 'made': True},
            {'time': 120, 'team': 'B', 'x': 470, 'y': 665, 'made': False},
            {'time': 180, 'team': 'A', 'x': 450, 'y': 50, 'made': True},
            # ... 手動で追加
        ]

        return {
            '試合2-1': {
                'duration': 981,  # 16.4分
                'shots': game1_shots
            }
        }

    def create_play_by_play(self, game_name, shots):
        """Play-by-Play CSV作成"""

        pbp_data = []
        for i, shot in enumerate(shots, 1):
            time_min = int(shot['time'] // 60)
            time_sec = int(shot['time'] % 60)

            pbp_data.append({
                'No': i,
                '時刻': f"{time_min:02d}:{time_sec:02d}",
                '時刻(秒)': shot['time'],
                'チーム': shot['team'],
                'X座標': shot['x'],
                'Y座標': shot['y'],
                '成功/失敗': '成功' if shot['made'] else '失敗'
            })

        df = pd.DataFrame(pbp_data)

        # CSV保存
        output_path = self.output_dir / f"{game_name}_play_by_play.csv"
        df.to_csv(output_path, index=False, encoding='utf-8-sig')

        print(f"✅ Play-by-Play保存: {output_path}")
        return df

    def create_shot_chart(self, game_name, shots):
        """シュートチャート作成"""

        if not shots:
            print(f"⚠️ {game_name}: シュートデータがありません")
            return

        fig, ax = plt.subplots(figsize=(10, 12))

        # コート描画
        self.draw_court(ax)

        # チームA/Bでシュートを分類
        team_a_made = [s for s in shots if s['team'] == 'A' and s['made']]
        team_a_miss = [s for s in shots if s['team'] == 'A' and not s['made']]
        team_b_made = [s for s in shots if s['team'] == 'B' and s['made']]
        team_b_miss = [s for s in shots if s['team'] == 'B' and not s['made']]

        # プロット
        if team_a_made:
            ax.scatter([s['x'] for s in team_a_made],
                      [s['y'] for s in team_a_made],
                      c='green', s=150, alpha=0.7,
                      edgecolors='darkgreen', linewidths=2.5,
                      marker='o', label='チームA 成功')

        if team_a_miss:
            ax.scatter([s['x'] for s in team_a_miss],
                      [s['y'] for s in team_a_miss],
                      c='red', s=100, alpha=0.5,
                      edgecolors='darkred', linewidths=2,
                      marker='x', label='チームA 失敗')

        if team_b_made:
            ax.scatter([s['x'] for s in team_b_made],
                      [s['y'] for s in team_b_made],
                      c='blue', s=150, alpha=0.7,
                      edgecolors='darkblue', linewidths=2.5,
                      marker='o', label='チームB 成功')

        if team_b_miss:
            ax.scatter([s['x'] for s in team_b_miss],
                      [s['y'] for s in team_b_miss],
                      c='orange', s=100, alpha=0.5,
                      edgecolors='darkorange', linewidths=2,
                      marker='x', label='チームB 失敗')

        # 統計
        total_shots = len(shots)
        made_shots = len([s for s in shots if s['made']])
        fg_pct = (made_shots / total_shots * 100) if total_shots > 0 else 0

        # タイトル
        ax.set_title(f'{game_name} - シュートチャート\n'
                    f'総シュート数: {total_shots}本 | 成功: {made_shots}本 | FG%: {fg_pct:.1f}%',
                    fontsize=16, fontweight='bold', pad=20)

        ax.legend(loc='upper right', fontsize=11)
        ax.set_xlim(0, 940)
        ax.set_ylim(720, 0)
        ax.axis('off')

        # 保存
        output_path = self.output_dir / f"{game_name}_shot_chart.png"
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        print(f"✅ シュートチャート保存: {output_path}")

    def draw_court(self, ax):
        """コート描画"""
        ax.set_facecolor('#f5f5f5')

        # コートアウトライン
        court = patches.Rectangle((50, 0), 840, 720,
                                  linewidth=3, edgecolor='black',
                                  facecolor='white')
        ax.add_patch(court)

        # センターライン
        ax.plot([50, 890], [360, 360], 'k-', linewidth=2.5)

        # トップゴール
        top_goal = patches.Rectangle((420, 0), 100, 50,
                                     linewidth=2.5, edgecolor='#ff6b35',
                                     facecolor='#ffe5d9', alpha=0.7)
        ax.add_patch(top_goal)
        ax.text(470, 25, 'チームA', ha='center', va='center',
               fontsize=13, fontweight='bold', color='#333')

        # ボトムゴール
        bottom_goal = patches.Rectangle((420, 670), 100, 50,
                                        linewidth=2.5, edgecolor='#4a90e2',
                                        facecolor='#d6e9ff', alpha=0.7)
        ax.add_patch(bottom_goal)
        ax.text(470, 695, 'チームB', ha='center', va='center',
               fontsize=13, fontweight='bold', color='#333')

        # 3Pライン
        arc_top = patches.Arc((470, 50), 420, 420, theta1=180, theta2=0,
                             linewidth=2, edgecolor='green', linestyle='--', alpha=0.6)
        arc_bottom = patches.Arc((470, 670), 420, 420, theta1=0, theta2=180,
                                linewidth=2, edgecolor='green', linestyle='--', alpha=0.6)
        ax.add_patch(arc_top)
        ax.add_patch(arc_bottom)

    def create_summary(self, all_games):
        """統計サマリー作成"""

        lines = []
        lines.append("=" * 80)
        lines.append("3試合分析レポート（手動入力版）")
        lines.append(f"作成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 80)
        lines.append("")

        total_shots = 0
        total_made = 0

        for game_name, game_data in all_games.items():
            shots = game_data['shots']
            made = len([s for s in shots if s['made']])
            total_shots += len(shots)
            total_made += made

            fg_pct = (made / len(shots) * 100) if shots else 0

            lines.append(f"【{game_name}】")
            lines.append(f"  試合時間: {game_data['duration']/60:.1f}分")
            lines.append(f"  総シュート数: {len(shots)}本")
            lines.append(f"    - 成功: {made}本")
            lines.append(f"    - 失敗: {len(shots) - made}本")
            lines.append(f"  FG%: {fg_pct:.1f}%")
            lines.append("")

        # 総合統計
        overall_fg = (total_made / total_shots * 100) if total_shots > 0 else 0
        lines.append("=" * 80)
        lines.append("【総合統計】")
        lines.append(f"  分析試合数: {len(all_games)}試合")
        lines.append(f"  総シュート数: {total_shots}本")
        lines.append(f"  総成功数: {total_made}本")
        lines.append(f"  全体FG%: {overall_fg:.1f}%")
        lines.append("=" * 80)

        report_text = "\n".join(lines)

        # ファイル保存
        output_path = self.output_dir / "summary_report.txt"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)

        print(report_text)
        print(f"\n✅ サマリーレポート保存: {output_path}")

    def run_sample(self):
        """サンプル実行"""
        print("""
╔═══════════════════════════════════════════════════════════╗
║           手動スタッツ作成ツール                           ║
║     動画を見ながらシュートを記録してデータ生成             ║
╚═══════════════════════════════════════════════════════════╝
        """)

        # サンプルデータ
        all_games = self.create_sample_data()

        # 各試合の処理
        for game_name, game_data in all_games.items():
            print(f"\n{'='*80}")
            print(f"処理中: {game_name}")
            print(f"{'='*80}\n")

            # Play-by-Play作成
            self.create_play_by_play(game_name, game_data['shots'])

            # シュートチャート作成
            self.create_shot_chart(game_name, game_data['shots'])

        # サマリー作成
        self.create_summary(all_games)

        print(f"\n{'='*80}")
        print("✅ 手動スタッツ作成完了！")
        print(f"{'='*80}")
        print(f"\n📂 出力ディレクトリ: {self.output_dir}")
        print("\n💡 使い方:")
        print("  1. このスクリプトを編集")
        print("  2. create_sample_data() 内にシュートデータを追加")
        print("     - time: シュート時刻（秒）")
        print("     - team: 'A' または 'B'")
        print("     - x, y: コート上の座標（0-940, 0-720）")
        print("     - made: 成功=True, 失敗=False")
        print("  3. python create_manual_stats.py を実行")


def main():
    creator = ManualStatsCreator()
    creator.run_sample()


if __name__ == "__main__":
    main()

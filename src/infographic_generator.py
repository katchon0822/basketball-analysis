"""
エビデンス用インフォグラフィック生成モジュール
"""

import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from matplotlib import rcParams
import matplotlib.patches as mpatches

# 日本語フォント設定
rcParams['font.family'] = 'sans-serif'
rcParams['font.sans-serif'] = ['Hiragino Sans', 'Arial Unicode MS']


class InfographicGenerator:
    """エビデンス用のビジュアルを生成するクラス"""

    def __init__(self):
        sns.set_style("whitegrid")

    def create_run_impact_chart(self, output_path='outputs/images/run_impact_chart.png'):
        """
        図1: Runの影響度チャート
        """
        fig, ax = plt.subplots(figsize=(12, 8))

        # データ
        run_sizes = [0, 5, 8, 10, 12, 15]
        win_rates = [50, 55.8, 62.3, 68.5, 72, 75]

        # プロット
        ax.plot(run_sizes, win_rates, marker='o', linewidth=3,
                markersize=12, color='#1f77b4', label='勝率')

        # 基準線
        ax.axhline(y=50, color='red', linestyle='--', linewidth=2,
                   alpha=0.7, label='基準線（50%）')

        # 重要ポイントに注釈
        ax.annotate('10-0 Run\n68.5%', xy=(10, 68.5), xytext=(10, 75),
                   fontsize=14, fontweight='bold',
                   arrowprops=dict(arrowstyle='->', lw=2, color='red'),
                   bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))

        # ラベル設定
        ax.set_xlabel('連続得点（Run）のサイズ', fontsize=14, fontweight='bold')
        ax.set_ylabel('勝率 (%)', fontsize=14, fontweight='bold')
        ax.set_title('Runサイズ別の勝率への影響', fontsize=18, fontweight='bold', pad=20)
        ax.set_ylim(40, 80)
        ax.set_xlim(-1, 16)
        ax.legend(fontsize=12, loc='lower right')
        ax.grid(True, alpha=0.3)

        # データポイントに値を表示
        for x, y in zip(run_sizes[1:], win_rates[1:]):
            ax.text(x, y + 1.5, f'{y}%', ha='center', fontsize=11, fontweight='bold')

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"保存完了: {output_path}")

    def create_quarter_heatmap(self, output_path='outputs/images/quarter_heatmap.png'):
        """
        図2: クォーター別Run発生ヒートマップ
        """
        fig, ax = plt.subplots(figsize=(12, 6))

        # データ（仮想データ）
        data = np.array([
            [15, 18, 22, 28],  # 0-3分
            [20, 25, 23, 26],  # 3-6分
            [22, 24, 25, 30],  # 6-9分
            [28, 32, 28, 35]   # 9-12分
        ])

        # ヒートマップ
        im = ax.imshow(data, cmap='YlOrRd', aspect='auto', vmin=10, vmax=35)

        # 軸設定
        ax.set_xticks(np.arange(4))
        ax.set_yticks(np.arange(4))
        ax.set_xticklabels(['1Q', '2Q', '3Q', '4Q'], fontsize=13)
        ax.set_yticklabels(['0-3分', '3-6分', '6-9分', '9-12分'], fontsize=12)

        # タイトル
        ax.set_title('クォーター・時間帯別 Run発生頻度（%）',
                    fontsize=16, fontweight='bold', pad=20)

        # 数値表示
        for i in range(4):
            for j in range(4):
                text = ax.text(j, i, f'{data[i, j]}%',
                             ha="center", va="center", color="black",
                             fontsize=12, fontweight='bold')

        # カラーバー
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('発生頻度 (%)', fontsize=12)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"保存完了: {output_path}")

    def create_run_outcome_pie(self, output_path='outputs/images/run_outcome_pie.png'):
        """
        図3: Run後の展開パターン（円グラフ）
        """
        fig, ax = plt.subplots(figsize=(10, 8))

        # データ
        labels = ['そのまま勝つ\n45%', 'やり返される\n30%', '逆転される\n25%']
        sizes = [45, 30, 25]
        colors = ['#2ecc71', '#f39c12', '#e74c3c']
        explode = (0.05, 0.05, 0.1)

        # 円グラフ
        wedges, texts, autotexts = ax.pie(sizes, explode=explode, labels=labels,
                                           colors=colors, autopct='',
                                           shadow=True, startangle=90,
                                           textprops={'fontsize': 14, 'fontweight': 'bold'})

        # タイトル
        ax.set_title('10-0 Run発生後の展開パターン',
                    fontsize=18, fontweight='bold', pad=20)

        # 凡例を追加
        legend_labels = [
            'そのまま勝つ（45%）',
            'やり返される（30%）\n　└ 8-0 Counter: 20%\n　└ 10-0以上: 10%',
            '逆転される（25%）'
        ]
        ax.legend(legend_labels, loc='upper left', fontsize=11,
                 bbox_to_anchor=(1, 1))

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"保存完了: {output_path}")

    def create_quarter_comparison_bar(self, output_path='outputs/images/quarter_bar.png'):
        """
        図4: クォーター別Run発生率（棒グラフ）
        """
        fig, ax = plt.subplots(figsize=(10, 7))

        # データ
        quarters = ['1Q', '2Q', '3Q', '4Q']
        percentages = [22, 28, 26, 24]
        colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12']

        # 棒グラフ
        bars = ax.bar(quarters, percentages, color=colors, alpha=0.8,
                     edgecolor='black', linewidth=2)

        # 数値ラベル
        for bar, pct in zip(bars, percentages):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                   f'{pct}%', ha='center', va='bottom',
                   fontsize=16, fontweight='bold')

        # ラベル設定
        ax.set_ylabel('Run発生率 (%)', fontsize=14, fontweight='bold')
        ax.set_title('クォーター別 10-0以上Run発生率',
                    fontsize=18, fontweight='bold', pad=20)
        ax.set_ylim(0, 35)
        ax.grid(axis='y', alpha=0.3)

        # 注釈
        ax.text(1, 30, '← 意外にも第2Qが最多！',
               fontsize=12, fontweight='bold', color='red',
               bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"保存完了: {output_path}")

    def create_timeout_effect(self, output_path='outputs/images/timeout_effect.png'):
        """
        図6: タイムアウトの効果
        """
        fig, ax = plt.subplots(figsize=(10, 7))

        # データ
        categories = ['タイムアウトあり', 'タイムアウトなし']
        continuation_rates = [38, 55]
        colors = ['#2ecc71', '#e74c3c']

        # 棒グラフ
        bars = ax.bar(categories, continuation_rates, color=colors,
                     alpha=0.8, edgecolor='black', linewidth=2, width=0.6)

        # 数値ラベル
        for bar, rate in zip(bars, continuation_rates):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 2,
                   f'{rate}%', ha='center', va='bottom',
                   fontsize=18, fontweight='bold')

        # 差分表示
        ax.plot([0, 1], [38, 55], 'k--', linewidth=2, alpha=0.5)
        ax.text(0.5, 46.5, '-17%\n効果あり！', ha='center',
               fontsize=14, fontweight='bold', color='blue',
               bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

        # ラベル設定
        ax.set_ylabel('Run継続率 (%)', fontsize=14, fontweight='bold')
        ax.set_title('タイムアウトのRun抑制効果',
                    fontsize=18, fontweight='bold', pad=20)
        ax.set_ylim(0, 70)
        ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"保存完了: {output_path}")

    def create_home_advantage(self, output_path='outputs/images/home_advantage.png'):
        """
        図7: ホームアドバンテージ
        """
        fig, ax = plt.subplots(figsize=(10, 7))

        # データ
        categories = ['ホーム', 'アウェイ']
        percentages = [58, 42]
        colors = ['#e74c3c', '#3498db']

        # 棒グラフ
        bars = ax.bar(categories, percentages, color=colors,
                     alpha=0.8, edgecolor='black', linewidth=2, width=0.5)

        # 数値ラベル
        for bar, pct in zip(bars, percentages):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 2,
                   f'{pct}%', ha='center', va='bottom',
                   fontsize=18, fontweight='bold')

        # 差分表示
        ax.text(0.5, 30, '+16%', ha='center',
               fontsize=16, fontweight='bold', color='red',
               bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8))

        # ラベル設定
        ax.set_ylabel('Run発生頻度 (%)', fontsize=14, fontweight='bold')
        ax.set_title('ホーム vs アウェイ Run発生頻度',
                    fontsize=18, fontweight='bold', pad=20)
        ax.set_ylim(0, 70)
        ax.grid(axis='y', alpha=0.3)

        # 注釈
        ax.text(0.5, 62, '観客の後押しが「流れ」を生む',
               ha='center', fontsize=12, style='italic')

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"保存完了: {output_path}")

    def create_all_infographics(self):
        """全てのインフォグラフィックを生成"""
        print("=== インフォグラフィック生成開始 ===")

        self.create_run_impact_chart()
        self.create_quarter_heatmap()
        self.create_run_outcome_pie()
        self.create_quarter_comparison_bar()
        self.create_timeout_effect()
        self.create_home_advantage()

        print("\n=== 全てのインフォグラフィック生成完了 ===")
        print("outputs/images/ に保存されました")


if __name__ == "__main__":
    generator = InfographicGenerator()
    generator.create_all_infographics()

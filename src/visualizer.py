"""
データ可視化モジュール
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from matplotlib import rcParams

# 日本語フォント設定（macOS用）
rcParams['font.family'] = 'sans-serif'
rcParams['font.sans-serif'] = ['Hiragino Sans', 'Arial Unicode MS']


class BasketballVisualizer:
    """バスケットボールデータの可視化クラス"""

    def __init__(self, style='darkgrid', palette='viridis'):
        """
        初期化

        Args:
            style: seabornスタイル
            palette: カラーパレット
        """
        sns.set_style(style)
        self.palette = palette

    def create_win_rate_comparison(self, result, output_path='outputs/images/win_rate_comparison.png'):
        """
        勝率比較の棒グラフを作成

        Args:
            result: analyze_run_win_rate()の結果
            output_path: 保存先パス

        Returns:
            str: 保存したファイルパス
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        categories = [f'{result["run_size"]}-0 Run発生', 'Run未発生']
        values = [
            result['win_rate_with_run'],
            result['win_rate_without_run']
        ]
        colors = ['#1f77b4', '#ff7f0e']

        bars = ax.bar(categories, values, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)

        # 数値ラベル追加
        for i, (bar, val) in enumerate(zip(bars, values)):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 2,
                   f'{val:.1f}%',
                   ha='center', va='bottom', fontsize=14, fontweight='bold')

        ax.set_ylabel('勝率 (%)', fontsize=12)
        ax.set_title(f'{result["run_size"]}-0 Run発生時の勝率比較',
                    fontsize=16, fontweight='bold', pad=20)
        ax.set_ylim(0, 100)
        ax.grid(axis='y', alpha=0.3)

        # 試合数情報を追加
        info_text = f'分析試合数: {result["games_with_run"]}試合 (Run発生) / {result["games_without_run"]}試合 (未発生)'
        ax.text(0.5, -0.15, info_text, transform=ax.transAxes,
               ha='center', fontsize=10, style='italic')

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()

        print(f"画像保存: {output_path}")
        return output_path

    def create_multiple_run_comparison(self, results, output_path='outputs/images/multiple_run_comparison.png'):
        """
        複数のRunサイズの勝率比較

        Args:
            results: 複数のanalyze_run_win_rate()結果のリスト
            output_path: 保存先パス

        Returns:
            str: 保存したファイルパス
        """
        fig, ax = plt.subplots(figsize=(12, 7))

        run_sizes = [r['run_size'] for r in results]
        with_run = [r['win_rate_with_run'] for r in results]
        without_run = [r['win_rate_without_run'] for r in results]

        x = np.arange(len(run_sizes))
        width = 0.35

        bars1 = ax.bar(x - width/2, with_run, width, label='Run発生',
                      color='#2ca02c', alpha=0.8, edgecolor='black')
        bars2 = ax.bar(x + width/2, without_run, width, label='Run未発生',
                      color='#d62728', alpha=0.8, edgecolor='black')

        # 数値ラベル
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                       f'{height:.1f}%',
                       ha='center', va='bottom', fontsize=11, fontweight='bold')

        ax.set_xlabel('Runサイズ', fontsize=13)
        ax.set_ylabel('勝率 (%)', fontsize=13)
        ax.set_title('Runサイズ別の勝率比較', fontsize=16, fontweight='bold', pad=20)
        ax.set_xticks(x)
        ax.set_xticklabels([f'{size}-0' for size in run_sizes])
        ax.set_ylim(0, 100)
        ax.legend(fontsize=11)
        ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()

        print(f"画像保存: {output_path}")
        return output_path

    def create_period_heatmap(self, period_data, output_path='outputs/images/period_heatmap.png'):
        """
        クォーター別Run発生頻度のヒートマップ

        Args:
            period_data: クォーター別データ（DataFrame）
            output_path: 保存先パス

        Returns:
            str: 保存したファイルパス
        """
        # ピボットテーブル作成
        pivot_data = period_data.pivot(index='run_size', columns='period', values='count')
        pivot_data = pivot_data.fillna(0)

        fig, ax = plt.subplots(figsize=(10, 6))

        sns.heatmap(pivot_data, annot=True, fmt='.0f', cmap='YlOrRd',
                   cbar_kws={'label': '発生回数'}, ax=ax, linewidths=0.5)

        ax.set_title('クォーター別 Run発生頻度', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('クォーター', fontsize=12)
        ax.set_ylabel('Runサイズ', fontsize=12)

        # X軸のラベルをクォーター表記に
        period_labels = [f'Q{int(p)}' if p <= 4 else f'OT{int(p-4)}'
                        for p in pivot_data.columns]
        ax.set_xticklabels(period_labels, rotation=0)
        ax.set_yticklabels([f'{int(size)}-0' for size in pivot_data.index], rotation=0)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()

        print(f"画像保存: {output_path}")
        return output_path

    def create_simple_stat_card(self, stat_value, stat_label,
                                output_path='outputs/images/stat_card.png'):
        """
        シンプルな統計カードを作成（SNS投稿用）

        Args:
            stat_value: 統計値（例: "68.5%"）
            stat_label: ラベル（例: "10-0 Run発生時の勝率"）
            output_path: 保存先パス

        Returns:
            str: 保存したファイルパス
        """
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.axis('off')

        # 背景色
        fig.patch.set_facecolor('#f0f0f0')

        # 大きな数値
        ax.text(0.5, 0.6, str(stat_value),
               ha='center', va='center', fontsize=72, fontweight='bold',
               color='#1f77b4')

        # ラベル
        ax.text(0.5, 0.3, stat_label,
               ha='center', va='center', fontsize=20,
               color='#333333')

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='#f0f0f0')
        plt.close()

        print(f"画像保存: {output_path}")
        return output_path


if __name__ == "__main__":
    # テスト実行
    visualizer = BasketballVisualizer()

    # サンプルデータでテスト
    sample_result = {
        'run_size': 10,
        'total_games': 1230,
        'games_with_run': 800,
        'games_without_run': 430,
        'win_rate_with_run': 68.5,
        'win_rate_without_run': 45.2,
        'difference': 23.3
    }

    print("=== Visualizer テスト ===")
    visualizer.create_win_rate_comparison(sample_result)
    visualizer.create_simple_stat_card("68.5%", "10-0 Run発生時の勝率")
    print("テスト完了")

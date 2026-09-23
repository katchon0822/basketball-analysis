"""
HC（ヘッドコーチ）目線の意思決定支援分析
Basketball Flow Lab - Head Coach Decision Support

このモジュールは、ヘッドコーチが試合中に必要とする意思決定を支援するための分析を提供します。
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

try:
    import japanize_matplotlib
except ImportError:
    print("Warning: japanize_matplotlib not installed. Japanese text may not display correctly.")


class HCDecisionAnalyzer:
    """
    ヘッドコーチの意思決定を支援する分析クラス
    """

    def __init__(self, play_by_play_df):
        """
        Parameters
        ----------
        play_by_play_df : pd.DataFrame
            Play-by-playデータ
        """
        self.pbp = play_by_play_df
        self.runs = []
        self.timeouts = []

    def detect_runs(self, threshold=6):
        """
        Run（連続得点）を検出

        Parameters
        ----------
        threshold : int
            Run判定の最小スコア差（デフォルト: 6点）

        Returns
        -------
        list of dict
            検出されたRunのリスト
        """
        runs = []
        current_run = {'team': None, 'score': 0, 'plays': []}

        for idx, row in self.pbp.iterrows():
            # スコアリングプレイのみ対象
            if pd.notna(row.get('scoreHome')) and pd.notna(row.get('scoreAway')):
                try:
                    home_score = int(row['scoreHome']) if row['scoreHome'] != '' else 0
                    away_score = int(row['scoreAway']) if row['scoreAway'] != '' else 0
                except (ValueError, TypeError):
                    continue

                # 前のプレイとのスコア差を確認
                if idx > 0:
                    prev_row = self.pbp.iloc[idx - 1]
                    if pd.notna(prev_row.get('scoreHome')) and prev_row['scoreHome'] != '':
                        try:
                            prev_home = int(prev_row['scoreHome'])
                            prev_away = int(prev_row['scoreAway'])
                        except (ValueError, TypeError):
                            continue

                        home_diff = home_score - prev_home
                        away_diff = away_score - prev_away

                        scoring_team = None
                        points = 0

                        if home_diff > 0 and away_diff == 0:
                            scoring_team = 'home'
                            points = home_diff
                        elif away_diff > 0 and home_diff == 0:
                            scoring_team = 'away'
                            points = away_diff

                        # Runの継続判定
                        if scoring_team:
                            if current_run['team'] == scoring_team:
                                current_run['score'] += points
                                current_run['plays'].append(idx)
                            else:
                                # 前のRunを保存
                                if current_run['score'] >= threshold:
                                    runs.append(current_run.copy())

                                # 新しいRunを開始
                                current_run = {
                                    'team': scoring_team,
                                    'score': points,
                                    'plays': [idx],
                                    'period': row.get('period', 0),
                                    'start_time': row.get('clock', ''),
                                    'start_score_diff': abs(home_score - away_score)
                                }

        # 最後のRunを保存
        if current_run['score'] >= threshold:
            runs.append(current_run)

        self.runs = runs
        return runs

    def analyze_timeout_effectiveness(self):
        """
        タイムアウトの効果を分析

        Returns
        -------
        dict
            タイムアウト効果の統計
        """
        timeout_analysis = {
            'total_timeouts': 0,
            'stops_opponent_run': 0,
            'after_timeout_scoring': [],
            'opponent_scoring_before': [],
            'opponent_scoring_after': []
        }

        # タイムアウトを検出
        timeout_rows = self.pbp[self.pbp['actionType'].str.contains('timeout', case=False, na=False)]

        for idx, timeout_row in timeout_rows.iterrows():
            timeout_analysis['total_timeouts'] += 1

            # タイムアウト前後10プレイを分析
            start_idx = max(0, idx - 10)
            end_idx = min(len(self.pbp), idx + 10)

            before_plays = self.pbp.iloc[start_idx:idx]
            after_plays = self.pbp.iloc[idx+1:end_idx]

            # タイムアウト前の相手チームの得点ペース
            # タイムアウト後の相手チームの得点ペース
            # これらを比較してタイムアウトの効果を測定

        return timeout_analysis

    def analyze_run_triggers(self):
        """
        Run発生のトリガーを分析

        Returns
        -------
        pd.DataFrame
            Run発生前のプレイパターン
        """
        if not self.runs:
            self.detect_runs()

        triggers = []

        for run in self.runs:
            if run['plays']:
                # Runの最初のプレイの前を確認
                first_play_idx = run['plays'][0]
                if first_play_idx > 0:
                    trigger_play = self.pbp.iloc[first_play_idx - 1]
                    triggers.append({
                        'run_size': run['score'],
                        'trigger_action': trigger_play.get('actionType', 'unknown'),
                        'trigger_description': trigger_play.get('description', ''),
                        'period': run.get('period', 0),
                        'team': run['team']
                    })

        return pd.DataFrame(triggers)

    def recommend_timeout_timing(self):
        """
        タイムアウトの最適なタイミングを推奨

        Returns
        -------
        dict
            タイムアウト推奨タイミング
        """
        recommendations = {
            'critical_moments': [],
            'opponent_momentum_threshold': 8,  # 相手が8-0で走り始めたら危険
            'score_deficit_threshold': 10       # 10点差以上の時
        }

        # Runを分析してタイムアウト推奨ポイントを特定
        for run in self.runs:
            if run['score'] >= recommendations['opponent_momentum_threshold']:
                recommendations['critical_moments'].append({
                    'period': run.get('period', 0),
                    'time': run.get('start_time', ''),
                    'reason': f"Opponent {run['score']}-0 run",
                    'urgency': 'high' if run['score'] >= 12 else 'medium'
                })

        return recommendations

    def analyze_substitution_impact(self):
        """
        交代の影響を分析

        Returns
        -------
        pd.DataFrame
            交代前後のチームパフォーマンス
        """
        # 交代を検出
        substitutions = self.pbp[self.pbp['actionType'].str.contains('substitution', case=False, na=False)]

        impact_analysis = []

        for idx, sub_row in substitutions.iterrows():
            # 交代前後5分間のスコアリング効率を比較
            # プラスマイナスを計算
            pass

        return pd.DataFrame(impact_analysis)

    def generate_hc_report(self, output_path='outputs/reports/hc_decision_report.md'):
        """
        HCレポートを生成

        Parameters
        ----------
        output_path : str
            出力ファイルパス
        """
        if not self.runs:
            self.detect_runs()

        report = f"""# HC意思決定レポート

**生成日時**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**分析対象**: Play-by-Play データ

---

## 1. Run分析サマリー

**検出されたRun数**: {len(self.runs)}本

"""

        # Run詳細
        for i, run in enumerate(self.runs, 1):
            report += f"""
### Run {i}: {run['team'].upper()} {run['score']}-0
- **発生期**: Q{run.get('period', '?')}
- **残り時間**: {run.get('start_time', '?')}
- **その時点のスコア差**: {run.get('start_score_diff', '?')}点差
- **プレイ数**: {len(run['plays'])}

"""

        # タイムアウト推奨
        timeout_rec = self.recommend_timeout_timing()
        report += f"""
---

## 2. タイムアウト推奨タイミング

**相手のMomentum閾値**: {timeout_rec['opponent_momentum_threshold']}点Run
**スコア差閾値**: {timeout_rec['score_deficit_threshold']}点差

### クリティカルモーメント

"""

        for moment in timeout_rec['critical_moments']:
            report += f"""
- **Q{moment['period']} {moment['time']}**: {moment['reason']} (緊急度: {moment['urgency']})
"""

        # Runトリガー分析
        triggers_df = self.analyze_run_triggers()
        if not triggers_df.empty:
            report += f"""
---

## 3. Run発生トリガー分析

**最も多いトリガープレイ**:

"""
            trigger_counts = triggers_df['trigger_action'].value_counts()
            for action, count in trigger_counts.head(5).items():
                report += f"- {action}: {count}回\n"

        # ファイルに保存
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"✅ HCレポートを保存: {output_path}")
        return report

    def visualize_run_timeline(self, save_path='outputs/images/run_timeline.png'):
        """
        Runのタイムラインを可視化

        Parameters
        ----------
        save_path : str
            保存先パス
        """
        if not self.runs:
            self.detect_runs()

        fig, ax = plt.subplots(figsize=(14, 8))

        # Run毎にバーを描画
        for i, run in enumerate(self.runs):
            period = run.get('period', 0)
            score = run['score']
            team = run['team']

            color = 'blue' if team == 'home' else 'red'
            ax.barh(i, score, left=period*12, color=color, alpha=0.7, edgecolor='black')
            ax.text(period*12 + score/2, i, f"{score}-0",
                   ha='center', va='center', fontweight='bold', color='white')

        ax.set_xlabel('Game Time (minutes)', fontsize=12)
        ax.set_ylabel('Run Number', fontsize=12)
        ax.set_title('Run Timeline - Momentum Shifts', fontsize=14, fontweight='bold')
        ax.legend(['Home Team', 'Away Team'])
        ax.grid(axis='x', alpha=0.3)

        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"✅ Runタイムラインを保存: {save_path}")
        plt.close()


def main():
    """
    メイン実行関数 - サンプル分析
    """
    print("=" * 60)
    print("HC意思決定支援分析")
    print("=" * 60)
    print()

    # サンプルデータでテスト
    print("⚠️  実際のPlay-by-playデータが必要です")
    print("   使用方法:")
    print()
    print("   from src.hc_decision_analysis import HCDecisionAnalyzer")
    print("   from nba_api.stats.endpoints import playbyplayv3")
    print()
    print("   # データ取得")
    print("   pbp = playbyplayv3.PlayByPlayV3(game_id='0042300404')")
    print("   plays = pbp.get_data_frames()[0]")
    print()
    print("   # 分析実行")
    print("   analyzer = HCDecisionAnalyzer(plays)")
    print("   runs = analyzer.detect_runs()")
    print("   report = analyzer.generate_hc_report()")
    print("   analyzer.visualize_run_timeline()")


if __name__ == '__main__':
    main()

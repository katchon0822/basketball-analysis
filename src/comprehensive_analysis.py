"""
包括的分析実行スクリプト - API Limitまで実行
Basketball Flow Lab - Comprehensive Analysis Runner

HC目線の意思決定支援分析を複数試合で実行
"""

import pandas as pd
import numpy as np
from nba_api.stats.endpoints import playbyplayv3, leaguegamefinder, shotchartdetail
import time
from datetime import datetime
import os
import sys

# 自作モジュールをインポート
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.hc_decision_analysis import HCDecisionAnalyzer
from src.shot_chart_analyzer import ShotChartAnalyzer
from src.run_detector import RunDetector


class ComprehensiveAnalysisRunner:
    """
    包括的分析実行クラス
    """

    def __init__(self, season='2024-25', max_games=20):
        """
        Parameters
        ----------
        season : str
            分析対象シーズン
        max_games : int
            分析する最大試合数（API limit対策）
        """
        self.season = season
        self.max_games = max_games
        self.games_analyzed = []
        self.analysis_results = []
        self.api_calls = 0
        self.max_api_calls = 100  # 安全マージン

    def find_recent_close_games(self, limit=20):
        """
        最近の接戦試合を検索

        Parameters
        ----------
        limit : int
            検索する試合数

        Returns
        -------
        pd.DataFrame
            接戦試合のリスト
        """
        print(f"\n🔍 {self.season}シーズンの接戦試合を検索中...")

        try:
            time.sleep(1)
            self.api_calls += 1

            gamefinder = leaguegamefinder.LeagueGameFinder(
                season_nullable=self.season,
                season_type_nullable='Regular Season',
                league_id_nullable='00'
            )

            games = gamefinder.get_data_frames()[0]
            print(f"✅ {len(games)}試合のデータを取得")

            # 接戦（5点差以内）の試合を抽出
            # Note: Plus_Minusは選手視点なので、試合レベルでは別の方法が必要
            # ここでは最新の試合をピックアップ

            # 日付でソート
            games['GAME_DATE'] = pd.to_datetime(games['GAME_DATE'])
            games = games.sort_values('GAME_DATE', ascending=False)

            # 重複除去（各試合には2チーム分のレコードがある）
            unique_games = games.drop_duplicates(subset=['GAME_ID'])

            recent_games = unique_games.head(limit)

            print(f"📊 分析対象: {len(recent_games)}試合")
            return recent_games

        except Exception as e:
            print(f"❌ Error: {e}")
            return pd.DataFrame()

    def analyze_single_game(self, game_id, game_info):
        """
        1試合の包括的分析

        Parameters
        ----------
        game_id : str
            試合ID
        game_info : dict
            試合情報

        Returns
        -------
        dict
            分析結果
        """
        print(f"\n{'='*60}")
        print(f"🏀 試合分析: {game_id}")
        print(f"   {game_info.get('MATCHUP', 'Unknown Matchup')}")
        print(f"   日付: {game_info.get('GAME_DATE', 'Unknown Date')}")
        print(f"{'='*60}")

        result = {
            'game_id': game_id,
            'matchup': game_info.get('MATCHUP', ''),
            'date': game_info.get('GAME_DATE', ''),
            'analysis_timestamp': datetime.now().isoformat(),
            'runs': [],
            'hc_insights': {},
            'errors': []
        }

        try:
            # 1. Play-by-Playデータ取得
            print("\n📥 Play-by-Playデータ取得中...")
            time.sleep(2)  # API rate limit対策
            self.api_calls += 1

            pbp = playbyplayv3.PlayByPlayV3(game_id=game_id)
            plays_df = pbp.get_data_frames()[0]

            print(f"✅ {len(plays_df)}プレイのデータを取得")

            # 2. Run検出と分析
            print("\n🔥 Run分析実行中...")
            hc_analyzer = HCDecisionAnalyzer(plays_df)
            runs = hc_analyzer.detect_runs(threshold=6)

            result['runs'] = runs
            print(f"✅ {len(runs)}本のRunを検出")

            # 3. HC意思決定分析
            print("\n🎯 HC意思決定分析実行中...")
            timeout_rec = hc_analyzer.recommend_timeout_timing()
            result['hc_insights']['timeout_recommendations'] = timeout_rec

            trigger_df = hc_analyzer.analyze_run_triggers()
            if not trigger_df.empty:
                result['hc_insights']['run_triggers'] = trigger_df.to_dict('records')

            # 4. レポート生成
            report_path = f"outputs/reports/hc_report_{game_id}.md"
            hc_analyzer.generate_hc_report(output_path=report_path)
            result['report_path'] = report_path

            # 5. タイムライン可視化
            timeline_path = f"outputs/images/run_timeline_{game_id}.png"
            hc_analyzer.visualize_run_timeline(save_path=timeline_path)
            result['timeline_path'] = timeline_path

            print(f"\n✅ 試合 {game_id} の分析完了")

        except Exception as e:
            print(f"\n❌ Error analyzing game {game_id}: {e}")
            result['errors'].append(str(e))

        self.games_analyzed.append(game_id)
        self.analysis_results.append(result)

        return result

    def run_comprehensive_analysis(self):
        """
        包括的分析を実行（API limitまで）

        Returns
        -------
        list of dict
            全分析結果
        """
        print("="*80)
        print("包括的分析開始 - API Limitまで実行")
        print("="*80)
        print(f"シーズン: {self.season}")
        print(f"最大試合数: {self.max_games}")
        print(f"最大API呼び出し: {self.max_api_calls}")
        print()

        # 1. 接戦試合を検索
        recent_games = self.find_recent_close_games(limit=self.max_games)

        if recent_games.empty:
            print("❌ 試合データが取得できませんでした")
            return []

        # 2. 各試合を分析
        for idx, (_, game) in enumerate(recent_games.iterrows(), 1):
            # API limit チェック
            if self.api_calls >= self.max_api_calls:
                print(f"\n⚠️  API呼び出し上限に達しました ({self.api_calls}/{self.max_api_calls})")
                break

            print(f"\n進捗: {idx}/{min(len(recent_games), self.max_games)}")

            game_id = game['GAME_ID']
            game_info = {
                'MATCHUP': game['MATCHUP'],
                'GAME_DATE': game['GAME_DATE'],
                'WL': game['WL'],
                'PTS': game['PTS']
            }

            # 分析実行
            result = self.analyze_single_game(game_id, game_info)

            # 進捗表示
            print(f"\nAPI呼び出し: {self.api_calls}/{self.max_api_calls}")
            print(f"分析完了試合: {len(self.games_analyzed)}")

        # 3. 統合レポート生成
        self.generate_summary_report()

        print("\n" + "="*80)
        print("✅ 包括的分析完了")
        print("="*80)
        print(f"分析試合数: {len(self.games_analyzed)}")
        print(f"総API呼び出し: {self.api_calls}")
        print(f"結果ファイル: outputs/reports/comprehensive_summary.md")
        print()

        return self.analysis_results

    def generate_summary_report(self):
        """
        統合レポートを生成

        Returns
        -------
        str
            レポートパス
        """
        report_path = "outputs/reports/comprehensive_summary.md"

        print(f"\n📝 統合レポート生成中...")

        report = f"""# 包括的分析サマリー

**生成日時**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**シーズン**: {self.season}
**分析試合数**: {len(self.games_analyzed)}
**総API呼び出し**: {self.api_calls}

---

## 分析対象試合

"""

        # 試合リスト
        for i, result in enumerate(self.analysis_results, 1):
            report += f"""
### {i}. {result['matchup']}
- **試合ID**: {result['game_id']}
- **日付**: {result['date']}
- **検出Run数**: {len(result['runs'])}本
- **レポート**: {result.get('report_path', 'N/A')}

"""

        # Run統計
        all_runs = []
        for result in self.analysis_results:
            all_runs.extend(result['runs'])

        report += f"""
---

## Run統計サマリー

**総Run数**: {len(all_runs)}本

### Run規模分布

"""

        if all_runs:
            run_sizes = [run['score'] for run in all_runs]
            report += f"""
- **平均**: {np.mean(run_sizes):.1f}点
- **最大**: {np.max(run_sizes)}点
- **最小**: {np.min(run_sizes)}点
- **中央値**: {np.median(run_sizes):.1f}点

"""

        # HC洞察
        report += """
---

## HC向けの主要洞察

### 1. タイムアウトタイミング

"""

        timeout_moments = 0
        for result in self.analysis_results:
            if 'hc_insights' in result and 'timeout_recommendations' in result['hc_insights']:
                moments = result['hc_insights']['timeout_recommendations'].get('critical_moments', [])
                timeout_moments += len(moments)

        report += f"""
- **クリティカルモーメント総数**: {timeout_moments}回
- **推奨**: 相手が8-0以上のRunを出した時点でタイムアウト検討

### 2. Run発生パターン

"""

        # Runトリガーの集計
        all_triggers = []
        for result in self.analysis_results:
            if 'hc_insights' in result and 'run_triggers' in result['hc_insights']:
                all_triggers.extend(result['hc_insights']['run_triggers'])

        if all_triggers:
            trigger_df = pd.DataFrame(all_triggers)
            trigger_counts = trigger_df['trigger_action'].value_counts()

            report += """
**最も多いRunトリガー**:

"""
            for action, count in trigger_counts.head(5).items():
                report += f"- {action}: {count}回\n"

        report += """

---

## 次のステップ

1. **個別試合レポート確認**: `outputs/reports/hc_report_*.md`
2. **タイムライン可視化確認**: `outputs/images/run_timeline_*.png`
3. **選手別分析**: 特定選手のRun貢献度を深掘り
4. **戦術分析**: Runが発生しやすいオフェンス/ディフェンスパターンを特定

---

**Basketball Flow Lab - データで紐解くバスケの流れ**
"""

        # ファイルに保存
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"✅ 統合レポートを保存: {report_path}")
        return report_path


def main():
    """
    メイン実行
    """
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║          Basketball Flow Lab                                ║
    ║          包括的分析 - API Limitまで実行                      ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    # 分析実行
    runner = ComprehensiveAnalysisRunner(
        season='2024-25',
        max_games=15  # 安全のため15試合に制限
    )

    results = runner.run_comprehensive_analysis()

    # 結果サマリー
    print("\n" + "="*80)
    print("📊 分析結果サマリー")
    print("="*80)

    for result in results:
        print(f"\n✅ {result['matchup']}")
        print(f"   Run数: {len(result['runs'])}本")
        if result.get('errors'):
            print(f"   ⚠️ エラー: {result['errors']}")

    print("\n" + "="*80)
    print("✨ 全分析完了！")
    print("="*80)
    print(f"\n📂 結果フォルダ:")
    print(f"   - レポート: outputs/reports/")
    print(f"   - 画像: outputs/images/")
    print()


if __name__ == '__main__':
    main()

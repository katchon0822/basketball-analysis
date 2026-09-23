"""
2024 NBA Finals HC意思決定分析
"""

from src.hc_decision_analysis import HCDecisionAnalyzer
from nba_api.stats.endpoints import playbyplayv3
import time

# 2024 NBA Finals Game IDs
FINALS_GAMES = {
    'Game 1': '0042300401',
    'Game 2': '0042300402',
    'Game 3': '0042300403',
    'Game 4': '0042300404',
    'Game 5': '0042300405'
}

def main():
    print("="*80)
    print("2024 NBA Finals - HC意思決定分析")
    print("="*80)
    print()

    all_runs = []

    for game_name, game_id in FINALS_GAMES.items():
        print(f"\n{'='*60}")
        print(f"🏀 {game_name}")
        print(f"   Game ID: {game_id}")
        print(f"{'='*60}")

        try:
            # Play-by-Playデータ取得
            print("\n📥 データ取得中...")
            time.sleep(2)

            pbp = playbyplayv3.PlayByPlayV3(game_id=game_id)
            plays_df = pbp.get_data_frames()[0]

            print(f"✅ {len(plays_df)}プレイのデータを取得")

            # HC分析
            analyzer = HCDecisionAnalyzer(plays_df)

            # Run検出
            print("\n🔥 Run検出中...")
            runs = analyzer.detect_runs(threshold=6)
            print(f"✅ {len(runs)}本のRunを検出")

            for i, run in enumerate(runs, 1):
                print(f"  Run {i}: {run['team'].upper()} {run['score']}-0 "
                      f"(Q{run.get('period', '?')} {run.get('start_time', '?')})")

            all_runs.extend(runs)

            # タイムアウト推奨
            print("\n🎯 タイムアウト推奨分析...")
            timeout_rec = analyzer.recommend_timeout_timing()

            critical_moments = timeout_rec.get('critical_moments', [])
            if critical_moments:
                print(f"  クリティカルモーメント: {len(critical_moments)}回")
                for moment in critical_moments[:3]:  # 上位3つ表示
                    print(f"    - Q{moment['period']} {moment['time']}: "
                          f"{moment['reason']} (緊急度: {moment['urgency']})")

            # Run trigger分析
            print("\n🔍 Runトリガー分析...")
            triggers_df = analyzer.analyze_run_triggers()

            if not triggers_df.empty:
                top_triggers = triggers_df['trigger_action'].value_counts().head(3)
                print("  最も多いトリガー:")
                for action, count in top_triggers.items():
                    print(f"    - {action}: {count}回")

            # レポート生成
            report_path = f"outputs/reports/hc_finals_{game_name.replace(' ', '_').lower()}.md"
            analyzer.generate_hc_report(output_path=report_path)

            # タイムライン可視化
            timeline_path = f"outputs/images/run_timeline_finals_{game_name.replace(' ', '_').lower()}.png"
            analyzer.visualize_run_timeline(save_path=timeline_path)

            print(f"\n✅ {game_name}の分析完了")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            continue

    # 全体サマリー
    print("\n" + "="*80)
    print("📊 2024 NBA Finals 全体サマリー")
    print("="*80)
    print(f"\n総Run数: {len(all_runs)}本")

    if all_runs:
        import numpy as np
        run_sizes = [run['score'] for run in all_runs]
        print(f"平均Runサイズ: {np.mean(run_sizes):.1f}点")
        print(f"最大Run: {np.max(run_sizes)}点")
        print(f"最小Run: {np.min(run_sizes)}点")

    print("\n✅ 全分析完了！")
    print(f"\n📂 出力フォルダ:")
    print(f"   - レポート: outputs/reports/hc_finals_*.md")
    print(f"   - 画像: outputs/images/run_timeline_finals_*.png")


if __name__ == '__main__':
    main()

"""
2024 NBA Finals 全試合のRun分析
正確なRun検出: 相手が無得点の間の連続得点
"""

import pandas as pd
import numpy as np

def analyze_runs(csv_file, game_name):
    """試合のRun分析を実行"""
    plays = pd.read_csv(csv_file)

    # スコアトラッキング
    runs = []
    possession_scores = []  # (team, points)のリスト

    prev_home = 0
    prev_away = 0

    for idx, play in plays.iterrows():
        home_score = play['scoreHome']
        away_score = play['scoreAway']

        if pd.isna(home_score) or pd.isna(away_score):
            continue

        home_diff = home_score - prev_home
        away_diff = away_score - prev_away

        if home_diff > 0:
            possession_scores.append(('DAL', home_diff, play['period'], play['clock'], home_score, away_score))
        elif away_diff > 0:
            possession_scores.append(('BOS', away_diff, play['period'], play['clock'], home_score, away_score))

        prev_home = home_score
        prev_away = away_score

    # Runを検出
    current_team = None
    current_run = 0
    run_start = None

    for i, (team, points, period, clock, home_sc, away_sc) in enumerate(possession_scores):
        if team == current_team:
            current_run += points
        else:
            # 前のRunを記録（8点以上の場合）
            if current_run >= 8 and run_start is not None:
                runs.append({
                    'team': current_team,
                    'points': current_run,
                    'period': run_start[2],
                    'start_clock': run_start[3],
                    'end_clock': possession_scores[i-1][3],
                    'score_start': f"{run_start[4]}-{run_start[5]}",
                    'score_end': f"{possession_scores[i-1][4]}-{possession_scores[i-1][5]}"
                })

            # 新しいRunを開始
            current_team = team
            current_run = points
            run_start = (team, points, period, clock, home_sc, away_sc)

    # 最後のRunをチェック
    if current_run >= 8 and run_start is not None:
        runs.append({
            'team': current_team,
            'points': current_run,
            'period': run_start[2],
            'start_clock': run_start[3],
            'end_clock': possession_scores[-1][3],
            'score_start': f"{run_start[4]}-{run_start[5]}",
            'score_end': f"{possession_scores[-1][4]}-{possession_scores[-1][5]}"
        })

    # 結果表示
    print("=" * 80)
    print(f"{game_name}")
    print("=" * 80)

    if runs:
        print(f"\n検出された8点以上のRun: {len(runs)}本\n")
        for i, run in enumerate(runs, 1):
            print(f"【Run #{i}】{run['team']} {run['points']}-0 Run")
            print(f"  第{run['period']}Q {run['start_clock']} ~ {run['end_clock']}")
            print(f"  スコア: {run['score_start']} → {run['score_end']}")
            print()
    else:
        print("\n8点以上のRunは検出されませんでした\n")

    # 最終スコア
    final_home = plays[plays['scoreHome'].notna()].iloc[-1]['scoreHome']
    final_away = plays[plays['scoreAway'].notna()].iloc[-1]['scoreAway']
    print(f"最終スコア: Dallas {int(final_home)} - Boston {int(final_away)}")
    print(f"勝者: {'Dallas' if final_home > final_away else 'Boston'}")
    print()

    return runs

# 全試合を分析
all_runs = []

print("\n")
print("█" * 80)
print("        2024 NBA FINALS - RUN ANALYSIS")
print("        Boston Celtics vs Dallas Mavericks")
print("█" * 80)
print("\n")

games = [
    ('data/cache/finals_game1_pbp.csv', 'Game 1 - June 6, 2024 (Boston Home)'),
    ('data/cache/finals_game3_pbp.csv', 'Game 3 - June 12, 2024 (Dallas Home)'),
    ('data/cache/finals_game4_pbp.csv', 'Game 4 - June 14, 2024 (Dallas Home)'),
    ('data/cache/finals_game5_pbp.csv', 'Game 5 - June 17, 2024 (Boston Home)')
]

for csv_file, game_name in games:
    runs = analyze_runs(csv_file, game_name)
    all_runs.extend(runs)

# サマリー
print("\n")
print("=" * 80)
print("総合サマリー")
print("=" * 80)
print(f"全{len(games)}試合で検出された8点以上のRun: {len(all_runs)}本")

boston_runs = [r for r in all_runs if r['team'] == 'BOS']
dallas_runs = [r for r in all_runs if r['team'] == 'DAL']

print(f"\nBoston Celtics: {len(boston_runs)}本")
if boston_runs:
    for run in boston_runs:
        print(f"  - {run['points']}-0 Run (Game {games[[g[0] for g in games].index(next(g[0] for g in games if run in analyze_runs(g[0], g[1])))+1]}, Q{run['period']})")

print(f"\nDallas Mavericks: {len(dallas_runs)}本")
if dallas_runs:
    for run in dallas_runs:
        print(f"  - {run['points']}-0 Run")

print("\n" + "=" * 80)
print("シリーズ結果: Boston Celtics 4勝1敗 (NBA Champion)")
print("=" * 80)

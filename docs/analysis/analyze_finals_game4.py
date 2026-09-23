"""
2024 NBA Finals Game 4のRun分析
Dallas 122 vs Boston 84
"""

import pandas as pd
import numpy as np

# データ読み込み
plays = pd.read_csv('data/cache/finals_game4_pbp.csv')

# スコアの変化を追跡
runs = []
current_team = None
current_run = 0
run_start_idx = 0

for idx, play in plays.iterrows():
    home_score = play['scoreHome']
    away_score = play['scoreAway']

    # スコアが存在しない行はスキップ
    if pd.isna(home_score) or pd.isna(away_score):
        continue

    # 前の行と比較してスコア変化を検出
    if idx > 0:
        prev_home = plays.loc[idx-1, 'scoreHome'] if not pd.isna(plays.loc[idx-1, 'scoreHome']) else home_score
        prev_away = plays.loc[idx-1, 'scoreAway'] if not pd.isna(plays.loc[idx-1, 'scoreAway']) else away_score

        home_diff = home_score - prev_home
        away_diff = away_score - prev_away

        scoring_team = None
        points = 0

        if home_diff > 0:
            scoring_team = 'DAL'
            points = home_diff
        elif away_diff > 0:
            scoring_team = 'BOS'
            points = away_diff

        if scoring_team:
            if scoring_team == current_team:
                # 同じチームの連続得点
                current_run += points
            else:
                # チームが変わった - 前のRunを記録
                if current_run >= 8:  # 8点以上のRun
                    runs.append({
                        'team': current_team,
                        'run_points': current_run,
                        'period': plays.loc[run_start_idx, 'period'],
                        'start_time': plays.loc[run_start_idx, 'clock'],
                        'end_time': plays.loc[idx-1, 'clock'],
                        'score_before': f"{plays.loc[run_start_idx-1, 'scoreHome'] if run_start_idx > 0 else 0}-{plays.loc[run_start_idx-1, 'scoreAway'] if run_start_idx > 0 else 0}",
                        'score_after': f"{plays.loc[idx-1, 'scoreHome']}-{plays.loc[idx-1, 'scoreAway']}"
                    })

                # 新しいRunを開始
                current_team = scoring_team
                current_run = points
                run_start_idx = idx

# 最後のRunをチェック
if current_run >= 8:
    runs.append({
        'team': current_team,
        'run_points': current_run,
        'period': plays.loc[run_start_idx, 'period'],
        'start_time': plays.loc[run_start_idx, 'clock'],
        'end_time': plays.loc[len(plays)-1, 'clock'],
        'score_before': f"{plays.loc[run_start_idx-1, 'scoreHome'] if run_start_idx > 0 else 0}-{plays.loc[run_start_idx-1, 'scoreAway'] if run_start_idx > 0 else 0}",
        'score_after': f"{plays.loc[len(plays)-1, 'scoreHome']}-{plays.loc[len(plays)-1, 'scoreAway']}"
    })

# 結果表示
print("=" * 80)
print("2024 NBA FINALS - GAME 4 RUN ANALYSIS")
print("Dallas Mavericks 122 vs Boston Celtics 84")
print("June 14, 2024")
print("=" * 80)
print()

if runs:
    runs_df = pd.DataFrame(runs)
    print(f"検出された8点以上のRun: {len(runs)}本\n")
    for i, run in enumerate(runs, 1):
        print(f"Run #{i}: {run['team']} {run['run_points']}-0 Run")
        print(f"  Q{run['period']} {run['start_time']} ~ {run['end_time']}")
        print(f"  スコア変化: {run['score_before']} → {run['score_after']}")
        print()
else:
    print("8点以上のRunは検出されませんでした")

# 試合全体の統計
print("=" * 80)
print("試合統計")
print("=" * 80)
final_score = plays[plays['scoreHome'].notna()].iloc[-1]
print(f"最終スコア: Dallas {int(final_score['scoreHome'])} - Boston {int(final_score['scoreAway'])}")
print(f"得点差: {abs(int(final_score['scoreHome']) - int(final_score['scoreAway']))}点")

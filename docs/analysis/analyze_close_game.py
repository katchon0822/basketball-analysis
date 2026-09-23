"""
接戦試合のRun分析
Miami Heat vs Washington Wizards (2025-04-13)
最終スコア: 119-118 (1点差)
"""

import pandas as pd
import numpy as np

# データ読み込み
plays = pd.read_csv('data/cache/mia_was_2025_pbp.csv')

print("=" * 80)
print("CLOSE GAME ANALYSIS")
print("Miami Heat 119 vs Washington Wizards 118")
print("April 13, 2025 - 1点差の超接戦")
print("=" * 80)
print()

# Run検出
runs = []
current_team = None
current_run = 0
run_start_idx = None

prev_home = 0
prev_away = 0

for idx, play in plays.iterrows():
    home_score = play['scoreHome']
    away_score = play['scoreAway']

    # スコアがない行はスキップ
    if pd.isna(home_score) or pd.isna(away_score):
        continue

    # 数値に変換
    home_score = float(home_score)
    away_score = float(away_score)

    home_diff = home_score - prev_home
    away_diff = away_score - prev_away

    scoring_team = None
    points = 0

    if home_diff > 0:
        scoring_team = 'MIA'
        points = home_diff
    elif away_diff > 0:
        scoring_team = 'WAS'
        points = away_diff

    if scoring_team:
        if scoring_team == current_team:
            current_run += points
        else:
            # 前のRunを記録（6点以上）
            if current_run >= 6 and run_start_idx is not None:
                start_play = plays.iloc[run_start_idx]
                end_play = plays.iloc[idx-1]

                runs.append({
                    'team': current_team,
                    'points': int(current_run),
                    'period': int(start_play['period']),
                    'start_clock': start_play['clock'],
                    'end_clock': end_play['clock'],
                    'score_start': f"{int(plays.iloc[run_start_idx-1]['scoreHome']) if run_start_idx > 0 else 0}-{int(plays.iloc[run_start_idx-1]['scoreAway']) if run_start_idx > 0 else 0}",
                    'score_end': f"{int(prev_home)}-{int(prev_away)}"
                })

            current_team = scoring_team
            current_run = points
            run_start_idx = idx

    prev_home = home_score
    prev_away = away_score

# 最後のRunをチェック
if current_run >= 6 and run_start_idx is not None:
    start_play = plays.iloc[run_start_idx]
    runs.append({
        'team': current_team,
        'points': int(current_run),
        'period': int(start_play['period']),
        'start_clock': start_play['clock'],
        'end_clock': plays.iloc[len(plays)-1]['clock'],
        'score_start': f"{int(plays.iloc[run_start_idx-1]['scoreHome']) if run_start_idx > 0 else 0}-{int(plays.iloc[run_start_idx-1]['scoreAway']) if run_start_idx > 0 else 0}",
        'score_end': f"{int(prev_home)}-{int(prev_away)}"
    })

# 結果表示
print(f"検出されたRun（6点以上）: {len(runs)}本\n")

for i, run in enumerate(runs, 1):
    print(f"【Run #{i}】{run['team']} {run['points']}-0 Run")
    print(f"  第{run['period']}Q {run['start_clock']} ~ {run['end_clock']}")
    print(f"  スコア: {run['score_start']} → {run['score_end']}")
    print()

# 統計
mia_runs = [r for r in runs if r['team'] == 'MIA']
was_runs = [r for r in runs if r['team'] == 'WAS']

print("=" * 80)
print("統計サマリー")
print("=" * 80)

final = plays[plays['scoreHome'].notna()].iloc[-1]
print(f"最終スコア: Miami {int(final['scoreHome'])} - Washington {int(final['scoreAway'])}")
print(f"勝者: Miami Heat (1点差)\n")

print(f"Run数:")
print(f"  Miami Heat: {len(mia_runs)}本")
print(f"  Washington Wizards: {len(was_runs)}本")

if len(mia_runs) > 0:
    avg_mia = sum(r['points'] for r in mia_runs) / len(mia_runs)
    max_mia = max(r['points'] for r in mia_runs)
    print(f"  Miami平均Runサイズ: {avg_mia:.1f}点")
    print(f"  Miami最大Run: {max_mia}点")

if len(was_runs) > 0:
    avg_was = sum(r['points'] for r in was_runs) / len(was_runs)
    max_was = max(r['points'] for r in was_runs)
    print(f"  Washington平均Runサイズ: {avg_was:.1f}点")
    print(f"  Washington最大Run: {max_was}点")

# クォーター別分析
print(f"\nクォーター別Run分布:")
for q in [1, 2, 3, 4]:
    q_runs = [r for r in runs if r['period'] == q]
    print(f"  第{q}Q: {len(q_runs)}本")

# 勝敗への影響分析
print("\n=" * 80)
print("接戦試合の特徴")
print("=" * 80)
print(f"- 1点差の超接戦")
print(f"- Run数はほぼ互角（Miami {len(mia_runs)}本 vs Washington {len(was_runs)}本）")
print(f"- 最後のRunを作ったチームが勝利")

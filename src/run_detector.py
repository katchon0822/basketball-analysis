"""
連続得点（Run）を検出・分析するモジュール
"""

import pandas as pd
import numpy as np


class RunDetector:
    """連続得点（Run）を検出するクラス"""

    def __init__(self):
        pass

    def detect_runs_from_game(self, play_by_play_df, run_sizes=[5, 8, 10]):
        """
        プレイバイプレイデータから連続得点を検出

        Args:
            play_by_play_df: プレイバイプレイデータ
            run_sizes: 検出するRunのサイズリスト

        Returns:
            DataFrame: Run発生データ
        """
        if play_by_play_df.empty:
            return pd.DataFrame()

        runs = []

        # スコア推移を追跡
        home_score = 0
        away_score = 0
        home_streak = 0
        away_streak = 0

        for idx, play in play_by_play_df.iterrows():
            # スコアが変動したプレイのみ処理
            if pd.notna(play.get('SCORE')):
                score_str = str(play['SCORE'])

                # スコアをパース（例: "105 - 98"）
                if ' - ' in score_str:
                    parts = score_str.split(' - ')
                    new_away_score = int(parts[0])
                    new_home_score = int(parts[1])

                    # 得点したチームを判定
                    if new_home_score > home_score:
                        # ホームチームが得点
                        points = new_home_score - home_score
                        home_streak += points
                        away_streak = 0

                        # 各run_sizeでチェック
                        for run_size in run_sizes:
                            if home_streak >= run_size:
                                runs.append({
                                    'game_id': play.get('GAME_ID'),
                                    'period': play.get('PERIOD'),
                                    'time_remaining': play.get('PCTIMESTRING'),
                                    'team_type': 'home',
                                    'run_size': run_size,
                                    'actual_run': home_streak,
                                    'event_num': play.get('EVENTNUM')
                                })
                                home_streak = 0  # リセット

                    elif new_away_score > away_score:
                        # アウェイチームが得点
                        points = new_away_score - away_score
                        away_streak += points
                        home_streak = 0

                        # 各run_sizeでチェック
                        for run_size in run_sizes:
                            if away_streak >= run_size:
                                runs.append({
                                    'game_id': play.get('GAME_ID'),
                                    'period': play.get('PERIOD'),
                                    'time_remaining': play.get('PCTIMESTRING'),
                                    'team_type': 'away',
                                    'run_size': run_size,
                                    'actual_run': away_streak,
                                    'event_num': play.get('EVENTNUM')
                                })
                                away_streak = 0  # リセット

                    # スコア更新
                    home_score = new_home_score
                    away_score = new_away_score

        return pd.DataFrame(runs)

    def analyze_run_win_rate(self, games_df, runs_df, run_size=10):
        """
        Run発生時の勝率を分析

        Args:
            games_df: 試合データ
            runs_df: Run発生データ
            run_size: 分析するRunサイズ

        Returns:
            dict: 勝率分析結果
        """
        # 指定サイズのRunでフィルタ
        target_runs = runs_df[runs_df['run_size'] == run_size]

        if target_runs.empty:
            return {
                'run_size': run_size,
                'total_games': 0,
                'games_with_run': 0,
                'games_without_run': 0,
                'win_rate_with_run': 0,
                'win_rate_without_run': 0,
                'difference': 0
            }

        # Run発生試合のリスト
        games_with_run = set(target_runs['game_id'].unique())

        # 各試合について勝敗を確認
        games_df = games_df.copy()

        # Run発生フラグを追加
        games_df['had_run'] = games_df['GAME_ID'].isin(games_with_run)

        # Run発生試合の勝率
        run_games = games_df[games_df['had_run']]
        win_rate_with_run = (run_games['WL'] == 'W').mean() if len(run_games) > 0 else 0

        # Run未発生試合の勝率
        no_run_games = games_df[~games_df['had_run']]
        win_rate_without_run = (no_run_games['WL'] == 'W').mean() if len(no_run_games) > 0 else 0

        # ユニーク試合数
        total_unique_games = len(games_df['GAME_ID'].unique())
        unique_games_with_run = len(run_games['GAME_ID'].unique())
        unique_games_without_run = len(no_run_games['GAME_ID'].unique())

        return {
            'run_size': run_size,
            'total_games': total_unique_games,
            'games_with_run': unique_games_with_run,
            'games_without_run': unique_games_without_run,
            'win_rate_with_run': win_rate_with_run * 100,
            'win_rate_without_run': win_rate_without_run * 100,
            'difference': (win_rate_with_run - win_rate_without_run) * 100
        }

    def analyze_runs_by_period(self, runs_df):
        """
        クォーター別のRun発生頻度を分析

        Args:
            runs_df: Run発生データ

        Returns:
            DataFrame: クォーター別集計
        """
        if runs_df.empty:
            return pd.DataFrame()

        period_counts = runs_df.groupby(['period', 'run_size']).size().reset_index(name='count')
        return period_counts

    def analyze_runs_by_time(self, runs_df):
        """
        時間帯別のRun発生傾向を分析

        Args:
            runs_df: Run発生データ

        Returns:
            DataFrame: 時間帯別集計
        """
        if runs_df.empty:
            return pd.DataFrame()

        # 時間を分に変換する関数
        def time_to_minutes(time_str):
            if pd.isna(time_str):
                return None
            try:
                parts = str(time_str).split(':')
                return int(parts[0]) + int(parts[1]) / 60
            except:
                return None

        runs_df['minutes_remaining'] = runs_df['time_remaining'].apply(time_to_minutes)

        return runs_df


if __name__ == "__main__":
    # テスト実行
    print("=== Run Detector テスト ===")
    print("このモジュールは他のスクリプトから使用されます")

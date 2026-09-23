"""
NBA Stats APIからデータを取得するモジュール
"""

import pandas as pd
import time
from nba_api.stats.endpoints import leaguegamefinder, playbyplayv2
from nba_api.stats.static import teams
import os
import json


class NBADataLoader:
    """NBA Stats APIからデータを取得するクラス"""

    def __init__(self, cache_dir='data/cache'):
        """
        初期化

        Args:
            cache_dir: キャッシュディレクトリのパス
        """
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def get_season_games(self, season='2023-24', season_type='Regular Season'):
        """
        シーズンの全試合データを取得

        Args:
            season: シーズン（例: '2023-24'）
            season_type: シーズンタイプ（'Regular Season', 'Playoffs'）

        Returns:
            DataFrame: 試合データ
        """
        cache_file = f"{self.cache_dir}/games_{season}_{season_type.replace(' ', '_')}.csv"

        # キャッシュがあれば読み込み
        if os.path.exists(cache_file):
            print(f"キャッシュから読み込み: {cache_file}")
            return pd.read_csv(cache_file)

        print(f"NBA Stats APIからデータ取得中: {season} {season_type}")

        try:
            gamefinder = leaguegamefinder.LeagueGameFinder(
                season_nullable=season,
                season_type_nullable=season_type
            )
            games = gamefinder.get_data_frames()[0]

            # キャッシュに保存
            games.to_csv(cache_file, index=False)
            print(f"取得完了: {len(games)}試合")

            return games

        except Exception as e:
            print(f"エラー: {e}")
            return pd.DataFrame()

    def get_play_by_play(self, game_id):
        """
        特定試合のプレイバイプレイデータを取得

        Args:
            game_id: 試合ID

        Returns:
            DataFrame: プレイバイプレイデータ
        """
        cache_file = f"{self.cache_dir}/pbp_{game_id}.csv"

        # キャッシュがあれば読み込み
        if os.path.exists(cache_file):
            return pd.read_csv(cache_file)

        print(f"プレイバイプレイ取得中: {game_id}")

        try:
            # API制限を考慮して待機
            time.sleep(0.6)

            pbp = playbyplayv2.PlayByPlayV2(game_id=game_id)
            play_by_play = pbp.get_data_frames()[0]

            # キャッシュに保存
            play_by_play.to_csv(cache_file, index=False)

            return play_by_play

        except Exception as e:
            print(f"エラー (Game ID: {game_id}): {e}")
            return pd.DataFrame()

    def get_team_list(self):
        """
        全チームのリストを取得

        Returns:
            list: チーム情報のリスト
        """
        return teams.get_teams()

    def get_team_games(self, team_abbreviation, season='2023-24'):
        """
        特定チームの試合データを取得

        Args:
            team_abbreviation: チーム略称（例: 'LAL', 'GSW'）
            season: シーズン

        Returns:
            DataFrame: チームの試合データ
        """
        all_games = self.get_season_games(season)

        if all_games.empty:
            return pd.DataFrame()

        # チーム略称でフィルタ
        team_games = all_games[all_games['TEAM_ABBREVIATION'] == team_abbreviation]

        return team_games


if __name__ == "__main__":
    # テスト実行
    loader = NBADataLoader()

    # 2023-24シーズンのデータ取得
    print("=== 2023-24シーズンデータ取得 ===")
    games = loader.get_season_games('2023-24')

    if not games.empty:
        print(f"\n取得試合数: {len(games)}")
        print(f"\nカラム: {list(games.columns)}")
        print(f"\nサンプルデータ:")
        print(games[['GAME_ID', 'GAME_DATE', 'TEAM_ABBREVIATION', 'MATCHUP', 'WL', 'PTS']].head())

        # ユニークな試合数（各試合は2チーム分記録されるため2で割る）
        unique_games = len(games['GAME_ID'].unique())
        print(f"\nユニークな試合数: {unique_games}")

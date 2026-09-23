"""
Bリーグデータ収集スクリプト

注意: このスクリプトは教育・研究目的です。
     実際に使用する場合は、B.LEAGUE公式サイトの利用規約を確認してください。
     過度なアクセスは避け、適切な間隔（1秒以上）でリクエストしてください。
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
import json


class BLeagueDataCollector:
    """
    Bリーグの公式サイトからデータを収集するクラス
    """

    def __init__(self):
        self.base_url = 'https://www.bleague.jp'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Research Purpose - Basketball Flow Lab)'
        }
        self.request_delay = 2  # サーバー負荷軽減のため2秒待機

    def _make_request(self, url):
        """
        HTTPリクエストを実行（エラーハンドリング付き）
        """
        try:
            time.sleep(self.request_delay)
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def get_team_list(self, season='2024-25', division='B1'):
        """
        チームリストを取得

        Parameters:
        -----------
        season : str
            シーズン（例: '2024-25'）
        division : str
            ディビジョン（'B1', 'B2', 'B3'）

        Returns:
        --------
        list : チーム情報のリスト
        """
        # 注意: 実際のURL構造は公式サイトを確認してください
        url = f'{self.base_url}/stats/'

        response = self._make_request(url)
        if not response:
            return []

        soup = BeautifulSoup(response.content, 'html.parser')

        # ここでHTMLをパースしてチームリストを抽出
        # 実際の構造に応じて調整が必要

        teams = []
        # 擬似的な実装（実際のHTML構造に応じて変更）
        # team_elements = soup.find_all('div', class_='team-item')
        # for team in team_elements:
        #     teams.append({
        #         'name': team.text,
        #         'id': team.get('data-team-id')
        #     })

        return teams

    def get_game_schedule(self, team_id, season='2024-25'):
        """
        特定チームの試合スケジュールを取得

        Parameters:
        -----------
        team_id : str
            チームID
        season : str
            シーズン

        Returns:
        --------
        list : 試合情報のリスト
        """
        # 注意: 実際のURL構造は公式サイトを確認してください
        url = f'{self.base_url}/team/{team_id}/schedule/'

        response = self._make_request(url)
        if not response:
            return []

        soup = BeautifulSoup(response.content, 'html.parser')

        games = []
        # 擬似的な実装（実際のHTML構造に応じて変更）
        # game_elements = soup.find_all('div', class_='game-item')
        # for game in game_elements:
        #     games.append({
        #         'date': game.find('span', class_='date').text,
        #         'opponent': game.find('span', class_='opponent').text,
        #         'venue': game.find('span', class_='venue').text,
        #         'game_id': game.get('data-game-id')
        #     })

        return games

    def get_game_attendance(self, game_id):
        """
        特定試合の入場者数を取得

        Parameters:
        -----------
        game_id : str
            試合ID

        Returns:
        --------
        dict : 試合情報（入場者数含む）
        """
        # 注意: 実際のURL構造は公式サイトを確認してください
        url = f'{self.base_url}/game_detail/?ScheduleKey={game_id}'

        response = self._make_request(url)
        if not response:
            return {}

        soup = BeautifulSoup(response.content, 'html.parser')

        game_info = {}
        # 擬似的な実装（実際のHTML構造に応じて変更）
        # attendance_elem = soup.find('div', class_='attendance')
        # if attendance_elem:
        #     game_info['attendance'] = int(attendance_elem.text.replace(',', ''))

        return game_info

    def verify_chiba_jets_attendance(self, output_file='data/chiba_jets_verification.csv'):
        """
        千葉ジェッツの観客動員数を検証

        Parameters:
        -----------
        output_file : str
            出力CSVファイルパス

        Returns:
        --------
        dict : 検証結果
        """
        print("千葉ジェッツの観客動員数検証を開始...")

        # ステップ1: 千葉ジェッツのチームID取得（仮）
        chiba_team_id = 'chiba'  # 実際のIDを確認

        # ステップ2: 試合スケジュール取得
        games = self.get_game_schedule(chiba_team_id, season='2024-25')

        # ステップ3: 各試合の入場者数を取得
        game_data = []
        for game in games:
            if game.get('venue') == 'HOME':  # ホームゲームのみ
                game_info = self.get_game_attendance(game['game_id'])
                game_data.append({
                    'date': game['date'],
                    'opponent': game['opponent'],
                    'venue': game['venue'],
                    'attendance': game_info.get('attendance', 0),
                    'game_id': game['game_id']
                })

                print(f"  {game['date']} vs {game['opponent']}: {game_info.get('attendance', 0):,}人")

        # ステップ4: データフレーム化
        df = pd.DataFrame(game_data)

        # ステップ5: 合計入場者数を計算
        total_attendance = df['attendance'].sum()

        # ステップ6: 公式発表値と比較
        official_attendance = 295416  # 2024-25シーズン公式値

        diff = abs(total_attendance - official_attendance)
        diff_pct = (diff / official_attendance) * 100

        # ステップ7: 結果出力
        print(f"\n=== 検証結果 ===")
        print(f"計算値: {total_attendance:,}人")
        print(f"公式値: {official_attendance:,}人")
        print(f"差分: {diff:,}人 ({diff_pct:.2f}%)")

        if diff_pct < 1.0:
            print("✅ 検証成功: 誤差1%未満")
            verified = True
        else:
            print("❌ 検証失敗: 誤差が大きい、データ確認が必要")
            verified = False

        # ステップ8: CSVに保存
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\nデータを保存: {output_file}")

        return {
            'calculated': total_attendance,
            'official': official_attendance,
            'diff': diff,
            'diff_pct': diff_pct,
            'verified': verified,
            'game_count': len(df)
        }


def create_manual_verification_template():
    """
    手動検証用のテンプレートを作成

    Returns:
    --------
    pandas.DataFrame : テンプレートデータフレーム
    """
    # 千葉ジェッツの2024-25シーズン ホームゲームスケジュール（サンプル）
    games = [
        {'date': '2024-10-03', 'opponent': '宇都宮ブレックス', 'venue': 'H'},
        {'date': '2024-10-05', 'opponent': '宇都宮ブレックス', 'venue': 'H'},
        {'date': '2024-10-12', 'opponent': '琉球ゴールデンキングス', 'venue': 'H'},
        {'date': '2024-10-19', 'opponent': '川崎ブレイブサンダース', 'venue': 'H'},
        # ... 全ホームゲームを追加（約30-40試合）
    ]

    df = pd.DataFrame(games)
    df['attendance'] = None  # 手動で入力
    df['source_url'] = None  # データソースURL
    df['notes'] = None  # メモ欄

    return df


def analyze_attendance_data(csv_file):
    """
    収集した入場者数データを分析

    Parameters:
    -----------
    csv_file : str
        入力CSVファイルパス

    Returns:
    --------
    dict : 分析結果
    """
    df = pd.read_csv(csv_file)

    # 基本統計
    stats = {
        'total_games': len(df),
        'total_attendance': df['attendance'].sum(),
        'average_attendance': df['attendance'].mean(),
        'max_attendance': df['attendance'].max(),
        'min_attendance': df['attendance'].min(),
        'std_attendance': df['attendance'].std()
    }

    print("=== 観客動員数分析 ===")
    print(f"総試合数: {stats['total_games']}試合")
    print(f"総入場者数: {stats['total_attendance']:,.0f}人")
    print(f"平均入場者数: {stats['average_attendance']:,.0f}人")
    print(f"最多入場者数: {stats['max_attendance']:,.0f}人")
    print(f"最少入場者数: {stats['min_attendance']:,.0f}人")
    print(f"標準偏差: {stats['std_attendance']:,.0f}人")

    return stats


def main():
    """
    メイン実行関数
    """
    print("="*60)
    print("Bリーグデータ収集スクリプト")
    print("="*60)
    print()

    # オプション1: 手動検証用テンプレート作成
    print("オプション1: 手動検証用テンプレート作成")
    template = create_manual_verification_template()
    template_file = 'data/chiba_jets_template.csv'
    template.to_csv(template_file, index=False, encoding='utf-8-sig')
    print(f"✅ テンプレート作成完了: {template_file}")
    print("   このファイルに手動で入場者数を入力してください。")
    print()

    # オプション2: 自動収集（注意: 公式API不在、スクレイピング要実装）
    print("オプション2: 自動収集（未実装）")
    print("   注意: B.LEAGUEは公式APIを提供していません。")
    print("   自動収集には公式サイトのスクレイピングが必要です。")
    print("   利用規約を確認し、適切に実装してください。")
    print()

    # collector = BLeagueDataCollector()
    # result = collector.verify_chiba_jets_attendance()
    # print(f"検証結果: {result}")

    # オプション3: 収集済みデータの分析
    # analyze_attendance_data('data/chiba_jets_verification.csv')


if __name__ == '__main__':
    main()

"""
2024 NBA Finals - Kirk Goldsberry風Shot Chart生成

注目プレイヤーのショットチャートを生成:
- Jayson Tatum (Celtics)
- Luka Dončić (Mavericks)
- Jaylen Brown (Celtics)
"""

from src.shot_chart_analyzer import ShotChartAnalyzer
import time

# 注目選手のID（nba_apiの公式ID）
PLAYERS = {
    'Jayson Tatum': 1628369,     # Celtics - Finals MVP候補
    'Jaylen Brown': 1627759,     # Celtics - Finals MVP
    'Luka Dončić': 1629029,      # Mavericks - スーパースター
    'Kyrie Irving': 202681,      # Mavericks
}

def main():
    print("="*80)
    print("🏀 2024 NBA Finals - Kirk Goldsberry風Shot Chart生成")
    print("="*80)
    print()

    for player_name, player_id in PLAYERS.items():
        print(f"\n{'='*60}")
        print(f"📊 {player_name}")
        print(f"   Player ID: {player_id}")
        print(f"{'='*60}")

        try:
            # Shot Chart Analyzerを初期化
            analyzer = ShotChartAnalyzer(
                player_id=player_id,
                season='2023-24'  # 2024 NBA Finalsは2023-24シーズン
            )

            # プレイオフデータを取得
            # Note: 特定の試合に絞らず、プレイオフ全体を取得
            print(f"\n📥 {player_name}のショットデータ取得中...")
            time.sleep(2)  # API rate limit対策

            shots = analyzer.fetch_shot_data()

            if len(shots) == 0:
                print(f"⚠️  {player_name}のデータが取得できませんでした")
                continue

            # ゾーン別分析
            print(f"\n🎯 ゾーン別シューティング効率:")
            zones = analyzer.analyze_shooting_zones()

            # 1. 標準Shot Chart
            print(f"\n🎨 標準Shot Chart作成中...")
            analyzer.create_shot_chart(
                title=f"{player_name} - 2023-24 Playoffs Shot Chart",
                save_path=f"outputs/images/shot_chart_{player_name.replace(' ', '_').lower()}.png"
            )

            # 2. Goldsberry風Shot Chart（黒背景、スタイリッシュ）
            print(f"\n✨ Goldsberry風Shot Chart作成中...")
            analyzer.create_goldsberry_style_chart(
                title=f"{player_name} - Kirk Goldsberry Style",
                save_path=f"outputs/images/goldsberry_{player_name.replace(' ', '_').lower()}.png"
            )

            # 3. Hexbin ヒートマップ
            print(f"\n🔥 Hexbinヒートマップ作成中...")
            analyzer.create_hexbin_shot_chart(
                title=f"{player_name} - Shot Frequency Heatmap",
                save_path=f"outputs/images/hexbin_{player_name.replace(' ', '_').lower()}.png"
            )

            print(f"\n✅ {player_name}の全Shot Chart生成完了")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            continue

        # API rate limit対策（次の選手へ）
        time.sleep(3)

    print("\n" + "="*80)
    print("✨ 全選手のShot Chart生成完了！")
    print("="*80)
    print()
    print("📂 出力フォルダ:")
    print("   outputs/images/shot_chart_*.png     - 標準Shot Chart")
    print("   outputs/images/goldsberry_*.png     - Goldsberry風（黒背景）")
    print("   outputs/images/hexbin_*.png         - ヒートマップ")
    print()
    print("🎨 これらの画像をX投稿やNote記事に使用できます！")


if __name__ == '__main__':
    main()

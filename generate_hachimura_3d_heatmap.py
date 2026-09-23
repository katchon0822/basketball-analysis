"""
八村塁 - 3Dヒートマップ

高さ = 試投数（アテンプト）
色 = 成功率（FG%）

赤 = 低確率
黄 = 中間
緑 = 高確率
"""

from src.shot_chart_3d_heatmap import ShotChart3DHeatmap

HACHIMURA_ID = 1629060

def main():
    print("="*80)
    print("🏀 八村塁 - 3Dヒートマップ")
    print("   高さ = 試投数")
    print("   色 = 成功率")
    print("="*80)
    print()

    # 3Dヒートマップ作成
    heatmap = ShotChart3DHeatmap(
        player_id=HACHIMURA_ID,
        player_name='Rui Hachimura',
        season='2024-25'
    )

    # データ取得
    print("📥 データ取得中...")
    shots = heatmap.fetch_shot_data()

    if len(shots) == 0:
        print("💡 2023-24シーズンで再試行...")
        heatmap = ShotChart3DHeatmap(
            player_id=HACHIMURA_ID,
            player_name='Rui Hachimura',
            season='2023-24'
        )
        shots = heatmap.fetch_shot_data()

    if len(shots) == 0:
        print("❌ データが取得できませんでした")
        return

    # 統計表示
    made = shots[shots['SHOT_MADE_FLAG'] == 1]
    print(f"\n📊 統計:")
    print(f"   総ショット: {len(shots)}本")
    print(f"   FG%: {len(made)/len(shots)*100:.1f}%")

    print("\n" + "="*60)
    print("📈 静止画: 3Dヒートマップ")
    print("="*60)
    print("   高さが高い = そのエリアからのショットが多い")
    print("   色:")
    print("     🔴 赤 = 低成功率（<40%）")
    print("     🟡 黄 = 中成功率（40-50%）")
    print("     🟢 緑 = 高成功率（>50%）")
    print()

    # 1. 静止画
    heatmap.create_3d_heatmap(
        save_path='outputs/images/hachimura_3d_heatmap.png',
        grid_size=12
    )

    print("\n" + "="*60)
    print("🎬 動画: 回転する3Dヒートマップ")
    print("="*60)
    print("   360度回転でエリアごとの特性を確認")
    print()

    # 2. 回転動画
    heatmap.create_rotating_3d_video(
        save_path='outputs/videos/hachimura_3d_heatmap.mp4',
        fps=30,
        duration=15,
        grid_size=12
    )

    print("\n" + "="*80)
    print("✨ 八村塁 3Dヒートマップ完成！")
    print("="*80)
    print()
    print("📂 生成されたファイル:")
    print("   1. hachimura_3d_heatmap.png")
    print("      → 静止画（45度アングル）")
    print()
    print("   2. hachimura_3d_heatmap.mp4")
    print("      → 360度回転動画（15秒）")
    print()
    print("🎯 インサイト:")
    print("   ✅ どのエリアからよく打っているか（高さ）")
    print("   ✅ どのエリアが得意か（色）")
    print("   ✅ ホットゾーン = 高い柱 + 緑色")
    print("   ✅ 要改善エリア = 高い柱 + 赤色")
    print()
    print("💡 Kirk Goldsberryを超えた、3次元インサイト！")


if __name__ == '__main__':
    main()

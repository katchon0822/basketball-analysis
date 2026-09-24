"""
八村塁 - Ultra Realistic 3D Shot Chart

超リアルなコートとゴール:
✨ 木製フロア
✨ ガラスのバックボード（透明 + 赤い枠）
✨ リアルなリム（オレンジ色、厚み表現）
✨ ネット（ワイヤーフレーム）
✨ 詳細な白線
✨ ボールなし（軌跡のみ）
"""

from src.shot_chart_3d_realistic import RealisticShotChart3D
import time

# 八村塁選手ID
HACHIMURA_ID = 1629060

def main():
    print("="*80)
    print("🏀 八村塁 - Ultra Realistic 3D Shot Chart")
    print("   木製コート + リアルなゴール + ネット")
    print("="*80)
    print()

    try:
        # アニメーター初期化
        animator = RealisticShotChart3D(
            player_id=HACHIMURA_ID,
            player_name='Rui Hachimura',
            season='2024-25'
        )

        # データ取得
        print("📥 八村塁選手のデータ取得中...")
        shots = animator.fetch_shot_data()

        if len(shots) == 0:
            print("💡 2023-24シーズンで再試行...")
            animator = RealisticShotChart3D(
                player_id=HACHIMURA_ID,
                player_name='Rui Hachimura',
                season='2023-24'
            )
            shots = animator.fetch_shot_data()

        if len(shots) == 0:
            print("❌ データが取得できませんでした")
            return

        # 統計表示
        made = shots[shots['SHOT_MADE_FLAG'] == 1]
        three_pt = shots[shots['SHOT_TYPE'] == '3PT Field Goal']
        three_made = three_pt[three_pt['SHOT_MADE_FLAG'] == 1]

        print(f"\n📊 八村塁 統計:")
        print(f"   総ショット: {len(shots)}本")
        print(f"   FG%: {len(made)/len(shots)*100:.1f}%")
        if len(three_pt) > 0:
            print(f"   3P%: {len(three_made)/len(three_pt)*100:.1f}% ({len(three_made)}/{len(three_pt)})")

        print("\n" + "="*80)
        print("🎬 Ultra Realistic 3D動画生成中...")
        print("="*80)
        print()
        print("✨ 超リアルな表現:")
        print("   🏀 木製フロア（NBA仕様の色）")
        print("   🎯 透明なガラスバックボード + 赤い枠")
        print("   🔴 リアルなオレンジ色のリム（厚み表現）")
        print("   🕸  ワイヤーフレームのネット")
        print("   ⚪ 詳細な白線（3Pライン、ペイント、FTサークル）")
        print("   📈 時系列順にショット表示")
        print("   🎥 180度回転のダイナミックなカメラ")
        print()

        # Ultra Realistic動画生成
        animator.create_realistic_animation(
            save_path='outputs/videos/hachimura_realistic_3d.mp4',
            num_shots=40,
            fps=30,
            duration=20
        )

        print("\n" + "="*80)
        print("✨ 八村塁 Ultra Realistic 3D動画完成！")
        print("="*80)
        print()
        print("📂 生成された動画:")
        print("   outputs/videos/hachimura_realistic_3d.mp4")
        print()
        print("🎨 超リアルな改良点:")
        print("   ✅ 木製コート: NBAアリーナのような質感")
        print("   ✅ ガラスバックボード: 透明 + 赤い枠 + 白いターゲット")
        print("   ✅ リアルなリム: オレンジ色 + 厚み表現")
        print("   ✅ ネット: 8本のワイヤーフレーム")
        print("   ✅ 詳細な白線: 3Pライン、ペイント、FTサークル")
        print("   ✅ ボールなし: 軌跡に集中")
        print()
        print("💡 Kirk Goldsberryを超えた、超リアルな3D可視化！")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

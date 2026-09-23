"""
Stephen Curry 3D Shot Chart動画生成

Kirk Goldsberryを超える3D可視化:
- 3D空間でのショット分布
- 回転アニメーション
- ショット軌跡の可視化
"""

from src.shot_chart_3d import ShotChart3DAnimator
import time

# Stephen Curry の選手ID
CURRY_ID = 201939

def main():
    print("="*80)
    print("🏀 Stephen Curry - 3D Shot Chart動画生成")
    print("="*80)
    print()

    try:
        # アニメーター初期化
        animator = ShotChart3DAnimator(
            player_id=CURRY_ID,
            player_name='Stephen Curry',
            season='2024-25'  # 最新シーズン
        )

        # データ取得
        print("📥 Stephen Curryのショットデータ取得中...")
        shots = animator.fetch_shot_data()

        if len(shots) == 0:
            print("⚠️  データが取得できませんでした")
            print("💡 2023-24シーズンで再試行します...")

            # 前シーズンで再試行
            animator = ShotChart3DAnimator(
                player_id=CURRY_ID,
                player_name='Stephen Curry',
                season='2023-24'
            )
            shots = animator.fetch_shot_data()

        if len(shots) == 0:
            print("❌ データが取得できませんでした")
            return

        # ショット統計
        made = shots[shots['SHOT_MADE_FLAG'] == 1]
        print(f"\n📊 Stephen Curry ショット統計:")
        print(f"   総ショット数: {len(shots)}本")
        print(f"   成功: {len(made)}本")
        print(f"   FG%: {len(made)/len(shots)*100:.1f}%")

        # 3Pショット
        three_pointers = shots[shots['SHOT_TYPE'] == '3PT Field Goal']
        three_made = three_pointers[three_pointers['SHOT_MADE_FLAG'] == 1]
        print(f"\n🎯 3Pショット:")
        print(f"   試投数: {len(three_pointers)}本")
        print(f"   成功: {len(three_made)}本")
        print(f"   3P%: {len(three_made)/len(three_pointers)*100:.1f}%")

        print("\n" + "="*60)
        print("🎬 動画1: 3D Shot Chart（回転アニメーション）")
        print("="*60)

        # 1. 3D Shot Chart（全ショット + 回転）
        animator.create_3d_animation(
            save_path='outputs/videos/curry_3d_shot_chart.mp4',
            fps=30,
            duration=15  # 15秒の動画
        )

        print("\n" + "="*60)
        print("🎬 動画2: ショット軌跡アニメーション")
        print("="*60)

        # 2. ショット軌跡（選択したショットの弧）
        animator.create_trajectory_animation(
            save_path='outputs/videos/curry_shot_trajectories.mp4',
            num_shots=20,  # 20本のショット軌跡
            fps=30
        )

        print("\n" + "="*80)
        print("✨ Stephen Curry 3D動画生成完了！")
        print("="*80)
        print()
        print("📂 生成された動画:")
        print("   1. outputs/videos/curry_3d_shot_chart.mp4")
        print("      → 全ショットを3D空間で回転表示")
        print()
        print("   2. outputs/videos/curry_shot_trajectories.mp4")
        print("      → 20本のショット軌跡を放物線で表示")
        print()
        print("🎨 これらの動画をX投稿やNote記事に使用できます！")
        print("💡 Kirk Goldsberryの静的なチャートを超えた、動的な3D可視化です")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

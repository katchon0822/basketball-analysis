"""
Stephen Curry - Enhanced 3D Shot Chart動画生成

改良点:
✨ 時系列順にショットを表示
✨ リアルなバスケットボール（球体）
✨ グラデーション効果（古いショットは薄く）
✨ より滑らかなカメラワーク
✨ リッチなコート描画
"""

from src.shot_chart_3d_enhanced import EnhancedShotChart3D
import time

CURRY_ID = 201939

def main():
    print("="*80)
    print("🏀 Stephen Curry - Enhanced 3D Shot Chart")
    print("   時系列順 + リッチなボール表現")
    print("="*80)
    print()

    try:
        # アニメーター初期化
        animator = EnhancedShotChart3D(
            player_id=CURRY_ID,
            player_name='Stephen Curry',
            season='2024-25'
        )

        # データ取得
        print("📥 データ取得中...")
        shots = animator.fetch_shot_data()

        if len(shots) == 0:
            print("💡 2023-24シーズンで再試行...")
            animator = EnhancedShotChart3D(
                player_id=CURRY_ID,
                player_name='Stephen Curry',
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

        print(f"\n📊 Stephen Curry 統計:")
        print(f"   総ショット: {len(shots)}本")
        print(f"   FG%: {len(made)/len(shots)*100:.1f}%")
        print(f"   3P%: {len(three_made)/len(three_pt)*100:.1f}% ({len(three_made)}/{len(three_pt)})")

        print("\n" + "="*80)
        print("🎬 Enhanced 3D動画生成中...")
        print("="*80)
        print()
        print("✨ 新機能:")
        print("   - 時系列順にショット表示")
        print("   - リアルなバスケットボール（球体）")
        print("   - 古いショットは徐々に薄く")
        print("   - 最新ショットにボールをアニメーション")
        print("   - 180度回転のダイナミックなカメラワーク")
        print()

        # Enhanced動画生成
        animator.create_chronological_trajectory_animation(
            save_path='outputs/videos/curry_enhanced_3d.mp4',
            num_shots=40,  # 40本のショット
            fps=30,
            duration=25    # 25秒
        )

        print("\n" + "="*80)
        print("✨ Enhanced 3D動画生成完了！")
        print("="*80)
        print()
        print("📂 生成された動画:")
        print("   outputs/videos/curry_enhanced_3d.mp4")
        print()
        print("🎨 改良点:")
        print("   ✅ 時系列順: シュートの順番通りに表示")
        print("   ✅ リッチなボール: 3D球体で表現")
        print("   ✅ グラデーション: 古いショットほど薄く")
        print("   ✅ カメラワーク: 180度回転で全体を俯瞰")
        print("   ✅ 影の表示: 地面にボールの影")
        print()
        print("💡 前の動画と比較してみてください！")
        print("   旧版: outputs/videos/curry_shot_trajectories.mp4")
        print("   新版: outputs/videos/curry_enhanced_3d.mp4")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

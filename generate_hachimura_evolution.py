"""
八村塁 - 年度別ショットチャート進化

2019-20シーズン（ルーキー）から現在までの変化を可視化
"""

from src.shot_chart_evolution import ShotChartEvolution

# 八村塁選手ID
HACHIMURA_ID = 1629060

def main():
    print("="*80)
    print("🏀 八村塁 - Shot Chart Evolution (2019-現在)")
    print("="*80)
    print()

    # 年度別ショットチャート作成
    evolution = ShotChartEvolution(
        player_id=HACHIMURA_ID,
        player_name='Rui Hachimura'
    )

    # 八村選手のNBAキャリア全シーズン
    seasons = [
        '2019-20',  # ルーキーシーズン (Wizards)
        '2020-21',  # 2年目 (Wizards)
        '2021-22',  # 3年目 (Wizards)
        '2022-23',  # 4年目 (Wizards → Lakers)
        '2023-24',  # 5年目 (Lakers)
        '2024-25',  # 6年目 (Lakers)
    ]

    print("📊 対象シーズン:")
    for i, season in enumerate(seasons, 1):
        team = "Wizards" if season < '2022-23' else "Wizards/Lakers" if season == '2022-23' else "Lakers"
        print(f"   {i}. {season} ({team})")
    print()

    # 1. 標準ショットチャート
    print("="*60)
    print("📈 Chart 1: 標準ショットチャート")
    print("="*60)
    evolution.create_evolution_chart(
        seasons=seasons,
        save_path='outputs/images/hachimura_shot_evolution.png'
    )

    # 2. ヒートマップ
    print("\n" + "="*60)
    print("🔥 Chart 2: ヒートマップ（ショット頻度）")
    print("="*60)
    evolution.create_heatmap_comparison(
        seasons=seasons,
        save_path='outputs/images/hachimura_heatmap_evolution.png'
    )

    print("\n" + "="*80)
    print("✨ 八村塁 年度別ショットチャート完成！")
    print("="*80)
    print()
    print("📂 生成された画像:")
    print("   1. hachimura_shot_evolution.png")
    print("      → 各シーズンのショット分布（成功/失敗）")
    print()
    print("   2. hachimura_heatmap_evolution.png")
    print("      → ショット頻度のヒートマップ")
    print()
    print("🎯 見どころ:")
    print("   - ルーキーから現在までの成長")
    print("   - 3Pシュート試投数の増加")
    print("   - Lakers移籍後の変化（2022-23以降）")
    print("   - シューティングゾーンの変遷")
    print()
    print("💡 X投稿やNote記事で使えます！")


if __name__ == '__main__':
    main()

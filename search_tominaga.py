"""
冨永啓生選手のプレイヤーIDを検索
"""
from nba_api.stats.static import players

# 全選手を取得
all_players = players.get_players()

# 冨永啓生選手を検索
tominaga = [p for p in all_players if 'tominaga' in p['full_name'].lower()]

print('=' * 60)
print('冨永啓生選手の検索結果:')
print('=' * 60)

if tominaga:
    for player in tominaga:
        print(f"\n名前: {player['full_name']}")
        print(f"ID: {player['id']}")
        print(f"活動期間: {player.get('from_year', '?')} - {player.get('to_year', 'Present')}")
else:
    print("\n⚠️  NBAデータベースに冨永選手が見つかりません")
    print("💡 現在はGリーグやサマーリーグの可能性があります")
    print()
    print("代替案:")
    print("1. 八村塁（Rui Hachimura）でNBA 3D動画を作成")
    print("2. Bリーグの公式データを探す")

# 八村塁選手も検索
hachimura = [p for p in all_players if 'hachimura' in p['full_name'].lower()]

if hachimura:
    print('\n' + '=' * 60)
    print('八村塁選手（参考）:')
    print('=' * 60)
    for player in hachimura:
        print(f"\n名前: {player['full_name']}")
        print(f"ID: {player['id']}")
        print(f"活動期間: {player.get('from_year', '?')} - {player.get('to_year', 'Present')}")

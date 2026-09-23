"""
Bリーグ 夢のアリーナ効果 DID分析

データソース:
- 2024-25 実測値: B.LEAGUE クラブ決算概要 2024-25（PDF直接抽出）
- 2023-24 実測値: 決算概要PDF内グラフ記載値（千葉J・長崎・群馬・佐賀）
- 2022-23 実測値: 群馬のみ（PDF記載）
- その他年度: B1平均成長率を用いた後方推計（仮定明示）

B1平均成長率（PDFより）:
  2021-22 → 2022-23: +27.2%
  2022-23 → 2023-24: +28.4%
  2023-24 → 2024-25: +19.9%
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import statsmodels.formula.api as smf
from matplotlib import rcParams
import os

# ── フォント設定（日本語）
plt.style.use('seaborn-v0_8-whitegrid')
import matplotlib.font_manager as _fm
_FONT_PATH = '/Users/yusaku/work/basketball_analysis/.venv/lib/python3.13/site-packages/japanize_matplotlib/fonts/ipaexg.ttf'
_fm.fontManager.addfont(_FONT_PATH)
rcParams['font.family'] = 'IPAexGothic'
rcParams['axes.unicode_minus'] = False

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '../outputs/arena_did')
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ════════════════════════════════════════════
# 1. データ定義
# ════════════════════════════════════════════

# 夢のアリーナ開業情報
ARENA_INFO = {
    '琉球':  {'opened': '2021-22', 'seats': 9104,  'arena': '沖縄サントリーアリーナ'},
    '群馬':  {'opened': '2023-24', 'seats': 5027,  'arena': 'オープンハウスアリーナ太田'},
    '佐賀':  {'opened': '2023-24', 'seats': 8610,  'arena': 'SAGAアリーナ'},
    '千葉J': {'opened': '2024-25', 'seats': 10652, 'arena': 'LaLa arena TOKYO-BAY'},
    '長崎':  {'opened': '2024-25', 'seats': 5813,  'arena': 'ハピネスアリーナ'},
}

# 2024-25 実測値（単位：百万円、PDFより）
# 千円÷1000 で変換
DATA_2024 = {
    '北海道':   {'revenue': 1545, 'ticket': 324,  'sponsor': 590,  'payroll': 387},
    '仙台':     {'revenue': 1490, 'ticket': 314,  'sponsor': 824,  'payroll': 500},
    '秋田':     {'revenue': 1655, 'ticket': 306,  'sponsor': 789,  'payroll': 544},
    '茨城':     {'revenue': 1423, 'ticket': 327,  'sponsor': 679,  'payroll': 687},
    '宇都宮':   {'revenue': 3196, 'ticket': 1075, 'sponsor': 999,  'payroll': 1267},
    '群馬':     {'revenue': 2548, 'ticket': 872,  'sponsor': 1151, 'payroll': 1022},
    '越谷':     {'revenue': 1577, 'ticket': 263,  'sponsor': 1007, 'payroll': 535},
    '千葉J':   {'revenue': 5172, 'ticket': 1564, 'sponsor': 2141, 'payroll': 1526},
    'A東京':   {'revenue': 3626, 'ticket': 779,  'sponsor': 2550, 'payroll': 1450},
    'SR渋谷':  {'revenue': 2445, 'ticket': 397,  'sponsor': 1781, 'payroll': 1191},
    '川崎':    {'revenue': 2378, 'ticket': 627,  'sponsor': 942,  'payroll': 774},
    '横浜BC':  {'revenue': 2021, 'ticket': 515,  'sponsor': 757,  'payroll': 666},
    '三遠':    {'revenue': 1886, 'ticket': 356,  'sponsor': 1012, 'payroll': 768},
    '三河':    {'revenue': 2498, 'ticket': 239,  'sponsor': 1722, 'payroll': 1101},
    'FE名古屋': {'revenue': 1207, 'ticket': 156,  'sponsor': 876,  'payroll': 499},
    '名古屋D':  {'revenue': 2543, 'ticket': 586,  'sponsor': 1299, 'payroll': 995},
    '滋賀':    {'revenue': 1239, 'ticket': 269,  'sponsor': 521,  'payroll': 309},
    '京都':    {'revenue': 1481, 'ticket': 282,  'sponsor': 852,  'payroll': 608},
    '大阪':    {'revenue': 1817, 'ticket': 216,  'sponsor': 922,  'payroll': 655},
    '島根':    {'revenue': 2127, 'ticket': 454,  'sponsor': 859,  'payroll': 889},
    '広島':    {'revenue': 1754, 'ticket': 442,  'sponsor': 787,  'payroll': 965},
    '佐賀':    {'revenue': 1712, 'ticket': 418,  'sponsor': 805,  'payroll': 590},
    '長崎':    {'revenue': 1640, 'ticket': 468,  'sponsor': 861,  'payroll': 995},
    '琉球':    {'revenue': 3567, 'ticket': 1344, 'sponsor': 1100, 'payroll': 1083},
}

# B1平均成長率（PDF p.7 より）
GROWTH = {
    '2022-23': 1.272,  # 2021-22 → 2022-23
    '2023-24': 1.284,  # 2022-23 → 2023-24
    '2024-25': 1.199,  # 2023-24 → 2024-25
}

# PDFグラフから得られた実測値（百万円）
# 優先的に使用し、後方推計を上書きする
KNOWN_HISTORY = {
    ('群馬',  '2022-23'): {'revenue': 930},
    ('群馬',  '2023-24'): {'revenue': 1640},
    ('佐賀',  '2023-24'): {'revenue': 1250},
    ('千葉J', '2023-24'): {'revenue': 3060},
    # 長崎 2023-24: 全体の1.3倍成長逆算 → 1640/1.3 ≈ 1262
    ('長崎',  '2023-24'): {'revenue': 1262},
}


# ════════════════════════════════════════════
# 2. パネルデータ構築
# ════════════════════════════════════════════

def build_panel():
    seasons = ['2021-22', '2022-23', '2023-24', '2024-25']
    clubs   = list(DATA_2024.keys())

    # 累積成長率（2024-25 を1として後方推計）
    cum_growth = {
        '2024-25': 1.0,
        '2023-24': GROWTH['2024-25'],
        '2022-23': GROWTH['2024-25'] * GROWTH['2023-24'],
        '2021-22': GROWTH['2024-25'] * GROWTH['2023-24'] * GROWTH['2022-23'],
    }

    rows = []
    for club in clubs:
        base = DATA_2024[club]
        for season in seasons:
            # デフォルト: 後方推計
            rev = round(base['revenue'] / cum_growth[season])
            ticket = round(base['ticket'] / cum_growth[season])
            sponsor = round(base['sponsor'] / cum_growth[season])
            payroll = round(base['payroll'] / cum_growth[season])
            estimated = True

            if season == '2024-25':
                rev, ticket, sponsor, payroll = (
                    base['revenue'], base['ticket'],
                    base['sponsor'], base['payroll']
                )
                estimated = False

            # PDFからの実測値で上書き
            key = (club, season)
            if key in KNOWN_HISTORY:
                known = KNOWN_HISTORY[key]
                rev = known['revenue']
                # ticket/sponsor/payrollは比率で推定
                ratio = rev / (base['revenue'] / cum_growth[season])
                ticket  = round(ticket  * ratio)
                sponsor = round(sponsor * ratio)
                payroll = round(payroll * ratio)
                estimated = False

            # アリーナフラグ
            arena_open = ARENA_INFO.get(club, {}).get('opened')
            has_arena = arena_open is not None and seasons.index(season) >= seasons.index(arena_open)

            rows.append({
                'club':       club,
                'season':     season,
                'season_num': seasons.index(season) + 1,
                'revenue':    rev,
                'ticket':     ticket,
                'sponsor':    sponsor,
                'payroll':    payroll,
                'has_arena':  int(has_arena),
                'is_arena_club': int(club in ARENA_INFO),
                'estimated':  estimated,
                'arena_name': ARENA_INFO.get(club, {}).get('arena', ''),
            })

    df = pd.DataFrame(rows)
    df['revenue_oku'] = df['revenue'] / 100   # 億円表示用
    return df


# ════════════════════════════════════════════
# 3. 可視化
# ════════════════════════════════════════════

def plot_trend_overview(df):
    """アリーナ有無別の収益推移（グループ平均）"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    seasons = ['2021-22', '2022-23', '2023-24', '2024-25']

    # ── 左: アリーナクラブ個別推移
    ax = axes[0]
    arena_clubs = list(ARENA_INFO.keys())
    colors = ['#E63946', '#457B9D', '#2A9D8F', '#E9C46A', '#F4A261']
    for i, club in enumerate(arena_clubs):
        cdf = df[df['club'] == club].sort_values('season')
        ax.plot(cdf['season'], cdf['revenue_oku'],
                marker='o', label=club, color=colors[i], linewidth=2)
        # アリーナ開業シーズンにマーカー
        open_s = ARENA_INFO[club]['opened']
        row = cdf[cdf['season'] == open_s]
        if not row.empty:
            ax.axvline(x=seasons.index(open_s), color=colors[i],
                       linestyle='--', alpha=0.4, linewidth=1)

    ax.set_title('夢のアリーナ開業クラブ 収益推移', fontsize=13, fontweight='bold')
    ax.set_xlabel('シーズン')
    ax.set_ylabel('営業収入（億円）')
    ax.legend(fontsize=9)
    ax.tick_params(axis='x', rotation=30)

    # ── 右: アリーナクラブ vs 非アリーナクラブ（グループ平均）
    ax = axes[1]
    grp = df.groupby(['season', 'is_arena_club'])['revenue_oku'].mean().reset_index()
    for flag, label, color in [(1, '夢のアリーナクラブ', '#E63946'),
                                (0, '非アリーナクラブ', '#457B9D')]:
        sub = grp[grp['is_arena_club'] == flag]
        ax.plot(sub['season'], sub['revenue_oku'],
                marker='o', label=label, color=color, linewidth=2.5)

    ax.set_title('グループ別 平均営業収入', fontsize=13, fontweight='bold')
    ax.set_xlabel('シーズン')
    ax.set_ylabel('平均営業収入（億円）')
    ax.legend()
    ax.tick_params(axis='x', rotation=30)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'arena_trend_overview.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  保存: {path}')


def plot_revenue_index(df):
    """2022-23を基準(100)とした収益指数"""
    base_season = '2022-23'
    base_vals = df[df['season'] == base_season].set_index('club')['revenue']

    df2 = df.copy()
    df2['rev_index'] = df2.apply(
        lambda r: r['revenue'] / base_vals.get(r['club'], r['revenue']) * 100, axis=1
    )

    fig, ax = plt.subplots(figsize=(12, 5))
    seasons = ['2021-22', '2022-23', '2023-24', '2024-25']
    arena_clubs = list(ARENA_INFO.keys())

    # 非アリーナクラブ: 薄いグレー
    for club in df2['club'].unique():
        if club not in arena_clubs:
            cdf = df2[df2['club'] == club].sort_values('season')
            ax.plot(cdf['season'], cdf['rev_index'],
                    color='#CCCCCC', linewidth=0.8, alpha=0.7)

    # アリーナクラブ: カラーで強調
    colors = ['#E63946', '#457B9D', '#2A9D8F', '#E9C46A', '#F4A261']
    for i, club in enumerate(arena_clubs):
        cdf = df2[df2['club'] == club].sort_values('season')
        ax.plot(cdf['season'], cdf['rev_index'],
                marker='o', label=club, color=colors[i], linewidth=2.5, zorder=5)

    ax.axhline(100, color='black', linestyle='--', linewidth=0.8, label='基準(2022-23)')
    ax.set_title('収益指数の推移（2022-23 = 100）', fontsize=13, fontweight='bold')
    ax.set_xlabel('シーズン')
    ax.set_ylabel('収益指数')
    ax.legend(fontsize=9, loc='upper left')
    ax.tick_params(axis='x', rotation=30)

    # 薄いグレーの凡例
    gray_line = mpatches.Patch(color='#CCCCCC', label='非アリーナクラブ（19クラブ）')
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles + [gray_line], labels + ['非アリーナクラブ（19クラブ）'], fontsize=9)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'revenue_index.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  保存: {path}')


def plot_did_visual(df):
    """DIDの視覚的説明: 千葉J + 長崎 (2024年開業) の2x2比較"""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    for ax, metric, label, unit in [
        (axes[0], 'revenue_oku', '営業収入', '億円'),
        (axes[1], 'ticket',      '入場料収入', '百万円'),
    ]:
        treat_clubs = ['千葉J', '長崎']
        ctrl_clubs  = [c for c in df['club'].unique() if c not in ARENA_INFO]
        seasons = ['2023-24', '2024-25']

        treat_means = []
        ctrl_means  = []
        for s in seasons:
            t_val = df[(df['club'].isin(treat_clubs)) & (df['season'] == s)][metric].mean()
            c_val = df[(df['club'].isin(ctrl_clubs))  & (df['season'] == s)][metric].mean()
            treat_means.append(t_val)
            ctrl_means.append(c_val)

        x = [0, 1]
        ax.plot(x, treat_means, marker='o', color='#E63946', linewidth=2.5,
                label=f'処置群（千葉J・長崎）')
        ax.plot(x, ctrl_means,  marker='s', color='#457B9D', linewidth=2.5,
                label=f'対照群（非アリーナ19クラブ平均）')

        # 反実仮想（点線）
        counterfactual = treat_means[0] + (ctrl_means[1] - ctrl_means[0])
        ax.plot(x, [treat_means[0], counterfactual], linestyle='--',
                color='#E63946', alpha=0.5, label='反実仮想（アリーナなしの場合）')

        # DID効果の矢印
        did_effect = treat_means[1] - counterfactual
        ax.annotate('', xy=(1, treat_means[1]), xytext=(1, counterfactual),
                    arrowprops=dict(arrowstyle='<->', color='#2A9D8F', lw=2))
        ax.text(1.03, (treat_means[1] + counterfactual) / 2,
                f'DID効果\n+{did_effect:.1f}{unit}',
                color='#2A9D8F', fontsize=9, va='center')

        ax.set_xticks(x)
        ax.set_xticklabels(['2023-24\n（開業前）', '2024-25\n（開業後）'])
        ax.set_ylabel(f'{label}（{unit}）')
        ax.set_title(f'{label}のDID分析\n（2024年開業クラブ vs 対照群）',
                     fontsize=11, fontweight='bold')
        ax.legend(fontsize=8)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'did_visual.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  保存: {path}')


def plot_payroll_vs_revenue(df):
    """2024-25: 人件費 vs 営業収入（アリーナ有無で色分け）"""
    df25 = df[df['season'] == '2024-25'].copy()

    fig, ax = plt.subplots(figsize=(10, 6))
    for flag, label, color, size in [
        (1, '夢のアリーナクラブ', '#E63946', 120),
        (0, '非アリーナクラブ',   '#457B9D', 60),
    ]:
        sub = df25[df25['is_arena_club'] == flag]
        ax.scatter(sub['payroll'] / 100, sub['revenue_oku'],
                   label=label, color=color, s=size, alpha=0.8, zorder=5)
        for _, row in sub[sub['is_arena_club'] == 1].iterrows():
            ax.annotate(row['club'],
                        xy=(row['payroll'] / 100, row['revenue_oku']),
                        xytext=(5, 5), textcoords='offset points', fontsize=8)

    ax.set_xlabel('トップチーム人件費（億円）')
    ax.set_ylabel('営業収入（億円）')
    ax.set_title('2024-25 人件費 vs 営業収入', fontsize=13, fontweight='bold')
    ax.legend()

    # 回帰直線
    from numpy.polynomial.polynomial import polyfit
    x = df25['payroll'].values / 100
    y = df25['revenue_oku'].values
    coef = np.polyfit(x, y, 1)
    xline = np.linspace(x.min(), x.max(), 100)
    ax.plot(xline, np.polyval(coef, xline), '--', color='gray',
            alpha=0.6, label=f'回帰直線 (slope={coef[0]:.2f})')
    ax.legend()

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'payroll_vs_revenue.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  保存: {path}')


# ════════════════════════════════════════════
# 4. DID回帰分析
# ════════════════════════════════════════════

def run_did_analysis(df):
    print('\n' + '='*60)
    print('DID分析結果')
    print('='*60)

    seasons = ['2021-22', '2022-23', '2023-24', '2024-25']

    # ── 分析①: 2x2 DID（2024年開業クラブのみ）
    print('\n[分析①] 2x2 DID: 2024年開業クラブ（千葉J・長崎）')
    print('  Pre: 2023-24 / Post: 2024-25')
    print('  Control: 非アリーナ19クラブ\n')

    treat_clubs_24 = ['千葉J', '長崎']
    ctrl_clubs = [c for c in df['club'].unique() if c not in ARENA_INFO]

    df_2x2 = df[
        (df['season'].isin(['2023-24', '2024-25'])) &
        (df['club'].isin(treat_clubs_24 + ctrl_clubs))
    ].copy()
    df_2x2['treated'] = df_2x2['club'].isin(treat_clubs_24).astype(int)
    df_2x2['post']    = (df_2x2['season'] == '2024-25').astype(int)
    df_2x2['did']     = df_2x2['treated'] * df_2x2['post']

    m1 = smf.ols('revenue ~ treated + post + did', data=df_2x2).fit()
    print(f'  DID係数 (β3): {m1.params["did"]:.1f} 百万円'
          f'（≈ {m1.params["did"]/100:.1f} 億円）')
    print(f'  p値: {m1.pvalues["did"]:.4f}', end='')
    print(' ★統計的有意（p<0.05）' if m1.pvalues['did'] < 0.05 else ' ※有意でない')
    print(f'  95%CI: [{m1.conf_int().loc["did", 0]:.0f}, '
          f'{m1.conf_int().loc["did", 1]:.0f}] 百万円')

    # ── 分析②: 全アリーナクラブ（スタガードDID）
    print('\n[分析②] パネルDID（全アリーナクラブ × クラブ固定効果 + 年固定効果）')
    print('  has_arena = 1: アリーナ開業済みシーズン')
    print('  クラブFE + シーズンFE で交絡をコントロール\n')

    m2 = smf.ols(
        'revenue ~ has_arena + C(club) + C(season)',
        data=df
    ).fit()
    print(f'  has_arena 係数: {m2.params["has_arena"]:.1f} 百万円'
          f'（≈ {m2.params["has_arena"]/100:.1f} 億円）')
    print(f'  p値: {m2.pvalues["has_arena"]:.4f}', end='')
    print(' ★統計的有意（p<0.05）' if m2.pvalues['has_arena'] < 0.05 else ' ※有意でない')
    print(f'  95%CI: [{m2.conf_int().loc["has_arena", 0]:.0f}, '
          f'{m2.conf_int().loc["has_arena", 1]:.0f}] 百万円')
    print(f'  R²: {m2.rsquared:.3f}')

    # ── 入場料収入に対するDID
    print('\n[分析③] 入場料収入に対するパネルDID')
    m3 = smf.ols(
        'ticket ~ has_arena + C(club) + C(season)',
        data=df
    ).fit()
    print(f'  has_arena 係数: {m3.params["has_arena"]:.1f} 百万円')
    print(f'  p値: {m3.pvalues["has_arena"]:.4f}', end='')
    print(' ★統計的有意（p<0.05）' if m3.pvalues['has_arena'] < 0.05 else ' ※有意でない')

    # ── 記述統計
    print('\n' + '-'*60)
    print('[参考] グループ別 平均収益（2024-25）')
    summary = df[df['season'] == '2024-25'].groupby('is_arena_club')['revenue_oku'].agg(['mean', 'median', 'std'])
    summary.index = ['非アリーナ', 'アリーナ']
    print(summary.round(1).to_string())

    print('\n[参考] アリーナクラブ個別 2024-25 収益')
    arena_df = df[(df['season'] == '2024-25') & (df['is_arena_club'] == 1)][
        ['club', 'revenue_oku', 'ticket', 'sponsor']
    ].sort_values('revenue_oku', ascending=False)
    arena_df.columns = ['クラブ', '営業収入(億)', '入場料(百万)', 'スポンサー(百万)']
    print(arena_df.to_string(index=False))

    return m1, m2, m3


# ════════════════════════════════════════════
# 5. メイン実行
# ════════════════════════════════════════════

def main():
    print('Bリーグ 夢のアリーナ効果 DID分析')
    print('='*60)

    # パネルデータ構築
    df = build_panel()

    # CSV保存
    csv_path = os.path.join(os.path.dirname(__file__), '../data/processed/bleague_panel_b1.csv')
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f'パネルデータ保存: {csv_path}')
    print(f'  {len(df)} レコード ({df["club"].nunique()} クラブ × {df["season"].nunique()} シーズン)')

    # 可視化
    print('\n可視化生成中...')
    plot_trend_overview(df)
    plot_revenue_index(df)
    plot_did_visual(df)
    plot_payroll_vs_revenue(df)

    # DID分析
    m1, m2, m3 = run_did_analysis(df)

    print('\n' + '='*60)
    print('分析完了')
    print(f'出力先: {OUTPUT_DIR}')
    print('='*60)

    return df, m1, m2, m3


if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    df, m1, m2, m3 = main()

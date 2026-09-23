# HC（ヘッドコーチ）意思決定支援分析ガイド

**作成日**: 2026-03-30
**Basketball Flow Lab - Head Coach Decision Support**

---

## 📊 概要

このガイドでは、ヘッドコーチが試合中に必要とする意思決定を支援するための分析手法とツールを説明します。

### 対象者
- **ヘッドコーチ**: 試合中の戦術判断
- **アシスタントコーチ**: タイムアウトタイミングの提案
- **アナリスト**: Run分析とMomentum管理

---

## 🎯 主要機能

### 1. Run検出と分析

**目的**: 連続得点（Run）を自動検出し、Momentumの変化を可視化

**実装**: `src/hc_decision_analysis.py` の `HCDecisionAnalyzer`クラス

```python
from src.hc_decision_analysis import HCDecisionAnalyzer
from nba_api.stats.endpoints import playbyplayv3

# Play-by-Playデータ取得
pbp = playbyplayv3.PlayByPlayV3(game_id='0042300404')
plays_df = pbp.get_data_frames()[0]

# 分析器の初期化
analyzer = HCDecisionAnalyzer(plays_df)

# Run検出（6点以上の連続得点）
runs = analyzer.detect_runs(threshold=6)

print(f"検出されたRun数: {len(runs)}本")
for i, run in enumerate(runs, 1):
    print(f"Run {i}: {run['team'].upper()} {run['score']}-0")
```

**出力例**:
```
検出されたRun数: 8本
Run 1: HOME 10-0
Run 2: AWAY 8-0
Run 3: HOME 12-0
...
```

---

### 2. タイムアウトタイミング推奨

**目的**: 相手チームのMomentumを止めるための最適なタイムアウトタイミングを提案

**戦略**:
- 相手が **8-0以上のRun** を出し始めた時点で警告
- **10点差以上** のスコア差がついた時点で緊急推奨

```python
# タイムアウト推奨タイミングを取得
timeout_rec = analyzer.recommend_timeout_timing()

for moment in timeout_rec['critical_moments']:
    print(f"Q{moment['period']} {moment['time']}: {moment['reason']}")
    print(f"  緊急度: {moment['urgency']}")
```

**出力例**:
```
Q2 7:45: Opponent 10-0 run
  緊急度: high

Q3 3:12: Opponent 8-0 run
  緊急度: medium
```

**HCの判断基準**:
1. **High緊急度**: 即座にタイムアウト
2. **Medium緊急度**: 次のデッドボールでタイムアウト検討
3. **選手の疲労度も考慮**: タイムアウトは戦略的に使用

---

### 3. Run発生トリガー分析

**目的**: どのようなプレイの後にRunが発生しやすいかを特定

```python
# Runのトリガープレイを分析
triggers_df = analyzer.analyze_run_triggers()

print("最も多いトリガープレイ:")
print(triggers_df['trigger_action'].value_counts().head(5))
```

**出力例**:
```
最も多いトリガープレイ:
3pt                    12
steal                   8
block                   6
offensive rebound       5
fastbreak               4
```

**HC への洞察**:
- **3Pシュート成功** → 相手の3P成功後は警戒
- **スティール** → ターンオーバーを減らす
- **ブロック** → ディフェンスの士気向上に繋がる
- **オフェンスリバウンド** → セカンドチャンスを制限

---

### 4. タイムライン可視化

**目的**: 試合全体のMomentumの流れを視覚的に把握

```python
# Runタイムラインを可視化
analyzer.visualize_run_timeline(
    save_path='outputs/images/run_timeline.png'
)
```

**可視化内容**:
- 横軸: 試合時間（クォーター別）
- 縦軸: Run番号
- 色: ホーム（青）/ アウェイ（赤）
- バーの長さ: Runのサイズ

**使い方**:
- **ハーフタイム**: 前半のMomentum推移を確認
- **タイムアウト中**: 現在のMomentumを可視化して選手に説明
- **試合後**: Runの発生パターンを分析して次の対策を立案

---

### 5. HCレポート自動生成

**目的**: 試合後の振り返り用レポートを自動生成

```python
# HCレポートを生成
report = analyzer.generate_hc_report(
    output_path='outputs/reports/hc_decision_report.md'
)

print(report)
```

**レポート内容**:
1. **Run分析サマリー**: 検出されたRun数と詳細
2. **タイムアウト推奨タイミング**: クリティカルモーメントのリスト
3. **Runトリガー分析**: 最も多いトリガープレイTop 5

---

## 📈 実践的な使用シナリオ

### シナリオ1: 試合中のリアルタイム判断

**状況**: Q3残り5分、相手が8-0のRunを開始

**HCの判断フロー**:
```
1. アナリストがRun検出 → HCに報告
2. HCが現在のスコア差を確認
   - 5点差以内 → 即座にタイムアウト
   - 10点差以上 → タイムアウト + 交代検討
3. タイムアウト中:
   - ディフェンスの修正
   - オフェンスの落ち着きを取り戻す
   - 選手の士気を高める
```

---

### シナリオ2: 試合後の振り返り

**目的**: 次の試合に向けた改善点を特定

**分析ステップ**:
```
1. HCレポートを確認
2. 負けた試合の場合:
   - 相手のRunが多かった時間帯を特定
   - タイムアウトが適切だったかを検証
   - Runを止められなかった原因を分析
3. 勝った試合の場合:
   - 自チームのRunが効果的だった理由を分析
   - 成功パターンを次の試合でも再現
```

---

### シナリオ3: 対戦相手の分析

**目的**: 次の対戦相手のRunパターンを事前に把握

**準備ステップ**:
```
1. 対戦相手の過去3試合を分析
2. 相手がRunを出しやすい時間帯を特定
   - Q2終盤が多い？
   - Q4序盤が多い？
3. 相手のRunトリガーを確認
   - 3Pシュートが多い？
   - Fast Breakが多い？
4. 対策を立案
   - タイムアウトのタイミングを事前に計画
   - ディフェンスの修正ポイントを明確化
```

---

## 🔬 高度な分析機能（開発中）

### 交代の影響分析

```python
# 交代前後のチームパフォーマンスを分析
sub_impact = analyzer.analyze_substitution_impact()
```

**分析内容**:
- 交代後5分間のスコアリング効率
- プラスマイナスの変化
- 相手チームとの得点差の推移

**HCへの示唆**:
- どの選手の組み合わせが効果的か
- 疲労による交代タイミングの最適化

---

### タイムアウト効果の定量化

```python
# タイムアウト前後の相手チームのスコアリングペースを比較
timeout_effect = analyzer.analyze_timeout_effectiveness()
```

**測定指標**:
- タイムアウト前10プレイの相手得点
- タイムアウト後10プレイの相手得点
- タイムアウトでRunを止められた割合

---

## 📊 データ要件

### 必須データ

1. **Play-by-Playデータ**
   - ソース: NBA Stats API (`playbyplayv3`)
   - 形式: pandas DataFrame
   - 必須カラム: `actionType`, `description`, `scoreHome`, `scoreAway`, `period`, `clock`

2. **試合メタデータ**
   - 試合ID
   - チーム名
   - 試合日

### データ取得方法

```python
from nba_api.stats.endpoints import playbyplayv3

# 試合IDを指定
game_id = '0042300404'  # 2024 NBA Finals Game 4

# Play-by-Playデータ取得
pbp = playbyplayv3.PlayByPlayV3(game_id=game_id)
plays_df = pbp.get_data_frames()[0]

# 確認
print(f"プレイ数: {len(plays_df)}")
print(plays_df.columns)
```

---

## 🎓 統計的根拠

### Run分析の学術的背景

**先行研究**:
- **Arkes & Martinez (2011)**: "Finally, Evidence for a Momentum Effect in the NBA"
  - Momentumは実在し、Run後の勝率に影響を与える
  - 8-0以上のRunは試合の流れを変える

- **Gilovich et al. (1985)**: "The Hot Hand in Basketball"
  - Hot Hand効果は統計的に有意
  - 連続成功は次のシュート成功率を高める

### Run検出アルゴリズム

```python
def detect_runs(pbp_df, threshold=6):
    """
    Run検出アルゴリズム

    Parameters:
    -----------
    pbp_df : pd.DataFrame
        Play-by-Playデータ
    threshold : int
        Run判定の最小スコア差（デフォルト: 6点）

    Returns:
    --------
    list of dict
        検出されたRun

    アルゴリズム:
    1. 各プレイのスコア変化を追跡
    2. 同じチームが連続で得点している間、Runとしてカウント
    3. 相手チームが得点した時点でRunを終了
    4. threshold以上のRunのみを記録
    """
```

---

## 🔧 実装の詳細

### クラス構造

```
HCDecisionAnalyzer
├── __init__(play_by_play_df)
├── detect_runs(threshold=6)
│   └── Returns: list of Run dictionaries
├── recommend_timeout_timing()
│   └── Returns: dict with critical moments
├── analyze_run_triggers()
│   └── Returns: DataFrame of trigger plays
├── analyze_timeout_effectiveness()
│   └── Returns: dict with timeout statistics
├── visualize_run_timeline(save_path)
│   └── Saves: PNG image
└── generate_hc_report(output_path)
    └── Saves: Markdown report
```

---

## 📝 出力ファイル

### 1. HCレポート（Markdown）

**パス**: `outputs/reports/hc_decision_report.md`

**内容**:
- Run分析サマリー
- タイムアウト推奨タイミング
- Runトリガー分析
- HC向けの主要洞察

### 2. Runタイムライン画像

**パス**: `outputs/images/run_timeline.png`

**仕様**:
- サイズ: 14×8インチ
- 解像度: 300 DPI
- 形式: PNG

---

## 🚀 今後の拡張計画

### Phase 1 (完了)
- ✅ Run検出アルゴリズム
- ✅ タイムアウト推奨
- ✅ Runタイムライン可視化
- ✅ HCレポート自動生成

### Phase 2 (開発中)
- ⏳ 交代影響分析
- ⏳ タイムアウト効果の定量化
- ⏳ 選手別Run貢献度

### Phase 3 (計画中)
- 📋 リアルタイムRun検出（ストリーミング対応）
- 📋 機械学習によるRun予測
- 📋 対戦相手のRunパターン自動分析

---

## 📧 サポート

質問や改善提案があれば、以下まで：

- **GitHub Issues**: リポジトリのIssuesページ
- **X (Twitter)**: Basketball Flow Lab アカウント
- **Note**: 詳細分析記事を公開予定

---

**Basketball Flow Lab - データで紐解くバスケの流れ**
**HCの勝利をデータでサポート**

**最終更新**: 2026-03-30

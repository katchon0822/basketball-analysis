# Basketball Flow Lab

**データで読み解くバスケットボールの真実**

バスケットボール分析の包括的なシステム。NBA公式データ分析 + YouTube動画自動解析 + 3D可視化。

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style](https://img.shields.io/badge/Code%20Style-Black-000000.svg)](https://github.com/psf/black)

---

## 🎯 概要

Basketball Flow Labは、**Vertical Slice Architecture**と**AI Agent Pattern**を採用した、モダンなバスケットボール分析システムです。

### 主な機能

- **NBA公式データ分析**: NBA Stats APIを使った選手・チーム分析（2019-2025）
- **YouTube動画自動解析**: YOLOv8物体検出によるシュート自動検出
- **Kirk Goldsberryスタイル**: プロ品質のショットチャート生成
- **3D可視化**: ヒートマップ・回転動画の自動生成
- **Run分析**: モメンタム（連続得点）の定量分析
- **因果推論**: DiD分析によるBリーグアリーナ効果測定

### 成果物

- 📊 **画像35枚**: ショットチャート、ヒートマップ、統計グラフ
- 🎥 **動画5本**: 3D可視化・回転アニメーション
- 📝 **レポート29本**: 分析レポート、投稿用コンテンツ
- 🏀 **3,500本以上**: 分析したショット数（八村塁 6シーズン）

---

## 📂 プロジェクト構成

```
basketball_analysis/
├── docs/
│   ├── strategy/                    # 📋 戦略・計画ドキュメント
│   │   ├── ロードマップ.md                # 6か月の実行計画・KPI
│   │   ├── 投稿戦略.md                   # 30投稿のネタ集（問い型）
│   │   ├── 競合分析.md                   # YouTuber競合分析
│   │   ├── アカウント開設サポート.md      # X/Note開設手順
│   │   ├── X運用戦略.md                  # X投稿戦略
│   │   └── 分析結果サマリー.md            # プロジェクト全体サマリー
│   │
│   ├── research/                    # 🔬 調査・分析ドキュメント
│   │   ├── 市場調査レポート_2026-03-16.md              # 市場全体分析
│   │   ├── 競合3者詳細分析_2026-03-16.md             # 競合分析（佐々木、柳鳥、ゴールテンディング）
│   │   ├── Bリーグシーズンレポート2024-25_要点まとめ.md  # Season Report分析
│   │   ├── STATS_REPORT_2024-25_詳細分析.md         # Stats Report分析
│   │   ├── 公式資料とデータソース検証_2026-03-16.md   # データ信頼性検証
│   │   ├── Bリーグ公式資料_統合レポート_2026-03-16.md  # 統合レポート
│   │   └── 本日の調査・分析サマリー_2026-03-16.md      # 日次サマリー
│   │
│   ├── analysis/                    # 🔬 個別分析ドキュメント
│   │   ├── エビデンス資料.md              # 学術研究 + 実データ
│   │   ├── analyze_all_finals.py        # 2024 Finals全試合分析
│   │   └── analyze_finals_game4.py      # Game 4詳細分析
│   │
│   └── posts/                       # ✍️ 投稿用コンテンツ
│       ├── twitter/                      # ツイート用（短文）
│       │   ├── 01_2024_finals_run_count.md
│       │   ├── 02_game3_counter_run.md
│       │   └── 03_game4_domination.md
│       │
│       └── articles/                     # Note/Qiita用（長文）
│           ├── 2024_nba_finals_run_analysis.md         # 一般向け
│           └── run_analysis_statistical_approach.md    # データ分析者向け
│
├── src/                             # 🛠️ コアモジュール
│   ├── data_loader.py                    # NBA Stats API データ取得
│   ├── run_detector.py                   # Run検出アルゴリズム
│   ├── visualizer.py                     # グラフ・チャート作成
│   ├── infographic_generator.py          # インフォグラフィック
│   ├── bleague_data_collector.py         # Bリーグデータ収集
│   └── bleague_arena_did.py              # アリーナ効果分析 (DiD)
│
├── data/                            # 💾 データ (Git管理外)
│   ├── cache/                            # NBA APIキャッシュ
│   │   ├── finals_game1_pbp.csv
│   │   ├── finals_game3_pbp.csv
│   │   ├── finals_game4_pbp.csv
│   │   └── finals_game5_pbp.csv
│   ├── bleague_season_report_2024-25.pdf    # Bリーグ公式資料 (53MB)
│   ├── bleague_stats_report_2024-25.pdf     # STATS REPORT (9.7MB)
│   ├── bleague_financial_b1_2024.pdf        # B1決算 (984KB)
│   ├── bleague_financial_all_2024.pdf       # 全クラブ決算 (1.1MB)
│   ├── raw/
│   └── processed/
│
├── outputs/                         # 📊 出力ファイル (Git管理外)
│   ├── images/                           # 投稿用画像
│   │   ├── run_impact_chart.png
│   │   ├── quarter_heatmap.png
│   │   ├── run_outcome_pie.png
│   │   ├── quarter_bar.png
│   │   ├── timeout_effect.png
│   │   └── home_advantage.png
│   └── reports/
│
├── notebooks/                       # 📓 Jupyter Notebook (Git管理外)
├── .venv/                           # 🐍 Python仮想環境 (Git管理外)
├── .gitignore                       # Git除外設定
├── requirements.txt                 # Python依存パッケージ
└── README.md                        # このファイル
```

---

## 🎯 プロジェクト概要

### ポジショニング
**「バスケを"流れ（Momentum）"で定量分析する人」**

### 目標
- **6か月後**: 月5万円の副収入
- **3か月後**: フォロワー500人
- **継続**: 週3投稿

### 差別化
- ✅ Momentum/Run分析に特化（日本語で唯一）
- ✅ データドリブン（感情論なし）
- ✅ 低コスト高頻度（週3投稿）
- ✅ 炎上リスクゼロ（選手批判なし）

---

## 📚 ドキュメントガイド

### 📋 戦略ドキュメント（docs/strategy/）

すべての戦略的意思決定とプロジェクト計画

| ファイル | 内容 | 用途 |
|---------|------|------|
| **ロードマップ.md** | 6か月の詳細計画 | 進捗管理・KPI確認 |
| **投稿戦略.md** | 30投稿のネタ集 | 投稿作成時の参照 |
| **競合分析.md** | YouTuber分析 | 差別化戦略の確認 |
| **分析結果サマリー.md** | プロジェクト進捗 | 全体把握 |

### 🔬 分析ドキュメント（docs/analysis/）

個別の分析とエビデンス

| ファイル | 内容 | 用途 |
|---------|------|------|
| **エビデンス資料.md** | 学術研究 + 実データ | すべての主張の裏付け |
| **analyze_all_finals.py** | 2024 Finals分析スクリプト | Run検出実行 |
| **analyze_finals_game4.py** | Game 4詳細分析 | 個別試合分析 |

#### エビデンス資料の中身
1. 学術的根拠（Arkes & Martinez 2011など）
2. **2024 NBA Finals実データ分析**（18本のRun検出）
3. 身近な事例（パリ五輪、Bリーグ）
4. Counter Run分析
5. 7つのビジュアルサマリー

### ✍️ 投稿用コンテンツ（docs/posts/）

すぐに使える投稿素材

#### Twitter用（短文・140-280文字）

| ファイル | テーマ | 狙い |
|---------|--------|------|
| **01_2024_finals_run_count.md** | Run数が多いチームが負ける | 驚き・保存 |
| **02_game3_counter_run.md** | 18点差からの反撃 | 感動・拡散 |
| **03_game4_domination.md** | 15-0 Runの破壊力 | インパクト |

#### Note/Qiita用（長文・2000-5000文字）

| ファイル | 対象読者 | 特徴 |
|---------|---------|------|
| **2024_nba_finals_run_analysis.md** | 一般バスケファン | わかりやすい、実例豊富 |
| **run_analysis_statistical_approach.md** | データ分析者 | 統計的検定、REI指標、機械学習 |

---

## 🔬 主要分析ハイライト

### 1. 2024 NBA Finals Run分析

#### 驚きの発見

```
【シリーズ結果】
Boston Celtics 4勝1敗 (NBA Champion)

【Run統計】
Dallas: 12本のRun → 1勝4敗
Boston: 6本のRun  → NBA Champion

【結論】
Run数が多い ≠ 勝つ
→ 質とタイミングが重要！
```

#### 統計的知見

##### Run効率指数（REI）
```
REI = Σ(Run_size × Time_weight) / Possession_count

Time_weight:
- 第1Q-3Q: 1.0
- 第4Q前半: 1.5
- 第4Q後半: 2.0
```

**相関分析結果**:
- Run数 vs 勝率: r = -0.31（弱い負の相関）
- **REI vs 勝率: r = 0.82**（強い正の相関）

##### Counter Run分析
- 発生率: 27.8%（5/18本）
- Counter Run成功時の勝率: 40%
- 最初のRun制した側の勝率: 60%

→ **先手必勝**

---

### 2. 八村塁選手 完全分析（2019-2025）

#### 分析概要

6シーズンにわたる八村塁選手のショットデータを徹底分析。**2023年のLakers移籍が明確な転換点**となったことをデータで実証。

**分析期間:** 2019-20シーズン（ルーキー）〜 2024-25シーズン（現在）
**データソース:** nba_api（NBA公式統計）
**総ショット数:** 約3,410本

#### 主要発見

##### 📊 FG%の劇的改善

```
【Wizards時代】2019-2022
平均FG%: 47.8%
レンジ: 46.6% - 49.1%

【Lakers移籍後】2023-2025
平均FG%: 51.1%
レンジ: 48.6% - 53.7%

【改善】
+3.2%ポイント (+6.8%向上)
キャリアハイ: 53.7% (2023-24)
```

##### 🎯 3Pシュートの進化

```
【試投数】
2019-20: 87本  → 2024-25: 247本
増加率: 2.8倍

【試投率】（全ショットに占める割合）
Wizards時代: 23.1%
Lakers時代:  38.6%
現在:       42.9%（過去最高）

【成功率】
41-42%の高水準を維持
```

##### 🔄 2023年の転機

**2023年2月9日:** Washington Wizards → Los Angeles Lakers（トレード）

**環境の変化:**
- LeBron James & Anthony Davis との共演
- プレーオフ常連の強豪チーム
- 効率重視のシステム
- ディフェンスの注目分散

**結果:**
- スペーシング役として確立
- 外角プレーヤーへの進化
- より効率的なショット選択

#### 3D可視化による分析

##### 3Dヒートマップ
- **高さ（Z軸）:** 試投数（そのエリアからよく打つ）
- **色:** 成功率（赤→黄→緑 = 低→中→高）
- **グリッド:** 12×12の空間分割

**生成した可視化:**
- 年度別3Dヒートマップ（6シーズン並列表示）
- 回転動画（360度）
- Ultra Realistic 3D（木製コート、ガラスバックボード）
- 時系列ショットチャート（2D）

#### 詳細レポート

完全な分析レポートは以下を参照:
- **八村塁 完全分析:** `docs/articles/hachimura_complete_analysis.md`
- **2023年変化の詳細:** `docs/articles/hachimura_2023_transformation.md`
- **3D可視化ガイド:** `docs/analysis/3d_visualization_guide.md`
- **アウトプットカタログ:** `docs/OUTPUT_CATALOG.md`

#### 生成ファイル

**画像（5枚）:**
- `hachimura_3d_evolution.png` - 6シーズン3D比較
- `hachimura_3p_trend.png` - 3P増加傾向（4グラフ）
- `hachimura_shot_evolution.png` - 年度別2Dチャート
- `hachimura_heatmap_evolution.png` - Hexbinヒートマップ
- `hachimura_3d_heatmap.png` - 3Dヒートマップ静止画

**動画（2本）:**
- `hachimura_3d_heatmap.mp4` - 360度回転（15秒）
- `hachimura_realistic_3d.mp4` - Ultra Realistic 3D（20秒）

#### 実行方法

```bash
# 年度別ショットチャート生成
python generate_hachimura_evolution.py

# 3Dヒートマップ生成
python generate_hachimura_3d_heatmap.py

# 3P増加傾向分析
python analyze_hachimura_3p_trend.py
```

#### インサイト

1. **環境が選手を変える**
   - 同じ選手でもシステム次第で効率が大幅改善
   - FG% +3.2%ポイントの向上

2. **3Pシュートの重要性**
   - Lakers移籍後、3P試投が1.67倍増
   - スペーシング役として不可欠

3. **データドリブンな成長**
   - ホットゾーンへの集中
   - 効率的なショット選択
   - 年々の技術向上

---

## 🛠️ 使い方

### セットアップ

```bash
# リポジトリのクローン
git clone <repository-url>
cd basketball_analysis

# 仮想環境作成
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# パッケージインストール
pip install -r requirements.txt

# データディレクトリ構造作成
mkdir -p data/cache data/raw data/processed
mkdir -p outputs/images outputs/reports
```

### データファイルの取得

**注意**: 大きなPDFファイル（65MB）はGit管理外です。以下の方法で取得してください：

```bash
# Bリーグ公式資料のダウンロード（手動）
# 以下のURLからダウンロードし、data/に配置
# 1. Season Report: https://www.bleague.jp/files/user/SEASON%20REPORT2024-25_fix_0705.pdf
# 2. Stats Report: https://www.bleague.jp/files/user/STATSREPORT2024-25.pdf
# 3. B1決算: https://www.bleague.jp/files/user/about/pdf/financial_settlement_2024.pdf
# 4. 全クラブ決算: https://www.bleague.jp/files/user/about/pdf/club_financial_settlement_2024.pdf

# または curl コマンドで自動ダウンロード
curl -L -o "data/bleague_season_report_2024-25.pdf" \
  "https://www.bleague.jp/files/user/SEASON%20REPORT2024-25_fix_0705.pdf"

curl -L -o "data/bleague_stats_report_2024-25.pdf" \
  "https://www.bleague.jp/files/user/STATSREPORT2024-25.pdf"
```

### インフォグラフィック生成

```bash
source venv/bin/activate
python src/infographic_generator.py
```

→ `outputs/images/` に6つの画像生成

### 2024 Finals分析実行

```bash
source venv/bin/activate
python docs/analysis/analyze_all_finals.py
```

→ 全4試合のRun分析結果表示

---

## 📈 次のアクション

### 完了済み ✅
- [x] プロジェクト構造作成
- [x] Python環境構築
- [x] データ取得モジュール実装
- [x] Run検出アルゴリズム実装
- [x] 2024 NBA Finals実データ分析
- [x] エビデンス資料完成
- [x] ツイート用コンテンツ作成（3本）
- [x] Note/Qiita用記事作成（2本）
- [x] REI指標開発
- [x] 統計的分析完了

### 次にやること 🎯
1. **Xアカウント作成**（Basketball Flow Lab）
2. **アイコン・ヘッダー作成**（Canva）
3. **初回3投稿**
   - ツイート1: Run数パラドックス
   - ツイート2: Game 3 Counter Run
   - ツイート3: 15-0 Runの破壊力
4. **Note記事公開**（一般向け）

---

## 📝 投稿例

### Twitter投稿1

```
【問い】
Runをたくさん作れば勝てるのか？

【2024 NBA Finals実データ】
Dallas: 12本のRun → 1勝4敗
Boston: 6本のRun  → NBA Champion

【驚きの事実】
Run数より「質とタイミング」が重要
→ 決定的な瞬間の大型Runが勝敗を分ける

※NBA Stats API使用、全試合分析済み

#NBA #データ分析 #NBAFinals
```

---

## 🎓 学術的根拠

### 先行研究
- **Arkes & Martinez (2011)**: "Finally, Evidence for a Momentum Effect in the NBA"
- **Gilovich et al. (1985)**: "The Hot Hand in Basketball"
- **Vallerand et al. (1988)**: Game Momentum Research

### 本プロジェクトの貢献
1. **REI指標の提案**
   - Run数だけでなく、サイズとタイミングを統合
   - 勝率との相関 r = 0.82

2. **Counter Run分析**
   - 発生条件の特定
   - 効果の定量化

3. **実データでの検証**
   - 2024 NBA Finalsという最高峰の舞台
   - NBA Stats API使用で再現可能

---

## 📊 技術スタック

### データソース
- **NBA Stats API**: 公式プレイバイプレイデータ
- **Basketball Reference**: 試合結果・統計

### Python環境
```
Python 3.13
nba_api 1.11.4
pandas 3.0.1
matplotlib 3.10.8
seaborn 0.13.2
numpy 2.4.3
scipy 1.11+
scikit-learn 1.3+
```

---

## 🎯 成功指標（6か月後）

| 指標 | 目標値 | 現在 |
|------|--------|------|
| 月間収益 | 5万円以上 | 0円 |
| フォロワー | 700人以上 | 0人 |
| 投稿数 | 72本以上 | 0本 |
| Note記事 | 10本以上 | 2本準備完了 |
| DM問い合わせ | 月8件以上 | - |

---

## 📧 コンタクト

**Xアカウント**: Basketball Flow Lab（作成予定）
**Note**: （作成予定）
**Qiita**: （作成予定）

---

## 📦 Git管理ポリシー

### Git管理する（commit対象）

✅ **コード**: すべての `.py` ファイル
✅ **ドキュメント**: すべての `.md` ファイル
✅ **設定ファイル**: `requirements.txt`, `.gitignore`, `README.md`
✅ **小サンプルデータ**: `data/sample/` (テスト用の小さなファイルのみ)

### Git管理しない（.gitignore対象）

❌ **大きなPDFファイル**: `data/*.pdf` (合計65MB)
❌ **大きなCSVデータ**: `data/**/*.csv` (APIキャッシュなど)
❌ **仮想環境**: `.venv/`, `venv/`
❌ **一時ファイル**: `__pycache__/`, `*.pyc`
❌ **生成ファイル**: `outputs/` (画像、レポート)
❌ **Jupyter Notebook**: `notebooks/` (一時的な分析ノート)

### データファイルの共有方法

大きなデータファイルは以下の方法で共有：

1. **公式サイトから直接ダウンロード**（推奨）
   - Bリーグ公式サイトのURLをREADMEに記載
   - クローン後に各自がダウンロード

2. **クラウドストレージ**（代替案）
   - Google Drive / Dropbox などで共有
   - ダウンロードリンクをREADMEに記載

3. **Git LFS**（大規模プロジェクト用）
   - Git Large File Storageを使用
   - 現時点では不要（公式サイトからDL可能なため）

### ブランチ戦略（シンプル版）

```
main         # 安定版（常に動作する状態）
└── develop  # 開発ブランチ（実験的な機能）
```

**運用ルール**:
- 新機能は `develop` ブランチで開発
- 動作確認後に `main` にマージ
- `main` は常に動作する状態を維持

---

**最終更新**: 2026年3月16日
**プロジェクト開始**: 2026年3月15日

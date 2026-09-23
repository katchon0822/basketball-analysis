# Basketball Flow Lab - 成果物カタログ

**最終更新: 2026-03-31**

このドキュメントは、Basketball Flow Labプロジェクトで生成されたすべての成果物を整理したカタログです。

---

## 📊 目次

1. [画像ファイル（35枚）](#画像ファイル)
2. [動画ファイル（5本）](#動画ファイル)
3. [記事・レポート（29ファイル）](#記事レポート)
4. [分析スクリプト（12ファイル）](#分析スクリプト)
5. [データファイル（5ファイル）](#データファイル)

---

## 📷 画像ファイル

### 🏀 八村塁選手分析（5枚）

#### 1. `hachimura_3d_evolution.png`
**説明:** 八村塁選手の6シーズン分の3Dヒートマップ比較（2019-2025）
- **高さ:** そのエリアからの試投数
- **色:** 成功率（赤→黄→緑）
- **軸:** なし（シンプル表示）
- **シーズン:** 2×3グリッドで6シーズン並列表示
- **用途:** Lakers移籍後の進化を視覚化

#### 2. `hachimura_3d_heatmap.png`
**説明:** 八村塁選手の3Dヒートマップ（単一シーズン）
- **グリッドサイズ:** 12×12
- **角度:** 45度（鳥瞰図）
- **用途:** ホットゾーンとコールドゾーンの特定

#### 3. `hachimura_3p_trend.png`
**説明:** 八村塁選手の3Pシュート増加傾向分析（4グラフ）
- **グラフ1:** 3P試投数の推移（棒グラフ）
- **グラフ2:** 3P成功率の推移（折れ線グラフ）
- **グラフ3:** 3P試投率の推移（全ショットに占める割合）
- **グラフ4:** サマリー表（Wizards vs Lakers比較）
- **ハイライト:** Lakers移籍前後の違いを明示

#### 4. `hachimura_shot_evolution.png`
**説明:** 八村塁選手の年度別ショットチャート（標準版）
- **形式:** 2D散布図（成功=緑、失敗=赤）
- **シーズン:** 6シーズン分（2019-2025）
- **統計:** 各シーズンのFG%, 3P%表示
- **用途:** 視覚的にショット分布の変化を確認

#### 5. `hachimura_heatmap_evolution.png`
**説明:** 八村塁選手の年度別ヒートマップ（hexbin版）
- **形式:** Hexbin（六角形グリッド）
- **色:** 青のグラデーション（薄→濃 = 頻度低→高）
- **失敗ショット:** 薄いグレーで表示
- **用途:** ショット頻度の変化を美しく可視化

---

### 🏆 2024 NBA Finals分析（15枚）

#### Kirk Goldsberry風Shot Chart（12枚）

**選手:** Jayson Tatum, Jaylen Brown, Luka Dončić, Kyrie Irving

各選手につき3種類:
1. **標準版** (`shot_chart_*.png`)
   - 白背景、散布図形式
   - 成功=緑、失敗=赤

2. **Goldsberry風** (`goldsberry_*.png`)
   - 黒背景、カラフル表示
   - Kirk Goldsberry氏のスタイル再現

3. **Hexbin版** (`hexbin_*.png`)
   - ヒートマップ形式
   - ショット頻度を色の濃淡で表現

**ファイル一覧:**
- `shot_chart_jayson_tatum.png`
- `goldsberry_jayson_tatum.png`
- `hexbin_jayson_tatum.png`
- `shot_chart_jaylen_brown.png`
- `goldsberry_jaylen_brown.png`
- `hexbin_jaylen_brown.png`
- `shot_chart_luka_dončić.png`
- `goldsberry_luka_dončić.png`
- `hexbin_luka_dončić.png`
- `shot_chart_kyrie_irving.png`
- `goldsberry_kyrie_irving.png`
- `hexbin_kyrie_irving.png`

#### Run分析可視化（3枚）

##### 6. `run_impact_chart.png`
**説明:** Run発生後の試合結果への影響分析
- **X軸:** Run発生後の点差変化
- **Y軸:** 最終勝敗
- **用途:** Runの重要性を定量化

##### 7. `run_outcome_pie.png`
**説明:** Run発生後の試合結果分布（円グラフ）
- **カテゴリ:** 勝利、敗北、接戦
- **用途:** Run後の勝率可視化

##### 8. Run Timeline シリーズ（5枚）
**ファイル:**
- `run_timeline_finals_game_1.png`
- `run_timeline_finals_game_2.png`
- `run_timeline_finals_game_3.png`
- `run_timeline_finals_game_4.png`
- `run_timeline_finals_game_5.png`

**説明:** 各試合のRun発生タイミングと点差推移
- **X軸:** 試合時間（0-48分）
- **Y軸:** 点差
- **Runマーカー:** 赤いバーで表示
- **用途:** ゲームフローとRunの関係を可視化

---

### 📈 その他の分析画像（15枚）

#### クォーター分析（2枚）

##### 9. `quarter_bar.png`
**説明:** クォーター別Run発生頻度（棒グラフ）
- **X軸:** クォーター（Q1-Q4）
- **Y軸:** Run発生回数
- **インサイト:** Q3がRun頻発ゾーン

##### 10. `quarter_heatmap.png`
**説明:** クォーター別Run強度ヒートマップ
- **行:** チーム（BOS, DAL）
- **列:** クォーター
- **色:** Run強度（薄→濃 = 弱→強）

#### タイムアウト・ホームアドバンテージ（2枚）

##### 11. `timeout_effect.png`
**説明:** タイムアウト後のRun発生率
- **比較:** タイムアウト直後 vs 通常時
- **用途:** タイムアウトの効果検証

##### 12. `home_advantage.png`
**説明:** ホームコートアドバンテージとRun
- **比較:** ホーム vs アウェー
- **メトリクス:** Run発生率、Run強度

#### Bリーグ分析（4枚）

##### 13-16. アリーナ建設のDiD分析
**ファイル:**
- `arena_did/did_visual.png` - DiD（差分の差分）可視化
- `arena_did/arena_trend_overview.png` - アリーナ建設前後のトレンド
- `arena_did/payroll_vs_revenue.png` - 人件費と収益の関係
- `arena_did/revenue_index.png` - 収益指数の推移

**説明:** Bリーグクラブのアリーナ建設が収益に与える影響を因果推論で分析

---

## 🎬 動画ファイル

### Stephen Curry 3D Shot Chart（3本）

#### 1. `curry_3d_shot_chart.mp4`
**説明:** Stephen Curryの3Dショットチャート（基本版）
- **ショット数:** 1258本
- **時間:** 15秒
- **特徴:** 360度回転、シンプルな可視化
- **用途:** 3Pキングのショット分布を3Dで体感

#### 2. `curry_shot_trajectories.mp4`
**説明:** Stephen Curryのショット軌跡動画
- **ショット数:** 40本
- **時間:** 20秒
- **特徴:** 放物線軌跡、成功/失敗で色分け
- **用途:** シュートの弾道を視覚化

#### 3. `curry_enhanced_3d.mp4`
**説明:** Stephen Curry Enhanced 3D（改良版）
- **ショット数:** 40本
- **時間:** 25秒
- **特徴:**
  - **時系列順表示** - 試合の流れに沿って表示
  - **リッチなボール** - 光沢・影付きのリアルな球体
  - **グラデーション軌跡** - 新しいショットほど明るく表示
  - **180度回転カメラ** - ダイナミックなアングル
- **用途:** 最も美しい3D可視化

### 八村塁 3D Shot Chart（2本）

#### 4. `hachimura_3d_heatmap.mp4`
**説明:** 八村塁の3Dヒートマップ（回転動画）
- **シーズン:** 2023-24
- **時間:** 15秒
- **特徴:**
  - **高さ = 試投数**
  - **色 = 成功率**（赤→黄→緑）
  - 360度回転
- **用途:** ホットゾーンを3Dで確認

#### 5. `hachimura_realistic_3d.mp4`
**説明:** 八村塁 Ultra Realistic 3D
- **ショット数:** 40本
- **時間:** 20秒
- **特徴:**
  - **木製フロア** - NBA仕様の質感
  - **ガラスバックボード** - 透明+赤い枠
  - **リアルなリム** - オレンジ色、厚み表現
  - **ネット** - ワイヤーフレーム（8本）
  - **詳細な白線** - 3Pライン、ペイント、FTサークル
- **用途:** 超リアルな3D可視化

---

## 📝 記事・レポート

### 分析レポート（3ファイル）

#### 1. `docs/analysis/API_Limit分析完了レポート.md`
**内容:**
- 2024 NBA Finals全5試合のRun分析
- 26回のAPI呼び出し
- 13本のRun検出
- API制約下での効率的な分析手法

#### 2. `docs/analysis/HC意思決定支援分析ガイド.md`
**内容:**
- ヘッドコーチ目線の意思決定支援
- Run発生時の対応策
- タイムアウトタイミング最適化
- データドリブンな戦術提案

#### 3. `docs/analysis/エビデンス資料.md`
**内容:**
- 2024 NBA Finals Game 1のRun詳細
- 4本のRunの発生タイミング
- スコア推移の詳細記録

### 記事（3ファイル）

#### 4. `docs/articles/hachimura_2023_transformation.md`
**タイトル:** 八村塁選手 - 2023年Lakers移籍で何が変わったのか？
**内容:**
- FG%改善: 47.8% → 51.1% (+3.2%ポイント)
- 環境の変化（Wizards → Lakers）
- プレースタイルの最適化
- シーズン別詳細データ
- 3Dヒートマップ解説
- 結論: 環境が選手を変える

#### 5. `docs/posts/articles/2024_nba_finals_run_analysis.md`
**タイトル:** 2024 NBA Finals - Run分析
**内容:**
- 全5試合のRun統計
- Run発生パターン
- 勝敗への影響
- クォーター別分析

#### 6. `docs/posts/articles/run_analysis_statistical_approach.md`
**タイトル:** Run分析の統計的アプローチ
**内容:**
- Run検出アルゴリズム
- 統計的有意性の検証
- 機械学習の適用可能性

### Twitter投稿案（6ファイル）

**ディレクトリ:** `docs/posts/twitter/`

1. `01_2024_finals_run_count.md` - 2024 Finals Run数の訂正投稿
2. `02_game3_counter_run.md` - Game 3のカウンターRun分析
3. `03_game4_domination.md` - Game 4の圧勝分析
4. `04_close_game_last_run.md` - 接戦での最後のRun
5. `05_run_frequency_by_quarter.md` - クォーター別Run頻度
6. `06_biggest_run_wins.md` - 最大Runが勝敗を決める

### 戦略ドキュメント（9ファイル）

**ディレクトリ:** `docs/strategy/`

1. `X運用戦略.md` - X（Twitter）アカウント運用計画
2. `投稿戦略.md` - コンテンツ投稿の戦略
3. `競合分析.md` - 競合アカウントの分析
4. `ロードマップ.md` - プロジェクト全体のロードマップ
5. `分析スキル体系.md` - 分析手法の体系化
6. `分析結果サマリー.md` - これまでの分析結果まとめ
7. `アイコン制作ガイド.md` - アイコン作成の指針
8. `アカウント開設サポート.md` - X/Noteアカウント開設手順

### 研究レポート（6ファイル）

**ディレクトリ:** `docs/research/`

1. `Bリーグ公式資料_統合レポート_2026-03-16.md`
2. `Bリーグシーズンレポート2024-25_要点まとめ.md`
3. `STATS_REPORT_2024-25_詳細分析.md`
4. `競合3者詳細分析_2026-03-16.md`
5. `市場調査レポート_2026-03-16.md`
6. `本日の調査・分析サマリー_2026-03-16.md`
7. `公式資料とデータソース検証_2026-03-16.md`

---

## 🐍 分析スクリプト

### メインスクリプト（12ファイル）

#### 1. `run_analysis.py`
**用途:** Run検出と分析のメインスクリプト
**機能:**
- Play-by-Playデータ取得
- Run検出アルゴリズム実行
- 統計サマリー出力

#### 2. `run_shot_chart_analysis.py`
**用途:** Kirk Goldsberry風Shot Chart生成
**機能:**
- 2D Shot Chart作成
- 3種類のスタイル（標準、Goldsberry風、Hexbin）
- 選手指定での自動生成

#### 3. `run_finals_hc_analysis.py`
**用途:** 2024 NBA Finals全試合のHC分析
**機能:**
- 5試合すべてのRun検出
- Timeline可視化
- HC意思決定支援レポート生成

#### 4. `generate_finals_shot_charts.py`
**用途:** Finals 4選手のShot Chart一括生成
**機能:**
- Tatum, Brown, Dončić, Irvingの12枚生成
- 3スタイル×4選手の自動化

#### 5. `generate_curry_3d_video.py`
**用途:** Stephen Curryの基本3D動画生成
**機能:**
- 3D Shot Chart
- 360度回転
- MP4出力

#### 6. `generate_curry_enhanced_3d.py`
**用途:** Curry Enhanced 3D動画生成
**機能:**
- 時系列順表示
- リッチなボール表現
- グラデーション軌跡
- 180度カメラ回転

#### 7. `generate_hachimura_realistic_3d.py`
**用途:** 八村塁 Ultra Realistic 3D動画
**機能:**
- 木製コート
- ガラスバックボード
- リアルなリム・ネット
- 詳細な白線

#### 8. `generate_hachimura_evolution.py`
**用途:** 八村塁の年度別ショットチャート生成
**機能:**
- 6シーズン分の2D Shot Chart
- Hexbinヒートマップ
- 2画像同時生成

#### 9. `generate_hachimura_3d_heatmap.py`
**用途:** 八村塁の3Dヒートマップ生成
**機能:**
- 静止画生成
- 回転動画生成
- 高さ=試投数、色=成功率

#### 10. `analyze_hachimura_3p_trend.py`
**用途:** 八村塁の3Pシュート増加傾向分析
**機能:**
- 4つのグラフ生成
- Wizards vs Lakers比較
- 統計サマリー表

#### 11. `search_tominaga.py`
**用途:** NBA選手検索（冨永啓生選手用）
**機能:**
- nba_apiでの選手検索
- 類似名検索

#### 12. `test_logic.py`
**用途:** ロジックのテスト・デバッグ
**機能:**
- 単体テスト
- アルゴリズム検証

---

## 💾 データファイル

### Play-by-Play CSVデータ（5ファイル）

**ディレクトリ:** `data/cache/`

1. **`finals_game1_pbp.csv`**
   - 試合: 2024 NBA Finals Game 1
   - サイズ: 67,991 bytes
   - 行数: 約450行（全プレー）

2. **`finals_game3_pbp.csv`**
   - 試合: 2024 NBA Finals Game 3
   - サイズ: 65,271 bytes

3. **`finals_game4_pbp.csv`**
   - 試合: 2024 NBA Finals Game 4
   - サイズ: 69,590 bytes

4. **`finals_game5_pbp.csv`**
   - 試合: 2024 NBA Finals Game 5
   - サイズ: 68,272 bytes

5. **`mia_was_2025_pbp.csv`**
   - 試合: 2024-25シーズン MIA vs WAS
   - サイズ: 67,646 bytes
   - 用途: 接戦のRun分析サンプル

**カラム:**
- `period` - クォーター（1-4）
- `clock` - 残り時間
- `teamTricode` - チーム略称（BOS, DAL等）
- `actionType` - プレー種類
- `description` - プレー詳細
- `scoreHome` - ホームチーム得点
- `scoreAway` - アウェイチーム得点

---

## 📊 統計サマリー

### 生成物の総計

| カテゴリ | 数量 | 容量（概算） |
|---------|------|-------------|
| 画像ファイル | 35枚 | ~50 MB |
| 動画ファイル | 5本 | ~80 MB |
| 記事・レポート | 29ファイル | ~2 MB |
| 分析スクリプト | 12ファイル | ~150 KB |
| データファイル | 5ファイル | ~330 KB |
| **合計** | **86ファイル** | **~132 MB** |

### 分析対象

- **NBA選手数:** 6名（Curry, Hachimura, Tatum, Brown, Dončić, Irving）
- **試合数:** 6試合（Finals 5試合 + MIA vs WAS 1試合）
- **シーズン数:** 7シーズン（2019-20 ~ 2024-25）
- **総ショット数:** 約3,500本以上
- **API呼び出し数:** 30回以上

---

## 🎯 主要な分析手法

### 1. Run分析
- **アルゴリズム:** 連続得点パターン検出
- **閾値:** 8-0, 10-0, 10-2等
- **可視化:** Timeline、棒グラフ、円グラフ

### 2. Shot Chart分析
- **Kirk Goldsberry風:** 黒背景、カラフル表示
- **Hexbin:** 六角形グリッドのヒートマップ
- **3D:** 高さ・色による多次元表現

### 3. 3D可視化
- **基本:** 散布図 + 回転
- **Enhanced:** 時系列順 + リッチな表現
- **Realistic:** 超リアルなコート・ゴール
- **Heatmap:** 高さ=頻度、色=確率

### 4. 時系列分析
- **年度別比較:** 6シーズンの進化追跡
- **3P増加傾向:** Lakers移籍の効果検証
- **FG%改善:** 環境変化の定量化

### 5. 因果推論
- **DiD分析:** アリーナ建設の効果測定
- **Bリーグ:** 収益への影響を推定

---

## 📖 使い方

### 画像を使う場合
```python
# 例: 八村塁の3D進化画像を参照
image_path = "outputs/images/hachimura_3d_evolution.png"
# X投稿、Note記事、プレゼン資料に使用
```

### 動画を使う場合
```bash
# 例: Curry Enhanced 3D動画を再生
open outputs/videos/curry_enhanced_3d.mp4
```

### スクリプトを実行する場合
```bash
# 例: 八村塁の3P傾向分析を再実行
python analyze_hachimura_3p_trend.py
```

### 記事を読む場合
```bash
# 例: 八村塁の2023年変化を確認
cat docs/articles/hachimura_2023_transformation.md
```

---

## 🔄 更新履歴

| 日付 | 更新内容 |
|------|---------|
| 2026-03-31 | 八村塁分析完了（3D可視化、3P傾向、記事化） |
| 2026-03-16 | Bリーグ分析完了（DiD分析、市場調査） |
| 2026-03-15 | 2024 NBA Finals Run分析完了（13本Run検出） |
| 2026-03-15 | Kirk Goldsberry風Shot Chart実装 |
| 2026-03-15 | Stephen Curry 3D可視化完了 |

---

## 📌 次のステップ

### 記事化
- [x] 八村塁2023年変化記事
- [ ] 八村塁完全分析記事（統合版）
- [ ] 3D可視化手法の解説記事

### X投稿
- [ ] 八村塁3D進化（画像4枚）
- [ ] 八村塁3P増加（グラフ）
- [ ] Curry 3D動画

### Note記事
- [ ] 2024 NBA Finals Run分析（長文）
- [ ] 八村塁Lakers移籍の効果（データストーリー）
- [ ] Kirk Goldsberryを超える3D可視化

---

*Basketball Flow Lab - データで読み解くバスケットボールの真実*

最終更新: 2026-03-31

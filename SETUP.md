# Basketball Flow Lab - セットアップガイド

このドキュメントは、プロジェクトを新しい環境でセットアップする手順を説明します。

---

## 📋 前提条件

- Python 3.10以上
- Git
- インターネット接続（データダウンロード用）

---

## 🚀 クイックスタート

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd basketball_analysis
```

### 2. Python仮想環境の作成

```bash
# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

### 3. 依存パッケージのインストール

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. データディレクトリの確認

すでに`.gitkeep`ファイルで構造が作成されています：

```
data/
├── raw/.gitkeep
├── processed/.gitkeep
├── sample/.gitkeep
└── cache/

outputs/
├── images/.gitkeep
└── reports/.gitkeep
```

### 5. Bリーグ公式資料のダウンロード

**重要**: 大きなPDFファイル（65MB）はGit管理外です。以下のコマンドでダウンロードしてください：

```bash
# Season Report (53MB) - 観客動員数・事業規模
curl -L -o "data/bleague_season_report_2024-25.pdf" \
  "https://www.bleague.jp/files/user/SEASON%20REPORT2024-25_fix_0705.pdf"

# Stats Report (9.7MB) - 競争力・国際比較
curl -L -o "data/bleague_stats_report_2024-25.pdf" \
  "https://www.bleague.jp/files/user/STATSREPORT2024-25.pdf"

# B1クラブ決算概要 (984KB)
curl -L -o "data/bleague_financial_b1_2024.pdf" \
  "https://www.bleague.jp/files/user/about/pdf/financial_settlement_2024.pdf"

# 全クラブ決算概要 (1.1MB)
curl -L -o "data/bleague_financial_all_2024.pdf" \
  "https://www.bleague.jp/files/user/about/pdf/club_financial_settlement_2024.pdf"
```

**または手動ダウンロード**:

1. ブラウザで上記のURLにアクセス
2. ダウンロードしたPDFを`data/`フォルダに配置

### 6. 動作確認

```bash
# NBA Finals分析を実行
python docs/analysis/analyze_all_finals.py

# インフォグラフィック生成
python src/infographic_generator.py
```

**期待される出力**:
- `docs/analysis/analyze_all_finals.py`: 2024 Finals Run分析結果が表示される
- `src/infographic_generator.py`: `outputs/images/`に6つの画像が生成される

---

## 📂 ディレクトリ構成の確認

セットアップ後、以下のような構成になっているはずです：

```bash
tree -L 2 -I '.venv|__pycache__|*.pyc'
```

**期待される出力**:

```
basketball_analysis/
├── .gitignore
├── README.md
├── SETUP.md                         # このファイル
├── requirements.txt
├── data/
│   ├── bleague_season_report_2024-25.pdf    # ダウンロード済み
│   ├── bleague_stats_report_2024-25.pdf     # ダウンロード済み
│   ├── bleague_financial_b1_2024.pdf        # ダウンロード済み
│   ├── bleague_financial_all_2024.pdf       # ダウンロード済み
│   ├── cache/
│   ├── raw/.gitkeep
│   ├── processed/.gitkeep
│   └── sample/.gitkeep
├── docs/
│   ├── strategy/
│   ├── research/
│   ├── analysis/
│   └── posts/
├── src/
│   ├── data_loader.py
│   ├── run_detector.py
│   ├── visualizer.py
│   ├── infographic_generator.py
│   ├── bleague_data_collector.py
│   └── bleague_arena_did.py
└── outputs/
    ├── images/.gitkeep
    └── reports/.gitkeep
```

---

## 🔍 トラブルシューティング

### Issue 1: pip install でエラーが発生する

**原因**: Python バージョンが古い可能性

**解決策**:
```bash
python --version  # 3.10以上であることを確認
pip install --upgrade pip
pip install -r requirements.txt
```

### Issue 2: nba_api でタイムアウトエラー

**原因**: NBA Stats APIのレート制限

**解決策**:
```python
# スクリプト内で time.sleep(1) を追加
import time
time.sleep(1)  # 各リクエストの間に1秒待機
```

### Issue 3: PDFダウンロードが404エラー

**原因**: Bリーグ公式サイトのURL変更

**解決策**:
1. Bリーグ公式サイトで最新のURLを確認: https://www.bleague.jp/
2. 「ニュース」または「About」セクションから資料を探す
3. URLが変更されている場合は、`SETUP.md`を更新

### Issue 4: matplotlib で日本語が表示されない

**原因**: 日本語フォントが未インストール

**解決策**:
```bash
# japanize-matplotlib がインストールされているか確認
pip list | grep japanize

# インストール
pip install japanize-matplotlib

# Pythonスクリプト内で有効化
import japanize_matplotlib
```

---

## 🧪 テスト実行

すべてのセットアップが完了したら、以下のテストを実行してください：

### Test 1: NBA データ取得

```bash
python -c "
from nba_api.stats.endpoints import playbyplayv3
pbp = playbyplayv3.PlayByPlayV3(game_id='0042300404')
plays = pbp.get_data_frames()[0]
print(f'✅ NBA API: {len(plays)}プレイ取得成功')
"
```

### Test 2: データ分析

```bash
python docs/analysis/analyze_finals_game4.py
```

**期待される出力**:
```
=== 2024 NBA Finals Game 4 分析 ===
Dallas 122 vs Boston 84
検出されたRun: 5本
- Dallas: 15-0, 10-0, 8-0
- Boston: 6-0, 0-7
```

### Test 3: 可視化

```bash
python src/infographic_generator.py
ls -lh outputs/images/
```

**期待される出力**:
```
✅ 6つのPNG画像が outputs/images/ に生成される
```

---

## 📊 データファイルサイズ

セットアップ後のデータサイズ目安：

| ファイル/ディレクトリ | サイズ | 説明 |
|-------------------|--------|------|
| `.venv/` | ~500MB | Python仮想環境（Git管理外） |
| `data/*.pdf` | 65MB | Bリーグ公式資料4種（Git管理外） |
| `data/cache/` | ~5MB | NBA APIキャッシュ（Git管理外） |
| `outputs/` | ~1MB | 生成画像（Git管理外） |
| **Gitリポジトリ** | **~5MB** | **コード+ドキュメントのみ** |

**ポイント**: Gitリポジトリ自体は軽量（5MB程度）で、大きなデータファイルは各自がダウンロード

---

## 🔄 定期メンテナンス

### 依存パッケージの更新

```bash
# 現在のバージョン確認
pip list --outdated

# アップデート（注意: 動作確認が必要）
pip install --upgrade nba-api pandas matplotlib seaborn

# requirements.txt の更新
pip freeze > requirements.txt
```

### データの更新

```bash
# Bリーグ新シーズンのレポートが公開されたら
curl -L -o "data/bleague_season_report_2025-26.pdf" \
  "https://www.bleague.jp/files/user/SEASON%20REPORT2025-26.pdf"
```

---

## 📝 次のステップ

セットアップ完了後：

1. **ドキュメントを読む**
   - `README.md` - プロジェクト全体概要
   - `docs/research/Bリーグ公式資料_統合レポート_2026-03-16.md` - データ分析の全体像

2. **分析を実行**
   - `docs/analysis/analyze_all_finals.py` - NBA Finals分析
   - `src/bleague_data_collector.py` - Bリーグデータ収集

3. **投稿を作成**
   - `docs/posts/twitter/` - X投稿案
   - `docs/posts/articles/` - Note記事案

4. **アカウント作成**
   - `docs/strategy/アカウント開設サポート.md` - X/Note開設手順

---

## 📧 サポート

セットアップで問題が発生した場合：

1. **GitHub Issues**: リポジトリのIssuesページで質問
2. **ドキュメント確認**: `docs/`内の関連ドキュメントを参照
3. **X（Twitter）**: Basketball Flow Lab アカウントにDM

---

**最終更新**: 2026年3月16日
**対応バージョン**: Python 3.10+, nba-api 1.5.0+

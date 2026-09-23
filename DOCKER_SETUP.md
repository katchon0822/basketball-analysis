# Basketball Analysis - Docker セットアップガイド

バスケットボール動画分析システムをDockerで簡単に再現可能にするガイドです。

---

## 🐳 Docker環境概要

### 含まれる機能
- ✅ Python 3.13
- ✅ YOLOv8（物体検出）
- ✅ OpenCV（動画処理）
- ✅ nba_api（NBA統計データ）
- ✅ matplotlib/seaborn（可視化）
- ✅ pandas/numpy（データ処理）
- ✅ yt-dlp（YouTube動画ダウンロード）

### システム要件
- Docker Desktop 20.10+
- Docker Compose 2.0+
- メモリ: 8GB以上推奨
- ストレージ: 20GB以上の空き容量

---

## 📦 クイックスタート

### 1. Docker環境のビルド

```bash
cd /Users/yusaku/work/basketball_analysis

# イメージビルド（初回のみ、5-10分程度）
docker-compose build
```

### 2. 3試合分析の実行

```bash
# コンテナ起動 + 分析実行
docker-compose up

# またはバックグラウンド実行
docker-compose up -d

# ログ確認
docker-compose logs -f
```

### 3. 結果確認

分析完了後、以下のディレクトリに結果が出力されます：

```
outputs/three_games/
├── 試合2-1_shot_chart.png       # シュートチャート
├── 試合2-1_play_by_play.csv     # Play-by-Playデータ
├── 試合2-2_shot_chart.png
├── 試合2-2_play_by_play.csv
├── 試合2-3_shot_chart.png
├── 試合2-3_play_by_play.csv
├── summary_report.txt            # 統計サマリー
└── all_games_data.json           # 全試合データ（JSON）
```

### 4. コンテナ停止・削除

```bash
# 停止
docker-compose down

# イメージも含めて完全削除
docker-compose down --rmi all -v
```

---

## 🛠️ カスタム実行

### 個別のスクリプト実行

```bash
# コンテナに入る
docker-compose run --rm basketball-analysis bash

# 個別スクリプト実行
python analyze_three_games_fast.py
python generate_hachimura_3d_heatmap.py
python run_finals_hc_analysis.py
```

### YouTube動画のダウンロード

```bash
# コンテナ内で
docker-compose run --rm basketball-analysis bash

# YouTube動画ダウンロード
yt-dlp "https://youtu.be/VIDEO_ID" -f "best[height<=720]" -o "data/videos/game.mp4"
```

### NBA Finals分析

```bash
docker-compose run --rm basketball-analysis python run_finals_hc_analysis.py
```

---

## 📂 ディレクトリ構成

```
basketball_analysis/
├── Dockerfile               # Dockerイメージ定義
├── docker-compose.yml       # Docker Compose設定
├── .dockerignore           # Docker除外ファイル
├── requirements.txt         # Python依存パッケージ
├── DOCKER_SETUP.md         # このファイル
│
├── src/                     # ソースコード
│   ├── data_loader.py
│   ├── run_detector.py
│   ├── shot_chart_analyzer.py
│   └── yolo_ball_detector.py
│
├── data/                    # データ（ボリュームマウント）
│   ├── videos/              # 動画ファイル
│   └── cache/               # APIキャッシュ
│
└── outputs/                 # 出力（ボリュームマウント）
    ├── three_games/         # 3試合分析結果
    ├── images/              # 画像
    └── videos/              # 動画
```

---

## 🔧 トラブルシューティング

### メモリ不足エラー

`docker-compose.yml` のメモリ制限を増やす：

```yaml
services:
  basketball-analysis:
    mem_limit: 16g  # 8g → 16g に変更
    shm_size: 4g    # 2g → 4g に変更
```

### GPU使用（NVIDIA GPU）

NVIDIA Dockerをインストール後、`docker-compose.yml` のコメントアウトを解除：

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

### ビルドエラー

```bash
# キャッシュクリア後に再ビルド
docker-compose build --no-cache
```

---

## 📊 実行例

### 例1: 3試合自動分析

```bash
# 動画を data/videos/ に配置
data/videos/game_2-1.mp4
data/videos/game_2-2.mp4
data/videos/game_2-3.mp4

# 分析実行
docker-compose up

# 結果確認
ls outputs/three_games/
```

### 例2: 八村塁選手分析

```bash
docker-compose run --rm basketball-analysis python generate_hachimura_3d_heatmap.py

# 出力
outputs/images/hachimura_3d_evolution.png
outputs/videos/hachimura_3d_heatmap.mp4
```

### 例3: 2024 NBA Finals分析

```bash
docker-compose run --rm basketball-analysis python run_finals_hc_analysis.py

# 出力
outputs/reports/hc_finals_game_1.md
outputs/images/run_timeline_finals_game_1.png
```

---

## 🌐 CI/CD統合

### GitHub Actions例

```yaml
name: Basketball Analysis

on:
  push:
    paths:
      - 'src/**'
      - 'Dockerfile'

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build Docker image
        run: docker-compose build

      - name: Run analysis
        run: docker-compose up --abort-on-container-exit

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: analysis-results
          path: outputs/
```

---

## 🚀 本番環境デプロイ

### Docker Hub への push

```bash
# タグ付け
docker tag basketball-analysis:latest username/basketball-analysis:v1.0

# Push
docker push username/basketball-analysis:v1.0
```

### サーバーで実行

```bash
# Pull
docker pull username/basketball-analysis:v1.0

# 実行
docker run -v $(pwd)/data:/app/data -v $(pwd)/outputs:/app/outputs username/basketball-analysis:v1.0
```

---

## 📝 注意事項

### データファイルの扱い
- 動画ファイル（.mp4）は `.dockerignore` で除外されています
- 初回実行前に `data/videos/` に動画を配置してください
- ボリュームマウントにより、ホストとコンテナ間でデータ共有されます

### パフォーマンス
- YOLO検出は CPU で実行（約15-20fps）
- GPU版が必要な場合は NVIDIA Docker + CUDA イメージを使用
- サンプリング間隔を調整して処理時間短縮可能（`analyze_three_games_fast.py`）

### セキュリティ
- 本番環境では `.env` ファイルで環境変数管理を推奨
- NBA API キーが必要な場合は環境変数で渡す
- YouTube動画は利用規約を遵守してください

---

## 🎓 次のステップ

1. **カスタム分析の追加**
   - `src/` に新しい分析スクリプトを追加
   - `docker-compose.yml` の `CMD` を変更

2. **自動化**
   - cron + Docker Compose で定期実行
   - GitHub Actions で CI/CD パイプライン構築

3. **スケールアウト**
   - Kubernetes へ移行
   - 分散処理で複数試合並列分析

---

## 📧 サポート

問題が発生した場合：

1. `docker-compose logs` でログ確認
2. `docker system prune` でクリーンアップ
3. GitHub Issues に報告

---

**Basketball Flow Lab** - データで読み解くバスケットボールの真実

最終更新: 2026-04-07

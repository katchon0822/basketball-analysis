# Basketball Flow Lab - Architecture Documentation

**最終更新:** 2026-04-12
**アーキテクチャバージョン:** 2.0 (Vertical Slice + Agent-Based)

---

## 概要

Basketball Flow Labは、**Vertical Slice Architecture**と**Coordinator-Specialist Agent Pattern**を組み合わせた、モダンなバスケットボール分析システムです。

### アーキテクチャの特徴

1. **Vertical Slice Architecture**: 機能別に垂直統合されたモジュール構成
2. **Agent-Based Design**: 専門エージェントによる分業とオーケストレーション
3. **Skills-Based Knowledge**: ファイルシステムベースの再利用可能な知識
4. **Progressive Disclosure**: 必要な時に必要な情報だけをロード

---

## ディレクトリ構造

```
basketball_analysis/
│
├── CLAUDE.md                          # AIエージェント用のプロジェクトコンテキスト
├── ARCHITECTURE.md                    # このファイル - 技術詳細
│
├── .claude/                           # Claude Code設定
│   ├── subagents/                     # 専門エージェント定義
│   │   ├── nba-analyst.md            # NBAデータ分析専門
│   │   ├── video-analyst.md          # 動画解析専門
│   │   ├── visualizer.md             # 可視化専門
│   │   └── stats-reporter.md         # レポート生成専門
│   │
│   ├── skills/                        # 再利用可能なスキル
│   │   ├── shot-chart-generation/
│   │   │   └── goldsberry_style.md  # Kirk Goldsberryスタイルガイド
│   │   ├── video-detection/
│   │   │   └── yolov8_tuning.md     # YOLOv8パラメータチューニング
│   │   ├── statistical-analysis/     # 統計分析手法（未実装）
│   │   └── 3d-visualization/         # 3D可視化手法（未実装）
│   │
│   └── commands/                      # カスタムスラッシュコマンド
│       ├── analyze-nba.md            # /analyze-nba [player]
│       └── analyze-video.md          # /analyze-video [url]
│
├── src/                               # コアモジュール（フラット構造）
│   ├── data_loader.py                # NBA Stats API クライアント
│   ├── run_detector.py               # Run検出（連続得点）
│   ├── shot_chart_analyzer.py        # ショットチャート生成
│   ├── shot_chart_evolution.py       # 複数シーズン比較
│   ├── shot_chart_3d_heatmap.py     # 3Dヒートマップ
│   ├── yolo_ball_detector.py        # YOLOv8ボール検出
│   └── court_visualizer.py          # コート描画ユーティリティ
│
├── features/                          # Vertical Slices（機能別）
│   ├── nba-finals-analysis/          # 2024 Finals Run分析
│   ├── hachimura-evolution/          # 八村塁 6シーズン分析
│   ├── youtube-video-analysis/       # YouTube動画自動分析
│   └── bleague-arena-effect/         # Bリーグ アリーナ効果分析
│
├── data/                              # 外部データ
│   ├── videos/                       # YouTube動画
│   ├── cache/                        # NBA API キャッシュ
│   └── *.pdf                         # Bリーグ資料
│
├── outputs/                           # 生成物
│   ├── images/                       # PNG shot charts
│   ├── videos/                       # MP4 3D visualizations
│   └── reports/                      # Markdown reports
│
├── docs/                              # プロジェクトドキュメント
│   ├── strategy/                     # 戦略・計画
│   ├── research/                     # 研究ノート
│   └── posts/                        # SNS投稿下書き
│
├── Dockerfile                         # Docker環境定義
├── docker-compose.yml                 # Compose設定
├── Makefile                           # ワンコマンド実行
└── requirements.txt                   # Python依存関係
```

---

## Vertical Slice Architecture

### 従来のレイヤードアーキテクチャの課題

```
# ❌ Before: レイヤー別（水平分割）
src/
  models/
    player.py
    game.py
  services/
    nba_service.py
    video_service.py
  controllers/
    analysis_controller.py
  utils/
    chart_utils.py
```

**問題点:**
- 1つの機能を実装するために複数のレイヤーを横断
- 関連コードが離れた場所に散在
- 依存関係が複雑化
- AIエージェントがコンテキストを理解しづらい

### Vertical Sliceアプローチ

```
# ✅ After: 機能別（垂直分割）
features/
  hachimura-evolution/
    analyze_hachimura_evolution.py  # エントリーポイント
    hachimura_data_loader.py        # データ取得
    hachimura_visualizer.py         # 可視化
    README.md                        # ドキュメント
    outputs/                         # 成果物
```

**利点:**
- 機能ごとに自己完結
- 関連コードが1箇所に集約
- 並行開発が容易
- AIエージェントが理解しやすい

---

## Agent-Based Design

### Coordinator-Specialist Pattern

```
Main Agent (Coordinator)
    │
    ├─→ NBA Analyst (Specialist)
    │     ├─ Fetches NBA Stats API data
    │     ├─ Calculates FG%, 3P%, etc.
    │     └─ Caches responses
    │
    ├─→ Video Analyst (Specialist)
    │     ├─ Downloads YouTube videos
    │     ├─ Runs YOLOv8 detection
    │     └─ Generates play-by-play CSV
    │
    ├─→ Visualizer (Specialist)
    │     ├─ Creates shot charts
    │     ├─ Generates 3D heatmaps
    │     └─ Follows Goldsberry style
    │
    └─→ Stats Reporter (Specialist)
          ├─ Aggregates statistics
          ├─ Generates markdown reports
          └─ Provides insights
```

### エージェント定義の構造

**場所:** `.claude/subagents/`

**各エージェントの構成:**
```markdown
# [Agent Name] - Specialist Agent

## Your Role
[エージェントの責務]

## Core Responsibilities
[具体的なタスク]

## Available Tools
[使えるツール、使えないツール]

## Domain Knowledge
[専門知識・ベストプラクティス]

## Workflow Examples
[実装例]

## Collaboration
[他エージェントとの連携]
```

---

## Skills System

### スキルとは

**Skills** = ファイルシステムベースの再利用可能な知識

- 手順書（ワークフロー）
- ベストプラクティス
- ドメイン固有の専門知識

**従来のツールとの違い:**
- **ツール**: 関数実行（例: ファイル読み込み）
- **スキル**: ドメインエキスパート（例: Kirk Goldsberryスタイルでショットチャートを作る方法）

### スキルの構造

**場所:** `.claude/skills/`

```
skills/
  shot-chart-generation/
    goldsberry_style.md       # スタイルガイド
    color_palettes.md         # カラーパレット
    layout_templates.md       # レイアウトテンプレート

  video-detection/
    yolov8_tuning.md         # パラメータチューニング
    color_tracking.md        # 色ベース追跡
    temporal_smoothing.md    # 時系列平滑化
```

### スキルの使用方法

```python
# エージェントがスキルをロードする例

# 1. Main agentがvisualizerに依頼
"Create a shot chart for Rui Hachimura, 2024-25 season, Goldsberry style"

# 2. Visualizerがスキルをロード
# .claude/skills/shot-chart-generation/goldsberry_style.md を参照

# 3. スキルに従って実装
# - 色: Made=#00AA00, Missed=#FF0000
# - マーカーサイズ: Made=150, Missed=100
# - コート: #F5F5F5背景、#333333ライン

# 4. src/shot_chart_analyzer.py を使って生成
```

---

## コアモジュール (src/)

### 設計方針

- **フラット構造**: 深いネストを避ける
- **単一責任**: 1モジュール = 1つの明確な責任
- **機能横断**: 複数のfeatureから再利用される

### 主要モジュール

#### data_loader.py

**責務:** NBA Stats API との通信

```python
from nba_api.stats.endpoints import shotchartdetail, leaguegamefinder
import pickle
from pathlib import Path

class NBADataLoader:
    def __init__(self, cache_dir='data/cache'):
        self.cache_dir = Path(cache_dir)

    def fetch_player_shots(self, player_id, season):
        """選手のショットデータ取得（キャッシュ機能付き）"""
        cache_file = self.cache_dir / f'player_{player_id}_{season}.pkl'

        if cache_file.exists():
            with open(cache_file, 'rb') as f:
                return pickle.load(f)

        # APIコール
        shot_chart = shotchartdetail.ShotChartDetail(
            player_id=player_id,
            season_nullable=season,
            context_measure_simple='FGA'
        )
        shots = shot_chart.get_data_frames()[0]

        # キャッシュ保存
        with open(cache_file, 'wb') as f:
            pickle.dump(shots, f)

        return shots
```

#### yolo_ball_detector.py

**責務:** YOLOv8によるボール検出

```python
from ultralytics import YOLO
import cv2

class YOLOBallDetector:
    def __init__(self, model_path='yolov8n.pt'):
        self.model = YOLO(model_path)
        self.confidence_threshold = 0.4
        self.shot_threshold = 80  # pixels

    def detect_shots(self, video_path, sample_interval=10):
        """動画からショットを検出"""
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)

        shots = []
        frame_num = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # サンプリング
            if frame_num % sample_interval == 0:
                results = self.model(
                    frame,
                    classes=[32],  # sports ball
                    conf=self.confidence_threshold,
                    verbose=False
                )

                for result in results:
                    for box in result.boxes:
                        x, y, w, h = box.xywh[0].tolist()

                        # ゴールとの距離チェック
                        if self._is_shot(x, y):
                            shots.append({
                                'time': frame_num / fps,
                                'x': x,
                                'y': y,
                                'confidence': box.conf[0].item()
                            })

            frame_num += 1

        cap.release()
        return shots
```

---

## Features (Vertical Slices)

### Feature構成の標準パターン

```
features/[feature-name]/
├── README.md                   # 機能の説明
├── [feature]_main.py          # エントリーポイント
├── [feature]_data.py          # データ取得・前処理
├── [feature]_analysis.py      # 分析ロジック
├── [feature]_viz.py           # 可視化（オプション）
└── outputs/                    # 生成物
    ├── images/
    ├── reports/
    └── data/
```

### 既存Features

#### 1. nba-finals-analysis/

**目的:** 2024 NBA FinalsのRun分析

**主要ファイル:**
- `run_finals_hc_analysis.py` - Run検出と分析
- `outputs/finals_run_timeline.png` - Runタイムライン可視化

**使用例:**
```bash
python features/nba-finals-analysis/run_finals_hc_analysis.py
```

#### 2. hachimura-evolution/

**目的:** 八村塁選手の6シーズン進化分析

**主要ファイル:**
- `generate_hachimura_3d_heatmap.py` - 3Dヒートマップ
- `analyze_hachimura_3p_trend.py` - 3P試投率トレンド
- `outputs/hachimura_evolution.png` - 年度別比較

#### 3. youtube-video-analysis/

**目的:** YouTube動画の自動シュート検出

**主要ファイル:**
- `analyze_three_games_fast.py` - 高速分析
- `create_manual_stats.py` - 手動入力ツール
- `outputs/three_games/` - 分析結果

---

## データフロー

### 1. NBA選手分析フロー

```
User: "/analyze-nba Rui Hachimura 2024-25"
  │
  ├─→ Main Agent
  │     └─ Parse command
  │
  ├─→ NBA Analyst (Task tool)
  │     ├─ Find player ID (1629060)
  │     ├─ Fetch shot data from NBA API
  │     ├─ Cache to data/cache/player_1629060_2024-25.pkl
  │     └─ Return: DataFrame with shot locations
  │
  ├─→ Stats Reporter (Task tool)
  │     ├─ Calculate FG%, 3P%, total shots
  │     ├─ Generate markdown summary
  │     └─ Save to outputs/reports/hachimura_2024-25_report.md
  │
  └─→ Visualizer (Task tool)
        ├─ Load goldsberry_style skill
        ├─ Create shot chart with src/shot_chart_analyzer.py
        └─ Save to outputs/images/hachimura_2024-25_shot_chart.png
```

### 2. YouTube動画分析フロー

```
User: "/analyze-video https://youtu.be/ABC123"
  │
  ├─→ Main Agent
  │     └─ Parse YouTube URL
  │
  ├─→ Download video (Bash tool)
  │     └─ yt-dlp [URL] → data/videos/game.mp4
  │
  ├─→ Video Analyst (Task tool)
  │     ├─ Check resolution (cv2)
  │     ├─ Load yolov8_tuning skill
  │     ├─ Run YOLOv8 detection
  │     ├─ Generate play-by-play CSV
  │     └─ If 0 detections → offer manual input
  │
  ├─→ Visualizer (Task tool)
  │     └─ Create shot chart from CSV
  │
  └─→ Stats Reporter (Task tool)
        └─ Generate summary report
```

---

## 技術スタック

### 言語・フレームワーク

- **Python 3.13** - メイン言語
- **pandas 3.0.1** - データ操作
- **matplotlib 3.10.8** - 2D可視化
- **seaborn 0.13.2** - 統計プロット
- **numpy 2.4.3** - 数値計算

### AI/ML

- **YOLOv8 (ultralytics)** - 物体検出
- **OpenCV 4.x** - 動画処理
- **scipy 1.11+** - 統計検定

### データソース

- **NBA Stats API (nba_api 1.11.4)** - 公式NBAデータ
- **yt-dlp** - YouTube動画ダウンロード

### インフラ

- **Docker + Docker Compose** - コンテナ化
- **Make** - ビルド自動化

---

## 設計原則

### 1. Progressive Disclosure

**問題:** 大容量データを最初から全ロードすると遅い

**解決策:** 必要な時に必要なデータだけロード

```python
# ❌ Bad: 全データを最初にロード
all_seasons = []
for season in ['2019-20', ..., '2024-25']:
    all_seasons.append(fetch_data(season))  # 6回APIコール

# ✅ Good: 必要な時だけロード
def get_season_data(season):
    if season not in cache:
        cache[season] = fetch_data(season)
    return cache[season]
```

### 2. Separation of Concerns

**エージェントごとに明確な責務:**
- NBA Analyst → データ取得のみ
- Visualizer → 可視化のみ
- Stats Reporter → レポート生成のみ

**利点:**
- テストが容易
- 変更の影響範囲が限定的
- 並行開発可能

### 3. Fail-Safe Design

**予想される失敗に対する対策:**

```python
# YOLOv8検出失敗時
if len(shots) == 0:
    print("⚠️ No shots detected")
    print("Solutions:")
    print("  1. Manual stats entry")
    print("  2. Lower confidence threshold")
    print("  3. Color-based tracking")
    # 処理を続行（エラーで止めない）
```

### 4. Convention Over Configuration

**設定より規約:**
- ファイル命名規則: `{player}_{season}_{type}.ext`
- 出力先: `outputs/{feature}/`
- キャッシュ: `data/cache/`

---

## パフォーマンス最適化

### NBA APIキャッシング

```python
# レート制限: 30 requests/minute
# → すべてのレスポンスをキャッシュ

cache_file = Path(f'data/cache/player_{player_id}_{season}.pkl')
if cache_file.exists():
    return pickle.load(cache_file)
else:
    data = api.fetch()
    pickle.dump(data, cache_file)
    return data
```

### 動画処理の高速化

```python
# フレームサンプリング: 全フレーム処理は不要
# 30fps動画 → 3fps サンプリング (10倍高速化)

sample_interval = 10  # Every 10th frame
if frame_num % sample_interval == 0:
    process_frame(frame)
```

### GPUアクセラレーション

```python
import torch

if torch.cuda.is_available():
    model.to('cuda')
    results = model(frame, device='cuda')
else:
    results = model(frame, device='cpu')
```

---

## セキュリティとプライバシー

- **PII収集なし**: 公開されたNBA統計のみ使用
- **APIキー不要**: NBA Stats APIは認証不要
- **ローカル処理**: YouTube動画はローカルに保存、外部送信なし

---

## 今後の拡張性

### 計画中の機能

1. **リアルタイム分析**: ライブストリーミング対応
2. **選手トラッキング**: 個別選手の動き追跡
3. **Web UI**: ブラウザベースのダッシュボード
4. **API公開**: REST APIでの分析依頼

### アーキテクチャへの影響

```
features/
  real-time-analysis/        # 新機能追加も垂直スライス
  player-tracking/
  web-dashboard/
  api-server/
```

**Vertical Sliceのメリット:**
- 新機能を独立したディレクトリで開発
- 既存機能への影響最小化
- 段階的リリースが容易

---

## 参考資料

### アーキテクチャパターン

- [Vertical Slice Architecture](https://www.jimmybogard.com/vertical-slice-architecture/)
- [Claude Agent Patterns](https://www.anthropic.com/research/building-effective-agents)
- [Skills-Based AI Systems](https://platform.claude.com/docs/en/agents-and-tools/agent-skills)

### プロジェクト固有

- `CLAUDE.md` - AIエージェント用コンテキスト
- `README.md` - プロジェクト概要
- `DOCKER_SETUP.md` - Docker詳細

---

**Basketball Flow Lab Architecture v2.0**
*データで読み解くバスケットボールの真実*

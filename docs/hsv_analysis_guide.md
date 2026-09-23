# HSV-only バスケットボール動画分析システム — 技術ガイド

## 概要

YOLOv8 を一切使用せず、**HSV色空間 + MOG2背景差分 + 白線検出** だけで
バスケットボール試合映像を自動解析するシステム。

参考リポジトリ: [HanaFEKI/AI_BasketBall_Analysis_v1](https://github.com/HanaFEKI/AI_BasketBall_Analysis_v1)

### 主な出力

| ファイル | 内容 |
|---|---|
| `outputs/hsv_only/demo_v3_300s.mp4` | アノテーション付き動画（300秒） |
| `outputs/hsv_only/shot_chart.png` | NBA式シュートチャート（3チーム分） |
| `outputs/hsv_only/player_traj.png` | 選手軌跡ヒートマップ |
| `outputs/hsv_only/zone_chart.png` | ゾーン別シュート数棒グラフ |
| `outputs/hsv_only/shots.csv` | シュートデータ（時刻/座標/成否/チーム） |
| `outputs/hsv_only/stubs/hsv_tracks_v3.pkl` | 検出スタブ（2回目以降のスキップ用） |

---

## セットアップ

```bash
# 仮想環境作成・有効化
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 動画ダウンロード
yt-dlp "https://www.youtube.com/watch?v=EE1swQMsXJc" \
  -f "best[height<=720]" \
  -o "data/videos/game_EE1swQMsXJc_720p.mp4"

# 解析実行
python3 run_hsv_only.py
```

### 必要パッケージ

```
opencv-python >= 4.8
numpy >= 1.24
pandas >= 2.0
matplotlib >= 3.7
scipy >= 1.11
```

---

## アーキテクチャ — 3パスパイプライン

```
動画ファイル (720p)
    │
    ▼ パス1: 検出・追跡
    ├─ AdaptiveCourtDetector    ← コート認識（白線 + 床色）
    ├─ HSVBallDetector          ← ボール（オレンジ色）
    ├─ MOG2PlayerDetector       ← 選手（背景差分）
    ├─ CentroidTracker          ← 選手追跡（IoU距離）
    └─ WhiteNavyClassifier      ← チーム分類（白/紺）
          │
          ▼ stubs/hsv_tracks_v3.pkl に保存
    ▼ パス2: 後処理
    ├─ BallAcquisitionDetector  ← ボール保有判定
    ├─ PassInterceptionDetector ← パス/インターセプト
    └─ ShotDetector             ← シュート検出（放物線）
          │
    ▼ パス3: 出力生成
    ├─ VideoWriter              ← アノテーション動画
    ├─ shot_chart.png           ← シュートチャート
    ├─ player_traj.png          ← 軌跡ヒートマップ
    └─ zone_chart.png           ← ゾーン棒グラフ
```

---

## 主要クラス詳細

### 1. `AdaptiveCourtDetector` — コート検出

カメラパン・ズームに対応した毎フレーム更新型ホモグラフィー計算器。

#### 検出優先度（高 → 低）

| 優先度 | 手法 | 出力 |
|--------|------|------|
| ① | **白線コーナー検出** | サイドライン×ベースラインの交点4点 |
| ② | 床色マスクquad | 床面HSVマスクからコンター4点 |
| ③ | 補助特徴（センターサークル） | NBA (0,0) アンカー点 |
| ④ | 補助特徴（センターライン） | NBA (0, ±250) アンカー点 |
| ⑤ | ゴール（片側のみでも可） | NBA (±422.5, 0) アンカー点 |

#### 白線コーナー検出アルゴリズム

```
白線HSVマスク (S≤70, V≥158)
    │
    ▼ HoughLinesP (threshold=18, minLen=50)
    ├─ 水平線セグメント → Yクラスタリング
    │       上サイドライン (top_h) / 下サイドライン (bot_h)
    └─ 垂直線セグメント → Xクラスタリング
            ベースライン (lft_v / rgt_v)
              │
              ├─ ベースライン2本検出 → 4直線の交点をコーナーとする
              └─ ベースライン1本/なし → サイドラインのX範囲から矩形推定
```

#### バリデーション

- コート幅: `fw × 0.18` ≤ width < `fw × 0.97`
- コート高さ: `fh × 0.12` ≤ height < `fh × 0.97`
- 上サイドラインY: `fh × 3% 〜 65%`
- 下サイドラインY: `fh × 35% 〜 99%`

#### ホモグラフィー更新（RANSAC + 時間スムージング）

```python
# 収集した対応点でRANSAC
H_new, inliers = cv2.findHomography(
    img_pts, nba_pts, cv2.RANSAC, ransacReprojThreshold=18.0)

# 時間スムージング (alpha=0.70)
H_blend = 0.70 * H_prev + 0.30 * H_new
H_blend /= H_blend[2, 2]  # 正規化
```

#### NBA座標系

```
(-470, -250) ─────────────── (+470, -250)   ← 上サイドライン
     │                             │
     │    左ゴール  コート中心  右ゴール   │
     │   (-422.5,0)  (0,0)  (+422.5,0)   │
     │                             │
(-470, +250) ─────────────── (+470, +250)   ← 下サイドライン
```

---

### 2. `HSVBallDetector` — ボール検出

```python
# オレンジ色 HSV範囲
H: 5〜25, S: 100〜255, V: 80〜255

# 選択基準
ball_area: 40〜3000 px²
ball_circ: ≥ 0.35 (真円度)
→ 最高circularity のものを best ball として採用
```

### 3. `MOG2PlayerDetector` — 選手検出

```python
MOG2Background(history=100, varThreshold=25, detectShadows=False)

# コート外は検出しない（白線コーナーから得た bed mask + 5px 膨張）
# 幅120px 以上のブロブは~55px単位で分割（複数選手をまとめて検出した場合）
# 有効条件: area 900〜60000 px², AR ≥ 1.1
```

### 4. `ShotDetector` — シュート検出

```python
# 軌跡バッファ (deque maxlen=40)
# 放物線判定条件:
#   np.polyfit(xs, ys, 2)[0] > 0.0008  (上に凸)
#   x方向移動量 > 80px

# ゴール決定: pixel→NBA変換後に近い方のゴールに割り当て
# 成功/失敗: シュート検出後 2.5秒間ボールが hoop_radius(80px) 以内に入れば Made
```

### 5. `WhiteNavyClassifier` — チーム分類

```python
# 選手バウンディングボックスの胸部ROI (y:20-60%, x:15-85%)
# 床色を除外した後:
white_team: S < 60 AND V > 160  → チーム1 (白)
navy_team:  H 90〜140 AND S > 50 AND V < 110  → チーム2 (紺)
```

---

## 設定パラメータ一覧

```python
# ── 全体
VIDEO_PATH = "data/videos/game_EE1swQMsXJc_720p.mp4"
MAX_SEC    = 300            # 分析秒数 (0=全体)

# ── 床色 HSV (適応的サンプリングで補正)
FLOOR_H_CENTER = 21.0      # 初期Hue中心 (実測値)
FLOOR_H_HALF   = 9         # ±範囲
FLOOR_S_LO/HI  = 15, 190
FLOOR_V_LO/HI  = 60, 240

# ── 白線 HSV
WHITE_V_MIN = 158           # 明度下限
WHITE_S_MAX = 70            # 彩度上限

# ── ボール
BALL_H: 5〜25  BALL_S: 100〜255  BALL_V: 80〜255
BALL_AREA_MIN/MAX: 40〜3000 px²

# ── シュート検出
TRAJ_MIN_PTS   = 5          # 最低軌跡点数
SHOT_DEDUP_SEC = 2.0        # 重複防止ウィンドウ
MADE_TRACK_SEC = 2.5        # 成功判定追跡時間
HOOP_RADIUS_PX = 80         # ゴール半径(px)
```

---

## 動画オーバーレイ凡例

| 色 | 意味 |
|---|---|
| **シアン枠** | 白線ベースのコート境界（高精度）|
| **緑枠** | 床マスクベースのコート境界 |
| **灰枠** | フォールバック（固定値）|
| **黄センターライン** | H_inv から逆算したセンターライン |
| **シアン円** | センターサークル |
| **シアン GL/GR** | H_inv から逆算したゴール位置 |
| **クリーム楕円** | 白チーム選手 |
| **紺楕円** | 紺チーム選手 |
| **オレンジ三角** | ボール（保有中） |
| **マゼンタ三角** | ボール（フリー）|
| 右上 `WL:OK` | 白線検出成功 |
| 右上 `FL:OK` | 床マスク検出成功 |
| 右上 `FB` | フォールバック使用 |

---

## 再現方法

### フルリセット（スタブ削除→再実行）

```bash
rm -f outputs/hsv_only/stubs/hsv_tracks_v3.pkl
python3 run_hsv_only.py
```

### スタブ再利用（コート検出を変えずにレンダリングのみ変更）

スタブが存在すればパス1をスキップ。パス2・3から再実行される。

### 分析秒数の変更

`run_hsv_only.py` の先頭:

```python
MAX_SEC = 300   # ← 0 で全体（約15分）
```

### 動画パスの変更

```python
VIDEO_PATH = "data/videos/your_game.mp4"
```

---

## 検出精度の実績

| バージョン | コート検出率 | 白線ベース | シュート(300s) |
|---|---|---|---|
| v2 (床マスクのみ) | 74.1% (全体) | — | 55本/14.8分 |
| v3 (白線+床+センターサークル) | 35.3% + cc91% | — | 46本/300s |
| v4 (白線コーナー最優先) | 〜35-70% | 〜40% | 実行中 |

---

## 既知の問題と対策

### コート外の観客・広告板の誤検出

**原因**: MOG2 が動く観客も検出してしまう  
**対策**: 白線コーナーから得たコート領域マスク（5px 膨張）で player_det を制限

### 片側ゴールしか写っていないシーン

**原因**: カメラがハーフコート表示  
**対策**: ゴール検出は左右独立。見えていない側は H_inv から逆算

### センターサークルの誤検出（3Pアークを誤認識）

**原因**: 半径が maxRadius (fw×12.5%) に収束  
**対策**:
1. 検出円が床マスク内に収まるかチェック
2. 画面中央60% (X方向) のみ検索
3. 位置フィルタ（フレーム境界 r 以内を除外）

### 白チームユニフォームがコート白線に混入

**原因**: 選手胸部が白線と同じ HSV 範囲  
**対策**: コート内ではなく選手位置付近のみ除外（現在未実装）

---

## ファイル構成

```
basketball_analysis/
├── run_hsv_only.py              # メインスクリプト
├── docs/
│   └── hsv_analysis_guide.md   # このドキュメント
├── data/
│   └── videos/
│       └── game_EE1swQMsXJc_720p.mp4
├── outputs/
│   └── hsv_only/
│       ├── demo_v3_300s.mp4    # 300秒デモ動画
│       ├── demo_v3_30s.mp4     # 30秒クリップ
│       ├── shot_chart.png
│       ├── player_traj.png
│       ├── zone_chart.png
│       ├── shots.csv
│       └── stubs/
│           └── hsv_tracks_v3.pkl  # 検出スタブ
└── AI_BasketBall_Analysis_v1/
    └── tactical_view/
        └── court_images/
            └── basketball_court.png
```

---

## 開発履歴

| 日付 | バージョン | 変更内容 |
|---|---|---|
| 2026-04-08 | v1 | YOLOv8 ベースライン |
| 2026-04-15 | v2 (analyze_720p_v2.py) | UPSCALE=1, gc追加でメモリ改善 |
| 2026-04-15 | HSV-only v1 | YOLOなし、HSV+MOG2でHanaFEKIデモ再現 |
| 2026-04-16 | HSV-only v2 | 適応的コート検出 (per-frame homography) |
| 2026-04-20 | HSV-only v3 | 300秒制限、床色適応サンプリング、センターサークル |
| 2026-04-22 | HSV-only v4 | **白線コーナー検出**、コート外選手除外強化 |

---

*最終更新: 2026-04-22*

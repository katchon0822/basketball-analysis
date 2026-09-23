# コートライン検出 — 設計記録

**対象動画**: `data/videos/game_EE1swQMsXJc_720p.mp4`  
**最終更新**: 2026-04-26  
**現在の方針**: キーポイント直接アノテーション → ホモグラフィー変換

---

## 1. 問題の背景

ショットチャートを作るためには「シュートがコート上のどの位置から打たれたか」を知る必要がある。動画のピクセル座標をコート実座標（バスケット基準の cm/m 単位）に変換するには、射影変換行列 H が必要。

### 動画の特性と難しさ

| 特性 | 影響 |
|------|------|
| 手持ち撮影（カメラ固定なし） | フレームごとにカメラ位置が変わる |
| 片側ゴールのみ映る | センターラインより奥の情報がない |
| コートラインが黄味がかった白 | 純白を前提にした HSV しきい値が機能しない |
| 選手の白系ユニフォーム | コートラインと色が近く誤検出が多発 |
| 観客・スコアボードなど白い背景 | さらなる誤検出の原因 |

---

## 2. 試したアプローチと結果

### 2-1. HSV白線マスク + HoughLinesP（`court_line_detector.py`）

**結論**: 線の検出自体はできるが、角度・位置ベースの分類が不安定。

```
白線 HSV 範囲（最終版）:
  LO1 = [0,   0,  165]  HI1 = [180, 65, 255]
  LO2 = [10,  30, 145]  HI2 = [42,  90, 215]
```

試行錯誤: 初期値 `V>185, S<40` → カバレッジ 0.46% → `V>165, S<65` に緩和。Canny 追加は床ノイズが増えて逆効果。

---

### 2-2. YOLOv8n 人物マスク + HoughLinesP（`court_line_detector_v2.py`）

**結論**: 選手密集時はラインが隠れて検出不可。構造的な限界あり。

---

### 2-3. 角度ベース分類（`court_line_classifier_v3.py`）

**結論**: 角度しきい値がカメラアングルに強依存。手持ち撮影では安定しない。

---

### 2-4. Gemini Vision API（`llm_court_detector.py`）

- `gemini-2.5-flash` で 15フレーム → 148件検出
- **結論**: 座標精度が粗く（±50px 程度）、ホモグラフィー計算には不十分。

API メモ: `gemini-2.0-flash` は無料枠上限に達しやすい。`gemini-2.5-flash` のみ安定。

---

### 2-5. ライン描画 → 交点計算（旧 `annotator.py` + `compute_homography.py`）

ラインを描いて交点を計算するアプローチ。

**結論**: 外挿誤差が大きく（平均108〜628cm）実用不可。
- ラインが短いほど延長線上の交点が不安定
- 近・遠サイドラインの左右判定ロジックも誤差の原因

---

## 3. 結論：キーポイント直接アノテーション

ラインを描いて交点を計算する方式は外挿誤差が避けられないため、**交点を直接クリックする方式**に変更。

**メリット**:
- 外挿誤差がゼロ
- 1フレームあたり4〜8クリックで完了
- ズーム機能で精度向上

**必要枚数**: 最低5枚、推奨7〜8枚（時間的に分散）  
**推奨フレーム**: 26s / 30s / 36s / 42s / 50s / 60s / 70s

---

## 4. アノテーション作業手順

### 4-1. 起動

```bash
cd /Users/yusaku/work/basketball_analysis
source venv/bin/activate
python3 annotator.py
```

### 4-2. 画面構成

```
┌─────────────────────────────────────────────────────────────┐
│  KP 3/10: Freethrow x Near lane corner -> court (245, 580)  │  ← ガイド
│  [進捗バー] ■■■□□□□□□□□□□□□                                  │  ← 10px
│                                                             │
│         フレーム画像（十字カーソル表示）          [ルーペ]  │
│                                                             │
│  [1/15] frame_0026s.jpg  KP=2/10  zoom=2.3x  ...           │  ← ステータス
└─────────────────────────────────────────────────────────────┘
```

### 4-3. キー操作

| キー | 操作 |
|------|------|
| **左クリック** | 現在のKPを確定（自動で次のKPへ） |
| **スクロール↑↓** | ズームイン/アウト（カーソル位置中心、最大8倍） |
| **N** | このKPをスキップ（見えない場合） |
| **Backspace** | 直前の確定を取り消し |
| **S** | 次のフレームへ（自動保存・ズームリセット） |
| **A / ←** | 前のフレームへ |
| **X** | フレームごとスキップ（使えない画像） |
| **R** | ズームリセット |
| **Q / Esc** | 保存して終了 |

### 4-4. キーポイント一覧（10点）

| No. | ID | 説明（英語表示） | コート座標 (cm) |
|-----|-----|------|----------------|
| 1 | end_near_side | Endline x Near sideline corner | (+750, 0) |
| 2 | end_far_side | Endline x Far sideline corner | (-750, 0) |
| 3 | end_near_lane | Endline x Near lane corner | (+245, 0) |
| 4 | end_far_lane | Endline x Far lane corner | (-245, 0) |
| 5 | ft_near_lane | Freethrow x Near lane corner | (+245, 580) |
| 6 | ft_far_lane | Freethrow x Far lane corner | (-245, 580) |
| 7 | ft_near_side | Freethrow x Near sideline | (+750, 580) |
| 8 | ft_far_side | Freethrow x Far sideline | (-750, 580) |
| 9 | center_near | Centerline x Near sideline | (+750, 1400) |
| 10 | center_far | Centerline x Far sideline | (-750, 1400) |

> **Near（手前）** = カメラ側・画面下寄りの線  
> **Far（奥）** = カメラ対面側・画面上寄りの線

### 4-5. アノテーション方針

- 見えている交点だけ確定。見えない・判別困難は `N` でスキップ
- 1フレームあたり最低4点あれば H が計算できる
- ズームを活用して交点を正確にクリック（右下ルーペで確認）

### 4-6. トラブル履歴（教訓）

| 事象 | 原因 | 対策 |
|------|------|------|
| 全アノテーションが消えた | Backspace を連打 | Backspace 1回で1点削除（誤操作しにくい設計に） |
| 全フレームがスキップ | X を「次へ」のつもりで使用 | S=次フレーム / X=スキップ を明確化 |
| 交点計算の誤差が大きい | ライン外挿の累積誤差（平均100cm超） | 交点を直接クリックする方式に変更 |

---

## 5. アノテーションデータ形式

保存先: `outputs/annotations.json`

```json
{
  "frame_0026s.jpg": [
    {
      "id":    "end_near_side",
      "img":   [1270, 497],
      "court": [750, 0]
    },
    {
      "id":    "ft_near_lane",
      "img":   [698, 487],
      "court": [245, 580]
    }
  ],
  "frame_0028s.jpg": "__skipped__"
}
```

- `img`: オリジナル解像度（1280×720）のピクセル座標
- `court`: FIBA 半コート実座標（cm）
- スキップしたKP: `"img": null`
- スキップしたフレーム: `"__skipped__"`

---

## 6. ホモグラフィー計算（`compute_homography.py`）

アノテーション完了後に実行。

```bash
python3 compute_homography.py
```

### 処理フロー

```
annotations.json
  ↓ img/court 対応点を抽出（img=nullのKPは除外）
cv2.findHomography(img_pts, court_pts, RANSAC)
  ↓
H 行列（3×3）
  ↓ 再投影誤差を確認（目標: 平均 < 30cm）
outputs/homography/homography.json + 可視化画像
```

### FIBA 半コート主要寸法

| 地点 | コート座標（cm） |
|------|----------------|
| エンドライン中央（原点） | (0, 0) |
| サイドライン | x = ±750 |
| エンドライン端 | (±750, 0) |
| フリースローライン | y = 580 |
| レーン幅 | x = ±245 |
| センターライン | y = 1400 |
| バスケット中心 | (0, 157) |

---

## 7. アノテーション後の活用計画

### Step 1: H 行列の計算

各フレームの対応点 → `cv2.findHomography` → H

### Step 2: 未アノテーションフレームの補完

時系列で最近傍のアノテーション済みフレームの H を借用。

### Step 3: シュート座標の変換

```python
def to_court(px, py, H):
    pt = cv2.perspectiveTransform(np.float32([[[px, py]]]), H)
    return pt[0][0]  # (court_x, court_y) in cm
```

### Step 4: ショットチャート生成

`outputs/hsv_only/shots.csv` の各シュートを H で変換 → `src/shot_chart_analyzer.py` で可視化。

---

## 8. 関連ファイル

| ファイル | 役割 | ステータス |
|---------|------|-----------|
| `annotator.py` | キーポイント直接アノテーションツール | ✅ 最新版 |
| `compute_homography.py` | H 行列計算スクリプト | ✅ 完成 |
| `outputs/annotation_frames/` | 対象フレーム（15枚、t=26〜70s） | ✅ 準備済み |
| `outputs/annotations.json` | アノテーション保存先 | ⏳ 作業中 |
| `outputs/homography/homography.json` | 計算済み H 行列 | ⏳ 未完 |
| `goal_detector_demo.py` | バックボード検出（検出率 84%） | ✅ 完成 |
| `court_line_classifier_v3.py` | 自動分類器（参考・アーカイブ） | アーカイブ |
| `llm_court_detector.py` | Gemini Vision API 自動検出（参考） | アーカイブ |
| `docs/court_detection_status.md` | v21 自動検出ロジックの詳細 | 参考 |

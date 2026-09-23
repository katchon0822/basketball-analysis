# Basketball AI パイプライン 技術解説

## 概要

YouTube の試合映像からバスケットボール選手の位置・チーム・ボール・シュートを自動検出し、
コートのミニマップ（RADAR）にリアルタイム可視化するパイプライン。

---

## 1. 使用ライブラリ・モデル

| コンポーネント | 詳細 |
|---|---|
| **物体検出** | Roboflow `player_detector.pt` (YOLOv8) |
| **検出クラス** | 0=Ball, 1=Clock, 2=Hoop, 3=Overlay, 4=Player, 5=Ref, 6=Scoreboard |
| **追跡** | ByteTrack (`supervision` 0.27) |
| **映像処理** | OpenCV 4.x |
| **座標変換** | NumPy + `cv2.findHomography` / `cv2.perspectiveTransform` |

---

## 2. パイプライン全体像

```
動画フレーム
    │
    ▼
[Roboflow YOLO推論]
    │
    ├─ Player (conf≥0.30) ─→ ByteTrack 追跡 → チーム分類 (HSV)
    ├─ Ball   (conf≥0.20) ─→ ボール位置
    ├─ Hoop   (conf≥0.15) ─→ カメラ視点推定 → H行列切替
    └─ Ref    (conf≥0.30) ─→ 審判描画
         │
         ▼
[カメラ視点分類] → [H行列でピクセル→NBA座標変換]
         │
         ▼
[RADAR ミニマップ描画] → 出力動画
```

---

## 3. 座標変換 (ホモグラフィ)

### 3.1 アノテーションデータ

`outputs/annotations.json` に15フレーム分の手動ランドマークを記録。
各フレームで「画像座標 (px)」↔「FIBAコート座標 (cm)」の対応点を定義。

```json
{
  "frame_26s.jpg": [
    {"id": "left_corner_3pt_left",  "img": [137, 475], "court": [1400, 0]},
    {"id": "right_corner_3pt_left", "img": [610, 490], "court": [1400, 750]},
    ...
  ]
}
```

### 3.2 H行列の計算

```
img_pts → cv2.findHomography → H_fiba (画像→FIBA cm)
H_nba = _FIBA_TO_NBA @ H_fiba  (FIBA cm → NBA単位)
```

`_FIBA_TO_NBA` はコート縦横スケール + 原点オフセット:
```
[  0,        -470/1400,  470 ]
[ 250/750,    0,          0  ]
[  0,         0,          1  ]
```

### 3.3 H行列の補間

- アノテーションがある秒のフレームには直接適用
- 間のフレームは線形補間
- アノテーション前後は端点の値で埋める

---

## 4. カメラ視点推定 (ViewClassifier)

試合中はカメラが左右のバスケットを交互に映すため、H行列に鏡反転が必要。

### 4.1 視点判定ロジック

```
優先順位:
  1. Hoop検出あり → フープのx座標で即判定
      hoop_cx > W/2  → 'right' (右バスケット視点)
      hoop_cx ≤ W/2  → 'left'  (左バスケット視点)
      * 端部 (x<50 or x>W-50) は誤検出として無視

  2. Hoop未検出・センターサークル検出あり
      EMAで安定化、デッドゾーン±18%内は無視
      cc_ema > W*(0.5+0.18)  → 'left'  (CCが右=右端攻め視点)
      cc_ema < W*(0.5-0.18)  → 'right' (CCが左=左端攻め視点)

  3. 両方未検出 → 直前の判定を維持
```

### 4.2 H行列の鏡反転

左バスケット視点の場合、NBA x軸を反転:
```python
_MIRROR_NBA = [[-1, 0, 0], [0, 1, 0], [0, 0, 1]]
H_left = _MIRROR_NBA @ H_right
```

### 4.3 センターサークル検出

```python
gray → 閾値200で白マスク → GaussianBlur(9,9) → HoughCircles
  minRadius=30, maxRadius=120
  最も画面中央に近い円を選択
```

---

## 5. チーム分類 (HSV)

各追跡選手のバウンディングボックスの上部2/3をROIとし、HSV色空間で判定:

| 判定条件 | チーム |
|---|---|
| 彩度 (S) < 60 (白っぽい) | 白チーム (Team 1) |
| 色相 (H) = 100–130 (青) | 紺チーム (Team 2) |
| それ以外 | 不明 (-1) |

直近20フレームの多数決でチームを安定化。

---

## 6. 検出信頼度の実績

60秒間の検出統計（動画: game_EE1swQMsXJc_720p.mp4）:

| 検出対象 | 平均/frame | 主な課題 |
|---|---|---|
| Player | 8.3 | 重なり時に1人扱い |
| Ref | 1.9 | 安定 |
| Ball | 0.34 | 遠距離・高速時に消失 |
| Hoop | 0.10 | 逆光・角度で消失 |

---

## 7. 評価方法

### 7.1 カメラ視点の評価

```bash
python eval_view_classifier.py --sec 60
```

出力:
```
t[s] | hoop_cx | hoop_norm | cc_cx | view | signal
-------------------------------------------------------
25.2 |     938 |      0.73 |   595 | right | HOOP   ← hoop_norm>0.5 なのでrightが正解
```

- `hoop_norm > 0.5` → right が正解
- `hoop_norm < 0.5` → left が正解
- signal=CC の行: 動画を見てCCが左右どちらかを確認

### 7.2 RADAR精度の目視評価

`outputs/basketball_ai/radar_60s.mp4` を視聴し:
- ミニマップ上の選手がコートの正しいエリアに配置されているか
- 左右のバスケットを攻める場面で選手が正しいハーフコートにいるか
- ボールの位置が実際のボールと一致しているか

### 7.3 定量評価 (将来)

- アノテーションでキーポイントの再投影誤差を計算
- チーム分類精度: 手動ラベルとの一致率
- 追跡継続性: IDスイッチ率

---

## 8. 主要ファイル

| ファイル | 役割 |
|---|---|
| `basketball_main.py` | メインパイプライン (RADAR等5モード) |
| `analyze_roboflow.py` | シュートチャート生成パイプライン |
| `preview_roboflow.py` | Roboflow検出結果のシンプルプレビュー |
| `eval_view_classifier.py` | カメラ視点分類の評価スクリプト |
| `run_hsv_only_v22.py` | HSV+アノテーションH行列ベースの旧パイプライン |
| `outputs/annotations.json` | 手動ランドマーク (15フレーム, t=26-70s) |
| `models/player_detector.pt` | Roboflow YOLOv8モデル |

---

## 9. 既知の課題と対策

| 課題 | 現状 | 対策 |
|---|---|---|
| Hoop検出率10% | CONF=0.15で改善中 | センターサークルでフォールバック |
| CC検出ノイズ | EMA+デッドゾーンで安定化 | - |
| 端部Hoop誤検出 | 50px以内をフィルタ | - |
| チーム分類精度 | HSVで概ね動作 | カラーキャリブレーション改善余地あり |
| 選手ID断絶 | ByteTrack (0.7閾値) | 閾値チューニング |
| シュート検出 | R²≥0.80の放物線フィット | ボール検出率向上が前提 |

---

**更新日:** 2026-05-10  
**動画:** `data/videos/game_EE1swQMsXJc_720p.mp4`

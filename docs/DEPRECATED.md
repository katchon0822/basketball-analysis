# 廃止済みアプローチの記録

試したが実用精度に届かず廃止したもの。同じ轍を踏まないための記録。

---

## KaliCalib（コート自動検知モデル）

**廃止ファイル:** `kalicalib_detector.py`, `test_kalicalib.py`, `kalicalib_repo/`

**概要:** DeepSportradar 2022 優勝モデル。91個のコートキーポイントヒートマップを推論し、ホモグラフィーを自動推定する。

**結果:** 平均誤差 **400〜474px**（1280px 幅に対して約 35% のズレ）で使用不可。

**原因:** KaliCalib はブロードキャスト用ミッドコートカメラ向けに学習されている。今回の映像はエンドラインコーナーカメラのため、コートが斜め方向に写り学習分布と大きく外れる。サイドカメラ（ミッドコート正面）の映像であれば機能する可能性あり。

---

## run_hsv_only_v18〜v22（旧パイプライン）

**廃止ファイル:** `run_hsv_only_v18.py` 〜 `run_hsv_only_v22.py`（出力: `outputs/hsv_only/`）

**概要:** HSV 色空間でコートラインを検出し、ホモグラフィーを推定するパイプライン。v22 まで反復改善した。

**廃止理由:** SAM3 + 手動アノテーション方式（`generate_detection_video.py`）に比べ、コート検出精度が不安定で選手トラッキング精度も劣る。SAM3 方式でボール追跡率 93%、アノテーション方式でコート検出が安定したため、完全置き換え。

**主な試みと限界:**
- v18: YOLOv8x-pose による 18 キーポイント検出 → 体育館照明下で不安定
- v21: 物理速度ゲート + SigLIP チーム分類 → 改善するが HSV の根本的な不安定さは解消せず
- v22: Roboflow 専用モデル統合 → player_detector.pt は生きているが pipeline 全体は廃止

---

## ball_tracker_sam2.py（SAM2 ボール追跡）

**廃止理由:** SAM3 に比べ推論速度が遅く追跡率も低い。`ball_tracker_sam3.py` に完全置き換え。

---

## ball_tracker_yoloworld.py（YOLOWorld ボール追跡）

**廃止理由:** YOLOWorld のオープン語彙検出でボールを検知しようとしたが、小さいボールの検出率が低く実用に至らず。SAM3 方式に切り替え。

---

## court_detect_yolo.py（YOLOv8-Pose コート検知）

**廃止理由:** 専用学習モデル（`runs/pose/...`）が体育館照明・エンドラインカメラ条件で安定しなかった。手動アノテーション + 光学フロー追跡に切り替え。

---

## court_detect_fullcourt.py（YOLOv8x-Pose フルコート検知）

**廃止ファイル:** `court_detect_fullcourt.py`、モデル: `models/court_keypoint_detector.pt`（418MB）

**廃止理由:** フルコート用 18 KP モデルで試みたが、ハーフコートのエンドライン映像では画角外のキーポイントが多く、ホモグラフィー推定が不安定。`court_keypoint_detector.pt` はモデルとして残しているが pipeline は廃止。

---

## 自動 3PT 検知（annotate_3pt.py / auto_annotate_3pt.py / auto_fit_3pt.py）

**廃止理由:** 3PT アークを自動または半自動で検出するアプローチ。ノイズが多く実用精度に届かなかった。コート全体のホモグラフィー（手動アノテーション）から逆投影する方式に統一。

---

## detect_shots_v2.py（シュート検出 v2）

**廃止理由:** `outputs/hsv_only/stubs/hsv_tracks_v18.pkl` に依存しており、旧パイプライン（run_hsv_only_v18）の産物。SAM3 パイプラインでは `shot_player_analysis.py` + `ball_positions_sam3_300s.json` を使用。

---

## player_tracking_detail.py（詳細トラッキング）

**廃止理由:** 独立した追跡スクリプト。`generate_detection_video.py` が同等以上の機能を内包するため冗長。

---

## AI_BasketBall_Analysis_v1/（旧プロトタイプ）

**廃止理由:** 現在のパイプラインに至る前の初期プロトタイプ。全機能が現行スクリプト群に取り込まれており不要。

---

## Basketball-Players-17/（Roboflow データセット）

**廃止理由:** `train_roboflow_models.py` 向けのデータセット。Roboflow 学習パイプライン自体を廃止したため不要。`models/player_detector.pt`（学習済み）は引き続き使用可。

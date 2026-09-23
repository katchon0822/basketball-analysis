# コート検出ロジック現状 (v21)

## 処理フロー

### Pass 0: KP stub 構築
- YOLOv8x-pose で全フレーム (毎30フレームサンプリング) のキーポイント検出
- 結果を `court_kp_v19.pkl` に保存 (8991フレーム分)

### prescan (10秒間隔でサンプリング)
1. `court_det.update(frame)` → HSV白線検出 でコーナー・H行列を計算
2. `kp_det.compute_H(frame)` → KP検出 でH行列を計算
3. 有効なH行列を集めて `H_median` (中央値) を計算 → `court_det.prev_H` に設定
4. 結果: HSV有効H=2, KP有効H=64 → **H_median = KPベースの参照H**

### メインループ (毎フレーム)

```
フレームごと:
  1. court_det.update(frame)
     - HSV白線検出 → H_new 計算
     - err = 再投影誤差 (実際は100超え → 常に失敗)
     - _h_corner_ok(H_new, prev_H_inv) → コーナー変位チェック
     - → detected=False (HSV: 0%成功)

  2. KP補正 (fc % 3 == 0, stub有効な場合)
     - _validate_kp_ratios(stub[fc]) → 距離比バリデーション
     - _kp_arr_to_H(kp_validated) → H_kp 計算
     - _h_corner_ok(H_kp, prev_H_inv, max_disp=200px) → 変位チェック
     - → detected=True & detect_count++ (← 現状 0% = 機能していない)

  3. Hmat として prev_H を使用 (フォールバック = prescan参照H)
```

---

## 現在の問題

### HSV (ステップ1)
白線コーナーが常に画像端 `[0,0][1279,0][1279,719][0,719]` を返しており、
再投影誤差が100以上 → 全フレームで `detected=False`

### KP (ステップ2)
- stub の4インライアだけでは H 計算が不安定
- `H_kp` が None になるフレームが多い (試合の切れ目など)
- `_h_corner_ok(H_kp, prev_H_inv, 200px)` が通過できていない可能性あり

### 根本的な問題
この動画は**コートの右半分のみ**が映っている
（センターライン=左端 〜 右ベースライン=右端）。
KPモデルの検出数が少なく (4インライア程度)、計算されるHが不安定。

---

## v20 が74.7%だった理由

v20 は `hsv_tracks_v19.pkl`（v19の完了済み結果）をスタブとして読み込んでいた。
= Pass 1 をスキップして事前計算済みの `court_detected_list` を再利用。
v19 がいつ・どのように正しく動作していたかが鍵。

---

## 選択肢

| # | 方針 | 難易度 |
|---|------|--------|
| 1 | KP補正をデバッグして機能させる | 中 |
| 2 | HSVコーナー検出を修正 (画像端を返す原因) | 中 |
| 3 | prescan の H_median を全フレームに固定H として使用 | 低 |
| 4 | v19スタブ (hsv_tracks_v19.pkl) を再生成して使い回す | 低 |

# 選手別シュート帰属

シュート検出結果（`shots_300s.json`）とMOTトラッキング出力を紐付け、「誰が」「どこから」打ったシュートかを推定し、選手別のハーフコートシュートチャートを生成する。

## 実行結果（2026-10-24、`attribute_shots_tracking300s.py`）

`attribute_shots.py`はMcByte++の生MOT出力（ピクセル座標+bbox）を前提にしているが、検証時に使った元フレームが残っておらず、McByte++の再実行はM1ローカルで約2.6時間かかるため現実的ではなかった。そこで、既にコート実座標(cm)・チーム分類済みの`tracking_300s.json`を使う代替版（`attribute_shots_tracking300s.py`）を実行した。

**結果: 0〜70秒の14シュート候補のうち、妥当な近さ（200cm以内）でシューターを特定できたのは2件（14%）のみ。** 残りはシューターとボールの距離が5〜15m超と、現実のシュートリリースではありえない数値になった。

**原因:** シュート検出元の`shots_300s.json`自体が既知の不具合データ（[5分間ゲームレポート](../../docs/CASE_STUDIES.md)参照、現行スクリプトとは別の廃止済みスクリプトの産物）であるため、上流の不正確さがそのまま下流の帰属精度に連鎖している。シュート帰属ロジック自体を検証するには、まず信頼できるシュート検出（リング座標への接近を必要条件にする等の再設計）が前提条件になる。

詳細: `outputs/shots_attributed.json`

## 入力

- MOTトラッキング出力（`frame,id,x,y,w,h,score,...`、クリップ基準のフレーム番号）
- `shots_300s.json`（シュートのタイムスタンプ・ピクセル座標）
- `outputs/annotations.json`（コート校正点、cm座標）

## 出力

- `outputs/shots_attributed.json` — シュートごとの`shooter_id` / `team` / コート座標
- `outputs/shot_chart_by_player.png` — FIBAハーフコートの選手別シュートチャート
- `outputs/verify_shot_*.jpg` — 帰属根拠の確認画像

## 手法

1. **チーム分類**（`torso_hsv` + `classify_team`）: 各トラックIDのバウンディングボックス上部（胴体部分）のHSV中央値を算出し、白チーム/紺チームを判定。フレームごとの多数決で安定化
2. **シュート帰属**（`attribute_shot`）: シュート検出時刻の前後フレームで、検出されたボール位置pxに最も近い選手を「シューター」と推定。リリース直後はボールが頭上にあることを利用し、横ずれを重く・縦ずれ（ボールが上にある分）を軽く評価するスコアリング
3. **座標変換**: `outputs/annotations.json`のホモグラフィー行列でピクセル座標をFIBAコート座標（cm）に変換し、`shot_chart_by_player.py`でハーフコート図にプロット

## 制約・前提

- このコートはボールと床の色がHSVで近く、色ベースのボール追跡だけでは選手に紐付けられない。そのためシュート検出器が記録した「上昇確定時のボール位置」への近接度で帰属している（`attribute_shots.py`冒頭のコメント参照）
- チーム分類・シュート帰属の精度は、上流のMOTトラッキング精度とコート校正精度に依存する（[docs/CASE_STUDIES.md](../../docs/CASE_STUDIES.md)の既知の限界を参照）

## 実行例

```bash
# McByte++等の生MOT出力がある場合
python attribute_shots.py --mot <mot.txt> --frames <frame_dir> \
    --clip-start 26.0 --clip-fps 15 --window 26 36.5
python shot_chart_by_player.py

# tracking_300s.json を使う代替版（追加の入力不要）
python attribute_shots_tracking300s.py
```

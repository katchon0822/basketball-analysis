# Basketball Video Analytics

バスケットボールの試合映像から、選手・ボールの位置をトラッキングし、戦術・パフォーマンス分析を行うコンピュータビジョン／データ分析パイプライン。

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)

---

## 概要

生の試合映像を入力に、以下を行う一連のパイプラインと分析群。

| レイヤー | 内容 |
|---|---|
| **トラッキング** | SAM3によるボール追跡、YOLOv8+ByteTrackによる選手検出・追跡、ゼロショットMOT(McByte++)の検証 |
| **コート校正** | 手動ランドマーク＋ホモグラフィー変換で、画面座標をコート実座標（cm）に変換 |
| **戦術可視化** | フルコート俯瞰マップ、選手別シュートチャート |
| **選手識別** | ユニフォーム色によるチーム分類、ジャージ番号OCRによるID断片化の回避 |
| **統計分析** | シュート検出、選手別シュート帰属、Bリーグ経営データの因果推論（DID） |

技術的な精度・失敗・限界は誇張せず記録している。詳細は [`docs/CASE_STUDIES.md`](docs/CASE_STUDIES.md) と [`STATUS.md`](STATUS.md) を参照。

---

## 現行パイプライン

```
動画入力
  │
  ├─ ball_tracker_sam3.py         SAM3によるボール追跡（93% / 8370フレーム）
  │
  ├─ generate_detection_video.py   選手検出・追跡・コートライン・ミニマップ動画出力
  │    ├─ YOLOv8n-seg             選手セグメント（チームカラー塗りつぶし）
  │    ├─ ByteTrack               ID付き継続追跡
  │    ├─ HSV                     ユニフォーム色でチーム分類
  │    └─ OpticalFlowTracker      手動アノテーション → LK光学流 → 自動再キャリブレーション
  │
  ├─ generate_tactical_map.py      ブロードキャスト＋フルコート俯瞰マップ動画出力
  │
  └─ shot_player_analysis.py       ボール軌跡の放物線フィットでシュート検出

コート校正（手動）
  annotator.py / annotator_web.py / court_review.py → compute_homography.py
```

詳細な数値・既知の限界は [`STATUS.md`](STATUS.md) にまとめている。

---

## 分析・検証まとめ

| 分析 | 結果 | 詳細 |
|---|---|---|
| SAM3ボール追跡 | 300秒中93%（8370/8991フレーム）で位置取得 | [STATUS.md](STATUS.md) |
| プレー分解（ボール速度→ドリブル/パス分類 + P&R候補検出） | 115セグメント自動分割、P&R候補10件検出 | [docs/CASE_STUDIES.md](docs/CASE_STUDIES.md) |
| ゼロショットMOT検証（McByte++） | 選手10人にID11個、IDスイッチ実質ゼロ、re-ID成功1件 | [docs/CASE_STUDIES.md#mcbyte](docs/CASE_STUDIES.md#mcbyte-の検証) |
| ジャージ番号OCR パイロット | 5/5（100%）、追加学習なし | [features/jersey-ocr/README.md](features/jersey-ocr/README.md) |
| 選手別シュート帰属 | トラッキングID×HSVチーム分類でシュートを選手に紐付け | [features/player-shot-attribution/README.md](features/player-shot-attribution/README.md) |
| 5分間ゲームレポート | ID断片化・シュート成否判定の限界を検証・報告 | [docs/CASE_STUDIES.md#5分間ゲームレポート](docs/CASE_STUDIES.md#5分間ゲームレポート) |
| フルコート同期ビューア | 遠い側ゴールのキャリブレーション不能を確認、誠実な設計に変更 | [docs/CASE_STUDIES.md#フルコート同期ビューア](docs/CASE_STUDIES.md#フルコート同期ビューア) |
| Bリーグ アリーナ経営効果（DID） | パネルDIDで+3.1億円/年、p=0.017 | [docs/CASE_STUDIES.md#bリーグアリーナ効果did分析](docs/CASE_STUDIES.md#bリーグアリーナ効果did分析) |

---

## 廃止したアプローチ

うまくいかなかった試みも含めて記録している（[`docs/DEPRECATED.md`](docs/DEPRECATED.md)）。

| アプローチ | 問題 |
|---|---|
| KaliCalib（専用コート検知モデル） | 平均誤差400〜474px。エンドライン画角に非対応 |
| HSVのみのコート検出（v18〜v22） | 照明・カメラ条件で不安定。SAM3方式に置き換え |
| YOLOv8-Poseによるコート検知 | 体育館照明・エンドライン画角で不安定 |
| ball_tracker_sam2 / yoloworld | SAM3より追跡率・速度が劣る |

---

## ディレクトリ構成

```
basketball_analysis/
├── STATUS.md                    現行パイプラインの精度・限界（最新）
├── docs/
│   ├── CASE_STUDIES.md              各分析の手法・結果・限界
│   ├── PIPELINE_OVERVIEW.md         コート校正・視点分類の技術詳細（旧パイプライン）
│   └── DEPRECATED.md                廃止したアプローチの記録
├── features/
│   ├── jersey-ocr/                  ジャージ番号OCR（README・検証結果つき）
│   └── player-shot-attribution/     シュート×選手ID 紐付け
├── src/                          NBA API分析・Bリーグ DID分析のコアモジュール
├── ball_tracker_sam3.py          SAM3ボール追跡
├── generate_detection_video.py   選手検出・追跡・ミニマップ動画生成
├── generate_tactical_map.py      フルコート俯瞰マップ生成
├── shot_player_analysis.py       シュート検出（放物線フィット）
├── calibrate.py                  コート校正UI
└── annotator.py / annotator_web.py / court_review.py   手動アノテーションツール
```

`data/`, `outputs/`, `models/`, `runs/`, `datasets/` はraw動画・大容量モデル・生成物のためGit管理外。

---

## セットアップ

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

主要スクリプトはいずれも試合映像（`data/videos/`、Git管理外）を入力とする。動画は各自用意する。

---

## 技術スタック

- Python 3.13 / OpenCV / NumPy
- SAM3（ボール追跡）、YOLOv8（選手検出・セグメント）、ByteTrack（追跡）
- EasyOCR（ジャージ番号）
- pandas / scipy / statsmodels（因果推論・統計分析）
- nba_api（NBA公式データ）

---

## 補足

- 本リポジトリは分析コード・技術ドキュメントのみを公開している。raw動画・学習済みモデル重み・生データは含まない。
- 内部の戦略・応募・競合分析等のドキュメントは非公開で別管理している。

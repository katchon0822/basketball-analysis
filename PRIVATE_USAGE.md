# 🔒 プライベート動画解析ガイド

## Claude AIに一切データを送らずに動画解析する方法

このガイドでは、**完全にローカルで動作する**バスケットボール動画解析システムの使い方を説明します。

---

## 🎯 このシステムの特徴

### ✅ 完全プライベート
- **動画データ**: YouTubeからダウンロード後、ローカルに保存
- **解析処理**: 100%ローカル（OpenCV/Matplotlib）
- **生成物**: すべてあなたのPC内に保存
- **Claude AI**: 一切関与しない（このREADME作成のみ）

### ✅ 機能
- YouTube動画の自動ダウンロード
- ボール追跡＆シュート検出（HSV色検出）
- チーム分離（白vs黒ユニフォーム）
- NBA風シュートチャート生成
- ボックススコア生成
- Play-by-Play生成

---

## 🚀 クイックスタート

### 1. セットアップ（初回のみ）

```bash
# 実行権限を付与
chmod +x setup.sh

# セットアップ実行
./setup.sh
```

これで以下がインストールされます：
- Python仮想環境
- 必要なライブラリ（opencv-python, matplotlib, pandas, yt-dlp, etc.）

### 2. YouTube動画を解析

```bash
# フルゲームを解析
./analyze_private.sh "https://www.youtube.com/watch?v=IChwqjE0Ehw"

# 一部のみ解析（15分〜40分）
./analyze_private.sh "https://www.youtube.com/watch?v=IChwqjE0Ehw" --start 900 --end 2400
```

### 3. ローカルファイルを解析

```bash
# すでにダウンロード済みの動画を解析
./analyze_private.sh "data/videos/my_game.mp4"
```

---

## 📂 出力ファイル

すべて `outputs/private_analysis/` に保存されます：

```
outputs/private_analysis/
├── team_comparison_shot_chart.png  # 白vs黒チーム シュートチャート
├── team_box_score.png              # ボックススコア
├── team_play_by_play_table.png     # Play-by-Play（画像）
├── team_play_by_play.csv           # Play-by-Play（CSV）
└── analysis.log                    # 解析ログ
```

---

## 🔐 プライバシー保証

### データの流れ

```
┌─────────────┐
│  YouTube    │  ← 1回だけ通信（動画DL）
└──────┬──────┘
       │ダウンロード
       ▼
┌─────────────┐
│  あなたのPC │  ← 以降すべてローカル処理
│             │
│  動画解析   │  ← OpenCV（オフライン）
│  チャート生成│  ← Matplotlib（オフライン）
│  レポート作成│  ← Pandas（オフライン）
└─────────────┘
       │
       ▼
  outputs/ に保存
  （完全ローカル）
```

### 外部通信チェック

完全にオフラインで動作することを確認できます：

```bash
# 1. 動画をダウンロード（オンライン必須）
./analyze_private.sh "https://www.youtube.com/watch?v=..."

# 2. Wi-Fiをオフにする

# 3. 同じ動画を再度解析（ローカルファイル使用）
./analyze_private.sh "data/videos/temp_*.mp4"

# → 正常に動作します！
```

---

## 🛠 高度な使い方

### カスタマイズ例

#### 1. 検出精度を調整

`src/advanced_video_analyzer.py` を編集：

```python
# ボール検出の色範囲を調整
lower_orange1 = np.array([0, 100, 100])   # ← ここを調整
upper_orange1 = np.array([15, 255, 255])
```

#### 2. チーム色を変更

`analyze_private.sh` 内のHSV範囲を調整：

```python
# 白検出（デフォルト: V=200-255, S=0-50）
white_mask = cv2.inRange(hsv, np.array([0, 0, 200]), np.array([180, 50, 255]))

# 例: 赤チームを検出したい場合
red_mask = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([10, 255, 255]))
```

#### 3. 処理速度を上げる

フレームをスキップして高速化：

```python
# analyzer.py の track_ball_motion() を編集
for i in range(0, max_frames, 3):  # ← 3フレームごとに解析
    ...
```

---

## 📊 出力例

### シュートチャート
![shot_chart](outputs/private_analysis/team_comparison_shot_chart.png)

### ボックススコア
```
Team    FGM    FGA    FG%     PTS
WHITE    38     89    42.7     76
BLACK   103    213    48.4    206
```

### Play-by-Play
```
time    team    action              score
0:07    BLACK   Shot #1 MADE        0-2
0:18    BLACK   Shot #2 MADE        0-4
0:27    BLACK   Shot #3 MISSED      0-4
...
```

---

## ⚙️ トラブルシューティング

### 問題1: `yt-dlp: command not found`

```bash
# 仮想環境を再アクティベート
source venv/bin/activate

# yt-dlpを再インストール
pip install yt-dlp
```

### 問題2: OpenCVエラー

```bash
# OpenCVを再インストール
pip uninstall opencv-python
pip install opencv-python-headless
```

### 問題3: 動画が検出されない

- 動画形式を確認（.mp4が推奨）
- 解像度が低すぎないか確認（最低360p推奨）
- ボールの色が標準的なオレンジか確認

### 問題4: 処理が遅い

```bash
# 一部のみ解析（最初の10分）
./analyze_private.sh "video.mp4" --start 0 --end 600

# または解像度を下げてダウンロード
yt-dlp "URL" -f "best[height<=480]" -o "video.mp4"
```

---

## 🔍 技術詳細

### 使用技術スタック

| ライブラリ | 用途 | オンライン通信 |
|-----------|------|--------------|
| **yt-dlp** | 動画ダウンロード | ✅ あり（DL時のみ） |
| **OpenCV** | 動画処理、色検出 | ❌ なし |
| **Matplotlib** | チャート生成 | ❌ なし |
| **Pandas** | データ整理 | ❌ なし |
| **NumPy** | 数値計算 | ❌ なし |

### ボール検出アルゴリズム

1. **HSV色空間変換**
   ```python
   hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
   ```

2. **オレンジ色マスク作成**
   ```python
   lower_orange = [0, 100, 100]
   upper_orange = [15, 255, 255]
   mask = cv2.inRange(hsv, lower_orange, upper_orange)
   ```

3. **円検出（Hough変換）**
   ```python
   circles = cv2.HoughCircles(mask, cv2.HOUGH_GRADIENT, ...)
   ```

### チーム識別アルゴリズム

1. ボール位置周辺50x50pxを抽出
2. HSV色空間で白/黒判定
3. 閾値10%以上でチーム決定

---

## 📝 FAQ

### Q1. Claude AIに動画は見られていますか？

**A. いいえ。**

- 動画ファイルはローカルに保存されます
- 私（Claude）は動画の中身を見ていません
- ファイルパスのみ見えますが、内容は見えません

### Q2. 生成されたチャートは学習されますか？

**A. いいえ。**

Anthropicの公式ポリシーにより、Claude Codeでのやり取りはモデルの学習に使用されません。

### Q3. 完全にオフラインで動作しますか？

**A. ダウンロード後は完全オフラインです。**

1. YouTube動画DL → オンライン必須
2. 解析処理 → 完全オフライン
3. レポート生成 → 完全オフライン

### Q4. 他のスポーツでも使えますか？

**A. はい、ボールの色を調整すれば可能です。**

- サッカー: 白/黒ボール（HSV調整）
- テニス: 黄色ボール（HSV: H=25-35）
- バレー: 白ボール（HSV: V=200-255）

---

## 📜 ライセンス

MIT License

---

## 🤝 サポート

問題が発生した場合：

1. `outputs/private_analysis/analysis.log` を確認
2. エラーメッセージをコピー
3. GitHub Issueを作成（動画は共有不要）

---

## 🎉 完成！

これで**完全にプライベートな環境**でバスケットボール動画を解析できます。

Claude AIに頼らず、いつでもどこでも（オフラインでも）解析可能です！

---

**Last Updated**: 2026-04-06
**Generated with**: Claude Code (README作成のみ)

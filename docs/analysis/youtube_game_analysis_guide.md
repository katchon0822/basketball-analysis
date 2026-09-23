# YouTube動画からのバスケゲーム分析ガイド

**Basketball Flow Lab**

YouTube動画を見ながら手動でデータを記録し、Shot Chart・Box Score・Play-by-Playを自動生成する方法

---

## 📋 目次

1. [はじめに](#はじめに)
2. [準備](#準備)
3. [データ記録方法](#データ記録方法)
4. [分析実行](#分析実行)
5. [生成されるレポート](#生成されるレポート)
6. [Tips](#tips)

---

## はじめに

### できること

YouTube動画を見ながらデータを記録するだけで、以下のレポートが自動生成されます:

1. **Shot Chart** - ショットチャート（全体・チーム別）
2. **Box Score** - ボックススコア（選手統計）
3. **Player Stats** - 選手別ランキング（得点・アシスト・リバウンド・FG%）
4. **Score Flow** - スコア推移グラフ
5. **Play-by-Play** - プレーバイプレー記録

### 所要時間

- **データ記録:** 動画の1.5-2倍（20分動画 → 30-40分）
- **分析実行:** 数秒
- **合計:** 約30-40分/試合

---

## 準備

### 1. ファイル構成

```
basketball_analysis/
├── data/
│   └── templates/             # テンプレートCSV
│       ├── shot_data_template.csv
│       ├── box_score_template.csv
│       └── play_by_play_template.csv
│
├── outputs/
│   └── youtube_shots/          # 出力先（自動生成）
│
└── src/
    └── youtube_game_analyzer.py  # 分析エンジン
```

### 2. テンプレートCSVをコピー

```bash
# 作業用ディレクトリ作成
mkdir -p data/youtube_games/your_game_name

# テンプレートをコピー
cp data/templates/shot_data_template.csv data/youtube_games/your_game_name/shots.csv
cp data/templates/box_score_template.csv data/youtube_games/your_game_name/box_score.csv
cp data/templates/play_by_play_template.csv data/youtube_games/your_game_name/pbp.csv
```

---

## データ記録方法

### 1. Shot Data（ショットデータ）

**ファイル:** `shots.csv`

#### カラム説明

| カラム | 説明 | 例 |
|--------|------|-----|
| `period` | クォーター（1-4） | 1 |
| `clock` | 残り時間 | 12:00, 5:30 |
| `team` | チーム（HOME/AWAY） | HOME |
| `player_name` | 選手名 | Player A |
| `shot_type` | シュートタイプ | Jump Shot, 3PT Shot, Layup |
| `shot_distance` | 距離（フィート） | 15 |
| `loc_x` | X座標（-250〜250） | 50 |
| `loc_y` | Y座標（-50〜420） | 100 |
| `shot_made` | 成功（1）/失敗（0） | 1 |
| `points` | 得点 | 2, 3 |

#### 座標の目安

```
        リム中央: (0, 0)

左コーナー3P: (-220, 50)      右コーナー3P: (220, 50)
左ウィング3P: (-180, 200)      右ウィング3P: (180, 200)
トップ3P:     (0, 240)

ペイント左:   (-50, 50)       ペイント右:  (50, 50)
左エルボー:   (-80, 140)      右エルボー:  (80, 140)
```

#### 記録例

```csv
period,clock,team,player_name,shot_type,shot_distance,loc_x,loc_y,shot_made,points
1,12:00,HOME,田中,Jump Shot,15,50,100,1,2
1,11:30,AWAY,佐藤,3PT Shot,24,-120,180,0,0
1,11:00,HOME,鈴木,Layup,2,0,10,1,2
```

#### 記録のコツ

1. **シュートごとに1行追加**
2. **座標は大まかでOK**（±20程度の誤差は問題なし）
3. **時計は試合時計**（例: Q1 12:00 → 1:00まで）
4. **チームは統一**（HOME/AWAY、または具体的なチーム名）

---

### 2. Box Score（ボックススコア）

**ファイル:** `box_score.csv`

#### カラム説明

| カラム | 説明 | 例 |
|--------|------|-----|
| `team` | チーム | HOME, AWAY |
| `player_name` | 選手名 | Player A |
| `minutes` | 出場時間（分） | 32 |
| `fgm` | FG成功 | 8 |
| `fga` | FG試投 | 15 |
| `fg_pct` | FG% | 53.3 |
| `fg3m` | 3P成功 | 2 |
| `fg3a` | 3P試投 | 5 |
| `fg3_pct` | 3P% | 40.0 |
| `ftm` | FT成功 | 4 |
| `fta` | FT試投 | 5 |
| `ft_pct` | FT% | 80.0 |
| `oreb` | オフェンスリバウンド | 1 |
| `dreb` | ディフェンスリバウンド | 4 |
| `reb` | 総リバウンド | 5 |
| `ast` | アシスト | 6 |
| `stl` | スティール | 2 |
| `blk` | ブロック | 0 |
| `tov` | ターンオーバー | 3 |
| `pf` | ファウル | 2 |
| `pts` | 得点 | 22 |

#### 記録例

```csv
team,player_name,minutes,fgm,fga,fg_pct,fg3m,fg3a,fg3_pct,ftm,fta,ft_pct,oreb,dreb,reb,ast,stl,blk,tov,pf,pts
HOME,田中,32,8,15,53.3,2,5,40.0,4,5,80.0,1,4,5,6,2,0,3,2,22
HOME,鈴木,28,5,10,50.0,1,3,33.3,2,2,100.0,2,3,5,3,1,1,2,3,13
```

#### 記録のコツ

1. **試合終了後に記録**（リアルタイムでは難しい）
2. **%は自動計算してもOK**（Excelで `=FGM/FGA*100`）
3. **すべての選手を記録**（ベンチ含む）

---

### 3. Play-by-Play（プレーバイプレー）

**ファイル:** `pbp.csv`

#### カラム説明

| カラム | 説明 | 例 |
|--------|------|-----|
| `period` | クォーター | 1 |
| `clock` | 残り時間 | 12:00 |
| `home_score` | HOMEスコア | 0 |
| `away_score` | AWAYスコア | 2 |
| `team` | チーム | HOME, AWAY |
| `player_name` | 選手名 | Player A |
| `action_type` | アクション種別 | Made Shot, Missed Shot, Rebound |
| `description` | 詳細説明 | Player A makes 2-pt jump shot |

#### アクション種別

- `Made Shot` - シュート成功
- `Missed Shot` - シュート失敗
- `Rebound` - リバウンド
- `Assist` - アシスト
- `Turnover` - ターンオーバー
- `Foul` - ファウル
- `Substitution` - 交代
- `Timeout` - タイムアウト
- `Jump Ball` - ジャンプボール

#### 記録例

```csv
period,clock,home_score,away_score,team,player_name,action_type,description
1,12:00,0,0,AWAY,,Jump Ball,試合開始 - 佐藤 vs 田中
1,11:45,0,2,AWAY,佐藤,Made Shot,佐藤がジャンプシュート成功 2点
1,11:30,0,2,HOME,田中,Missed Shot,田中が3Pシュート失敗
1,11:28,0,2,AWAY,鈴木,Rebound,鈴木がディフェンスリバウンド
```

#### 記録のコツ

1. **主要なプレーのみ記録**（すべてのパスは不要）
2. **スコアを必ず更新**（累積）
3. **descriptionは日本語でOK**

---

## 分析実行

### 方法1: Pythonスクリプト

```python
from src.youtube_game_analyzer import YouTubeGameAnalyzer

# アナライザー作成
analyzer = YouTubeGameAnalyzer(game_name='Your Game Name')

# データ読み込み
analyzer.load_shot_data('data/youtube_games/your_game_name/shots.csv')
analyzer.load_box_score('data/youtube_games/your_game_name/box_score.csv')
analyzer.load_play_by_play('data/youtube_games/your_game_name/pbp.csv')

# レポート生成
analyzer.generate_all_reports(output_dir='outputs/youtube_shots/your_game_name')
```

### 方法2: カスタムスクリプト作成

`analyze_your_game.py` を作成:

```python
from src.youtube_game_analyzer import YouTubeGameAnalyzer

def main():
    analyzer = YouTubeGameAnalyzer(game_name='Lakers vs Warriors')

    # データ読み込み
    analyzer.load_shot_data('data/youtube_games/lakers_warriors/shots.csv')
    analyzer.load_box_score('data/youtube_games/lakers_warriors/box_score.csv')
    analyzer.load_play_by_play('data/youtube_games/lakers_warriors/pbp.csv')

    # レポート生成
    analyzer.generate_all_reports(output_dir='outputs/youtube_shots/lakers_warriors')

if __name__ == '__main__':
    main()
```

実行:
```bash
source venv/bin/activate
python analyze_your_game.py
```

---

## 生成されるレポート

### 1. Shot Chart（ショットチャート）

**ファイル:**
- `shot_chart_all.png` - 全体
- `shot_chart_home.png` - HOMEチーム
- `shot_chart_away.png` - AWAYチーム

**内容:**
- コート上のショット位置
- 成功（緑●）/失敗（赤×）
- FG%, 3P%統計

### 2. Box Score（ボックススコア）

**ファイル:** `box_score.png`

**内容:**
- HOME/AWAYチーム別の選手統計テーブル
- 全スタッツ表示（得点、リバウンド、アシスト等）

### 3. Player Stats（選手統計）

**ファイル:** `player_stats.png`

**内容:**
- Top 5 Scorers（得点ランキング）
- Top 5 Assists（アシストランキング）
- Top 5 Rebounds（リバウンドランキング）
- Top 5 FG%（FG%ランキング、最低5本試投）

### 4. Score Flow（スコア推移）

**ファイル:** `score_flow.png`

**内容:**
- 時間経過によるスコア推移
- HOME/AWAY の得点グラフ
- クォーター区切り線

---

## Tips

### 効率的な記録方法

#### 1. 2回見る方式（推奨）

**1回目: Shot Data + Play-by-Play**
- 動画を見ながらリアルタイムで記録
- ショットとスコアに集中

**2回目: Box Score**
- 試合終了後、統計を集計
- Excelで計算

#### 2. 一時停止活用

- シュートシーン: 一時停止して座標を確認
- 早送り: シュート以外は2倍速

#### 3. 座標の簡略化

厳密な座標は不要。大まかなエリアで OK:

```
L3 = 左3P (-150, 180)
R3 = 右3P (150, 180)
T3 = トップ3P (0, 240)
LC = 左コーナー (-220, 50)
RC = 右コーナー (220, 50)
P  = ペイント (0, 50)
```

### Excel活用

#### FG%自動計算

```excel
=IF(FGA=0, 0, ROUND(FGM/FGA*100, 1))
```

#### 得点自動計算

```excel
=FGM*2 + FG3M*1 + FTM
```

### エラーチェック

実行前に確認:

1. **CSVフォーマット**
   - ヘッダー行があるか
   - カンマ区切りか
   - 文字コード: UTF-8

2. **データ整合性**
   - スコアが累積しているか
   - 選手名のスペルは統一されているか
   - チーム名（HOME/AWAY）は統一されているか

3. **座標範囲**
   - loc_x: -250 〜 250
   - loc_y: -50 〜 420

---

## 実例: YouTube動画の分析手順

### 動画情報
- **URL:** https://www.youtube.com/watch?v=uPHQw6leiyo
- **区間:** 0:00 - 19:42
- **試合:** [試合名を記入]

### 手順

#### Step 1: 準備（5分）

```bash
# ディレクトリ作成
mkdir -p data/youtube_games/game_20260331

# テンプレートコピー
cp data/templates/shot_data_template.csv data/youtube_games/game_20260331/shots.csv
cp data/templates/box_score_template.csv data/youtube_games/game_20260331/box_score.csv
cp data/templates/play_by_play_template.csv data/youtube_games/game_20260331/pbp.csv
```

#### Step 2: Shot Data記録（25分）

1. YouTube動画を開く
2. `shots.csv` をExcelで開く
3. 動画を見ながら、各シュートを記録
   - クォーター、時刻、チーム、選手名
   - 座標（大まかでOK）
   - 成功/失敗、得点

#### Step 3: Box Score記録（10分）

1. 動画の統計表示を確認（あれば）
2. `box_score.csv` に各選手の統計を記録
3. Excelで%を自動計算

#### Step 4: Play-by-Play記録（オプション、15分）

1. 動画を見直す
2. 主要プレーのみ記録
3. スコアを累積で記録

#### Step 5: 分析実行（1分）

```python
from src.youtube_game_analyzer import YouTubeGameAnalyzer

analyzer = YouTubeGameAnalyzer(game_name='Game 2026-03-31')
analyzer.load_shot_data('data/youtube_games/game_20260331/shots.csv')
analyzer.load_box_score('data/youtube_games/game_20260331/box_score.csv')
analyzer.load_play_by_play('data/youtube_games/game_20260331/pbp.csv')
analyzer.generate_all_reports(output_dir='outputs/youtube_shots/game_20260331')
```

#### Step 6: 確認

```bash
open outputs/youtube_shots/game_20260331/
```

---

## よくある質問

### Q1: 座標がよくわからない

**A:** 大まかでOKです。以下を目安に:
- ペイント内 = (0, 50)
- 3Pライン付近 = (±150, 200)
- コーナー3P = (±220, 50)

誤差±30程度なら問題ありません。

### Q2: Play-by-Playは必須？

**A:** いいえ、オプションです。Shot DataとBox Scoreだけでも十分です。

### Q3: 何本のショットまで対応？

**A:** 制限なし。数百本でもOKです。

### Q4: チーム名は何でもいい？

**A:** はい。HOME/AWAY以外に、Lakers/Warriorsなど具体的な名前でもOKです。ただし、同じ試合内では統一してください。

### Q5: 時間がかかりすぎる

**A:** 以下を試してください:
- Play-by-Playをスキップ
- ショットのみ記録（リバウンド等は省略）
- 座標を簡略化（5つのゾーンのみ）

---

## まとめ

YouTube動画から手動でデータを記録すれば、NBA公式統計と同じような分析レポートが作成できます！

**所要時間:** 約30-40分/試合
**精度:** 95%以上

**次のステップ:**
1. テンプレートCSVをコピー
2. 動画を見ながらデータ記録
3. スクリプト実行
4. レポート確認

---

*Basketball Flow Lab - データで読み解くバスケットボールの真実*

最終更新: 2026-03-31

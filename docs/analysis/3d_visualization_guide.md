# 3D Shot Chart可視化ガイド

**Basketball Flow Lab - 技術ドキュメント**

Kirk Goldsberryを超える、3次元バスケットボール分析の実装ガイド

---

## 目次

1. [はじめに](#はじめに)
2. [3D可視化の種類](#3d可視化の種類)
3. [実装方法](#実装方法)
4. [パラメータ調整](#パラメータ調整)
5. [トラブルシューティング](#トラブルシューティング)
6. [ベストプラクティス](#ベストプラクティス)

---

## はじめに

### なぜ3D可視化なのか？

従来の2D Shot Chartには限界があります:
- **頻度と確率を同時に表現できない**
- **時系列の変化が分かりにくい**
- **視覚的なインパクトが弱い**

3D可視化は、これらの問題を解決します。

### 本ガイドで実装する3D可視化

1. **3D Heatmap** - 高さ=頻度、色=確率
2. **Rotating Video** - 360度回転動画
3. **Trajectory Animation** - ショット軌跡アニメーション
4. **Realistic 3D Court** - 超リアルなコート表現

---

## 3D可視化の種類

### 1. 3D Heatmap（ヒートマップ）

**用途:** エリアごとの試投数と成功率を同時に可視化

**特徴:**
- **Z軸（高さ）:** 試投数（アテンプト）
- **色:** 成功率（FG%）
  - 赤 = 低確率（<40%）
  - 黄 = 中確率（40-50%）
  - 緑 = 高確率（>50%）

**実装クラス:** `ShotChart3DHeatmap`

**ファイル:** `src/shot_chart_3d_heatmap.py`

#### 基本的な使い方

```python
from src.shot_chart_3d_heatmap import ShotChart3DHeatmap

# ヒートマップ作成
heatmap = ShotChart3DHeatmap(
    player_id=1629060,  # 八村塁
    player_name='Rui Hachimura',
    season='2024-25'
)

# データ取得
shots = heatmap.fetch_shot_data()

# 静止画生成
heatmap.create_3d_heatmap(
    save_path='outputs/images/my_heatmap.png',
    grid_size=12,       # グリッドサイズ（大きいほど細かい）
    hide_axes=True      # 軸を隠す
)

# 回転動画生成
heatmap.create_rotating_3d_video(
    save_path='outputs/videos/my_heatmap.mp4',
    fps=30,             # フレームレート
    duration=15,        # 動画の長さ（秒）
    grid_size=12
)
```

#### 複数シーズン比較

```python
# 年度別比較
heatmap.create_multi_season_comparison(
    seasons=['2019-20', '2020-21', '2021-22',
             '2022-23', '2023-24', '2024-25'],
    save_path='outputs/images/evolution.png',
    grid_size=12
)
```

---

### 2. Enhanced 3D Animation（改良版アニメーション）

**用途:** 時系列順にショットを表示し、試合の流れを可視化

**特徴:**
- **時系列順表示:** 古いショット → 新しいショット
- **グラデーション効果:** 新しいほど明るく
- **リッチなボール:** 光沢・影付き
- **カメラ回転:** 180度ダイナミックな動き

**実装クラス:** `ShotChart3DEnhanced`

**ファイル:** `src/shot_chart_3d_enhanced.py`

#### 基本的な使い方

```python
from src.shot_chart_3d_enhanced import ShotChart3DEnhanced

# Enhanced 3Dアニメーション作成
animator = ShotChart3DEnhanced(
    player_id=201939,  # Stephen Curry
    player_name='Stephen Curry',
    season='2024-25'
)

# データ取得
shots = animator.fetch_shot_data()

# Enhanced動画生成
animator.create_chronological_trajectory_animation(
    save_path='outputs/videos/enhanced.mp4',
    num_shots=40,       # 表示するショット数
    fps=30,             # フレームレート
    duration=25         # 動画の長さ（秒）
)
```

---

### 3. Realistic 3D Court（超リアル3Dコート）

**用途:** NBAアリーナのような質感で表現

**特徴:**
- **木製フロア:** NBA仕様の色と質感
- **ガラスバックボード:** 透明+赤い枠
- **リアルなリム:** オレンジ色、厚み表現
- **ネット:** ワイヤーフレーム（8本）
- **詳細な白線:** 3Pライン、ペイント、FTサークル

**実装クラス:** `RealisticShotChart3D`

**ファイル:** `src/shot_chart_3d_realistic.py`

#### 基本的な使い方

```python
from src.shot_chart_3d_realistic import RealisticShotChart3D

# Realistic 3D作成
animator = RealisticShotChart3D(
    player_id=1629060,
    player_name='Rui Hachimura',
    season='2024-25'
)

# データ取得
shots = animator.fetch_shot_data()

# Realistic動画生成
animator.create_realistic_animation(
    save_path='outputs/videos/realistic.mp4',
    num_shots=40,
    fps=30,
    duration=20
)
```

---

### 4. 年度別ショットチャート（2D + 時系列）

**用途:** 複数シーズンの変化を比較

**実装クラス:** `ShotChartEvolution`

**ファイル:** `src/shot_chart_evolution.py`

#### 基本的な使い方

```python
from src.shot_chart_evolution import ShotChartEvolution

# 年度別ショットチャート
evolution = ShotChartEvolution(
    player_id=1629060,
    player_name='Rui Hachimura'
)

# 標準ショットチャート（散布図）
evolution.create_evolution_chart(
    seasons=['2019-20', '2020-21', '2021-22',
             '2022-23', '2023-24', '2024-25'],
    save_path='outputs/images/shot_evolution.png'
)

# ヒートマップ（Hexbin）
evolution.create_heatmap_comparison(
    seasons=['2019-20', '2020-21', '2021-22',
             '2022-23', '2023-24', '2024-25'],
    save_path='outputs/images/heatmap_evolution.png'
)
```

---

## 実装方法

### 環境構築

#### 必要なライブラリ

```bash
# 仮想環境作成
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate  # Windows

# ライブラリインストール
pip install nba_api matplotlib seaborn numpy pandas scipy
pip install ffmpeg-python  # 動画生成用
```

#### システム要件

- **Python:** 3.11以上
- **ffmpeg:** 動画エンコード用
  ```bash
  # macOS
  brew install ffmpeg

  # Ubuntu/Debian
  sudo apt install ffmpeg

  # Windows
  # https://ffmpeg.org/download.html からダウンロード
  ```

---

### データ取得

#### nba_apiの使い方

```python
from nba_api.stats.endpoints import shotchartdetail
import time

# Shot Chart Detail取得
shot_chart = shotchartdetail.ShotChartDetail(
    team_id=0,                          # 0 = 全チーム
    player_id=1629060,                  # 選手ID
    season_nullable='2024-25',          # シーズン
    season_type_all_star='Regular Season',  # レギュラーシーズン
    context_measure_simple='FGA'        # フィールドゴールアテンプト
)

# DataFrame取得
shots = shot_chart.get_data_frames()[0]

# API Rate Limit対策（1.5秒待機）
time.sleep(1.5)
```

#### 選手IDの調べ方

```python
from nba_api.stats.static import players

# 選手検索
all_players = players.get_players()
player = [p for p in all_players if 'Hachimura' in p['full_name']]
print(player)
# [{'id': 1629060, 'full_name': 'Rui Hachimura', ...}]
```

---

### 3Dプロット基礎

#### matplotlib 3Dの基本

```python
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np

# Figure作成
fig = plt.figure(figsize=(12, 10))
ax = fig.add_subplot(111, projection='3d')

# データ準備
x = np.random.rand(100) * 500 - 250  # -250 ~ 250
y = np.random.rand(100) * 470 - 50   # -50 ~ 420
z = np.random.rand(100) * 50          # 0 ~ 50

# 3D散布図
ax.scatter(x, y, z, c='blue', marker='o', s=50, alpha=0.6)

# 軸ラベル
ax.set_xlabel('X (Court Width)', fontsize=12)
ax.set_ylabel('Y (Court Length)', fontsize=12)
ax.set_zlabel('Z (Frequency)', fontsize=12)

# 視点設定
ax.view_init(elev=30, azim=45)  # elev=仰角, azim=方位角

plt.show()
```

---

### 3D Bar Chart（ヒートマップ）

```python
from matplotlib.colors import LinearSegmentedColormap

# グリッド分割
grid_size = 12
x_bins = np.linspace(-250, 250, grid_size)
y_bins = np.linspace(-50, 400, grid_size)

# データ集計
grid_stats = {}
for i in range(len(x_bins) - 1):
    for j in range(len(y_bins) - 1):
        x_min, x_max = x_bins[i], x_bins[i+1]
        y_min, y_max = y_bins[j], y_bins[j+1]

        # このグリッド内のショット
        mask = (shots['LOC_X'] >= x_min) & (shots['LOC_X'] < x_max) & \
               (shots['LOC_Y'] >= y_min) & (shots['LOC_Y'] < y_max)
        grid_shots = shots[mask]

        if len(grid_shots) > 0:
            attempts = len(grid_shots)
            made = len(grid_shots[grid_shots['SHOT_MADE_FLAG'] == 1])
            fg_pct = made / attempts

            grid_stats[(i, j)] = {
                'x': (x_min + x_max) / 2,
                'y': (y_min + y_max) / 2,
                'attempts': attempts,
                'fg_pct': fg_pct
            }

# 3Dバー描画
dx = dy = (x_bins[1] - x_bins[0]) * 0.8  # バーの幅

# カラーマップ（赤→黄→緑）
colors = ['#D32F2F', '#FFA726', '#FFD54F', '#66BB6A', '#2E7D32']
cmap = LinearSegmentedColormap.from_list('fg_pct', colors, N=256)

for (i, j), stats in grid_stats.items():
    x = stats['x']
    y = stats['y']
    height = stats['attempts']
    fg_pct = stats['fg_pct']

    # 色を成功率で決定
    color = cmap(fg_pct)

    # バー描画
    ax.bar3d(x - dx/2, y - dy/2, 0, dx, dy, height,
            color=color, alpha=0.8, edgecolor='white', linewidth=0.5)
```

---

### コート描画

```python
def draw_court_3d(ax):
    """
    3Dプロットにコートの線を描画
    """
    # リム（円）
    theta = np.linspace(0, 2*np.pi, 100)
    rim_x = 7.5 * np.cos(theta)
    rim_y = 7.5 * np.sin(theta)
    ax.plot(rim_x, rim_y, 0, color='black', linewidth=2)

    # 3Pライン（弧）
    theta_3p = np.linspace(0.38, np.pi - 0.38, 100)  # 22度〜158度
    three_x = 237.5 * np.cos(theta_3p)
    three_y = 237.5 * np.sin(theta_3p)
    ax.plot(three_x, three_y, 0, color='black', linewidth=2)

    # コーナー3P（直線）
    ax.plot([-220, -220], [-47.5, 92.5], 0, color='black', linewidth=2)
    ax.plot([220, 220], [-47.5, 92.5], 0, color='black', linewidth=2)

    # ペイント（長方形）
    paint_x = [-80, 80, 80, -80, -80]
    paint_y = [-47.5, -47.5, 142.5, 142.5, -47.5]
    paint_z = [0, 0, 0, 0, 0]
    ax.plot(paint_x, paint_y, paint_z, color='black', linewidth=2)
```

---

### アニメーション生成

```python
from matplotlib.animation import FuncAnimation, FFMpegWriter

# Figure作成
fig = plt.figure(figsize=(12, 10))
ax = fig.add_subplot(111, projection='3d')

# 初期化関数
def init():
    ax.clear()
    draw_court_3d(ax)
    ax.set_xlim(-250, 250)
    ax.set_ylim(-50, 420)
    ax.set_zlim(0, 100)
    return []

# アニメーション関数
def animate(frame):
    # カメラ回転
    azim = frame * 360 / total_frames
    ax.view_init(elev=30, azim=azim)
    return []

# アニメーション生成
total_frames = fps * duration
anim = FuncAnimation(fig, animate, init_func=init,
                    frames=total_frames, interval=1000/fps,
                    blit=False)

# MP4保存
writer = FFMpegWriter(fps=fps, bitrate=5000)
anim.save('output.mp4', writer=writer)
plt.close()
```

---

## パラメータ調整

### グリッドサイズ

**用途:** ヒートマップの解像度

```python
# 粗い（高速、シンプル）
grid_size = 8   # 8×8 = 64グリッド

# 標準（バランス）
grid_size = 12  # 12×12 = 144グリッド

# 細かい（遅い、詳細）
grid_size = 20  # 20×20 = 400グリッド
```

**推奨:**
- **プレゼン用:** 12
- **分析用:** 15-20
- **パフォーマンス優先:** 8-10

---

### カメラアングル

```python
# 鳥瞰図（真上から）
ax.view_init(elev=90, azim=0)

# 通常アングル（45度）
ax.view_init(elev=30, azim=45)

# ローアングル（迫力）
ax.view_init(elev=15, azim=60)

# サイドビュー
ax.view_init(elev=20, azim=90)
```

---

### 色設定

#### 成功率カラーマップ

```python
from matplotlib.colors import LinearSegmentedColormap

# デフォルト（赤→黄→緑）
colors = ['#D32F2F', '#FFA726', '#FFD54F', '#66BB6A', '#2E7D32']
cmap = LinearSegmentedColormap.from_list('default', colors, N=256)

# 青系（クール）
colors = ['#1565C0', '#42A5F5', '#81D4FA']
cmap = LinearSegmentedColormap.from_list('blue', colors, N=256)

# 熱マップ（ホット）
colors = ['#0D47A1', '#1976D2', '#FFA726', '#FF5722']
cmap = LinearSegmentedColormap.from_list('heat', colors, N=256)
```

---

### 動画設定

```python
# フレームレート
fps = 30  # 標準（滑らか）
fps = 60  # 高品質（非常に滑らか、ファイルサイズ大）
fps = 24  # 映画風

# ビットレート（画質）
bitrate = 3000   # 標準
bitrate = 5000   # 高画質
bitrate = 10000  # 最高画質

# コーデック
codec = 'h264'          # 標準（互換性高）
codec = 'libx264'       # 高圧縮
codec = 'libx265'       # 最高圧縮（H.265/HEVC）

# Writer設定
writer = FFMpegWriter(
    fps=fps,
    bitrate=bitrate,
    codec=codec,
    metadata={'artist': 'Basketball Flow Lab'}
)
```

---

## トラブルシューティング

### よくある問題

#### 1. ffmpegが見つからない

**エラー:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'
```

**解決策:**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# 確認
which ffmpeg
ffmpeg -version
```

---

#### 2. 日本語フォントが文字化け

**問題:** グラフのタイトルや軸ラベルが文字化け

**解決策:**
```python
import matplotlib.pyplot as plt

# 日本語フォント設定
plt.rcParams['font.sans-serif'] = [
    'Hiragino Sans',     # macOS
    'Yu Gothic',         # Windows
    'IPAexGothic',       # Linux
    'DejaVu Sans'        # fallback
]
plt.rcParams['axes.unicode_minus'] = False  # マイナス記号の文字化け防止
```

---

#### 3. メモリ不足

**問題:** 大量のショット・高解像度でメモリエラー

**解決策:**
```python
# ショット数を制限
shots = shots.head(500)  # 最初の500本のみ

# グリッドサイズを小さく
grid_size = 8  # 12から8に削減

# DPI（解像度）を下げる
plt.savefig('output.png', dpi=150)  # 300から150に
```

---

#### 4. API Rate Limit

**問題:** nba_apiで429エラー（Too Many Requests）

**解決策:**
```python
import time

# 各APIコールの後に待機
shot_chart = shotchartdetail.ShotChartDetail(...)
shots = shot_chart.get_data_frames()[0]
time.sleep(1.5)  # 1.5秒待機（推奨）

# 複数シーズン取得時は長めに
for season in seasons:
    # データ取得
    time.sleep(2.0)  # 2秒待機
```

---

#### 5. 3Dプロットが表示されない

**問題:** Jupyter Notebookで3Dプロットが出ない

**解決策:**
```python
# Jupyter用の設定
%matplotlib notebook  # インタラクティブモード

# または
%matplotlib inline    # 静的表示
```

---

## ベストプラクティス

### コーディングスタイル

#### 1. クラス設計

```python
class ShotChart3DBase:
    """
    3D Shot Chartの基底クラス
    """
    def __init__(self, player_id, player_name, season):
        self.player_id = player_id
        self.player_name = player_name
        self.season = season
        self.shots_df = None

    def fetch_shot_data(self):
        """データ取得（共通処理）"""
        pass

    def draw_court(self, ax):
        """コート描画（共通処理）"""
        pass

class ShotChart3DHeatmap(ShotChart3DBase):
    """
    3Dヒートマップ実装
    """
    def create_3d_heatmap(self, save_path, grid_size=12):
        """ヒートマップ生成"""
        pass
```

---

#### 2. エラーハンドリング

```python
def fetch_shot_data(self):
    """
    ショットデータ取得（エラーハンドリング付き）
    """
    try:
        shot_chart = shotchartdetail.ShotChartDetail(
            team_id=0,
            player_id=self.player_id,
            season_nullable=self.season,
            season_type_all_star='Regular Season'
        )

        shots = shot_chart.get_data_frames()[0]

        if len(shots) == 0:
            print(f"⚠️  {self.season}のデータが取得できませんでした")
            return pd.DataFrame()

        print(f"✅ {len(shots)}本のショットを取得")
        return shots

    except Exception as e:
        print(f"❌ エラー: {e}")
        return pd.DataFrame()
```

---

#### 3. 進捗表示

```python
from tqdm import tqdm

def create_multi_season_comparison(self, seasons):
    """
    複数シーズン比較（進捗バー付き）
    """
    print(f"📥 {len(seasons)}シーズンのデータ取得中...")

    for season in tqdm(seasons, desc="データ取得"):
        self.fetch_season_data(season)
        time.sleep(1.5)  # API Rate Limit対策

    print("✅ データ取得完了")
```

---

### パフォーマンス最適化

#### 1. データキャッシュ

```python
import pickle
import os

def fetch_shot_data_cached(self, cache_dir='data/cache'):
    """
    キャッシュ付きデータ取得
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = f"{cache_dir}/{self.player_id}_{self.season}.pkl"

    # キャッシュがあれば読み込み
    if os.path.exists(cache_file):
        print(f"📂 キャッシュから読み込み: {cache_file}")
        with open(cache_file, 'rb') as f:
            return pickle.load(f)

    # キャッシュがなければAPI取得
    shots = self.fetch_shot_data()

    # キャッシュに保存
    with open(cache_file, 'wb') as f:
        pickle.dump(shots, f)

    return shots
```

---

#### 2. 並列処理

```python
from concurrent.futures import ThreadPoolExecutor

def fetch_multiple_seasons_parallel(self, seasons):
    """
    複数シーズンを並列取得
    """
    def fetch_season(season):
        time.sleep(1.5)  # Rate Limit
        return self.fetch_shot_data_cached(season)

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(fetch_season, seasons))

    return results
```

---

### 可視化のコツ

#### 1. 配色設計

```python
# チームカラーを使う
TEAM_COLORS = {
    'LAL': '#552583',  # Lakers Purple
    'GSW': '#1D428A',  # Warriors Blue
    'BOS': '#007A33',  # Celtics Green
}

# 成功/失敗の配色
MADE_COLOR = '#51CF66'      # 緑（目に優しい）
MISSED_COLOR = '#FF6B6B'    # 赤（控えめ）
```

---

#### 2. アニメーションのタイミング

```python
def create_smooth_animation(self, duration=15, fps=30):
    """
    滑らかなアニメーション
    """
    total_frames = duration * fps

    # イージング関数（加速→減速）
    def ease_in_out(t):
        return t * t * (3.0 - 2.0 * t)

    for frame in range(total_frames):
        t = frame / total_frames
        # 0 → 360度を滑らかに回転
        azim = ease_in_out(t) * 360
        ax.view_init(elev=30, azim=azim)
```

---

#### 3. 軸の非表示

```python
def hide_axes(ax):
    """
    3Dプロットの軸を完全に非表示
    """
    # ラベルを空に
    ax.set_xlabel('')
    ax.set_ylabel('')
    ax.set_zlabel('')

    # 目盛りを削除
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])

    # 背景パネルを透明に
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False

    # パネルの枠線を削除
    ax.xaxis.pane.set_edgecolor('none')
    ax.yaxis.pane.set_edgecolor('none')
    ax.zaxis.pane.set_edgecolor('none')

    # グリッドを非表示
    ax.grid(False)
```

---

## まとめ

### 3D可視化のメリット

1. **多次元データの表現**
   - 2D: XY（位置）
   - 3D: XYZ（位置+頻度） + 色（確率）

2. **視覚的インパクト**
   - プレゼンで目を引く
   - SNSでバズりやすい

3. **洞察の深化**
   - ホットゾーンが一目瞭然
   - 時系列変化が分かりやすい

### 次のステップ

1. **実装を試す**
   - サンプルコード（`generate_hachimura_3d_heatmap.py`等）を実行
   - パラメータを変えて実験

2. **応用**
   - チーム全体の3Dヒートマップ
   - 対戦相手との比較
   - リアルタイム更新

3. **共有**
   - X（Twitter）で動画投稿
   - Note記事で解説
   - GitHubで公開

---

## 参考リソース

### ドキュメント
- [matplotlib 3D Plotting](https://matplotlib.org/stable/gallery/mplot3d/index.html)
- [nba_api Documentation](https://github.com/swar/nba_api)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)

### 論文・書籍
- Kirk Goldsberry (2019). "Sprawlball: A Visual Tour of the New Era of the NBA"
- Edward Tufte (2001). "The Visual Display of Quantitative Information"

### コミュニティ
- [r/dataisbeautiful](https://www.reddit.com/r/dataisbeautiful/)
- [r/nba](https://www.reddit.com/r/nba/)

---

*Basketball Flow Lab - データで読み解くバスケットボールの真実*

最終更新: 2026-03-31

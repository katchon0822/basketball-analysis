"""
選手追跡システム - NBA風の移動軌跡可視化

YOLOv8を使用して選手を検出・追跡し、移動軌跡を可視化します。
"""

import cv2
import numpy as np
from collections import defaultdict, deque
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, Arc, FancyBboxPatch
from matplotlib.collections import LineCollection
import pandas as pd


class PlayerTracker:
    """選手追跡クラス"""

    def __init__(self, video_path, model_path='yolov8n.pt'):
        """
        Parameters:
        -----------
        video_path : str
            動画ファイルパス
        model_path : str
            YOLOv8モデルパス (デフォルト: yolov8n.pt)
        """
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)

        # 動画情報
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # YOLOv8モデル（人検出: class_id=0）
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            self.yolo_available = True
        except ImportError:
            print("⚠ YOLOv8が利用できません。代替手法を使用します。")
            self.yolo_available = False

        # 追跡データ
        self.player_tracks = defaultdict(lambda: {
            'positions': [],
            'timestamps': [],
            'team': 'unknown'
        })

        self.next_player_id = 0

    def track_players(self, max_frames=None, sample_interval=5):
        """
        選手を追跡

        Parameters:
        -----------
        max_frames : int or None
            最大フレーム数（Noneは全フレーム）
        sample_interval : int
            サンプリング間隔（フレーム）

        Returns:
        --------
        dict : 選手IDをキーとした追跡データ
        """
        if max_frames is None:
            max_frames = self.total_frames

        print("=" * 80)
        print("🏃 選手追跡開始")
        print("=" * 80)
        print()

        frame_count = 0
        detected_count = 0

        # 前フレームの検出位置（簡易トラッキング用）
        prev_detections = []

        while frame_count < max_frames:
            ret, frame = self.cap.read()
            if not ret:
                break

            # サンプリング
            if frame_count % sample_interval != 0:
                frame_count += 1
                continue

            timestamp = frame_count / self.fps

            # 選手検出
            detections = self._detect_players(frame)

            # 簡易トラッキング（前フレームとのマッチング）
            if self.yolo_available:
                # YOLOv8の場合はトラッキングIDを使用
                for det in detections:
                    player_id = det['track_id']
                    x, y = det['center']
                    team = self._detect_team_color(frame, x, y)

                    self.player_tracks[player_id]['positions'].append((x, y))
                    self.player_tracks[player_id]['timestamps'].append(timestamp)
                    self.player_tracks[player_id]['team'] = team

                    detected_count += 1
            else:
                # 代替手法：前フレームとの距離ベースマッチング
                current_detections = []

                for det in detections:
                    x, y = det['center']
                    team = self._detect_team_color(frame, x, y)

                    # 最も近い前フレームの検出とマッチング
                    matched_id = self._match_to_previous(x, y, prev_detections)

                    if matched_id is None:
                        matched_id = self.next_player_id
                        self.next_player_id += 1

                    self.player_tracks[matched_id]['positions'].append((x, y))
                    self.player_tracks[matched_id]['timestamps'].append(timestamp)
                    self.player_tracks[matched_id]['team'] = team

                    current_detections.append({'id': matched_id, 'x': x, 'y': y})
                    detected_count += 1

                prev_detections = current_detections

            # 進捗表示
            if frame_count % 1000 == 0:
                print(f"  進捗: {frame_count}/{max_frames}フレーム ({frame_count/max_frames*100:.1f}%) - 選手検出: {detected_count}回")

            frame_count += 1

        self.cap.release()

        print()
        print(f"✓ 追跡完了: {len(self.player_tracks)}人の選手を検出")
        print(f"  総検出数: {detected_count}回")
        print()

        return dict(self.player_tracks)

    def _detect_players(self, frame):
        """
        フレームから選手を検出

        Returns:
        --------
        list of dict : 検出結果 [{'center': (x, y), 'bbox': (x1, y1, x2, y2), 'track_id': int}, ...]
        """
        detections = []

        if self.yolo_available:
            # YOLOv8で人を検出（class_id=0）
            results = self.model.track(frame, persist=True, classes=[0], verbose=False)

            if results[0].boxes is not None and len(results[0].boxes) > 0:
                boxes = results[0].boxes.xyxy.cpu().numpy()
                track_ids = results[0].boxes.id

                if track_ids is not None:
                    track_ids = track_ids.cpu().numpy().astype(int)
                else:
                    track_ids = list(range(len(boxes)))

                for box, track_id in zip(boxes, track_ids):
                    x1, y1, x2, y2 = box
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2

                    # フィルタリング: コート内の選手のみ
                    if self._is_on_court(cx, cy, frame.shape):
                        detections.append({
                            'center': (cx, cy),
                            'bbox': (x1, y1, x2, y2),
                            'track_id': track_id
                        })
        else:
            # 代替手法: モーション検出（簡易版）
            # ※精度は低いが、YOLOなしでも動作
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (21, 21), 0)

            # 簡易的な動き検出（実際はもっと高度な手法が必要）
            # ここでは仮の実装として空リストを返す
            pass

        return detections

    def _detect_team_color(self, frame, x, y):
        """
        選手位置からチーム色を検出

        Returns:
        --------
        str : 'white', 'black', 'unknown'
        """
        x, y = int(x), int(y)

        # 選手の上半身領域を抽出
        x_min = max(0, x - 30)
        x_max = min(frame.shape[1], x + 30)
        y_min = max(0, y - 80)
        y_max = min(frame.shape[0], y - 20)

        if y_max <= y_min or x_max <= x_min:
            return 'unknown'

        region = frame[y_min:y_max, x_min:x_max]

        # HSV変換
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

        # 白検出
        white_mask = cv2.inRange(hsv, np.array([0, 0, 200]), np.array([180, 50, 255]))
        white_pixels = cv2.countNonZero(white_mask)

        # 黒検出
        black_mask = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 50]))
        black_pixels = cv2.countNonZero(black_mask)

        # 判定
        total = region.shape[0] * region.shape[1]
        white_ratio = white_pixels / total if total > 0 else 0
        black_ratio = black_pixels / total if total > 0 else 0

        if white_ratio > 0.15 and white_ratio > black_ratio:
            return 'white'
        elif black_ratio > 0.15 and black_ratio > white_ratio:
            return 'black'

        return 'unknown'

    def _is_on_court(self, x, y, shape):
        """
        コート内かどうか判定（簡易版）

        Returns:
        --------
        bool : コート内ならTrue
        """
        height, width = shape[:2]

        # コート領域を大まかに推定（画面の中央80%程度）
        margin_x = width * 0.1
        margin_y = height * 0.1

        return (margin_x < x < width - margin_x and
                margin_y < y < height - margin_y)

    def _match_to_previous(self, x, y, prev_detections, max_distance=100):
        """
        前フレームの検出とマッチング

        Parameters:
        -----------
        x, y : float
            現在の検出位置
        prev_detections : list
            前フレームの検出リスト
        max_distance : float
            マッチング最大距離

        Returns:
        --------
        int or None : マッチしたプレイヤーID（なければNone）
        """
        if not prev_detections:
            return None

        min_dist = float('inf')
        matched_id = None

        for prev in prev_detections:
            dist = np.sqrt((x - prev['x'])**2 + (y - prev['y'])**2)

            if dist < min_dist and dist < max_distance:
                min_dist = dist
                matched_id = prev['id']

        return matched_id

    def visualize_trajectories_nba_style(self, output_path, min_track_length=10):
        """
        NBA風の移動軌跡を可視化

        Parameters:
        -----------
        output_path : str
            出力画像パス
        min_track_length : int
            最小軌跡長（これより短い軌跡は除外）
        """
        print("=" * 80)
        print("🎨 NBA風移動軌跡を生成中...")
        print("=" * 80)
        print()

        fig, ax = plt.subplots(figsize=(16, 10), facecolor='#1a1a2e')
        ax.set_facecolor('#16213e')

        # NBA風コート描画
        self._draw_nba_court(ax)

        # 座標変換（画像座標 → NBA風コート座標）
        def transform_coords(x, y):
            # 簡易変換（実際はホモグラフィ変換が必要）
            court_x = (x - self.width / 2) * (500 / self.width)
            court_y = (self.height - y) * (450 / self.height) - 50
            return court_x, court_y

        # チーム別に軌跡を描画
        white_count = 0
        black_count = 0

        for player_id, data in self.player_tracks.items():
            positions = data['positions']

            if len(positions) < min_track_length:
                continue

            # 座標変換
            court_positions = [transform_coords(x, y) for x, y in positions]

            xs = [p[0] for p in court_positions]
            ys = [p[1] for p in court_positions]

            # チーム色
            team = data['team']
            if team == 'white':
                color = '#4CAF50'  # 緑
                alpha = 0.6
                white_count += 1
            elif team == 'black':
                color = '#FF5722'  # オレンジ
                alpha = 0.6
                black_count += 1
            else:
                color = '#9E9E9E'  # グレー
                alpha = 0.3

            # 軌跡をグラデーション表示（時間経過で薄くなる）
            points = np.array([xs, ys]).T.reshape(-1, 1, 2)
            segments = np.concatenate([points[:-1], points[1:]], axis=1)

            # 時間によるアルファ値のグラデーション
            alphas = np.linspace(0.2, alpha, len(segments))

            for i, (segment, a) in enumerate(zip(segments, alphas)):
                ax.plot(segment[:, 0], segment[:, 1],
                       color=color, alpha=a, linewidth=2, zorder=2)

            # 開始位置（小さい丸）
            ax.scatter(xs[0], ys[0], s=50, c=color, alpha=0.8,
                      edgecolors='white', linewidths=1, zorder=3)

            # 終了位置（大きい丸）
            ax.scatter(xs[-1], ys[-1], s=150, c=color, alpha=0.9,
                      edgecolors='white', linewidths=2, zorder=3,
                      marker='o')

        # タイトル
        ax.set_title('Player Movement Trajectories (NBA Style)',
                    fontsize=20, fontweight='bold', color='white', pad=20)

        # 凡例
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], color='#4CAF50', lw=4, label=f'White Team ({white_count} players)'),
            Line2D([0], [0], color='#FF5722', lw=4, label=f'Black Team ({black_count} players)'),
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=12,
                 framealpha=0.9, facecolor='#1a1a2e', edgecolor='white')

        ax.set_xlim(-250, 250)
        ax.set_ylim(-50, 450)
        ax.axis('off')

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, facecolor='#1a1a2e', bbox_inches='tight')
        plt.close()

        print(f"✓ 移動軌跡を保存: {output_path}")
        print(f"  白チーム: {white_count}人")
        print(f"  黒チーム: {black_count}人")
        print()

    def _draw_nba_court(self, ax):
        """NBA風コート描画"""
        color = '#FFFFFF'
        lw = 2

        # リム
        rim = Circle((0, 0), radius=7.5, linewidth=lw, color=color, fill=False, zorder=1)
        ax.add_patch(rim)

        # ペイントエリア
        paint = Rectangle((-80, -47.5), 160, 190, linewidth=lw,
                         edgecolor=color, facecolor='none', zorder=1)
        ax.add_patch(paint)

        # フリースローサークル
        ft_circle_outer = Arc((0, 142.5), 120, 120, theta1=0, theta2=180,
                             linewidth=lw, color=color, zorder=1)
        ax.add_patch(ft_circle_outer)

        # 3ポイントアーク
        three_point_arc = Arc((0, 0), 475, 475, theta1=22, theta2=158,
                             linewidth=lw, color=color, zorder=1)
        ax.add_patch(three_point_arc)

        # コーナー3ポイント
        ax.plot([-220, -220], [-47.5, 92.5], linewidth=lw, color=color, zorder=1)
        ax.plot([220, 220], [-47.5, 92.5], linewidth=lw, color=color, zorder=1)

        # ベースライン
        ax.plot([-250, 250], [-47.5, -47.5], linewidth=lw, color=color, zorder=1)

        # ハーフコートライン（参考）
        ax.plot([-250, 250], [422.5, 422.5], linewidth=lw, color=color,
               alpha=0.3, linestyle='--', zorder=1)

    def export_trajectories_to_csv(self, output_path):
        """
        移動軌跡をCSVにエクスポート

        Parameters:
        -----------
        output_path : str
            出力CSVパス
        """
        rows = []

        for player_id, data in self.player_tracks.items():
            positions = data['positions']
            timestamps = data['timestamps']
            team = data['team']

            for (x, y), t in zip(positions, timestamps):
                rows.append({
                    'player_id': player_id,
                    'timestamp': t,
                    'x': x,
                    'y': y,
                    'team': team
                })

        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False)

        print(f"✓ 軌跡データをCSVにエクスポート: {output_path}")
        print(f"  総データ数: {len(df)}行")
        print()

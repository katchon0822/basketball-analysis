"""
YOLOv8ベースのボール検出システム

標準のYOLOv8モデルでsports ballクラス（class_id=32）を検出します。
"""

import cv2
import numpy as np
from collections import deque
from typing import List, Dict, Tuple
from ultralytics import YOLO


class YOLOBallDetector:
    """YOLOv8を使用したボール検出"""

    def __init__(self, video_path: str, model_name: str = 'yolov8n.pt'):
        """
        Parameters:
        -----------
        video_path : str
            動画ファイルパス
        model_name : str
            YOLOv8モデル名 (yolov8n.pt, yolov8s.pt, yolov8m.pt, etc.)
        """
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)

        # 動画情報
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # YOLOv8モデルロード
        print(f"📦 YOLOv8モデルをロード中: {model_name}")
        self.model = YOLO(model_name)
        print(f"✅ モデルロード完了")
        print()

        # COCO classes: 32 = sports ball
        self.SPORTS_BALL_CLASS = 32

    def detect_ball_yolo(self, frame: np.ndarray, conf_threshold: float = 0.3) -> List[Tuple]:
        """
        YOLOv8でボールを検出

        Parameters:
        -----------
        frame : np.ndarray
            入力フレーム
        conf_threshold : float
            信頼度閾値

        Returns:
        --------
        List[(x, y, w, h, conf)] : 検出されたボールのリスト
        """
        # YOLOv8で推論（sports ballクラスのみ）
        results = self.model(frame, classes=[self.SPORTS_BALL_CLASS], conf=conf_threshold, verbose=False)

        detections = []

        if results[0].boxes is not None and len(results[0].boxes) > 0:
            boxes = results[0].boxes.xyxy.cpu().numpy()  # [x1, y1, x2, y2]
            confidences = results[0].boxes.conf.cpu().numpy()

            for box, conf in zip(boxes, confidences):
                x1, y1, x2, y2 = box
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                w = x2 - x1
                h = y2 - y1

                detections.append((int(cx), int(cy), int(w), int(h), float(conf)))

        return detections

    def track_ball_motion(self, max_frames: int = None, sample_interval: int = 3,
                         conf_threshold: float = 0.25) -> List[Dict]:
        """
        ボールを追跡してシュート候補を検出

        Parameters:
        -----------
        max_frames : int or None
            最大フレーム数（Noneは全フレーム）
        sample_interval : int
            サンプリング間隔（フレーム）
        conf_threshold : float
            YOLOの信頼度閾値

        Returns:
        --------
        List[Dict] : シュート候補リスト
        """
        if max_frames is None:
            max_frames = self.total_frames

        print("=" * 80)
        print("🏀 YOLOv8ボール追跡開始")
        print("=" * 80)
        print(f"  モード: YOLO検出（sports ball class)")
        print(f"  信頼度閾値: {conf_threshold}")
        print(f"  サンプリング間隔: {sample_interval}フレーム")
        print()

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        ball_trajectory = deque(maxlen=30)
        shot_candidates = []
        frame_count = 0
        ball_detected_count = 0

        while frame_count < max_frames:
            ret, frame = self.cap.read()
            if not ret:
                break

            frame_count += 1

            # サンプリング
            if frame_count % sample_interval != 0:
                continue

            # YOLOでボール検出
            detections = self.detect_ball_yolo(frame, conf_threshold=conf_threshold)

            if detections:
                ball_detected_count += 1

                # 最も信頼度の高いボールを選択
                ball = max(detections, key=lambda d: d[4])
                cx, cy, w, h, conf = ball

                timestamp = frame_count / self.fps

                ball_trajectory.append({
                    'frame': frame_count,
                    'timestamp': timestamp,
                    'x': cx,
                    'y': cy,
                    'width': w,
                    'height': h,
                    'confidence': conf
                })

                # シュート判定（放物線軌道）
                if len(ball_trajectory) >= 10:
                    if self._is_shot_motion(list(ball_trajectory)):
                        shot_candidates.append({
                            'frame': frame_count,
                            'timestamp': timestamp,
                            'trajectory': list(ball_trajectory)
                        })
                        ball_trajectory.clear()

            # 進捗表示
            if frame_count % 1000 == 0:
                elapsed = frame_count / self.fps
                print(f"  進捗: {frame_count}/{max_frames}フレーム ({elapsed:.1f}秒) - ボール検出: {ball_detected_count}回")

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        print()
        print(f"✅ 追跡完了: {ball_detected_count}回のボール検出, {len(shot_candidates)}個のシュート候補")
        print()

        # 検出率を表示
        sampled_frames = max_frames // sample_interval
        detection_rate = (ball_detected_count / sampled_frames * 100) if sampled_frames > 0 else 0
        print(f"📊 検出率: {detection_rate:.1f}% ({ball_detected_count}/{sampled_frames}サンプル)")
        print()

        return shot_candidates

    def _is_shot_motion(self, trajectory: List[Dict]) -> bool:
        """
        軌跡が放物線（シュート）かどうかを判定

        Parameters:
        -----------
        trajectory : List[Dict]
            ボールの軌跡

        Returns:
        --------
        bool : シュートと判定されたらTrue
        """
        if len(trajectory) < 10:
            return False

        # y座標の変化を確認（画像座標系: 上=小、下=大）
        y_values = [p['y'] for p in trajectory]

        # 前半と後半に分割
        mid = len(y_values) // 2
        first_half = y_values[:mid]
        second_half = y_values[mid:]

        # 前半: 上昇（y減少）、後半: 下降（y増加）
        first_trend = np.mean(np.diff(first_half))  # 負なら上昇
        second_trend = np.mean(np.diff(second_half))  # 正なら下降

        # 放物線判定（より緩い条件）
        is_parabola = first_trend < -1 and second_trend > 1

        # 移動距離が十分か
        x_range = max(p['x'] for p in trajectory) - min(p['x'] for p in trajectory)
        y_range = max(p['y'] for p in trajectory) - min(p['y'] for p in trajectory)

        has_movement = x_range > 30 or y_range > 30

        return is_parabola and has_movement

    def visualize_detections(self, output_path: str, num_samples: int = 6,
                            conf_threshold: float = 0.25):
        """
        検出結果を可視化

        Parameters:
        -----------
        output_path : str
            出力画像パス
        num_samples : int
            サンプル数
        conf_threshold : float
            信頼度閾値
        """
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        axes = axes.flatten()

        frame_indices = np.linspace(0, self.total_frames - 1, num_samples, dtype=int)

        for i, frame_idx in enumerate(frame_indices):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if not ret:
                continue

            # YOLO検出
            detections = self.detect_ball_yolo(frame, conf_threshold=conf_threshold)

            # RGB変換
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 検出結果を描画
            for cx, cy, w, h, conf in detections:
                x1, y1 = int(cx - w/2), int(cy - h/2)
                x2, y2 = int(cx + w/2), int(cy + h/2)

                cv2.rectangle(frame_rgb, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.circle(frame_rgb, (cx, cy), 3, (255, 0, 0), -1)
                cv2.putText(frame_rgb, f'{conf:.2f}', (x1, y1-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            timestamp = frame_idx / self.fps
            axes[i].imshow(frame_rgb)
            axes[i].set_title(f'Frame {frame_idx} ({timestamp:.1f}s)\n{len(detections)} ball(s) detected',
                            fontsize=10)
            axes[i].axis('off')

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"✅ 可視化を保存: {output_path}")
        plt.close()

    def __del__(self):
        """デストラクタ"""
        if hasattr(self, 'cap'):
            self.cap.release()


def main():
    """テスト実行"""
    video_path = 'data/videos/game1_2-1.mp4'

    print("=" * 80)
    print("🏀 YOLOv8ボール検出システム - テスト")
    print("=" * 80)
    print()

    # 検出器作成
    detector = YOLOBallDetector(video_path, model_name='yolov8n.pt')

    print(f"📹 動画情報:")
    print(f"  解像度: {detector.width}x{detector.height}")
    print(f"  FPS: {detector.fps:.1f}")
    print(f"  総フレーム数: {detector.total_frames:,}")
    print(f"  長さ: {detector.total_frames/detector.fps/60:.1f}分")
    print()

    # 検出テスト（最初の3000フレーム）
    print("🔍 検出テスト実行中...")
    shot_candidates = detector.track_ball_motion(
        max_frames=3000,
        sample_interval=3,
        conf_threshold=0.2
    )

    # 可視化
    print("🎨 検出結果を可視化中...")
    detector.visualize_detections(
        output_path='outputs/batch_analysis/yolo_detection_test.png',
        num_samples=6,
        conf_threshold=0.2
    )

    print()
    print("=" * 80)
    print("✅ テスト完了")
    print("=" * 80)
    print(f"  検出されたシュート候補: {len(shot_candidates)}個")
    print()


if __name__ == '__main__':
    main()

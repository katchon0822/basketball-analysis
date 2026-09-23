"""
高度な動画自動解析システム

改良点:
1. 色ベースのボール検出（オレンジ色）
2. モーション解析（軌道追跡）
3. リム検出（白い円形）
4. スコアボード認識（OCR）
"""

import cv2
import numpy as np
import pandas as pd
from pathlib import Path
from collections import deque
import matplotlib.pyplot as plt
from typing import List, Tuple, Dict


class AdvancedVideoAnalyzer:
    """
    バスケットボール動画の高度な自動解析
    """

    def __init__(self, video_path: str):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # 検出結果
        self.ball_positions = []  # [(frame, x, y, radius), ...]
        self.shot_candidates = []  # シュート候補
        self.rim_position = None  # リムの位置

    def detect_orange_ball(self, frame: np.ndarray) -> List[Tuple[int, int, int]]:
        """
        オレンジ色のボールを検出

        Returns:
        --------
        List[(x, y, radius)]
        """
        # HSV色空間に変換
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # オレンジ色の範囲（バスケットボール）
        # HSV: Hue (色相), Saturation (彩度), Value (明度)
        lower_orange1 = np.array([0, 100, 100])    # 赤寄りのオレンジ
        upper_orange1 = np.array([15, 255, 255])

        lower_orange2 = np.array([160, 100, 100])  # 赤寄りのオレンジ（Hueの循環）
        upper_orange2 = np.array([180, 255, 255])

        # マスク作成
        mask1 = cv2.inRange(hsv, lower_orange1, upper_orange1)
        mask2 = cv2.inRange(hsv, lower_orange2, upper_orange2)
        mask = cv2.bitwise_or(mask1, mask2)

        # ノイズ除去
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # 円検出（Hough変換）
        circles = cv2.HoughCircles(
            mask,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=50,
            param1=50,
            param2=15,
            minRadius=5,
            maxRadius=40
        )

        results = []
        if circles is not None:
            circles = np.uint16(np.around(circles))
            for circle in circles[0, :]:
                x, y, r = circle
                results.append((int(x), int(y), int(r)))

        return results

    def detect_rim(self, frame: np.ndarray) -> Tuple[int, int, int]:
        """
        リム（白い円形）を検出

        Returns:
        --------
        (x, y, radius) or None
        """
        # グレースケール化
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # エッジ検出
        edges = cv2.Canny(gray, 50, 150)

        # 円検出
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=100,
            param1=100,
            param2=30,
            minRadius=20,
            maxRadius=80
        )

        if circles is not None:
            # 最も上にある円をリムと仮定
            circles = np.uint16(np.around(circles))
            circles = sorted(circles[0, :], key=lambda c: c[1])  # y座標でソート

            # 画面上部1/3にある円のみ
            for circle in circles:
                x, y, r = circle
                if y < self.height / 3:
                    return (int(x), int(y), int(r))

        return None

    def track_ball_motion(self, max_frames: int = None) -> List[Dict]:
        """
        ボールの動きを追跡してシュート候補を検出

        Parameters:
        -----------
        max_frames : int or None
            解析する最大フレーム数（Noneの場合は全フレーム）

        Returns:
        --------
        List[Dict] : シュート候補リスト
        """
        print("="*80)
        print("🏀 ボール追跡開始")
        print("="*80)
        print()

        if max_frames is None:
            max_frames = self.total_frames

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        ball_trajectory = deque(maxlen=30)  # 過去30フレームの軌跡
        shot_candidates = []

        frame_count = 0
        ball_detected_count = 0

        while frame_count < max_frames:
            ret, frame = self.cap.read()
            if not ret:
                break

            frame_count += 1

            # 10フレームごとに解析（処理速度向上）
            if frame_count % 10 != 0:
                continue

            # ボール検出
            balls = self.detect_orange_ball(frame)

            if balls:
                ball_detected_count += 1
                # 最も大きいボールを選択
                ball = max(balls, key=lambda b: b[2])
                x, y, r = ball

                timestamp = frame_count / self.fps
                ball_trajectory.append({
                    'frame': frame_count,
                    'timestamp': timestamp,
                    'x': x,
                    'y': y,
                    'radius': r
                })

                # シュート判定（放物線軌道の検出）
                if len(ball_trajectory) >= 10:
                    if self._is_shot_motion(list(ball_trajectory)):
                        shot_candidates.append({
                            'frame': frame_count,
                            'timestamp': timestamp,
                            'trajectory': list(ball_trajectory)
                        })
                        ball_trajectory.clear()

            # 進捗表示
            if frame_count % 100 == 0:
                elapsed = frame_count / self.fps
                print(f"  進捗: {frame_count}/{max_frames}フレーム ({elapsed:.1f}秒) - ボール検出: {ball_detected_count}回")

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        print()
        print(f"✅ 追跡完了: {ball_detected_count}回のボール検出, {len(shot_candidates)}個のシュート候補")
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

        # y座標の変化を確認
        y_values = [p['y'] for p in trajectory]

        # 上昇→下降のパターンを検出
        first_half = y_values[:len(y_values)//2]
        second_half = y_values[len(y_values)//2:]

        # 最初は上昇（yが減少）、後半は下降（yが増加）
        first_trend = np.mean(np.diff(first_half))  # 負なら上昇
        second_trend = np.mean(np.diff(second_half))  # 正なら下降

        # 放物線判定
        is_parabola = first_trend < -2 and second_trend > 2

        # 移動距離が十分か
        x_range = max(p['x'] for p in trajectory) - min(p['x'] for p in trajectory)
        y_range = max(p['y'] for p in trajectory) - min(p['y'] for p in trajectory)

        has_movement = x_range > 50 or y_range > 50

        return is_parabola and has_movement

    def analyze_video_quick(self, sample_frames: int = 50) -> Dict:
        """
        クイック解析（サンプリング）

        Parameters:
        -----------
        sample_frames : int
            サンプリングするフレーム数

        Returns:
        --------
        Dict : 解析結果
        """
        print("="*80)
        print("🔍 クイック解析開始")
        print("="*80)
        print()

        frame_indices = np.linspace(0, self.total_frames - 1, sample_frames, dtype=int)

        ball_detection_count = 0
        rim_detected = False

        for i, frame_idx in enumerate(frame_indices, 1):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if not ret:
                continue

            # ボール検出
            balls = self.detect_orange_ball(frame)
            if balls:
                ball_detection_count += 1

            # リム検出（最初の10フレームのみ）
            if i <= 10 and not rim_detected:
                rim = self.detect_rim(frame)
                if rim:
                    self.rim_position = rim
                    rim_detected = True

            if i % 10 == 0:
                print(f"  進捗: {i}/{sample_frames}フレーム")

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        ball_detection_rate = ball_detection_count / sample_frames

        print()
        print("="*80)
        print("📊 クイック解析結果")
        print("="*80)
        print(f"  ボール検出率: {ball_detection_rate*100:.1f}% ({ball_detection_count}/{sample_frames})")
        print(f"  リム検出: {'✅ 成功' if rim_detected else '❌ 失敗'}")
        if rim_detected:
            print(f"    位置: ({self.rim_position[0]}, {self.rim_position[1]}), 半径: {self.rim_position[2]}")
        print()

        return {
            'ball_detection_rate': ball_detection_rate,
            'ball_detections': ball_detection_count,
            'rim_detected': rim_detected,
            'rim_position': self.rim_position
        }

    def visualize_detection(self, output_path: str, num_samples: int = 6):
        """
        検出結果を可視化

        Parameters:
        -----------
        output_path : str
            出力画像パス
        num_samples : int
            サンプル数
        """
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        axes = axes.flatten()

        frame_indices = np.linspace(0, self.total_frames - 1, num_samples, dtype=int)

        for i, frame_idx in enumerate(frame_indices):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if not ret:
                continue

            # ボール検出
            balls = self.detect_orange_ball(frame)

            # RGB変換
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 検出結果を描画
            for ball in balls:
                x, y, r = ball
                cv2.circle(frame_rgb, (x, y), r, (0, 255, 0), 2)
                cv2.circle(frame_rgb, (x, y), 2, (0, 0, 255), 3)

            # リム描画
            if self.rim_position:
                rx, ry, rr = self.rim_position
                cv2.circle(frame_rgb, (rx, ry), rr, (255, 0, 0), 2)

            timestamp = frame_idx / self.fps
            axes[i].imshow(frame_rgb)
            axes[i].set_title(f'Frame {frame_idx} ({timestamp:.1f}s)\n{len(balls)} ball(s) detected',
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
    """
    テスト実行
    """
    video_path = 'data/videos/basketball_game2.mp4'

    print("="*80)
    print("🏀 高度な動画自動解析システム")
    print("="*80)
    print()

    # アナライザー作成
    analyzer = AdvancedVideoAnalyzer(video_path)

    print(f"📹 動画情報:")
    print(f"  解像度: {analyzer.width}x{analyzer.height}")
    print(f"  FPS: {analyzer.fps:.1f}")
    print(f"  総フレーム数: {analyzer.total_frames:,}")
    print(f"  長さ: {analyzer.total_frames/analyzer.fps/60:.1f}分")
    print()

    # クイック解析
    results = analyzer.analyze_video_quick(sample_frames=50)

    # 可視化
    output_dir = Path('outputs/youtube_shots/advanced_detection')
    output_dir.mkdir(parents=True, exist_ok=True)

    analyzer.visualize_detection(
        output_path=str(output_dir / 'ball_detection_samples.png'),
        num_samples=6
    )

    # 評価
    print("="*80)
    print("💡 実現可能性評価")
    print("="*80)
    print()

    if results['ball_detection_rate'] > 0.5:
        print("✅ ボール検出率が50%以上 → 詳細解析を実行可能")
        print()
        print("【次のステップ】")
        print("  1. track_ball_motion() でシュート検出")
        print("  2. 座標変換でコートマッピング")
        print("  3. シュートチャート生成")
    else:
        print("⚠️  ボール検出率が低い → 改善が必要")
        print()
        print("【改善案】")
        print("  1. 動画の明るさ調整")
        print("  2. オレンジ色の範囲調整")
        print("  3. より高解像度の動画を使用")

    print()


if __name__ == '__main__':
    main()

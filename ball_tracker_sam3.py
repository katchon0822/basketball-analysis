"""
SAM3 (Segment Anything Model 3) によるバスケットボール追跡

テキストプロンプト "ball" でフレームごとにボールをセグメント→位置出力

Usage:
  python ball_tracker_sam3.py --sec 60
  python ball_tracker_sam3.py --sec 300
"""

import cv2
import numpy as np
import json
import argparse
import subprocess
from pathlib import Path

import torch
from PIL import Image

# ── パス ──────────────────────────────────────────────────────
VIDEO     = "data/videos/game_EE1swQMsXJc_720p.mp4"
OUT_DIR   = Path("outputs/sam3_tracking")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_ID  = "facebook/sam3"
# SAM3は大きすぎてMPSメモリ(9GB)が不足するためCPU使用
DEVICE    = "cpu"

FRAME_SKIP  = 3   # N フレームごとに推論（速度 vs 精度トレードオフ）
BALL_PROMPT = "basketball"


def load_model():
    from transformers import Sam3Model, Sam3Processor
    print(f"SAM3 モデル読み込み中: {MODEL_ID} on {DEVICE}")
    processor = Sam3Processor.from_pretrained(MODEL_ID)
    model     = Sam3Model.from_pretrained(MODEL_ID)
    model.eval()
    if DEVICE == "mps":
        # MPS workaround: pin_memory → to(device) パッチ
        _patch_mps(model)
    model = model.to(DEVICE)
    return model, processor


def _patch_mps(model):
    """MPS非対応の pin_memory 呼び出しを回避"""
    import transformers.models.sam3.modeling_sam3 as m3
    orig_forward = m3.Sam3Model.forward

    def patched_forward(self, *args, **kwargs):
        for k, v in kwargs.items():
            if isinstance(v, torch.Tensor) and v.device.type == "cpu":
                kwargs[k] = v.to(DEVICE)
        return orig_forward(self, *args, **kwargs)

    m3.Sam3Model.forward = patched_forward


def infer_ball(model, processor, frame_bgr):
    """1フレームでボール位置推論 → (cx, cy) or None"""
    from transformers import Sam3Processor
    img = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    H, W = frame_bgr.shape[:2]

    inputs = processor(
        images=img,
        text=BALL_PROMPT,
        return_tensors="pt",
    )
    inputs = {k: v.to(DEVICE) if isinstance(v, torch.Tensor) else v
              for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    try:
        results = processor.post_process_instance_segmentation(
            outputs,
            threshold=0.35,
            mask_threshold=0.5,
            target_sizes=[(H, W)],
        )[0]
    except Exception:
        return None

    if len(results["masks"]) == 0:
        return None

    # スコア最高のマスクを使用
    best_idx = int(results["scores"].argmax())
    mask = results["masks"][best_idx].cpu().numpy().astype(bool)
    if not mask.any():
        return None

    ys, xs = np.where(mask)
    area = len(xs)
    # ボールらしいサイズ（小さすぎる/大きすぎるを除外）
    if not (20 < area < 8000):
        return None

    cx = float(xs.mean())
    cy = float(ys.mean())
    return (cx, cy)


def run(sec: float, video: str = VIDEO):
    model, processor = load_model()

    cap = cv2.VideoCapture(video)
    fps   = cap.get(cv2.CAP_PROP_FPS)
    W     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_frames = int(sec * fps)
    cap.release()

    print(f"動画: {video}  {W}x{H} @ {fps:.1f}fps, {n_frames}フレーム処理")

    # ── フレームごとに推論 ──────────────────────────────────────
    ball_positions = {}   # {frame_idx: (cx, cy) or None}

    cap = cv2.VideoCapture(video)
    fi = 0
    n_detected = 0

    while fi < n_frames:
        ret, frame = cap.read()
        if not ret:
            break

        if fi % FRAME_SKIP == 0:
            pos = infer_ball(model, processor, frame)
            ball_positions[fi] = pos
            if pos:
                n_detected += 1
        # FRAME_SKIP間は前フレーム位置を補間
        elif fi > 0:
            ball_positions[fi] = ball_positions.get(fi - 1)

        if fi % 300 == 0:
            pos = ball_positions.get(fi)
            ps = f"({pos[0]:.0f},{pos[1]:.0f})" if pos else "None"
            detected_so_far = sum(1 for v in ball_positions.values() if v is not None)
            print(f"  frame {fi:5d}/{n_frames}  ball={ps}  検出率={detected_so_far}/{fi+1 if fi > 0 else 1}")

        fi += 1

    cap.release()

    total = len(ball_positions)
    detected = sum(1 for v in ball_positions.values() if v is not None)
    print(f"\n追跡完了: {detected}/{total} ({100*detected/max(total,1):.1f}%)")

    # ── 保存 ──────────────────────────────────────────────────
    video_stem = Path(video).stem
    pos_path = OUT_DIR / f"ball_positions_{video_stem}_{int(sec)}s.json"
    serializable = {str(k): list(v) if v else None for k, v in ball_positions.items()}
    with open(pos_path, "w") as f:
        json.dump(serializable, f)
    print(f"ボール位置保存: {pos_path}")

    # ── 軌跡動画 ──────────────────────────────────────────────
    vid_path = OUT_DIR / f"sam3_tracking_{video_stem}_{int(sec)}s.mp4"
    _draw_trajectory(video, ball_positions, n_frames, fps, W, H, vid_path)

    return pos_path


def _draw_trajectory(video_path, ball_positions, n_frames, fps, W, H, out_path):
    cap = cv2.VideoCapture(video_path)
    tmp = str(out_path).replace(".mp4", "_tmp.mp4")
    writer = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))

    trail = []
    for fi in range(n_frames):
        ret, frame = cap.read()
        if not ret:
            break
        pos = ball_positions.get(fi)
        if pos:
            trail.append(pos)
            if len(trail) > 25:
                trail.pop(0)

        for i in range(1, len(trail)):
            alpha = i / len(trail)
            c = int(255 * alpha)
            cv2.line(frame,
                     (int(trail[i-1][0]), int(trail[i-1][1])),
                     (int(trail[i][0]),   int(trail[i][1])),
                     (0, c, 255 - c), 2, cv2.LINE_AA)
        if pos:
            cv2.circle(frame, (int(pos[0]), int(pos[1])), 12, (0, 200, 255), -1)
            cv2.circle(frame, (int(pos[0]), int(pos[1])), 12, (255, 255, 255), 2)

        detected = sum(1 for v in ball_positions.values() if v is not None)
        total    = len(ball_positions)
        t = fi / fps
        cv2.putText(frame, f"SAM3  t={t:.1f}s  Ball:{'✓' if pos else '-'}  ({detected}/{total})",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3)
        cv2.putText(frame, f"SAM3  t={t:.1f}s  Ball:{'✓' if pos else '-'}  ({detected}/{total})",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        writer.write(frame)

    cap.release()
    writer.release()

    subprocess.run([
        "ffmpeg", "-y", "-i", tmp,
        "-vcodec", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "23", "-movflags", "+faststart", str(out_path)
    ], capture_output=True)
    Path(tmp).unlink(missing_ok=True)
    print(f"軌跡動画: {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sec",   type=float, default=60)
    parser.add_argument("--video", default=VIDEO)
    args = parser.parse_args()
    run(args.sec, args.video)


if __name__ == "__main__":
    main()

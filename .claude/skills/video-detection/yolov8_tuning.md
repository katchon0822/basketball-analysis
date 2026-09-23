# YOLOv8 Ball Detection - Tuning Guide

This skill provides best practices for tuning YOLOv8 object detection parameters for basketball video analysis.

## Overview

YOLOv8 (You Only Look Once version 8) is a state-of-the-art object detection model. For basketball analysis, we use it to detect the "sports ball" class (ID: 32).

## Model Selection

### Available YOLOv8 Models

| Model      | Size | Speed | Accuracy | Use Case                    |
|------------|------|-------|----------|-----------------------------|
| yolov8n.pt | 3MB  | Fastest | Good   | **Recommended** - Fast analysis |
| yolov8s.pt | 11MB | Fast    | Better | Higher accuracy needed      |
| yolov8m.pt | 26MB | Medium  | High   | Production quality          |
| yolov8l.pt | 44MB | Slow    | Higher | Maximum accuracy            |
| yolov8x.pt | 68MB | Slowest | Highest| Research/benchmark only     |

**For this project:** Use `yolov8n.pt` (nano) for speed

## Core Parameters

### 1. Confidence Threshold (`conf`)

**Definition:** Minimum confidence score (0-1) for a detection to be accepted.

**Resolution-based guidelines:**
```python
# High resolution (1080p+)
conf = 0.6  # Strict - fewer false positives

# Medium resolution (720p)
conf = 0.4  # Standard - balanced

# Low resolution (480p, 360p)
conf = 0.2  # Lenient - catch more balls, accept some false positives
```

**Example:**
```python
from ultralytics import YOLO

model = YOLO('yolov8n.pt')

# For 640×360 video
results = model(frame, classes=[32], conf=0.2, verbose=False)
```

### 2. Class Filtering (`classes`)

**Basketball detection:**
```python
classes = [32]  # Sports ball only
```

**Alternative (if struggling):**
```python
classes = [32, 37]  # Sports ball + baseball (sometimes helps)
```

### 3. Image Size (`imgsz`)

**Definition:** Input image size for the model (resize before detection).

```python
# Default (optimal for yolov8n)
imgsz = 640

# For higher accuracy (slower)
imgsz = 1280

# For speed (lower accuracy)
imgsz = 320
```

**Impact:**
- Larger `imgsz` = Better detection of small objects, slower
- Smaller `imgsz` = Faster, may miss small balls

### 4. IOU Threshold (`iou`)

**Definition:** Intersection over Union threshold for Non-Max Suppression (remove duplicate detections).

```python
# Default
iou = 0.7

# More aggressive deduplication
iou = 0.5

# Less aggressive (keep more boxes)
iou = 0.8
```

## Frame Sampling Strategy

### Why Sample?

Processing every frame is unnecessary and slow:
- 30 fps video = 1800 frames/minute
- Basketball moves continuously - sampling 3-6 fps is sufficient

### Sampling Intervals

```python
# High-resolution video (1080p)
sample_interval = 15  # Every 15th frame → ~2 fps at 30fps video

# Medium-resolution (720p)
sample_interval = 10  # Every 10th frame → ~3 fps

# Low-resolution (360p, 480p)
sample_interval = 5   # Every 5th frame → ~6 fps (need more samples)
```

### Implementation

```python
import cv2

cap = cv2.VideoCapture('video.mp4')
fps = cap.get(cv2.CAP_PROP_FPS)
sample_interval = 10

frame_num = 0
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Only process every Nth frame
    if frame_num % sample_interval == 0:
        results = model(frame, classes=[32], conf=0.4, verbose=False)
        # ... process results ...

    frame_num += 1

cap.release()
```

## Resolution-Specific Tuning

### High Resolution (1080p+)

**Characteristics:**
- Ball is large and clear
- High detail available
- YOLOv8 performs well

**Optimal settings:**
```python
conf = 0.6
sample_interval = 15
imgsz = 640
```

### Medium Resolution (720p)

**Characteristics:**
- Ball visible but smaller
- Good detection rate
- Standard use case

**Optimal settings:**
```python
conf = 0.4
sample_interval = 10
imgsz = 640
```

### Low Resolution (480p, 360p)

**Characteristics:**
- Ball is very small (few pixels)
- YOLOv8 struggles
- High false negative rate

**Optimal settings:**
```python
conf = 0.2  # Lower threshold
sample_interval = 5  # More frequent sampling
imgsz = 640  # Keep default (don't go lower)
```

**Alternative approaches:**
1. **Upscale video** before detection:
```python
frame_large = cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_CUBIC)
results = model(frame_large, ...)
```

2. **Color-based tracking** (see `color_tracking.md` skill)

## Advanced Techniques

### Multi-Scale Detection

Run detection at multiple resolutions and combine results:

```python
def multi_scale_detect(frame, model, conf=0.4):
    detections = []

    # Original scale
    results_1x = model(frame, classes=[32], conf=conf, verbose=False)
    detections.extend(extract_boxes(results_1x))

    # 1.5× scale
    frame_1_5x = cv2.resize(frame, None, fx=1.5, fy=1.5)
    results_1_5x = model(frame_1_5x, classes=[32], conf=conf, verbose=False)
    detections.extend(scale_boxes(extract_boxes(results_1_5x), 1/1.5))

    # Deduplicate with NMS
    final_detections = non_max_suppression(detections, iou_threshold=0.5)
    return final_detections
```

### Temporal Consistency

Track ball across frames using motion prediction:

```python
class BallTracker:
    def __init__(self, max_missing_frames=10):
        self.last_position = None
        self.missing_frames = 0
        self.max_missing = max_missing_frames

    def update(self, detection):
        if detection:
            self.last_position = detection
            self.missing_frames = 0
        else:
            self.missing_frames += 1

    def predict_position(self):
        """Predict where ball should be if not detected."""
        if self.missing_frames < self.max_missing and self.last_position:
            # Simple: return last known position
            return self.last_position
        return None
```

### Region of Interest (ROI)

Limit detection to court area only:

```python
# Define court boundaries (from calibration)
court_mask = np.zeros((height, width), dtype=np.uint8)
court_polygon = np.array([[50, 0], [890, 0], [890, 720], [50, 720]])
cv2.fillPoly(court_mask, [court_polygon], 255)

# Apply mask before detection
frame_masked = cv2.bitwise_and(frame, frame, mask=court_mask)
results = model(frame_masked, classes=[32], conf=0.4)
```

## Debugging and Validation

### Save Detection Frames

```python
import os

debug_dir = 'outputs/debug/detections'
os.makedirs(debug_dir, exist_ok=True)

for i, result in enumerate(results):
    if len(result.boxes) > 0:
        # Draw bounding boxes
        annotated = result.plot()
        cv2.imwrite(f'{debug_dir}/frame_{frame_num:05d}.jpg', annotated)
```

### Log Detection Statistics

```python
detection_log = []

for frame_num in range(total_frames):
    results = model(frame, classes=[32], conf=0.4)
    num_detections = len(results[0].boxes)

    detection_log.append({
        'frame': frame_num,
        'time': frame_num / fps,
        'detections': num_detections,
        'confidences': [box.conf.item() for box in results[0].boxes]
    })

# Save log
import json
with open('outputs/debug/detection_log.json', 'w') as f:
    json.dump(detection_log, f, indent=2)

# Analyze
import pandas as pd
df = pd.DataFrame(detection_log)
print(f"Total frames with detection: {(df['detections'] > 0).sum()}")
print(f"Average confidence: {df['confidences'].apply(lambda x: np.mean(x) if x else 0).mean():.2f}")
```

## Common Issues and Solutions

### Issue 1: No Detections

**Symptoms:** `len(results[0].boxes) == 0` for all frames

**Causes:**
1. Video resolution too low
2. Confidence threshold too high
3. Ball not in frame / camera angle issue
4. Wrong video codec

**Solutions:**
```python
# 1. Check video metadata
cap = cv2.VideoCapture('video.mp4')
print(f"Resolution: {int(cap.get(3))}×{int(cap.get(4))}")
print(f"FPS: {cap.get(5)}")
print(f"Total frames: {int(cap.get(7))}")

# 2. Lower confidence
conf = 0.1  # Very lenient

# 3. Try on a single clear frame
frame_clear = cv2.imread('clear_ball_frame.jpg')
results = model(frame_clear, classes=[32], conf=0.1, verbose=True)
print(f"Detections: {len(results[0].boxes)}")

# 4. Convert video
# ffmpeg -i input.mp4 -c:v libx264 -crf 23 output.mp4
```

### Issue 2: Too Many False Positives

**Symptoms:** Detecting non-ball objects (faces, other round objects)

**Solutions:**
```python
# 1. Increase confidence
conf = 0.6  # Stricter

# 2. Filter by size (basketball should be 20-100 pixels diameter)
for box in results[0].boxes:
    x, y, w, h = box.xywh[0].tolist()
    if 20 <= w <= 100 and 20 <= h <= 100:
        # Valid ball size
        pass

# 3. Filter by location (should be on court)
if 50 <= x <= 890 and 0 <= y <= 720:
    # Inside court bounds
    pass
```

### Issue 3: Inconsistent Detection

**Symptoms:** Ball detected in some frames, not in adjacent frames

**Solutions:**
```python
# 1. Use temporal smoothing
from collections import deque

detection_history = deque(maxlen=5)  # Last 5 frames

for frame in frames:
    results = model(frame, classes=[32], conf=0.4)
    detection_history.append(len(results[0].boxes) > 0)

    # Consider detected if ≥3 of last 5 frames had detection
    if sum(detection_history) >= 3:
        # Process as valid detection
        pass

# 2. Lower sample interval
sample_interval = 5  # More frequent checks
```

## Performance Optimization

### GPU Acceleration

```python
# Check GPU availability
import torch
print(f"CUDA available: {torch.cuda.is_available()}")

# Force GPU usage
model = YOLO('yolov8n.pt')
model.to('cuda')  # Move model to GPU

# Or specify device per inference
results = model(frame, device='cuda')
```

### Batch Processing

```python
# Process multiple frames at once
frames_batch = [frame1, frame2, frame3, frame4]
results_batch = model(frames_batch, classes=[32], conf=0.4)

# ~2-3× faster than individual frames
```

### Memory Management

```python
import gc

# Clear GPU memory periodically
if frame_num % 1000 == 0:
    torch.cuda.empty_cache()
    gc.collect()
```

## Complete Tuning Workflow

```python
def tune_detection_params(video_path, test_frames=100):
    """
    Test different parameter combinations to find optimal settings.
    """
    cap = cv2.VideoCapture(video_path)
    width = int(cap.get(3))
    height = int(cap.get(4))

    print(f"Video: {width}×{height}")

    # Determine resolution category
    if width >= 1920:
        print("→ High resolution detected")
        conf_range = [0.6, 0.5, 0.4]
        sample_interval = 15
    elif width >= 1280:
        print("→ Medium resolution detected")
        conf_range = [0.4, 0.3, 0.2]
        sample_interval = 10
    else:
        print("→ Low resolution detected")
        conf_range = [0.3, 0.2, 0.1]
        sample_interval = 5

    model = YOLO('yolov8n.pt')

    # Test each confidence level
    for conf in conf_range:
        detections = 0
        for i in range(test_frames):
            ret, frame = cap.read()
            if not ret:
                break

            if i % sample_interval == 0:
                results = model(frame, classes=[32], conf=conf, verbose=False)
                if len(results[0].boxes) > 0:
                    detections += 1

        detection_rate = detections / (test_frames / sample_interval)
        print(f"  conf={conf}: {detection_rate*100:.1f}% detection rate")

        # Stop if good detection rate found
        if 0.3 <= detection_rate <= 0.8:
            print(f"✓ Optimal: conf={conf}, sample_interval={sample_interval}")
            break

    cap.release()
```

## References

- [YOLOv8 Official Docs](https://docs.ultralytics.com/)
- [COCO Dataset Classes](https://tech.amikelive.com/node-718/what-object-categories-labels-are-in-coco-dataset/)
- This project: `src/yolo_ball_detector.py`

"""ジャージ番号OCRのパイロット検証。
既存の目視確認済みクロップ(バウンディングボックス)にEasyOCRを適用し、
正解ラベルと比較して認識精度を測る。
"""
import json
import re
import time
from pathlib import Path

import cv2
import easyocr

S = Path("/private/tmp/claude-501/-Users-yusaku-work/38e7d352-ffe0-4fa9-b231-3c6cb78a6143/scratchpad")
OUT = Path(__file__).resolve().parent / "outputs"
OUT.mkdir(exist_ok=True)

# (crop画像, 正解番号, チーム, 由来)
CASES = [
    ("jc_navy10.jpg", "10", "navy", "frame103 正面 前"),
    ("jc_navy7.jpg", "7", "navy", "frame103 背面"),
    ("jc_navy4.jpg", "4", "navy", "frame103 背面(ジャンプ中)"),
    ("jc_white6.jpg", "6", "white", "frame103 背面"),
    ("jc_navy4_far.jpg", "4", "navy", "far_450 背面(別フレーム)"),
]

print("[INFO] EasyOCR reader loading (digits only, en model)...")
t0 = time.time()
reader = easyocr.Reader(["en"], gpu=False)
print(f"[INFO] loaded in {time.time()-t0:.1f}s")

DIGIT_RE = re.compile(r"\d+")

def preprocess(img):
    """コントラスト強調 + 拡大。ジャージ番号は白抜き文字が多いのでCLAHEをかける。"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    return gray

results = []
correct = 0
for fname, gt, team, note in CASES:
    path = S / fname
    img = cv2.imread(str(path))
    if img is None:
        print(f"[WARN] missing {path}")
        continue

    raw_out = reader.readtext(img, detail=1, allowlist="0123456789")
    pre_out = reader.readtext(preprocess(img), detail=1, allowlist="0123456789")

    def best_guess(dets):
        if not dets:
            return None, 0.0
        dets = sorted(dets, key=lambda d: -d[2])
        return dets[0][1], dets[0][2]

    raw_guess, raw_conf = best_guess(raw_out)
    pre_guess, pre_conf = best_guess(pre_out)

    final_guess = pre_guess if pre_guess else raw_guess
    final_conf = pre_conf if pre_guess else raw_conf
    is_correct = final_guess == gt
    correct += int(is_correct)

    results.append(dict(
        file=fname, ground_truth=gt, team=team, note=note,
        raw_guess=raw_guess, raw_conf=round(raw_conf, 3),
        preprocessed_guess=pre_guess, preprocessed_conf=round(pre_conf, 3),
        final_guess=final_guess, correct=is_correct,
    ))
    mark = "OK " if is_correct else "NG "
    print(f"[{mark}] {fname:20s} GT={gt:>3s}  raw={raw_guess!r}({raw_conf:.2f})  "
          f"pre={pre_guess!r}({pre_conf:.2f})")

n = len(results)
acc = correct / n if n else 0
summary = dict(total=n, correct=correct, accuracy=round(acc, 3), cases=results)
json.dump(summary, open(OUT / "ocr_pilot_result.json", "w"), ensure_ascii=False, indent=2)
print(f"\n[RESULT] {correct}/{n} correct ({acc*100:.1f}%)")

"""ジャージ番号OCR — 複数前処理のアンサンブルで頑健性を上げる。

単純な生画像OCRは、日本の学生ユニフォームによくある "(10)" 括弧付き
表記で誤認識しやすい(括弧が余分な"1"に化ける)ことがパイロット検証で
判明した。生画像・CLAHE強調・Otsu二値化の3種類を試し、最も妥当な
1〜2桁の背番号を選ぶ。
"""
import re
from dataclasses import dataclass

import cv2
import easyocr
import numpy as np

_READER = None


def get_reader():
    global _READER
    if _READER is None:
        _READER = easyocr.Reader(["en"], gpu=False)
    return _READER


def _clahe(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
    return cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)


def _binarize(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th


@dataclass
class Candidate:
    text: str
    conf: float
    variant: str


def _trim_spurious_digit(text, conf):
    """3桁以上は括弧の誤検出を疑い、末尾/先頭を落とした2桁も候補に加える。"""
    cands = [(text, conf)]
    if len(text) >= 3:
        cands.append((text[1:], conf * 0.85))  # 先頭1文字が括弧由来の疑い
        cands.append((text[:-1], conf * 0.85))  # 末尾側の疑い
    return cands


def read_jersey_number(img_bgr, min_conf=0.15):
    """1枚の選手クロップから背番号を推定する。

    Returns: (number:str|None, confidence:float, detail:list[Candidate])
    """
    reader = get_reader()
    variants = {
        "raw": img_bgr,
        "clahe": _clahe(img_bgr),
        "binary": _binarize(img_bgr),
    }
    all_candidates = []
    for name, variant_img in variants.items():
        # まずデフォルト閾値(誤検出が少ない)、何も拾えなければ緩い閾値にエスカレーション
        dets = reader.readtext(variant_img, detail=1, allowlist="0123456789")
        if not dets:
            dets = reader.readtext(variant_img, detail=1, allowlist="0123456789",
                                    text_threshold=0.3, low_text=0.3, link_threshold=0.3,
                                    min_size=5)
            name = name + "+loose"
        for _, text, conf in dets:
            for t, c in _trim_spurious_digit(text, conf):
                if t and 0 < int(t) <= 99 and t == str(int(t)):  # 先頭0は除外、0〜99
                    all_candidates.append(Candidate(t, c, name))

    if not all_candidates:
        return None, 0.0, []

    # 同じ数字を出した候補同士で信頼度を合算し、票数×平均confでスコアリング
    grouped = {}
    for c in all_candidates:
        g = grouped.setdefault(c.text, [])
        g.append(c.conf)
    scored = [(text, len(confs) * (sum(confs) / len(confs)), confs) for text, confs in grouped.items()]
    scored.sort(key=lambda x: -x[1])
    best_text, best_score, best_confs = scored[0]
    if max(best_confs) < min_conf:
        return None, 0.0, all_candidates
    return best_text, round(max(best_confs), 3), all_candidates


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    S = Path("/private/tmp/claude-501/-Users-yusaku-work/38e7d352-ffe0-4fa9-b231-3c6cb78a6143/scratchpad")
    OUT = Path(__file__).resolve().parent / "outputs"
    OUT.mkdir(exist_ok=True)

    CASES = [
        ("jc_navy10.jpg", "10", "navy", "frame103 正面"),
        ("jc_navy7_v2.jpg", "7", "navy", "frame103 背面(bbox再調整)"),
        ("jc_navy4.jpg", "4", "navy", "frame103 背面(ジャンプ中)"),
        ("jc_white6.jpg", "6", "white", "frame103 背面"),
        ("jc_navy4_far.jpg", "4", "navy", "far_450 背面(別フレーム)"),
    ]

    results = []
    correct = 0
    for fname, gt, team, note in CASES:
        img = cv2.imread(str(S / fname))
        guess, conf, detail = read_jersey_number(img)
        ok = guess == gt
        correct += int(ok)
        results.append(dict(file=fname, ground_truth=gt, team=team, note=note,
                             guess=guess, confidence=conf, ok=ok,
                             all_candidates=[(c.text, round(c.conf, 3), c.variant) for c in detail]))
        print(f"[{'OK ' if ok else 'NG '}] {fname:20s} GT={gt:>3s}  guess={guess!r} conf={conf}")

    n = len(results)
    summary = dict(total=n, correct=correct, accuracy=round(correct / n, 3) if n else 0, cases=results)
    json.dump(summary, open(OUT / "ocr_ensemble_result.json", "w"), ensure_ascii=False, indent=2)
    print(f"\n[RESULT] {correct}/{n} correct ({100*correct/n:.1f}%)")

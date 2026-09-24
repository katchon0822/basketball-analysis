#!/usr/bin/env python3
"""
player_number_ocr.py — 選手ユニフォーム背番号OCR

DeNA方式: EasyOCRでユニフォームの背番号を読取り → Tracking IDに紐づけ
  - 複数フレームで投票して安定化
  - 番号が見えないシーンでも別フレームで特定済みならそちらを使用

Usage:
    from player_number_ocr import PlayerNumberTracker

    tracker = PlayerNumberTracker()
    # ... ループ内 ...
    tracker.update(frame, track_ids, bboxes)
    label = tracker.get_label(track_id)   # "#7" or "P12"
"""

import cv2
import numpy as np
import easyocr
from collections import defaultdict, Counter
from typing import Optional

_reader: Optional[easyocr.Reader] = None


def _get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        print("EasyOCR 初期化中 (初回のみ)...")
        _reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        print("EasyOCR 準備完了")
    return _reader


def read_jersey_number(frame: np.ndarray, bbox) -> Optional[int]:
    """
    1選手のBBoxから背番号を読取る

    BBoxの上部20-70%をクロップしてOCR実行。
    Returns: 0-99 の整数、または None (読取失敗)
    """
    x1, y1, x2, y2 = map(int, bbox)
    h, w = y2 - y1, x2 - x1
    if h < 18 or w < 8:
        return None

    # ジャージ番号はBBox上部 20-72% あたりに出やすい (背番号 / 胸番号)
    cy1 = y1 + int(h * 0.18)
    cy2 = y1 + int(h * 0.72)
    crop = frame[cy1:cy2, x1:x2]
    if crop.size == 0:
        return None

    # 小さすぎる場合は拡大 (OCR精度向上)
    if crop.shape[0] < 28:
        scale = 28 / crop.shape[0]
        crop  = cv2.resize(crop, None, fx=scale, fy=scale,
                           interpolation=cv2.INTER_LANCZOS4)

    # コントラスト強調
    gray  = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray  = cv2.equalizeHist(gray)
    crop3 = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    reader = _get_reader()
    try:
        results = reader.readtext(
            crop3,
            allowlist='0123456789',
            detail=1,
            paragraph=False,
            width_ths=0.6,
            height_ths=0.6,
        )
    except Exception:
        return None

    best_conf, best_num = 0.0, None
    for _, text, conf in results:
        text = text.strip()
        if text.isdigit() and 0 <= int(text) <= 99 and conf > best_conf:
            best_conf = conf
            best_num  = int(text)

    return best_num if best_conf >= 0.35 else None


class PlayerNumberTracker:
    """
    Tracking IDごとに背番号を投票で安定特定するクラス。

    Usage:
        tracker = PlayerNumberTracker()
        tracker.update(frame, track_ids, bboxes)
        label = tracker.get_label(track_id)  # "#7" / "P{id}"
    """

    def __init__(self, vote_window: int = 40, ocr_every: int = 8):
        """
        vote_window : 何フレーム分の投票を保持するか
        ocr_every   : 何フレームおきにOCRを実行するか (負荷調整)
        """
        self.vote_window = vote_window
        self.ocr_every   = ocr_every
        self._votes: dict[int, list] = defaultdict(list)
        self._cache: dict[int, int]  = {}
        self._tick  = 0

    def update(self, frame: np.ndarray, track_ids, bboxes):
        """フレームごとに呼び出す。track_ids と bboxes は同じ長さのリスト。"""
        self._tick += 1
        if self._tick % self.ocr_every != 0:
            return

        for tid, bbox in zip(track_ids, bboxes):
            num = read_jersey_number(frame, bbox)
            if num is not None:
                votes = self._votes[tid]
                votes.append(num)
                if len(votes) > self.vote_window:
                    votes.pop(0)
                self._cache[tid] = Counter(votes).most_common(1)[0][0]

    def get_number(self, track_id: int) -> Optional[int]:
        """最多投票の背番号 (未特定なら None)"""
        return self._cache.get(track_id)

    def get_label(self, track_id: int) -> str:
        """表示ラベル: '#7' or 'P12'"""
        num = self.get_number(track_id)
        return f"#{num}" if num is not None else f"P{track_id % 100}"

    def summary(self) -> dict:
        """{track_id: number} の一覧"""
        return dict(self._cache)

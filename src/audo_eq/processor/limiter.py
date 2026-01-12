from __future__ import annotations

import numpy as np

from .base import BaseProcessor


class LimiterProcessor(BaseProcessor):
    """Apply a simple peak limiter."""

    def __init__(self, threshold_db: float = -1.0, mode: str = "true_peak") -> None:
        self.threshold_db = float(threshold_db)
        self.mode = mode

    def process(self, audio: np.ndarray, sample_rate: float) -> np.ndarray:
        threshold = 10 ** (self.threshold_db / 20.0)
        return np.clip(audio, -threshold, threshold)

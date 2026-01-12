from __future__ import annotations

import numpy as np

from .base import BaseProcessor
from ..analyzer.loudness import LoudnessAnalyzer


class LoudnessCompProcessor(BaseProcessor):
    """Apply gain to reach a target integrated loudness."""

    def __init__(self, target_lufs: float, max_gain_db: float = 20.0) -> None:
        self.target_lufs = float(target_lufs)
        self.max_gain_db = float(max_gain_db)
        self._analyzer = LoudnessAnalyzer()

    def process(self, audio: np.ndarray, sample_rate: float) -> np.ndarray:
        current_lufs = self._analyzer.analyze(audio, sample_rate)
        gain_db = self.target_lufs - current_lufs
        gain_db = float(np.clip(gain_db, -self.max_gain_db, self.max_gain_db))
        gain = 10 ** (gain_db / 20.0)
        return (audio * gain).astype(audio.dtype, copy=False)

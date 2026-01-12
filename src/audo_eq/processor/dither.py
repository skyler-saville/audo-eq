from __future__ import annotations

import numpy as np

from .base import BaseProcessor


class DitherProcessor(BaseProcessor):
    """Add low-level noise for basic dithering."""

    def __init__(self, noise_amplitude: float = 1e-5) -> None:
        self.noise_amplitude = float(noise_amplitude)

    def process(self, audio: np.ndarray, sample_rate: float) -> np.ndarray:
        noise = np.random.uniform(
            low=-self.noise_amplitude,
            high=self.noise_amplitude,
            size=audio.shape,
        )
        return (audio + noise).astype(audio.dtype, copy=False)

from __future__ import annotations

import numpy as np

from .base import BaseProcessor


class EQMatchProcessor(BaseProcessor):
    """Apply a simple spectral curve to match a reference."""

    def __init__(self, target_eq_curve: np.ndarray, strength: float = 1.0) -> None:
        self.target_eq_curve = np.asarray(target_eq_curve, dtype=float)
        self.strength = float(strength)

    def process(self, audio: np.ndarray, sample_rate: float) -> np.ndarray:
        if self.target_eq_curve.size == 0:
            return audio

        if audio.ndim == 1:
            return self._apply_curve(audio)
        if audio.ndim == 2:
            processed = np.column_stack(
                [self._apply_curve(audio[:, idx]) for idx in range(audio.shape[1])]
            )
            return processed

        raise ValueError("Audio must be 1D (mono) or 2D (samples, channels).")

    def _apply_curve(self, channel: np.ndarray) -> np.ndarray:
        spectrum = np.fft.rfft(channel)
        magnitude = np.abs(spectrum)
        phase = np.exp(1j * np.angle(spectrum))

        target_curve = self._resample_curve(magnitude.size)
        gain = (1.0 - self.strength) + self.strength * target_curve
        gain = np.clip(gain, 1e-6, None)

        shaped = magnitude * gain * phase
        processed = np.fft.irfft(shaped, n=channel.size)
        return processed.astype(channel.dtype, copy=False)

    def _resample_curve(self, size: int) -> np.ndarray:
        if self.target_eq_curve.size == size:
            return self.target_eq_curve

        x_old = np.linspace(0.0, 1.0, self.target_eq_curve.size)
        x_new = np.linspace(0.0, 1.0, size)
        return np.interp(x_new, x_old, self.target_eq_curve)

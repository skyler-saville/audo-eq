import numpy as np


class SpectrumAnalyzer:
    """Basic spectrum analysis for EQ matching."""

    def analyze(self, audio: np.ndarray, sample_rate: float) -> np.ndarray:
        """Return a normalized magnitude spectrum."""
        if audio.ndim > 1:
            mono = np.mean(audio, axis=1)
        else:
            mono = audio

        spectrum = np.abs(np.fft.rfft(mono))
        max_val = np.max(spectrum) if spectrum.size else 0.0
        if max_val == 0.0:
            return spectrum
        return spectrum / max_val

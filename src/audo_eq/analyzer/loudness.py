# src/audo_eq/analyzer/loudness.py
import pyloudnorm as pyln
import numpy as np

class LoudnessAnalyzer:
    def analyze(self, audio: np.ndarray, sample_rate: float) -> float:
        """Return integrated LUFS of audio."""
        meter = pyln.Meter(sample_rate)
        loudness = meter.integrated_loudness(audio.T)  # .T for channel format
        return loudness
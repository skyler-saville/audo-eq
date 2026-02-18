"""Audio analysis primitives for mastering decisions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class TrackMetrics:
    """Analysis metrics extracted from a single track."""

    rms_db: float
    spectral_centroid_hz: float
    spectral_rolloff_hz: float
    low_band_energy: float
    mid_band_energy: float
    high_band_energy: float
    crest_factor_db: float
    is_clipping: bool
    is_silent: bool


@dataclass(frozen=True, slots=True)
class AnalysisPayload:
    """Combined analysis metrics for target and reference tracks."""

    target: TrackMetrics
    reference: TrackMetrics

    @property
    def rms_delta_db(self) -> float:
        return self.reference.rms_db - self.target.rms_db

    @property
    def centroid_delta_hz(self) -> float:
        return self.reference.spectral_centroid_hz - self.target.spectral_centroid_hz

    @property
    def rolloff_delta_hz(self) -> float:
        return self.reference.spectral_rolloff_hz - self.target.spectral_rolloff_hz


def _mono(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio.astype(np.float64, copy=False)
    return np.mean(audio, axis=0, dtype=np.float64)


def _rms_db(audio: np.ndarray) -> float:
    if audio.size == 0:
        return -96.0
    rms = float(np.sqrt(np.mean(np.square(audio), dtype=np.float64)))
    if rms <= 0:
        return -96.0
    return float(20.0 * np.log10(rms))


def _spectral_metrics(audio: np.ndarray, sample_rate: int) -> tuple[float, float, float, float, float]:
    if audio.size == 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0

    spectrum = np.abs(np.fft.rfft(audio))
    if not np.any(spectrum):
        return 0.0, 0.0, 0.0, 0.0, 0.0

    freqs = np.fft.rfftfreq(audio.size, d=1.0 / sample_rate)
    weight_sum = float(np.sum(spectrum))
    centroid = float(np.sum(freqs * spectrum) / weight_sum)

    cumulative = np.cumsum(spectrum)
    rolloff_idx = int(np.searchsorted(cumulative, cumulative[-1] * 0.85))
    rolloff = float(freqs[min(rolloff_idx, freqs.size - 1)])

    energy = np.square(spectrum, dtype=np.float64)
    total_energy = float(np.sum(energy))
    if total_energy <= 0:
        return centroid, rolloff, 0.0, 0.0, 0.0

    low = float(np.sum(energy[freqs < 200.0]) / total_energy)
    mid = float(np.sum(energy[(freqs >= 200.0) & (freqs < 4_000.0)]) / total_energy)
    high = float(np.sum(energy[freqs >= 4_000.0]) / total_energy)
    return centroid, rolloff, low, mid, high


def compute_track_metrics(audio: np.ndarray, sample_rate: int) -> TrackMetrics:
    """Compute mastering-oriented metrics for a track."""

    mono = _mono(audio)
    rms_db = _rms_db(mono)
    centroid, rolloff, low_band, mid_band, high_band = _spectral_metrics(mono, sample_rate)

    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    rms_linear = float(np.sqrt(np.mean(np.square(mono), dtype=np.float64))) if mono.size else 0.0
    crest_factor_db = float(20.0 * np.log10((peak + 1e-12) / (rms_linear + 1e-12)))

    return TrackMetrics(
        rms_db=rms_db,
        spectral_centroid_hz=centroid,
        spectral_rolloff_hz=rolloff,
        low_band_energy=low_band,
        mid_band_energy=mid_band,
        high_band_energy=high_band,
        crest_factor_db=crest_factor_db,
        is_clipping=peak >= 0.999,
        is_silent=rms_db <= -60.0,
    )


def analyze_tracks(target_audio: np.ndarray, reference_audio: np.ndarray, sample_rate: int) -> AnalysisPayload:
    """Analyze target and reference tracks for downstream decisioning."""

    return AnalysisPayload(
        target=compute_track_metrics(target_audio, sample_rate),
        reference=compute_track_metrics(reference_audio, sample_rate),
    )

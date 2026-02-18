"""Audio analysis primitives for mastering decisions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_EQ_BAND_EDGES_HZ = np.array([20.0, 60.0, 120.0, 250.0, 500.0, 1_000.0, 2_000.0, 4_000.0, 8_000.0, 16_000.0])
_EQ_SMOOTHING_KERNEL = np.array([0.25, 0.5, 0.25], dtype=np.float64)
_EQ_MAX_ABS_DB = 4.0
_EQ_MIN_CORRECTION_DB = 0.75
_TARGET_NORMALIZED_RMS_DB = -24.0


@dataclass(frozen=True, slots=True)
class EqBandCorrection:
    """Per-band EQ correction in decibels for reference matching."""

    center_hz: float
    delta_db: float


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
    eq_band_corrections: tuple[EqBandCorrection, ...]

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


def _normalize_to_target_rms(audio: np.ndarray, target_rms_db: float = _TARGET_NORMALIZED_RMS_DB) -> np.ndarray:
    """Normalize loudness by RMS so spectral deltas compare tone, not level."""

    if audio.size == 0:
        return audio

    rms_linear = float(np.sqrt(np.mean(np.square(audio), dtype=np.float64)))
    if rms_linear <= 1e-12:
        return audio

    target_linear = float(10.0 ** (target_rms_db / 20.0))
    gain = target_linear / rms_linear
    normalized = audio * gain
    return np.clip(normalized, -1.0, 1.0)


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


def _band_energies(audio: np.ndarray, sample_rate: int, edges_hz: np.ndarray = _EQ_BAND_EDGES_HZ) -> tuple[np.ndarray, np.ndarray]:
    """Average energy per octave-ish band from FFT power spectrum."""

    if audio.size == 0:
        return np.array([]), np.array([])

    spectrum = np.abs(np.fft.rfft(audio))
    power = np.square(spectrum, dtype=np.float64)
    freqs = np.fft.rfftfreq(audio.size, d=1.0 / sample_rate)

    energies: list[float] = []
    centers: list[float] = []
    for low_hz, high_hz in zip(edges_hz[:-1], edges_hz[1:]):
        band_mask = (freqs >= low_hz) & (freqs < high_hz)
        if not np.any(band_mask):
            energies.append(0.0)
            centers.append(float(np.sqrt(low_hz * high_hz)))
            continue

        energies.append(float(np.mean(power[band_mask])))
        centers.append(float(np.sqrt(low_hz * high_hz)))

    return np.asarray(centers, dtype=np.float64), np.asarray(energies, dtype=np.float64)


def _derive_eq_band_corrections(
    target_audio: np.ndarray,
    reference_audio: np.ndarray,
    sample_rate: int,
    max_abs_db: float = _EQ_MAX_ABS_DB,
    min_correction_db: float = _EQ_MIN_CORRECTION_DB,
) -> tuple[EqBandCorrection, ...]:
    """Create bounded/smoothed dB deltas for an EQ stage."""

    target_centers, target_energy = _band_energies(target_audio, sample_rate)
    reference_centers, reference_energy = _band_energies(reference_audio, sample_rate)
    if target_energy.size == 0 or reference_energy.size == 0:
        return tuple()

    if target_centers.size != reference_centers.size or not np.allclose(target_centers, reference_centers):
        raise ValueError("Band centers must match for EQ delta derivation.")

    target_db = 10.0 * np.log10(target_energy + 1e-12)
    reference_db = 10.0 * np.log10(reference_energy + 1e-12)
    deltas_db = reference_db - target_db
    smoothed = np.convolve(deltas_db, _EQ_SMOOTHING_KERNEL, mode="same")
    bounded = np.clip(smoothed, -max_abs_db, max_abs_db)

    corrections = []
    for center_hz, delta_db in zip(target_centers, bounded):
        if abs(delta_db) < min_correction_db:
            continue
        corrections.append(EqBandCorrection(center_hz=float(center_hz), delta_db=float(delta_db)))
    return tuple(corrections)


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

    target_mono = _mono(target_audio)
    reference_mono = _mono(reference_audio)
    target_normalized = _normalize_to_target_rms(target_mono)
    reference_normalized = _normalize_to_target_rms(reference_mono)

    return AnalysisPayload(
        target=compute_track_metrics(target_audio, sample_rate),
        reference=compute_track_metrics(reference_audio, sample_rate),
        eq_band_corrections=_derive_eq_band_corrections(
            target_audio=target_normalized,
            reference_audio=reference_normalized,
            sample_rate=sample_rate,
        ),
    )

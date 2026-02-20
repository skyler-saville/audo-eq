"""Audio analysis primitives for mastering decisions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class AnalysisTuning:
    """Tunable constants for analysis and reference-match EQ derivation."""

    eq_band_edges_hz: tuple[float, ...]
    eq_smoothing_kernel: tuple[float, ...]
    eq_max_abs_db: float
    eq_min_correction_db: float
    target_normalized_rms_db: float


ANALYSIS_TUNINGS: dict[str, AnalysisTuning] = {
    "default": AnalysisTuning(
        eq_band_edges_hz=(
            20.0,
            60.0,
            120.0,
            250.0,
            500.0,
            1_000.0,
            2_000.0,
            4_000.0,
            8_000.0,
            16_000.0,
        ),
        eq_smoothing_kernel=(0.25, 0.5, 0.25),
        eq_max_abs_db=4.0,
        eq_min_correction_db=0.75,
        target_normalized_rms_db=-24.0,
    ),
    "conservative": AnalysisTuning(
        eq_band_edges_hz=(
            20.0,
            60.0,
            120.0,
            250.0,
            500.0,
            1_000.0,
            2_000.0,
            4_000.0,
            8_000.0,
            16_000.0,
        ),
        eq_smoothing_kernel=(0.2, 0.6, 0.2),
        eq_max_abs_db=3.0,
        eq_min_correction_db=1.0,
        target_normalized_rms_db=-24.0,
    ),
    "aggressive": AnalysisTuning(
        eq_band_edges_hz=(
            20.0,
            60.0,
            120.0,
            250.0,
            500.0,
            1_000.0,
            2_000.0,
            4_000.0,
            8_000.0,
            16_000.0,
        ),
        eq_smoothing_kernel=(0.3, 0.4, 0.3),
        eq_max_abs_db=5.5,
        eq_min_correction_db=0.5,
        target_normalized_rms_db=-23.0,
    ),
}


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
    sibilance_ratio: float
    crest_factor_db: float
    is_clipping: bool
    is_silent: bool


@dataclass(frozen=True, slots=True)
class TemporalTrackMetrics:
    """Short-time descriptors for dynamics and spectral balance."""

    frame_times_s: tuple[float, ...] = tuple()
    loudness_envelope_db: tuple[float, ...] = tuple()
    band_centers_hz: tuple[float, ...] = tuple()
    multiband_energy_trajectories: tuple[tuple[float, ...], ...] = tuple()
    transient_density_trajectory: tuple[float, ...] = tuple()
    crest_factor_trajectory_db: tuple[float, ...] = tuple()
    mean_transient_density: float = 0.0
    peak_transient_density: float = 0.0
    mean_crest_factor_db: float = 0.0
    peak_crest_factor_db: float = 0.0


@dataclass(frozen=True, slots=True)
class AnalysisPayload:
    """Combined analysis metrics for target and reference tracks."""

    target: TrackMetrics
    reference: TrackMetrics
    eq_band_corrections: tuple[EqBandCorrection, ...]
    target_temporal: TemporalTrackMetrics = TemporalTrackMetrics()
    reference_temporal: TemporalTrackMetrics = TemporalTrackMetrics()

    @property
    def rms_delta_db(self) -> float:
        return self.reference.rms_db - self.target.rms_db

    @property
    def centroid_delta_hz(self) -> float:
        return self.reference.spectral_centroid_hz - self.target.spectral_centroid_hz

    @property
    def rolloff_delta_hz(self) -> float:
        return self.reference.spectral_rolloff_hz - self.target.spectral_rolloff_hz

    @property
    def sibilance_ratio_delta(self) -> float:
        return self.target.sibilance_ratio - self.reference.sibilance_ratio


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


def _normalize_to_target_rms(audio: np.ndarray, target_rms_db: float) -> np.ndarray:
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


def _spectral_metrics(
    audio: np.ndarray, sample_rate: int
) -> tuple[float, float, float, float, float, float]:
    if audio.size == 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    spectrum = np.abs(np.fft.rfft(audio))
    if not np.any(spectrum):
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    freqs = np.fft.rfftfreq(audio.size, d=1.0 / sample_rate)
    weight_sum = float(np.sum(spectrum))
    centroid = float(np.sum(freqs * spectrum) / weight_sum)

    cumulative = np.cumsum(spectrum)
    rolloff_idx = int(np.searchsorted(cumulative, cumulative[-1] * 0.85))
    rolloff = float(freqs[min(rolloff_idx, freqs.size - 1)])

    energy = np.square(spectrum, dtype=np.float64)
    total_energy = float(np.sum(energy))
    if total_energy <= 0:
        return centroid, rolloff, 0.0, 0.0, 0.0, 0.0

    low = float(np.sum(energy[freqs < 200.0]) / total_energy)
    mid = float(np.sum(energy[(freqs >= 200.0) & (freqs < 4_000.0)]) / total_energy)
    high = float(np.sum(energy[freqs >= 4_000.0]) / total_energy)
    sibilant = float(np.sum(energy[(freqs >= 5_000.0) & (freqs <= 10_000.0)]))
    sibilance_ratio = float(sibilant / (total_energy + 1e-12))
    return centroid, rolloff, low, mid, high, sibilance_ratio


def _band_energies(
    audio: np.ndarray, sample_rate: int, edges_hz: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
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
    tuning: AnalysisTuning,
) -> tuple[EqBandCorrection, ...]:
    """Create bounded/smoothed dB deltas for an EQ stage."""

    edges_hz = np.asarray(tuning.eq_band_edges_hz, dtype=np.float64)
    smoothing_kernel = np.asarray(tuning.eq_smoothing_kernel, dtype=np.float64)
    target_centers, target_energy = _band_energies(
        target_audio, sample_rate, edges_hz=edges_hz
    )
    reference_centers, reference_energy = _band_energies(
        reference_audio, sample_rate, edges_hz=edges_hz
    )
    if target_energy.size == 0 or reference_energy.size == 0:
        return tuple()

    if target_centers.size != reference_centers.size or not np.allclose(
        target_centers, reference_centers
    ):
        raise ValueError("Band centers must match for EQ delta derivation.")

    target_db = 10.0 * np.log10(target_energy + 1e-12)
    reference_db = 10.0 * np.log10(reference_energy + 1e-12)
    deltas_db = reference_db - target_db
    smoothed = np.convolve(deltas_db, smoothing_kernel, mode="same")
    bounded = np.clip(smoothed, -tuning.eq_max_abs_db, tuning.eq_max_abs_db)

    corrections = []
    for center_hz, delta_db in zip(target_centers, bounded):
        if abs(delta_db) < tuning.eq_min_correction_db:
            continue
        corrections.append(
            EqBandCorrection(center_hz=float(center_hz), delta_db=float(delta_db))
        )
    return tuple(corrections)


def _frame_signal(
    audio: np.ndarray,
    sample_rate: int,
    window_duration_s: float,
    overlap_ratio: float,
) -> tuple[np.ndarray, int, int]:
    """Return overlapping analysis frames [n_frames, frame_size]."""

    frame_size = max(1, int(sample_rate * window_duration_s))
    overlap_ratio = float(np.clip(overlap_ratio, 0.0, 0.95))
    hop_size = max(1, int(frame_size * (1.0 - overlap_ratio)))

    if audio.size <= frame_size:
        padded = np.pad(audio, (0, max(0, frame_size - audio.size)), mode="constant")
        return padded.reshape(1, frame_size), frame_size, hop_size

    starts = np.arange(0, audio.size - frame_size + 1, hop_size, dtype=np.int64)
    if starts[-1] + frame_size < audio.size:
        starts = np.concatenate([starts, np.array([audio.size - frame_size])])
    frames = np.stack([audio[start : start + frame_size] for start in starts], axis=0)
    return frames, frame_size, hop_size


def _short_time_metrics(
    audio: np.ndarray,
    sample_rate: int,
    tuning: AnalysisTuning,
    window_duration_s: float = 0.3,
    overlap_ratio: float = 0.5,
) -> TemporalTrackMetrics:
    """Compute temporal descriptors over short overlapping windows."""

    if audio.size == 0:
        return TemporalTrackMetrics()

    frames, frame_size, hop_size = _frame_signal(
        audio,
        sample_rate=sample_rate,
        window_duration_s=window_duration_s,
        overlap_ratio=overlap_ratio,
    )
    frame_times = tuple(
        ((idx * hop_size) + (0.5 * frame_size)) / sample_rate
        for idx in range(frames.shape[0])
    )

    loudness_envelope = tuple(float(_rms_db(frame)) for frame in frames)

    band_edges_hz = np.asarray(tuning.eq_band_edges_hz, dtype=np.float64)
    band_centers, _ = _band_energies(frames[0], sample_rate=sample_rate, edges_hz=band_edges_hz)
    per_frame_band_energies: list[tuple[float, ...]] = []
    crest_factors: list[float] = []
    transient_density: list[float] = []
    for frame in frames:
        _, band_energy = _band_energies(frame, sample_rate=sample_rate, edges_hz=band_edges_hz)
        normalized_band_energy = band_energy / (float(np.sum(band_energy)) + 1e-12)
        per_frame_band_energies.append(tuple(float(v) for v in normalized_band_energy))

        peak = float(np.max(np.abs(frame)))
        rms_linear = float(np.sqrt(np.mean(np.square(frame), dtype=np.float64)))
        crest_factors.append(float(20.0 * np.log10((peak + 1e-12) / (rms_linear + 1e-12))))

        if frame.size <= 1:
            transient_density.append(0.0)
            continue
        diff = np.abs(np.diff(frame, prepend=frame[0]))
        threshold = float(np.mean(diff) + 2.0 * np.std(diff))
        transient_density.append(float(np.mean(diff > threshold)))

    return TemporalTrackMetrics(
        frame_times_s=frame_times,
        loudness_envelope_db=loudness_envelope,
        band_centers_hz=tuple(float(v) for v in band_centers),
        multiband_energy_trajectories=tuple(per_frame_band_energies),
        transient_density_trajectory=tuple(transient_density),
        crest_factor_trajectory_db=tuple(crest_factors),
        mean_transient_density=float(np.mean(transient_density)) if transient_density else 0.0,
        peak_transient_density=float(np.max(transient_density)) if transient_density else 0.0,
        mean_crest_factor_db=float(np.mean(crest_factors)) if crest_factors else 0.0,
        peak_crest_factor_db=float(np.max(crest_factors)) if crest_factors else 0.0,
    )


def resolve_analysis_tuning(profile: str = "default") -> AnalysisTuning:
    try:
        return ANALYSIS_TUNINGS[profile]
    except KeyError as exc:
        allowed = ", ".join(sorted(ANALYSIS_TUNINGS))
        raise ValueError(
            f"Unknown analysis profile '{profile}'. Allowed: {allowed}."
        ) from exc


def compute_track_metrics(audio: np.ndarray, sample_rate: int) -> TrackMetrics:
    """Compute mastering-oriented metrics for a track."""

    mono = _mono(audio)
    rms_db = _rms_db(mono)
    centroid, rolloff, low_band, mid_band, high_band, sibilance_ratio = (
        _spectral_metrics(mono, sample_rate)
    )

    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    rms_linear = (
        float(np.sqrt(np.mean(np.square(mono), dtype=np.float64))) if mono.size else 0.0
    )
    crest_factor_db = float(20.0 * np.log10((peak + 1e-12) / (rms_linear + 1e-12)))

    return TrackMetrics(
        rms_db=rms_db,
        spectral_centroid_hz=centroid,
        spectral_rolloff_hz=rolloff,
        low_band_energy=low_band,
        mid_band_energy=mid_band,
        high_band_energy=high_band,
        sibilance_ratio=sibilance_ratio,
        crest_factor_db=crest_factor_db,
        is_clipping=peak >= 0.999,
        is_silent=rms_db <= -60.0,
    )


def analyze_tracks(
    target_audio: np.ndarray,
    reference_audio: np.ndarray,
    sample_rate: int,
    profile: str = "default",
) -> AnalysisPayload:
    """Analyze target and reference tracks for downstream decisioning."""

    tuning = resolve_analysis_tuning(profile)
    target_mono = _mono(target_audio)
    reference_mono = _mono(reference_audio)
    target_normalized = _normalize_to_target_rms(
        target_mono, target_rms_db=tuning.target_normalized_rms_db
    )
    reference_normalized = _normalize_to_target_rms(
        reference_mono, target_rms_db=tuning.target_normalized_rms_db
    )

    return AnalysisPayload(
        target=compute_track_metrics(target_audio, sample_rate),
        reference=compute_track_metrics(reference_audio, sample_rate),
        eq_band_corrections=_derive_eq_band_corrections(
            target_audio=target_normalized,
            reference_audio=reference_normalized,
            sample_rate=sample_rate,
            tuning=tuning,
        ),
        target_temporal=_short_time_metrics(
            target_normalized,
            sample_rate=sample_rate,
            tuning=tuning,
        ),
        reference_temporal=_short_time_metrics(
            reference_normalized,
            sample_rate=sample_rate,
            tuning=tuning,
        ),
    )

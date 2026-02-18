"""DSP processing chain construction and application."""

from __future__ import annotations

from enum import Enum

import numpy as np
import pyloudnorm as pyln
from pedalboard import (
    Compressor,
    Gain,
    HighShelfFilter,
    HighpassFilter,
    Limiter,
    LowShelfFilter,
    Pedalboard,
)

from .analysis import EqBandCorrection
from .decision import DecisionPayload

_POST_LIMITER_LUFS_TOLERANCE = 0.3


class EqMode(str, Enum):
    """Available EQ behavior profiles."""

    FIXED = "fixed"
    REFERENCE_MATCH = "reference-match"


def _audio_for_loudness_measurement(audio: np.ndarray) -> np.ndarray:
    """Convert channel-first pedalboard arrays for pyloudnorm."""

    if audio.ndim == 1:
        return audio.astype(np.float64, copy=False)
    return np.moveaxis(audio, 0, -1).astype(np.float64, copy=False)


def measure_integrated_lufs(audio: np.ndarray, sample_rate: int) -> float:
    """Measure integrated loudness in LUFS."""

    meter = pyln.Meter(sample_rate)
    measured = float(meter.integrated_loudness(_audio_for_loudness_measurement(audio)))
    if not np.isfinite(measured):
        return -70.0
    return measured


def _build_reference_match_eq_stage(eq_band_corrections: tuple[EqBandCorrection, ...]) -> list:
    """Map per-band dB deltas into a compact Pedalboard filter bank."""

    plugins: list = []
    for correction in eq_band_corrections:
        center_hz = correction.center_hz
        gain_db = float(correction.delta_db)
        if center_hz <= 250.0:
            plugins.append(LowShelfFilter(cutoff_frequency_hz=max(40.0, center_hz), gain_db=gain_db))
            continue

        if center_hz >= 4_000.0:
            plugins.append(HighShelfFilter(cutoff_frequency_hz=min(12_000.0, center_hz), gain_db=gain_db))
            continue

        # Approximate a broad bell with opposing shelves around the center.
        plugins.append(LowShelfFilter(cutoff_frequency_hz=max(100.0, center_hz / 1.6), gain_db=gain_db * 0.5))
        plugins.append(HighShelfFilter(cutoff_frequency_hz=min(10_000.0, center_hz * 1.6), gain_db=-gain_db * 0.5))

    return plugins


def build_dsp_chain(
    decision: DecisionPayload,
    eq_mode: EqMode = EqMode.FIXED,
    eq_band_corrections: tuple[EqBandCorrection, ...] = tuple(),
) -> Pedalboard:
    """Build the mastering DSP chain from the decision payload."""

    plugins = [
        HighpassFilter(cutoff_frequency_hz=30.0),
        LowShelfFilter(cutoff_frequency_hz=125.0, gain_db=decision.low_shelf_gain_db),
        HighShelfFilter(cutoff_frequency_hz=6_000.0, gain_db=decision.high_shelf_gain_db),
    ]

    if eq_mode is EqMode.REFERENCE_MATCH:
        plugins.extend(_build_reference_match_eq_stage(eq_band_corrections))

    plugins.extend(
        [
            Compressor(
                threshold_db=decision.compressor_threshold_db,
                ratio=decision.compressor_ratio,
                attack_ms=15.0,
                release_ms=120.0,
            ),
            Gain(gain_db=decision.gain_db),
            Limiter(threshold_db=decision.limiter_ceiling_db, release_ms=150.0),
        ]
    )

    return Pedalboard(plugins)


def apply_processing(
    target_audio: np.ndarray,
    sample_rate: int,
    decision: DecisionPayload,
    eq_mode: EqMode = EqMode.FIXED,
    eq_band_corrections: tuple[EqBandCorrection, ...] = tuple(),
) -> np.ndarray:
    """Apply the constructed DSP chain to target audio."""

    board = build_dsp_chain(decision, eq_mode=eq_mode, eq_band_corrections=eq_band_corrections)
    return board(target_audio, sample_rate)


def apply_processing_with_loudness_target(
    target_audio: np.ndarray,
    sample_rate: int,
    decision: DecisionPayload,
    loudness_gain_db: float,
    target_lufs: float,
    eq_mode: EqMode = EqMode.FIXED,
    eq_band_corrections: tuple[EqBandCorrection, ...] = tuple(),
) -> np.ndarray:
    """Apply mastering chain with loudness targeting around the final limiter."""

    pre_limiter_plugins = [
        HighpassFilter(cutoff_frequency_hz=30.0),
        LowShelfFilter(cutoff_frequency_hz=125.0, gain_db=decision.low_shelf_gain_db),
        HighShelfFilter(cutoff_frequency_hz=6_000.0, gain_db=decision.high_shelf_gain_db),
    ]
    if eq_mode is EqMode.REFERENCE_MATCH:
        pre_limiter_plugins.extend(_build_reference_match_eq_stage(eq_band_corrections))

    pre_limiter_plugins.extend(
        [
            Compressor(
                threshold_db=decision.compressor_threshold_db,
                ratio=decision.compressor_ratio,
                attack_ms=15.0,
                release_ms=120.0,
            ),
            Gain(gain_db=decision.gain_db + loudness_gain_db),
        ]
    )

    pre_limiter_chain = Pedalboard(pre_limiter_plugins)
    pre_limiter_audio = pre_limiter_chain(target_audio, sample_rate)

    limiter = Limiter(threshold_db=decision.limiter_ceiling_db, release_ms=150.0)
    limited_audio = limiter(pre_limiter_audio, sample_rate)

    final_lufs = measure_integrated_lufs(limited_audio, sample_rate)
    correction_db = float(np.clip(target_lufs - final_lufs, -1.5, 1.5))
    if abs(correction_db) < _POST_LIMITER_LUFS_TOLERANCE:
        return limited_audio

    post_gain = Gain(gain_db=correction_db)
    corrected_audio = post_gain(limited_audio, sample_rate)
    return limiter(corrected_audio, sample_rate)

"""DSP processing chain construction and application."""

from __future__ import annotations

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

from .decision import DecisionPayload

_POST_LIMITER_LUFS_TOLERANCE = 0.3


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


def build_dsp_chain(decision: DecisionPayload) -> Pedalboard:
    """Build the mastering DSP chain from the decision payload."""

    return Pedalboard(
        [
            HighpassFilter(cutoff_frequency_hz=30.0),
            LowShelfFilter(cutoff_frequency_hz=125.0, gain_db=decision.low_shelf_gain_db),
            HighShelfFilter(cutoff_frequency_hz=6_000.0, gain_db=decision.high_shelf_gain_db),
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


def apply_processing(target_audio: np.ndarray, sample_rate: int, decision: DecisionPayload) -> np.ndarray:
    """Apply the constructed DSP chain to target audio."""

    board = build_dsp_chain(decision)
    return board(target_audio, sample_rate)


def apply_processing_with_loudness_target(
    target_audio: np.ndarray,
    sample_rate: int,
    decision: DecisionPayload,
    loudness_gain_db: float,
    target_lufs: float,
) -> np.ndarray:
    """Apply mastering chain with loudness targeting around the final limiter."""

    pre_limiter_chain = Pedalboard(
        [
            HighpassFilter(cutoff_frequency_hz=30.0),
            LowShelfFilter(cutoff_frequency_hz=125.0, gain_db=decision.low_shelf_gain_db),
            HighShelfFilter(cutoff_frequency_hz=6_000.0, gain_db=decision.high_shelf_gain_db),
            Compressor(
                threshold_db=decision.compressor_threshold_db,
                ratio=decision.compressor_ratio,
                attack_ms=15.0,
                release_ms=120.0,
            ),
            Gain(gain_db=decision.gain_db + loudness_gain_db),
        ]
    )
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

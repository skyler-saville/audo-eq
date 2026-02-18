"""DSP processing chain construction and application."""

from __future__ import annotations

import numpy as np
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

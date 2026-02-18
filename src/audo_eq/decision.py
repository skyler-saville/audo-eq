"""Mapping analysis metrics into concrete mastering decisions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .analysis import AnalysisPayload


@dataclass(frozen=True, slots=True)
class DecisionPayload:
    """Mastering decisions derived from analysis metrics."""

    gain_db: float
    low_shelf_gain_db: float
    high_shelf_gain_db: float
    compressor_threshold_db: float
    compressor_ratio: float
    limiter_ceiling_db: float


def _clamp(value: float, low: float, high: float) -> float:
    return float(np.clip(value, low, high))


def decide_mastering(analysis: AnalysisPayload) -> DecisionPayload:
    """Translate analysis deltas into DSP parameters."""

    gain_db = _clamp(analysis.rms_delta_db, -8.0, 8.0)

    low_delta = analysis.reference.low_band_energy - analysis.target.low_band_energy
    high_delta = analysis.reference.high_band_energy - analysis.target.high_band_energy

    low_shelf_gain_db = _clamp(low_delta * 12.0, -3.0, 3.0)
    high_shelf_gain_db = _clamp(high_delta * 12.0, -3.0, 3.0)

    crest_delta = analysis.target.crest_factor_db - analysis.reference.crest_factor_db
    compressor_threshold_db = _clamp(-22.0 + crest_delta * 1.2, -30.0, -14.0)
    compressor_ratio = _clamp(2.2 + max(0.0, crest_delta) * 0.3, 1.5, 4.0)

    limiter_ceiling_db = -1.0 if analysis.target.is_clipping else -0.9

    return DecisionPayload(
        gain_db=gain_db,
        low_shelf_gain_db=low_shelf_gain_db,
        high_shelf_gain_db=high_shelf_gain_db,
        compressor_threshold_db=compressor_threshold_db,
        compressor_ratio=compressor_ratio,
        limiter_ceiling_db=limiter_ceiling_db,
    )

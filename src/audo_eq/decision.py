"""Mapping analysis metrics into concrete mastering decisions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .analysis import AnalysisPayload


@dataclass(frozen=True, slots=True)
class DecisionTuning:
    """Tunable constants for translating analysis deltas into decisions."""

    gain_clamp_db: tuple[float, float]
    shelf_scale: float
    shelf_clamp_db: tuple[float, float]
    compressor_base_threshold_db: float
    compressor_threshold_scale: float
    compressor_threshold_clamp_db: tuple[float, float]
    compressor_base_ratio: float
    compressor_ratio_scale: float
    compressor_ratio_clamp: tuple[float, float]
    limiter_ceiling_clipping_db: float
    limiter_ceiling_default_db: float


DECISION_TUNINGS: dict[str, DecisionTuning] = {
    "default": DecisionTuning(
        gain_clamp_db=(-8.0, 8.0),
        shelf_scale=12.0,
        shelf_clamp_db=(-3.0, 3.0),
        compressor_base_threshold_db=-22.0,
        compressor_threshold_scale=1.2,
        compressor_threshold_clamp_db=(-30.0, -14.0),
        compressor_base_ratio=2.2,
        compressor_ratio_scale=0.3,
        compressor_ratio_clamp=(1.5, 4.0),
        limiter_ceiling_clipping_db=-1.0,
        limiter_ceiling_default_db=-0.9,
    ),
    "conservative": DecisionTuning(
        gain_clamp_db=(-6.0, 6.0),
        shelf_scale=9.0,
        shelf_clamp_db=(-2.25, 2.25),
        compressor_base_threshold_db=-20.0,
        compressor_threshold_scale=0.8,
        compressor_threshold_clamp_db=(-27.0, -16.0),
        compressor_base_ratio=1.9,
        compressor_ratio_scale=0.2,
        compressor_ratio_clamp=(1.3, 3.0),
        limiter_ceiling_clipping_db=-1.1,
        limiter_ceiling_default_db=-1.0,
    ),
    "aggressive": DecisionTuning(
        gain_clamp_db=(-9.0, 9.0),
        shelf_scale=14.0,
        shelf_clamp_db=(-4.0, 4.0),
        compressor_base_threshold_db=-24.0,
        compressor_threshold_scale=1.5,
        compressor_threshold_clamp_db=(-32.0, -12.0),
        compressor_base_ratio=2.6,
        compressor_ratio_scale=0.45,
        compressor_ratio_clamp=(1.8, 5.0),
        limiter_ceiling_clipping_db=-0.9,
        limiter_ceiling_default_db=-0.7,
    ),
}


def resolve_decision_tuning(profile: str = "default") -> DecisionTuning:
    try:
        return DECISION_TUNINGS[profile]
    except KeyError as exc:
        allowed = ", ".join(sorted(DECISION_TUNINGS))
        raise ValueError(f"Unknown decision profile '{profile}'. Allowed: {allowed}.") from exc


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


def decide_mastering(analysis: AnalysisPayload, profile: str = "default") -> DecisionPayload:
    """Translate analysis deltas into DSP parameters."""

    tuning = resolve_decision_tuning(profile)
    gain_db = _clamp(analysis.rms_delta_db, *tuning.gain_clamp_db)

    low_delta = analysis.reference.low_band_energy - analysis.target.low_band_energy
    high_delta = analysis.reference.high_band_energy - analysis.target.high_band_energy

    low_shelf_gain_db = _clamp(low_delta * tuning.shelf_scale, *tuning.shelf_clamp_db)
    high_shelf_gain_db = _clamp(high_delta * tuning.shelf_scale, *tuning.shelf_clamp_db)

    crest_delta = analysis.target.crest_factor_db - analysis.reference.crest_factor_db
    compressor_threshold_db = _clamp(
        tuning.compressor_base_threshold_db + crest_delta * tuning.compressor_threshold_scale,
        *tuning.compressor_threshold_clamp_db,
    )
    compressor_ratio = _clamp(
        tuning.compressor_base_ratio + max(0.0, crest_delta) * tuning.compressor_ratio_scale,
        *tuning.compressor_ratio_clamp,
    )

    limiter_ceiling_db = (
        tuning.limiter_ceiling_clipping_db if analysis.target.is_clipping else tuning.limiter_ceiling_default_db
    )

    return DecisionPayload(
        gain_db=gain_db,
        low_shelf_gain_db=low_shelf_gain_db,
        high_shelf_gain_db=high_shelf_gain_db,
        compressor_threshold_db=compressor_threshold_db,
        compressor_ratio=compressor_ratio,
        limiter_ceiling_db=limiter_ceiling_db,
    )

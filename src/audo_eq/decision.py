"""Mapping analysis metrics into concrete mastering decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

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
    de_esser_threshold_base: float
    de_esser_threshold_delta_scale: float
    de_esser_threshold_clamp: tuple[float, float]
    de_esser_depth_scale: float
    de_esser_depth_clamp_db: tuple[float, float]


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
        de_esser_threshold_base=0.08,
        de_esser_threshold_delta_scale=0.2,
        de_esser_threshold_clamp=(0.04, 0.2),
        de_esser_depth_scale=30.0,
        de_esser_depth_clamp_db=(0.0, 6.0),
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
        de_esser_threshold_base=0.1,
        de_esser_threshold_delta_scale=0.15,
        de_esser_threshold_clamp=(0.05, 0.22),
        de_esser_depth_scale=24.0,
        de_esser_depth_clamp_db=(0.0, 4.0),
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
        de_esser_threshold_base=0.07,
        de_esser_threshold_delta_scale=0.25,
        de_esser_threshold_clamp=(0.035, 0.18),
        de_esser_depth_scale=36.0,
        de_esser_depth_clamp_db=(0.0, 8.0),
    ),
}


def resolve_decision_tuning(profile: str = "default") -> DecisionTuning:
    try:
        return DECISION_TUNINGS[profile]
    except KeyError as exc:
        allowed = ", ".join(sorted(DECISION_TUNINGS))
        raise ValueError(
            f"Unknown decision profile '{profile}'. Allowed: {allowed}."
        ) from exc


@dataclass(frozen=True, slots=True)
class DecisionPayload:
    """Mastering decisions derived from analysis metrics."""

    gain_db: float
    low_shelf_gain_db: float
    high_shelf_gain_db: float
    compressor_threshold_db: float
    compressor_ratio: float
    limiter_ceiling_db: float
    de_esser_threshold: float = 0.0
    de_esser_depth_db: float = 0.0
    multiband_compression_enabled: bool = False
    multiband_low_threshold_db: float = -24.0
    multiband_low_ratio: float = 1.0
    multiband_mid_threshold_db: float = -24.0
    multiband_mid_ratio: float = 1.0
    multiband_high_threshold_db: float = -24.0
    multiband_high_ratio: float = 1.0
    dynamic_eq_enabled: bool = False
    dynamic_eq_harsh_threshold: float = 0.0
    dynamic_eq_harsh_attenuation_db: float = 0.0
    stereo_ms_correction_enabled: bool = False
    stereo_mid_gain_db: float = 0.0
    stereo_side_gain_db: float = 0.0


class StrategyCondition(str, Enum):
    """Named mix conditions inferred from analysis features."""

    BASS_HEAVY = "bass_heavy"
    HARSH_UPPER_MIDS = "harsh_upper_mids"
    OVER_COMPRESSED = "over_compressed"
    CLIPPING_PRONE = "clipping_prone"


@dataclass(frozen=True, slots=True)
class DecisionStrategyPolicy:
    """Variant behavior knobs applied on top of profile-level tuning."""

    strategy_id: str
    eq_intensity_scale: float = 1.0
    dynamics_aggressiveness_scale: float = 1.0
    de_esser_depth_scale: float = 1.0
    de_esser_threshold_offset: float = 0.0
    limiter_ceiling_offset_db: float = 0.0


@dataclass(frozen=True, slots=True)
class StrategySelection:
    """Auditable strategy-selection outcome."""

    policy: DecisionStrategyPolicy
    conditions: tuple[StrategyCondition, ...]


DECISION_STRATEGY_POLICIES: dict[str, DecisionStrategyPolicy] = {
    "balanced": DecisionStrategyPolicy(strategy_id="balanced"),
    "bass_control": DecisionStrategyPolicy(
        strategy_id="bass_control",
        eq_intensity_scale=1.2,
        dynamics_aggressiveness_scale=1.1,
        limiter_ceiling_offset_db=-0.05,
    ),
    "harsh_tame": DecisionStrategyPolicy(
        strategy_id="harsh_tame",
        eq_intensity_scale=1.15,
        de_esser_depth_scale=1.2,
        de_esser_threshold_offset=-0.01,
    ),
    "dynamic_rescue": DecisionStrategyPolicy(
        strategy_id="dynamic_rescue",
        dynamics_aggressiveness_scale=1.3,
        limiter_ceiling_offset_db=-0.1,
    ),
    "clip_guard": DecisionStrategyPolicy(
        strategy_id="clip_guard",
        limiter_ceiling_offset_db=-0.2,
        dynamics_aggressiveness_scale=1.15,
    ),
    "corrective_combo": DecisionStrategyPolicy(
        strategy_id="corrective_combo",
        eq_intensity_scale=1.2,
        dynamics_aggressiveness_scale=1.25,
        de_esser_depth_scale=1.25,
        de_esser_threshold_offset=-0.01,
        limiter_ceiling_offset_db=-0.2,
    ),
}


def _clamp(value: float, low: float, high: float) -> float:
    return float(np.clip(value, low, high))


def select_decision_strategy(analysis: AnalysisPayload) -> StrategySelection:
    """Classify mix conditions and select a decision-strategy policy."""

    conditions: list[StrategyCondition] = []
    low_energy_delta = analysis.target.low_band_energy - analysis.reference.low_band_energy
    high_energy_delta = analysis.target.high_band_energy - analysis.reference.high_band_energy
    crest_delta = analysis.reference.crest_factor_db - analysis.target.crest_factor_db

    if low_energy_delta >= 0.08:
        conditions.append(StrategyCondition.BASS_HEAVY)
    if high_energy_delta >= 0.08 or analysis.sibilance_ratio_delta >= 0.025:
        conditions.append(StrategyCondition.HARSH_UPPER_MIDS)
    if crest_delta >= 2.0:
        conditions.append(StrategyCondition.OVER_COMPRESSED)
    if analysis.target.is_clipping or analysis.target.rms_db >= -9.0:
        conditions.append(StrategyCondition.CLIPPING_PRONE)

    condition_set = set(conditions)
    if len(condition_set) >= 3:
        policy = DECISION_STRATEGY_POLICIES["corrective_combo"]
    elif StrategyCondition.CLIPPING_PRONE in condition_set:
        policy = DECISION_STRATEGY_POLICIES["clip_guard"]
    elif StrategyCondition.OVER_COMPRESSED in condition_set:
        policy = DECISION_STRATEGY_POLICIES["dynamic_rescue"]
    elif StrategyCondition.HARSH_UPPER_MIDS in condition_set:
        policy = DECISION_STRATEGY_POLICIES["harsh_tame"]
    elif StrategyCondition.BASS_HEAVY in condition_set:
        policy = DECISION_STRATEGY_POLICIES["bass_control"]
    else:
        policy = DECISION_STRATEGY_POLICIES["balanced"]

    return StrategySelection(policy=policy, conditions=tuple(conditions))


def decide_mastering(
    analysis: AnalysisPayload,
    profile: str = "default",
    strategy: StrategySelection | None = None,
    advanced_mode: bool = False,
) -> DecisionPayload:
    """Translate analysis deltas into DSP parameters."""

    tuning = resolve_decision_tuning(profile)
    selected_strategy = strategy or select_decision_strategy(analysis)
    policy = selected_strategy.policy
    gain_db = _clamp(analysis.rms_delta_db, *tuning.gain_clamp_db)

    low_delta = analysis.reference.low_band_energy - analysis.target.low_band_energy
    high_delta = analysis.reference.high_band_energy - analysis.target.high_band_energy

    low_shelf_gain_db = _clamp(
        low_delta * tuning.shelf_scale * policy.eq_intensity_scale,
        *tuning.shelf_clamp_db,
    )
    high_shelf_gain_db = _clamp(
        high_delta * tuning.shelf_scale * policy.eq_intensity_scale,
        *tuning.shelf_clamp_db,
    )

    crest_delta = analysis.target.crest_factor_db - analysis.reference.crest_factor_db
    compressor_threshold_db = _clamp(
        tuning.compressor_base_threshold_db
        + crest_delta
        * tuning.compressor_threshold_scale
        * policy.dynamics_aggressiveness_scale,
        *tuning.compressor_threshold_clamp_db,
    )
    compressor_ratio = _clamp(
        tuning.compressor_base_ratio
        + max(0.0, crest_delta)
        * tuning.compressor_ratio_scale
        * policy.dynamics_aggressiveness_scale,
        *tuning.compressor_ratio_clamp,
    )

    limiter_ceiling_db = (
        tuning.limiter_ceiling_clipping_db
        if analysis.target.is_clipping
        else tuning.limiter_ceiling_default_db
    )
    limiter_ceiling_db += policy.limiter_ceiling_offset_db

    de_esser_threshold = _clamp(
        tuning.de_esser_threshold_base
        + analysis.reference.sibilance_ratio * tuning.de_esser_threshold_delta_scale
        + policy.de_esser_threshold_offset,
        *tuning.de_esser_threshold_clamp,
    )
    sibilance_excess = max(0.0, analysis.target.sibilance_ratio - de_esser_threshold)
    sibilance_delta_excess = max(0.0, analysis.sibilance_ratio_delta)
    de_esser_depth_db = _clamp(
        (sibilance_excess + (0.5 * sibilance_delta_excess))
        * tuning.de_esser_depth_scale
        * policy.de_esser_depth_scale,
        *tuning.de_esser_depth_clamp_db,
    )

    multiband_compression_enabled = False
    multiband_low_threshold_db = -24.0
    multiband_low_ratio = 1.0
    multiband_mid_threshold_db = -24.0
    multiband_mid_ratio = 1.0
    multiband_high_threshold_db = -24.0
    multiband_high_ratio = 1.0
    dynamic_eq_enabled = False
    dynamic_eq_harsh_threshold = 0.0
    dynamic_eq_harsh_attenuation_db = 0.0
    stereo_ms_correction_enabled = False
    stereo_mid_gain_db = 0.0
    stereo_side_gain_db = 0.0

    if advanced_mode:
        low_excess = max(
            0.0,
            analysis.target.low_band_energy - analysis.reference.low_band_energy,
        )
        high_excess = max(
            0.0,
            analysis.target.high_band_energy - analysis.reference.high_band_energy,
        )
        crest_miss = max(
            0.0,
            analysis.reference.crest_factor_db - analysis.target.crest_factor_db,
        )

        multiband_compression_enabled = (
            low_excess >= 0.04 or high_excess >= 0.04 or crest_miss >= 1.5
        )
        multiband_low_threshold_db = _clamp(-26.0 + (low_excess * 30.0), -32.0, -16.0)
        multiband_low_ratio = _clamp(1.6 + (low_excess * 6.0), 1.2, 4.0)
        multiband_mid_threshold_db = _clamp(-24.0 + (crest_miss * 1.2), -30.0, -16.0)
        multiband_mid_ratio = _clamp(1.5 + (crest_miss * 0.45), 1.2, 3.8)
        multiband_high_threshold_db = _clamp(
            -25.0 + ((high_excess + analysis.sibilance_ratio_delta) * 25.0),
            -32.0,
            -15.0,
        )
        multiband_high_ratio = _clamp(
            1.5 + ((high_excess + analysis.sibilance_ratio_delta) * 8.0), 1.2, 4.2
        )

        dynamic_eq_harsh_threshold = _clamp(
            analysis.reference.high_band_energy + 0.02,
            0.04,
            0.35,
        )
        harsh_excess = max(
            0.0,
            analysis.target.high_band_energy - dynamic_eq_harsh_threshold,
        ) + max(0.0, analysis.sibilance_ratio_delta)
        dynamic_eq_harsh_attenuation_db = _clamp(harsh_excess * 22.0, 0.0, 4.5)
        dynamic_eq_enabled = dynamic_eq_harsh_attenuation_db > 0.0

        mid_delta = analysis.reference.mid_band_energy - analysis.target.mid_band_energy
        side_delta = analysis.target.high_band_energy - analysis.reference.high_band_energy
        stereo_side_gain_db = _clamp(-(side_delta * 8.0), -1.5, 1.5)
        stereo_mid_gain_db = _clamp(mid_delta * 6.0, -1.0, 1.0)
        stereo_ms_correction_enabled = (
            abs(stereo_side_gain_db) >= 0.1 or abs(stereo_mid_gain_db) >= 0.1
        )

    return DecisionPayload(
        gain_db=gain_db,
        low_shelf_gain_db=low_shelf_gain_db,
        high_shelf_gain_db=high_shelf_gain_db,
        compressor_threshold_db=compressor_threshold_db,
        compressor_ratio=compressor_ratio,
        limiter_ceiling_db=limiter_ceiling_db,
        de_esser_threshold=de_esser_threshold,
        de_esser_depth_db=de_esser_depth_db,
        multiband_compression_enabled=multiband_compression_enabled,
        multiband_low_threshold_db=multiband_low_threshold_db,
        multiband_low_ratio=multiband_low_ratio,
        multiband_mid_threshold_db=multiband_mid_threshold_db,
        multiband_mid_ratio=multiband_mid_ratio,
        multiband_high_threshold_db=multiband_high_threshold_db,
        multiband_high_ratio=multiband_high_ratio,
        dynamic_eq_enabled=dynamic_eq_enabled,
        dynamic_eq_harsh_threshold=dynamic_eq_harsh_threshold,
        dynamic_eq_harsh_attenuation_db=dynamic_eq_harsh_attenuation_db,
        stereo_ms_correction_enabled=stereo_ms_correction_enabled,
        stereo_mid_gain_db=stereo_mid_gain_db,
        stereo_side_gain_db=stereo_side_gain_db,
    )

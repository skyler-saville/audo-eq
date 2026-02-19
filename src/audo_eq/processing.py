"""DSP processing chain construction and application."""

from __future__ import annotations

from dataclasses import dataclass

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

from .analysis import EqBandCorrection
from .decision import DecisionPayload
from .mastering_options import EqMode, EqPreset

_POST_LIMITER_LUFS_TOLERANCE = 0.3

@dataclass(frozen=True, slots=True)
class EqPresetTuning:
    """Deterministic per-preset tuning offsets."""

    low_shelf_offset_db: float = 0.0
    high_shelf_offset_db: float = 0.0
    low_band_bias_db: float = 0.0
    mid_band_bias_db: float = 0.0
    high_band_bias_db: float = 0.0


EQ_PRESET_TUNINGS: dict[EqPreset, EqPresetTuning] = {
    EqPreset.NEUTRAL: EqPresetTuning(),
    EqPreset.WARM: EqPresetTuning(low_shelf_offset_db=1.5, high_shelf_offset_db=-0.8, low_band_bias_db=0.5),
    EqPreset.BRIGHT: EqPresetTuning(low_shelf_offset_db=-0.8, high_shelf_offset_db=1.8, high_band_bias_db=0.4),
    EqPreset.VOCAL_PRESENCE: EqPresetTuning(
        low_shelf_offset_db=-0.6,
        high_shelf_offset_db=1.2,
        mid_band_bias_db=0.8,
        high_band_bias_db=0.2,
    ),
    EqPreset.BASS_BOOST: EqPresetTuning(low_shelf_offset_db=2.0, high_shelf_offset_db=-0.5, low_band_bias_db=0.8),
}


def _audio_for_loudness_measurement(audio: np.ndarray) -> np.ndarray:
    """Convert channel-first pedalboard arrays for pyloudnorm."""

    if audio.ndim == 1:
        return audio.astype(np.float64, copy=False)
    return np.moveaxis(audio, 0, -1).astype(np.float64, copy=False)


def measure_integrated_lufs(audio: np.ndarray, sample_rate: int) -> float:
    """Measure integrated loudness in LUFS."""

    try:
        import pyloudnorm as pyln
    except ModuleNotFoundError:
        rms = float(np.sqrt(np.mean(np.square(audio.astype(np.float64, copy=False)))))
        if rms <= 0.0:
            return -70.0
        return float(np.clip(20.0 * np.log10(rms), -70.0, 5.0))

    meter = pyln.Meter(sample_rate)
    measured = float(meter.integrated_loudness(_audio_for_loudness_measurement(audio)))
    if not np.isfinite(measured):
        return -70.0
    return measured


def _band_bias_for_frequency(center_hz: float, tuning: EqPresetTuning) -> float:
    if center_hz <= 250.0:
        return tuning.low_band_bias_db
    if center_hz >= 4_000.0:
        return tuning.high_band_bias_db
    return tuning.mid_band_bias_db


def _build_reference_match_eq_stage(
    eq_band_corrections: tuple[EqBandCorrection, ...],
    tuning: EqPresetTuning,
) -> list:
    """Map per-band dB deltas into a compact Pedalboard filter bank."""

    plugins: list = []
    for correction in eq_band_corrections:
        center_hz = correction.center_hz
        gain_db = float(correction.delta_db) + _band_bias_for_frequency(center_hz, tuning)
        if center_hz <= 250.0:
            plugins.append(LowShelfFilter(cutoff_frequency_hz=max(40.0, center_hz), gain_db=round(float(gain_db), 6)))
            continue

        if center_hz >= 4_000.0:
            plugins.append(HighShelfFilter(cutoff_frequency_hz=min(12_000.0, center_hz), gain_db=round(float(gain_db), 6)))
            continue

        # Approximate a broad bell with opposing shelves around the center.
        plugins.append(LowShelfFilter(cutoff_frequency_hz=max(100.0, center_hz / 1.6), gain_db=round(float(gain_db * 0.5), 6)))
        plugins.append(HighShelfFilter(cutoff_frequency_hz=min(10_000.0, center_hz * 1.6), gain_db=round(float(-gain_db * 0.5), 6)))

    return plugins


def build_dsp_chain(
    decision: DecisionPayload,
    eq_mode: EqMode = EqMode.FIXED,
    eq_preset: EqPreset = EqPreset.NEUTRAL,
    eq_band_corrections: tuple[EqBandCorrection, ...] = tuple(),
) -> Pedalboard:
    """Build the mastering DSP chain from the decision payload."""

    tuning = EQ_PRESET_TUNINGS[eq_preset]

    plugins = [
        HighpassFilter(cutoff_frequency_hz=30.0),
        LowShelfFilter(cutoff_frequency_hz=125.0, gain_db=round(float(decision.low_shelf_gain_db + tuning.low_shelf_offset_db), 6)),
        HighShelfFilter(
            cutoff_frequency_hz=6_000.0,
            gain_db=round(float(decision.high_shelf_gain_db + tuning.high_shelf_offset_db), 6),
        ),
    ]

    if eq_mode is EqMode.REFERENCE_MATCH:
        plugins.extend(_build_reference_match_eq_stage(eq_band_corrections, tuning=tuning))

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
    eq_preset: EqPreset = EqPreset.NEUTRAL,
    eq_band_corrections: tuple[EqBandCorrection, ...] = tuple(),
) -> np.ndarray:
    """Apply the constructed DSP chain to target audio."""

    board = build_dsp_chain(
        decision,
        eq_mode=eq_mode,
        eq_preset=eq_preset,
        eq_band_corrections=eq_band_corrections,
    )
    return board(target_audio, sample_rate)


def apply_processing_with_loudness_target(
    target_audio: np.ndarray,
    sample_rate: int,
    decision: DecisionPayload,
    loudness_gain_db: float,
    target_lufs: float,
    eq_mode: EqMode = EqMode.FIXED,
    eq_preset: EqPreset = EqPreset.NEUTRAL,
    eq_band_corrections: tuple[EqBandCorrection, ...] = tuple(),
) -> np.ndarray:
    """Apply mastering chain with loudness targeting around the final limiter."""

    tuning = EQ_PRESET_TUNINGS[eq_preset]

    pre_limiter_plugins = [
        HighpassFilter(cutoff_frequency_hz=30.0),
        LowShelfFilter(cutoff_frequency_hz=125.0, gain_db=round(float(decision.low_shelf_gain_db + tuning.low_shelf_offset_db), 6)),
        HighShelfFilter(
            cutoff_frequency_hz=6_000.0,
            gain_db=round(float(decision.high_shelf_gain_db + tuning.high_shelf_offset_db), 6),
        ),
    ]
    if eq_mode is EqMode.REFERENCE_MATCH:
        pre_limiter_plugins.extend(_build_reference_match_eq_stage(eq_band_corrections, tuning=tuning))

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

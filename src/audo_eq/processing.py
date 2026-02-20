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
from .mastering_options import DeEsserMode, EqMode, EqPreset


@dataclass(frozen=True, slots=True)
class LoudnessTuning:
    """Tunable constants for loudness target correction around limiting."""

    post_limiter_lufs_tolerance: float
    max_post_limiter_correction_db: float


@dataclass(frozen=True, slots=True)
class TruePeakTuning:
    """Tunable constants for post-limiter true-peak guard behavior."""

    target_dbtp: float
    tolerance_db: float
    oversample_factor: int = 4


LOUDNESS_TUNINGS: dict[str, LoudnessTuning] = {
    "default": LoudnessTuning(
        post_limiter_lufs_tolerance=0.3, max_post_limiter_correction_db=1.5
    ),
    "conservative": LoudnessTuning(
        post_limiter_lufs_tolerance=0.45, max_post_limiter_correction_db=1.0
    ),
    "aggressive": LoudnessTuning(
        post_limiter_lufs_tolerance=0.2, max_post_limiter_correction_db=2.0
    ),
}

TRUE_PEAK_TUNINGS: dict[str, TruePeakTuning] = {
    "default": TruePeakTuning(target_dbtp=-1.0, tolerance_db=0.1, oversample_factor=4),
    "conservative": TruePeakTuning(
        target_dbtp=-1.2, tolerance_db=0.08, oversample_factor=4
    ),
    "aggressive": TruePeakTuning(
        target_dbtp=-0.8, tolerance_db=0.12, oversample_factor=4
    ),
}


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
    EqPreset.WARM: EqPresetTuning(
        low_shelf_offset_db=1.5, high_shelf_offset_db=-0.8, low_band_bias_db=0.5
    ),
    EqPreset.BRIGHT: EqPresetTuning(
        low_shelf_offset_db=-0.8, high_shelf_offset_db=1.8, high_band_bias_db=0.4
    ),
    EqPreset.VOCAL_PRESENCE: EqPresetTuning(
        low_shelf_offset_db=-0.6,
        high_shelf_offset_db=1.2,
        mid_band_bias_db=0.8,
        high_band_bias_db=0.2,
    ),
    EqPreset.BASS_BOOST: EqPresetTuning(
        low_shelf_offset_db=2.0, high_shelf_offset_db=-0.5, low_band_bias_db=0.8
    ),
}

EQ_PRESET_TO_PROFILE: dict[EqPreset, str] = {
    EqPreset.NEUTRAL: "default",
    EqPreset.WARM: "conservative",
    EqPreset.BRIGHT: "aggressive",
    EqPreset.VOCAL_PRESENCE: "default",
    EqPreset.BASS_BOOST: "aggressive",
}

MASTERING_PROFILE_ALIASES: dict[str, str] = {
    "reference-mastering-default": "default",
    "reference-mastering-conservative": "conservative",
    "reference-mastering-aggressive": "aggressive",
}


def resolve_mastering_profile(
    eq_preset: EqPreset, mastering_profile: str | None = None
) -> str:
    if mastering_profile is not None:
        normalized = mastering_profile.strip().lower()
        if normalized in MASTERING_PROFILE_ALIASES:
            return MASTERING_PROFILE_ALIASES[normalized]
        if normalized in LOUDNESS_TUNINGS:
            return normalized
        allowed = ", ".join(sorted(LOUDNESS_TUNINGS))
        raise ValueError(
            f"Unknown mastering profile '{mastering_profile}'. Allowed: {allowed}."
        )
    return EQ_PRESET_TO_PROFILE[eq_preset]


def resolve_loudness_tuning(profile: str) -> LoudnessTuning:
    return LOUDNESS_TUNINGS[profile]


def resolve_true_peak_tuning(profile: str) -> TruePeakTuning:
    return TRUE_PEAK_TUNINGS[profile]


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


def measure_true_peak_dbtp(audio: np.ndarray, oversample_factor: int = 4) -> float:
    """Estimate true peak (dBTP) using channel-wise oversampling."""

    if oversample_factor < 1:
        raise ValueError("oversample_factor must be >= 1")

    audio_float = audio.astype(np.float64, copy=False)
    if audio_float.ndim == 1:
        channels = (audio_float,)
    else:
        channels = tuple(
            audio_float[channel_index] for channel_index in range(audio_float.shape[0])
        )

    max_abs_peak = 0.0
    for channel in channels:
        if channel.size == 0:
            continue
        if oversample_factor == 1 or channel.size == 1:
            oversampled = channel
        else:
            base_positions = np.arange(channel.size, dtype=np.float64)
            oversampled_positions = np.linspace(
                0.0,
                channel.size - 1,
                channel.size * oversample_factor,
                dtype=np.float64,
            )
            oversampled = np.interp(oversampled_positions, base_positions, channel)
        channel_peak = float(np.max(np.abs(oversampled)))
        max_abs_peak = max(max_abs_peak, channel_peak)

    if max_abs_peak <= 0.0:
        return -np.inf
    return float(20.0 * np.log10(max_abs_peak))


def apply_true_peak_guard(
    audio: np.ndarray,
    sample_rate: int,
    limiter: Limiter,
    tuning: TruePeakTuning,
) -> np.ndarray:
    """Apply post-limiter TP guard by gain trim and re-limiting when needed."""

    measured_dbtp = measure_true_peak_dbtp(
        audio, oversample_factor=tuning.oversample_factor
    )
    tp_overshoot_db = measured_dbtp - tuning.target_dbtp
    if tp_overshoot_db <= tuning.tolerance_db:
        return audio

    gain_trim_db = -(tp_overshoot_db + tuning.tolerance_db)
    trimmed_audio = Gain(gain_db=gain_trim_db)(audio, sample_rate)
    return limiter(trimmed_audio, sample_rate)


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
        gain_db = float(correction.delta_db) + _band_bias_for_frequency(
            center_hz, tuning
        )
        if center_hz <= 250.0:
            plugins.append(
                LowShelfFilter(
                    cutoff_frequency_hz=max(40.0, center_hz),
                    gain_db=round(float(gain_db), 6),
                )
            )
            continue

        if center_hz >= 4_000.0:
            plugins.append(
                HighShelfFilter(
                    cutoff_frequency_hz=min(12_000.0, center_hz),
                    gain_db=round(float(gain_db), 6),
                )
            )
            continue

        # Approximate a broad bell with opposing shelves around the center.
        plugins.append(
            LowShelfFilter(
                cutoff_frequency_hz=max(100.0, center_hz / 1.6),
                gain_db=round(float(gain_db * 0.5), 6),
            )
        )
        plugins.append(
            HighShelfFilter(
                cutoff_frequency_hz=min(10_000.0, center_hz * 1.6),
                gain_db=round(float(-gain_db * 0.5), 6),
            )
        )

    return plugins


def _build_optional_de_esser_stage(
    decision: DecisionPayload, de_esser_mode: DeEsserMode
) -> list:
    """Build a lightweight static de-esser stage when enabled."""

    if de_esser_mode is DeEsserMode.OFF:
        return []

    if decision.de_esser_depth_db <= 0.0:
        return []

    return [
        HighShelfFilter(
            cutoff_frequency_hz=6_500.0,
            gain_db=round(float(-decision.de_esser_depth_db), 6),
        )
    ]


def build_dsp_chain(
    decision: DecisionPayload,
    eq_mode: EqMode = EqMode.FIXED,
    eq_preset: EqPreset = EqPreset.NEUTRAL,
    eq_band_corrections: tuple[EqBandCorrection, ...] = tuple(),
    de_esser_mode: DeEsserMode = DeEsserMode.OFF,
) -> Pedalboard:
    """Build the mastering DSP chain from the decision payload."""

    tuning = EQ_PRESET_TUNINGS[eq_preset]

    plugins = [
        HighpassFilter(cutoff_frequency_hz=30.0),
        LowShelfFilter(
            cutoff_frequency_hz=125.0,
            gain_db=round(
                float(decision.low_shelf_gain_db + tuning.low_shelf_offset_db), 6
            ),
        ),
        HighShelfFilter(
            cutoff_frequency_hz=6_000.0,
            gain_db=round(
                float(decision.high_shelf_gain_db + tuning.high_shelf_offset_db), 6
            ),
        ),
    ]

    if eq_mode is EqMode.REFERENCE_MATCH:
        plugins.extend(
            _build_reference_match_eq_stage(eq_band_corrections, tuning=tuning)
        )

    plugins.extend(
        [
            Compressor(
                threshold_db=decision.compressor_threshold_db,
                ratio=decision.compressor_ratio,
                attack_ms=15.0,
                release_ms=120.0,
            ),
            Gain(gain_db=decision.gain_db),
        ]
    )
    plugins.extend(
        _build_optional_de_esser_stage(decision, de_esser_mode=de_esser_mode)
    )
    plugins.append(Limiter(threshold_db=decision.limiter_ceiling_db, release_ms=150.0))

    return Pedalboard(plugins)


def apply_processing(
    target_audio: np.ndarray,
    sample_rate: int,
    decision: DecisionPayload,
    eq_mode: EqMode = EqMode.FIXED,
    eq_preset: EqPreset = EqPreset.NEUTRAL,
    eq_band_corrections: tuple[EqBandCorrection, ...] = tuple(),
    mastering_profile: str | None = None,
    de_esser_mode: DeEsserMode = DeEsserMode.OFF,
) -> np.ndarray:
    """Apply the constructed DSP chain to target audio."""

    board = build_dsp_chain(
        decision,
        eq_mode=eq_mode,
        eq_preset=eq_preset,
        eq_band_corrections=eq_band_corrections,
        de_esser_mode=de_esser_mode,
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
    mastering_profile: str | None = None,
    de_esser_mode: DeEsserMode = DeEsserMode.OFF,
) -> np.ndarray:
    """Apply mastering chain with loudness targeting around the final limiter."""

    profile = resolve_mastering_profile(
        eq_preset=eq_preset, mastering_profile=mastering_profile
    )
    loudness_tuning = resolve_loudness_tuning(profile)
    true_peak_tuning = resolve_true_peak_tuning(profile)
    tuning = EQ_PRESET_TUNINGS[eq_preset]

    pre_limiter_plugins = [
        HighpassFilter(cutoff_frequency_hz=30.0),
        LowShelfFilter(
            cutoff_frequency_hz=125.0,
            gain_db=round(
                float(decision.low_shelf_gain_db + tuning.low_shelf_offset_db), 6
            ),
        ),
        HighShelfFilter(
            cutoff_frequency_hz=6_000.0,
            gain_db=round(
                float(decision.high_shelf_gain_db + tuning.high_shelf_offset_db), 6
            ),
        ),
    ]
    if eq_mode is EqMode.REFERENCE_MATCH:
        pre_limiter_plugins.extend(
            _build_reference_match_eq_stage(eq_band_corrections, tuning=tuning)
        )

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
    pre_limiter_plugins.extend(
        _build_optional_de_esser_stage(decision, de_esser_mode=de_esser_mode)
    )

    pre_limiter_chain = Pedalboard(pre_limiter_plugins)
    pre_limiter_audio = pre_limiter_chain(target_audio, sample_rate)

    limiter = Limiter(threshold_db=decision.limiter_ceiling_db, release_ms=150.0)
    limited_audio = limiter(pre_limiter_audio, sample_rate)

    final_lufs = measure_integrated_lufs(limited_audio, sample_rate)
    correction_db = float(
        np.clip(
            target_lufs - final_lufs,
            -loudness_tuning.max_post_limiter_correction_db,
            loudness_tuning.max_post_limiter_correction_db,
        )
    )
    if abs(correction_db) < loudness_tuning.post_limiter_lufs_tolerance:
        return apply_true_peak_guard(
            limited_audio, sample_rate, limiter=limiter, tuning=true_peak_tuning
        )

    post_gain = Gain(gain_db=correction_db)
    corrected_audio = post_gain(limited_audio, sample_rate)
    corrected_limited_audio = limiter(corrected_audio, sample_rate)
    return apply_true_peak_guard(
        corrected_limited_audio, sample_rate, limiter=limiter, tuning=true_peak_tuning
    )

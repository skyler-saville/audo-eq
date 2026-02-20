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


def _build_optional_dynamic_eq_stage(
    decision: DecisionPayload,
    advanced_mode: bool,
) -> list:
    """Build optional harsh-region attenuation stage."""

    if not advanced_mode or not decision.dynamic_eq_enabled:
        return []
    if decision.dynamic_eq_harsh_attenuation_db <= 0.0:
        return []

    return [
        HighShelfFilter(
            cutoff_frequency_hz=3_500.0,
            gain_db=round(float(-decision.dynamic_eq_harsh_attenuation_db), 6),
        )
    ]


def _bandpass_via_fft(
    audio: np.ndarray,
    sample_rate: int,
    low_hz: float | None,
    high_hz: float | None,
) -> np.ndarray:
    """Simple linear-phase band split using FFT masks."""

    audio_float = audio.astype(np.float64, copy=False)
    squeeze = False
    if audio_float.ndim == 1:
        audio_float = audio_float[np.newaxis, :]
        squeeze = True

    spectrum = np.fft.rfft(audio_float, axis=-1)
    freqs = np.fft.rfftfreq(audio_float.shape[-1], d=1.0 / sample_rate)
    mask = np.ones_like(freqs, dtype=bool)
    if low_hz is not None:
        mask &= freqs >= low_hz
    if high_hz is not None:
        mask &= freqs < high_hz
    filtered = np.fft.irfft(spectrum * mask[np.newaxis, :], n=audio_float.shape[-1], axis=-1)
    if squeeze:
        return filtered[0]
    return filtered


def _apply_optional_multiband_compression(
    audio: np.ndarray,
    sample_rate: int,
    decision: DecisionPayload,
    advanced_mode: bool,
) -> np.ndarray:
    if not advanced_mode or not decision.multiband_compression_enabled:
        return audio

    low_band = _bandpass_via_fft(audio, sample_rate, low_hz=None, high_hz=200.0)
    mid_band = _bandpass_via_fft(audio, sample_rate, low_hz=200.0, high_hz=4_000.0)
    high_band = _bandpass_via_fft(audio, sample_rate, low_hz=4_000.0, high_hz=None)

    low_processed = Compressor(
        threshold_db=decision.multiband_low_threshold_db,
        ratio=decision.multiband_low_ratio,
        attack_ms=25.0,
        release_ms=160.0,
    )(low_band, sample_rate)
    mid_processed = Compressor(
        threshold_db=decision.multiband_mid_threshold_db,
        ratio=decision.multiband_mid_ratio,
        attack_ms=15.0,
        release_ms=120.0,
    )(mid_band, sample_rate)
    high_processed = Compressor(
        threshold_db=decision.multiband_high_threshold_db,
        ratio=decision.multiband_high_ratio,
        attack_ms=8.0,
        release_ms=90.0,
    )(high_band, sample_rate)
    return low_processed + mid_processed + high_processed


def _apply_optional_ms_gain_correction(
    audio: np.ndarray,
    decision: DecisionPayload,
    advanced_mode: bool,
) -> np.ndarray:
    if not advanced_mode or not decision.stereo_ms_correction_enabled:
        return audio
    if audio.ndim != 2 or audio.shape[0] < 2:
        return audio

    left = audio[0].astype(np.float64, copy=False)
    right = audio[1].astype(np.float64, copy=False)
    mid = 0.5 * (left + right)
    side = 0.5 * (left - right)
    mid *= 10.0 ** (decision.stereo_mid_gain_db / 20.0)
    side *= 10.0 ** (decision.stereo_side_gain_db / 20.0)
    corrected_left = mid + side
    corrected_right = mid - side
    corrected = np.vstack([corrected_left, corrected_right])
    return np.clip(corrected, -1.0, 1.0).astype(audio.dtype, copy=False)


def _build_pre_limiter_plugins(
    decision: DecisionPayload,
    tuning: EqPresetTuning,
    eq_mode: EqMode,
    eq_band_corrections: tuple[EqBandCorrection, ...],
    de_esser_mode: DeEsserMode,
    gain_db: float,
    advanced_mode: bool,
) -> list:
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

    plugins.extend(_build_optional_dynamic_eq_stage(decision, advanced_mode=advanced_mode))

    if not (advanced_mode and decision.multiband_compression_enabled):
        plugins.append(
            Compressor(
                threshold_db=decision.compressor_threshold_db,
                ratio=decision.compressor_ratio,
                attack_ms=15.0,
                release_ms=120.0,
            )
        )
    plugins.append(Gain(gain_db=gain_db))
    plugins.extend(_build_optional_de_esser_stage(decision, de_esser_mode=de_esser_mode))
    return plugins


def build_dsp_chain(
    decision: DecisionPayload,
    eq_mode: EqMode = EqMode.FIXED,
    eq_preset: EqPreset = EqPreset.NEUTRAL,
    eq_band_corrections: tuple[EqBandCorrection, ...] = tuple(),
    de_esser_mode: DeEsserMode = DeEsserMode.OFF,
    advanced_mode: bool = False,
) -> Pedalboard:
    """Build the mastering DSP chain from the decision payload."""

    tuning = EQ_PRESET_TUNINGS[eq_preset]

    plugins = _build_pre_limiter_plugins(
        decision=decision,
        tuning=tuning,
        eq_mode=eq_mode,
        eq_band_corrections=eq_band_corrections,
        de_esser_mode=de_esser_mode,
        gain_db=decision.gain_db,
        advanced_mode=advanced_mode,
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
    advanced_mode: bool = False,
) -> np.ndarray:
    """Apply the constructed DSP chain to target audio."""

    staged_audio = _apply_optional_ms_gain_correction(
        target_audio,
        decision=decision,
        advanced_mode=advanced_mode,
    )
    staged_audio = _apply_optional_multiband_compression(
        staged_audio,
        sample_rate=sample_rate,
        decision=decision,
        advanced_mode=advanced_mode,
    )
    board = build_dsp_chain(
        decision,
        eq_mode=eq_mode,
        eq_preset=eq_preset,
        eq_band_corrections=eq_band_corrections,
        de_esser_mode=de_esser_mode,
        advanced_mode=advanced_mode,
    )
    return board(staged_audio, sample_rate)


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
    advanced_mode: bool = False,
) -> np.ndarray:
    """Apply mastering chain with loudness targeting around the final limiter."""

    profile = resolve_mastering_profile(
        eq_preset=eq_preset, mastering_profile=mastering_profile
    )
    loudness_tuning = resolve_loudness_tuning(profile)
    true_peak_tuning = resolve_true_peak_tuning(profile)
    tuning = EQ_PRESET_TUNINGS[eq_preset]

    pre_limiter_audio = _apply_optional_ms_gain_correction(
        target_audio,
        decision=decision,
        advanced_mode=advanced_mode,
    )
    pre_limiter_audio = _apply_optional_multiband_compression(
        pre_limiter_audio,
        sample_rate=sample_rate,
        decision=decision,
        advanced_mode=advanced_mode,
    )

    pre_limiter_plugins = _build_pre_limiter_plugins(
        decision=decision,
        tuning=tuning,
        eq_mode=eq_mode,
        eq_band_corrections=eq_band_corrections,
        de_esser_mode=de_esser_mode,
        gain_db=decision.gain_db + loudness_gain_db,
        advanced_mode=advanced_mode,
    )
    pre_limiter_chain = Pedalboard(pre_limiter_plugins)
    pre_limiter_audio = pre_limiter_chain(pre_limiter_audio, sample_rate)

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

import numpy as np
import pytest
from pedalboard import Compressor, HighShelfFilter, Limiter, LowShelfFilter

from audo_eq.analysis import EqBandCorrection
from audo_eq.decision import DecisionPayload
from audo_eq.processing import (
    DeEsserMode,
    EqMode,
    EqPreset,
    apply_true_peak_guard,
    build_dsp_chain,
    resolve_mastering_profile,
    resolve_true_peak_tuning,
    apply_processing_with_loudness_target,
)


def _decision() -> DecisionPayload:
    return DecisionPayload(
        gain_db=1.0,
        low_shelf_gain_db=0.5,
        high_shelf_gain_db=-0.5,
        compressor_threshold_db=-20.0,
        compressor_ratio=2.0,
        limiter_ceiling_db=-1.0,
    )


def test_build_dsp_chain_neutral_preset_keeps_current_shelf_gains() -> None:
    chain = build_dsp_chain(
        _decision(), eq_mode=EqMode.FIXED, eq_preset=EqPreset.NEUTRAL
    )

    low_shelf = next(plugin for plugin in chain if isinstance(plugin, LowShelfFilter))
    high_shelf = next(plugin for plugin in chain if isinstance(plugin, HighShelfFilter))

    assert low_shelf.gain_db == pytest.approx(0.5)
    assert high_shelf.gain_db == pytest.approx(-0.5)


def test_build_dsp_chain_applies_preset_bias_to_reference_match_bands() -> None:
    chain = build_dsp_chain(
        _decision(),
        eq_mode=EqMode.REFERENCE_MATCH,
        eq_preset=EqPreset.WARM,
        eq_band_corrections=(EqBandCorrection(center_hz=100.0, delta_db=1.0),),
    )

    low_shelves = [plugin for plugin in chain if isinstance(plugin, LowShelfFilter)]

    assert low_shelves[0].gain_db == pytest.approx(2.0)
    assert low_shelves[1].gain_db == pytest.approx(1.5)


def test_true_peak_tuning_profiles_have_expected_targets() -> None:
    assert resolve_true_peak_tuning("default").target_dbtp == pytest.approx(-1.0)
    assert resolve_true_peak_tuning("conservative").target_dbtp == pytest.approx(-1.2)
    assert resolve_true_peak_tuning("aggressive").target_dbtp == pytest.approx(-0.8)


def test_apply_true_peak_guard_skips_trim_when_within_tolerance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio = np.array([0.25, -0.25, 0.1, -0.1], dtype=np.float32)
    tuning = resolve_true_peak_tuning("default")
    limiter = Limiter(threshold_db=-1.0, release_ms=150.0)

    monkeypatch.setattr(
        "audo_eq.processing.measure_true_peak_dbtp",
        lambda *_args, **_kwargs: tuning.target_dbtp + tuning.tolerance_db,
    )

    guarded = apply_true_peak_guard(
        audio, sample_rate=48_000, limiter=limiter, tuning=tuning
    )
    np.testing.assert_allclose(guarded, audio)


def test_apply_true_peak_guard_trims_and_relimits_on_overshoot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio = np.array([1.0, -1.0, 0.95, -0.95], dtype=np.float32)
    tuning = resolve_true_peak_tuning("default")
    limiter = Limiter(threshold_db=-0.5, release_ms=150.0)

    monkeypatch.setattr(
        "audo_eq.processing.measure_true_peak_dbtp", lambda *_args, **_kwargs: -0.2
    )

    guarded = apply_true_peak_guard(
        audio, sample_rate=48_000, limiter=limiter, tuning=tuning
    )

    assert guarded.shape == audio.shape
    assert not np.allclose(guarded, audio)


def test_build_dsp_chain_includes_de_esser_high_shelf_before_limiter_when_auto() -> (
    None
):
    decision = DecisionPayload(
        gain_db=1.0,
        low_shelf_gain_db=0.5,
        high_shelf_gain_db=-0.5,
        compressor_threshold_db=-20.0,
        compressor_ratio=2.0,
        limiter_ceiling_db=-1.0,
        de_esser_threshold=0.08,
        de_esser_depth_db=3.0,
    )
    chain = build_dsp_chain(
        decision,
        eq_mode=EqMode.FIXED,
        eq_preset=EqPreset.NEUTRAL,
        de_esser_mode=DeEsserMode.AUTO,
    )

    limiter_index = next(
        i for i, plugin in enumerate(chain) if isinstance(plugin, Limiter)
    )
    de_esser = chain[limiter_index - 1]

    assert isinstance(de_esser, HighShelfFilter)
    assert de_esser.gain_db == pytest.approx(-3.0)


def test_build_dsp_chain_skips_de_esser_when_off() -> None:
    decision = DecisionPayload(
        gain_db=1.0,
        low_shelf_gain_db=0.5,
        high_shelf_gain_db=-0.5,
        compressor_threshold_db=-20.0,
        compressor_ratio=2.0,
        limiter_ceiling_db=-1.0,
        de_esser_threshold=0.08,
        de_esser_depth_db=3.0,
    )
    chain = build_dsp_chain(decision, de_esser_mode=DeEsserMode.OFF)

    high_shelves = [plugin for plugin in chain if isinstance(plugin, HighShelfFilter)]
    assert len(high_shelves) == 1


def test_build_dsp_chain_adds_dynamic_eq_in_advanced_mode() -> None:
    decision = DecisionPayload(
        gain_db=1.0,
        low_shelf_gain_db=0.5,
        high_shelf_gain_db=-0.5,
        compressor_threshold_db=-20.0,
        compressor_ratio=2.0,
        limiter_ceiling_db=-1.0,
        dynamic_eq_enabled=True,
        dynamic_eq_harsh_attenuation_db=2.5,
    )

    chain = build_dsp_chain(decision, advanced_mode=True)

    high_shelves = [plugin for plugin in chain if isinstance(plugin, HighShelfFilter)]
    assert any(plugin.gain_db == pytest.approx(-2.5) for plugin in high_shelves)


def test_build_dsp_chain_skips_single_band_compressor_with_multiband_mode() -> None:
    decision = DecisionPayload(
        gain_db=1.0,
        low_shelf_gain_db=0.5,
        high_shelf_gain_db=-0.5,
        compressor_threshold_db=-20.0,
        compressor_ratio=2.0,
        limiter_ceiling_db=-1.0,
        multiband_compression_enabled=True,
    )

    chain = build_dsp_chain(decision, advanced_mode=True)

    compressors = [plugin for plugin in chain if isinstance(plugin, Compressor)]
    assert len(compressors) == 0


def test_resolve_mastering_profile_supports_streaming_aliases() -> None:
    assert resolve_mastering_profile(EqPreset.NEUTRAL, mastering_profile="streaming-balanced") == "default"
    assert resolve_mastering_profile(EqPreset.NEUTRAL, mastering_profile="streaming-loud") == "aggressive"


def test_apply_processing_with_loudness_target_runs_iterative_convergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = _decision()
    source = np.array([0.1, -0.1, 0.08, -0.08], dtype=np.float32)

    monkeypatch.setattr("audo_eq.processing._apply_optional_ms_gain_correction", lambda audio, **_: audio)
    monkeypatch.setattr("audo_eq.processing._apply_optional_multiband_compression", lambda audio, **_: audio)

    class _BypassChain:
        def __call__(self, audio, _sample_rate):
            return audio

    monkeypatch.setattr("audo_eq.processing.Pedalboard", lambda _plugins: _BypassChain())

    limiter_calls = {"count": 0}

    class _LimiterStub:
        def __call__(self, audio, _sample_rate):
            limiter_calls["count"] += 1
            return audio

    monkeypatch.setattr("audo_eq.processing.Limiter", lambda **_: _LimiterStub())

    measured_lufs = iter([-18.0, -15.0, -14.05])
    monkeypatch.setattr(
        "audo_eq.processing.measure_integrated_lufs",
        lambda *_args, **_kwargs: next(measured_lufs),
    )
    monkeypatch.setattr(
        "audo_eq.processing.apply_true_peak_guard",
        lambda audio, _sample_rate, **_: audio,
    )

    mastered = apply_processing_with_loudness_target(
        target_audio=source,
        sample_rate=48_000,
        decision=decision,
        loudness_gain_db=0.0,
        target_lufs=-14.0,
        eq_preset=EqPreset.NEUTRAL,
    )

    assert mastered.shape == source.shape
    assert limiter_calls["count"] == 3

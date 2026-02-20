import numpy as np
import pytest
from pedalboard import HighShelfFilter, Limiter, LowShelfFilter

from audo_eq.analysis import EqBandCorrection
from audo_eq.decision import DecisionPayload
from audo_eq.processing import (
    EqMode,
    EqPreset,
    apply_true_peak_guard,
    build_dsp_chain,
    resolve_true_peak_tuning,
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
    chain = build_dsp_chain(_decision(), eq_mode=EqMode.FIXED, eq_preset=EqPreset.NEUTRAL)

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


def test_apply_true_peak_guard_skips_trim_when_within_tolerance(monkeypatch: pytest.MonkeyPatch) -> None:
    audio = np.array([0.25, -0.25, 0.1, -0.1], dtype=np.float32)
    tuning = resolve_true_peak_tuning("default")
    limiter = Limiter(threshold_db=-1.0, release_ms=150.0)

    monkeypatch.setattr(
        "audo_eq.processing.measure_true_peak_dbtp",
        lambda *_args, **_kwargs: tuning.target_dbtp + tuning.tolerance_db,
    )

    guarded = apply_true_peak_guard(audio, sample_rate=48_000, limiter=limiter, tuning=tuning)
    np.testing.assert_allclose(guarded, audio)


def test_apply_true_peak_guard_trims_and_relimits_on_overshoot(monkeypatch: pytest.MonkeyPatch) -> None:
    audio = np.array([1.0, -1.0, 0.95, -0.95], dtype=np.float32)
    tuning = resolve_true_peak_tuning("default")
    limiter = Limiter(threshold_db=-0.5, release_ms=150.0)

    monkeypatch.setattr("audo_eq.processing.measure_true_peak_dbtp", lambda *_args, **_kwargs: -0.2)

    guarded = apply_true_peak_guard(audio, sample_rate=48_000, limiter=limiter, tuning=tuning)

    assert guarded.shape == audio.shape
    assert not np.allclose(guarded, audio)

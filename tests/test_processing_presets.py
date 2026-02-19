import pytest
from pedalboard import HighShelfFilter, LowShelfFilter

from audo_eq.analysis import EqBandCorrection
from audo_eq.decision import DecisionPayload
from audo_eq.processing import EqMode, EqPreset, build_dsp_chain


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

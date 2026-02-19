import json
from pathlib import Path

import numpy as np

from audo_eq.analysis import analyze_tracks
from audo_eq.decision import decide_mastering
from audo_eq.mastering_options import EqPreset
from audo_eq.processing import resolve_mastering_profile


def _tone(frequency_hz: float, amplitude: float, sample_rate: int, duration_s: float = 1.0) -> np.ndarray:
    t = np.arange(int(sample_rate * duration_s), dtype=np.float64) / sample_rate
    return amplitude * np.sin(2.0 * np.pi * frequency_hz * t)


def _scenario_audio(sample_rate: int) -> tuple[np.ndarray, np.ndarray]:
    target = _tone(120.0, 0.75, sample_rate) + _tone(1200.0, 0.2, sample_rate) + _tone(7000.0, 0.08, sample_rate)
    reference = _tone(120.0, 0.2, sample_rate) + _tone(1200.0, 0.35, sample_rate) + _tone(7000.0, 0.65, sample_rate)
    return target, reference


def _rounded_corrections(corrections: tuple) -> list[dict[str, float]]:
    return [{"center_hz": round(c.center_hz, 6), "delta_db": round(c.delta_db, 6)} for c in corrections]


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "tuning_regression.json"


def test_profile_regression_fixture_matches_current_tuning_outputs() -> None:
    fixture = json.loads(_fixture_path().read_text())

    sample_rate = fixture["sample_rate"]
    target, reference = _scenario_audio(sample_rate)

    for profile_name in fixture["profiles"]:
        analysis = analyze_tracks(target, reference, sample_rate, profile=profile_name)
        decision = decide_mastering(analysis, profile=profile_name)
        expected = fixture["profiles"][profile_name]

        observed = {
            "eq_band_corrections": _rounded_corrections(analysis.eq_band_corrections),
            "decision": {
                "gain_db": round(decision.gain_db, 6),
                "low_shelf_gain_db": round(decision.low_shelf_gain_db, 6),
                "high_shelf_gain_db": round(decision.high_shelf_gain_db, 6),
                "compressor_threshold_db": round(decision.compressor_threshold_db, 6),
                "compressor_ratio": round(decision.compressor_ratio, 6),
                "limiter_ceiling_db": round(decision.limiter_ceiling_db, 6),
            },
        }

        assert observed == expected


def test_eq_preset_resolves_to_expected_named_profiles() -> None:
    assert resolve_mastering_profile(EqPreset.NEUTRAL) == "default"
    assert resolve_mastering_profile(EqPreset.WARM) == "conservative"
    assert resolve_mastering_profile(EqPreset.BRIGHT) == "aggressive"

import numpy as np

from audo_eq.analysis import analyze_tracks


def _tone(
    frequency_hz: float, amplitude: float, sample_rate: int, duration_s: float = 1.0
) -> np.ndarray:
    t = np.arange(int(sample_rate * duration_s), dtype=np.float64) / sample_rate
    return amplitude * np.sin(2.0 * np.pi * frequency_hz * t)


def test_reference_match_eq_curve_is_deterministic_for_synthetic_tones() -> None:
    sample_rate = 48_000
    target = _tone(200.0, 0.8, sample_rate) + _tone(4_000.0, 0.1, sample_rate)
    reference = _tone(200.0, 0.1, sample_rate) + _tone(4_000.0, 0.8, sample_rate)

    first = analyze_tracks(target, reference, sample_rate).eq_band_corrections
    second = analyze_tracks(target, reference, sample_rate).eq_band_corrections

    first_curve = [(round(b.center_hz, 6), round(b.delta_db, 6)) for b in first]
    second_curve = [(round(b.center_hz, 6), round(b.delta_db, 6)) for b in second]
    assert first_curve == second_curve


def test_reference_match_eq_curve_applies_bounded_meaningful_corrections() -> None:
    sample_rate = 48_000
    target = _tone(125.0, 0.9, sample_rate) + _tone(8_000.0, 0.05, sample_rate)
    reference = _tone(125.0, 0.05, sample_rate) + _tone(8_000.0, 0.9, sample_rate)

    corrections = analyze_tracks(target, reference, sample_rate).eq_band_corrections
    assert corrections

    assert all(abs(c.delta_db) >= 0.75 for c in corrections)
    assert all(abs(c.delta_db) <= 4.0 for c in corrections)

    low_band = [c for c in corrections if c.center_hz < 250.0]
    high_band = [c for c in corrections if c.center_hz >= 4_000.0]

    assert low_band and all(c.delta_db < 0 for c in low_band)
    assert high_band and all(c.delta_db > 0 for c in high_band)


def test_analysis_reports_higher_sibilance_ratio_for_sibilant_tone() -> None:
    sample_rate = 48_000
    target = _tone(7_000.0, 0.8, sample_rate) + _tone(300.0, 0.1, sample_rate)
    reference = _tone(7_000.0, 0.1, sample_rate) + _tone(300.0, 0.8, sample_rate)

    analysis = analyze_tracks(target, reference, sample_rate)

    assert analysis.target.sibilance_ratio > analysis.reference.sibilance_ratio
    assert analysis.sibilance_ratio_delta > 0.0

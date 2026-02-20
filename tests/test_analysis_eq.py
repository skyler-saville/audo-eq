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


def test_analysis_includes_short_time_temporal_descriptors() -> None:
    sample_rate = 48_000
    duration_s = 2.0
    t = np.arange(int(sample_rate * duration_s), dtype=np.float64) / sample_rate
    envelope = np.where(t < 1.0, 0.2, 0.8)
    target = envelope * np.sin(2.0 * np.pi * 440.0 * t)
    reference = np.sin(2.0 * np.pi * 440.0 * t)

    analysis = analyze_tracks(target, reference, sample_rate)

    temporal = analysis.target_temporal
    assert temporal.frame_times_s
    assert len(temporal.frame_times_s) == len(temporal.loudness_envelope_db)
    assert len(temporal.frame_times_s) == len(temporal.multiband_energy_trajectories)
    assert len(temporal.frame_times_s) == len(temporal.transient_density_trajectory)
    assert len(temporal.frame_times_s) == len(temporal.crest_factor_trajectory_db)
    assert temporal.band_centers_hz

    mid = len(temporal.loudness_envelope_db) // 2
    assert np.mean(temporal.loudness_envelope_db[:mid]) < np.mean(temporal.loudness_envelope_db[mid:])


def test_analysis_temporal_windowing_uses_overlap_for_300ms_frames() -> None:
    sample_rate = 48_000
    duration_s = 1.2
    target = _tone(440.0, 0.4, sample_rate, duration_s)
    reference = _tone(440.0, 0.4, sample_rate, duration_s)

    analysis = analyze_tracks(target, reference, sample_rate)

    frame_times = np.asarray(analysis.target_temporal.frame_times_s)
    assert frame_times.size > 4

    hop_seconds = float(np.median(np.diff(frame_times)))
    assert 0.14 <= hop_seconds <= 0.16

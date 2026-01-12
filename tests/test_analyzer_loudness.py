from src.analyzer.loudness import LoudnessAnalyzer


def test_loudness_analyzer_monotonic(sine_wave):
    analyzer = LoudnessAnalyzer()
    quiet_lufs = analyzer.analyze(sine_wave["quiet"], sine_wave["sample_rate"])
    loud_lufs = analyzer.analyze(sine_wave["loud"], sine_wave["sample_rate"])

    assert loud_lufs > quiet_lufs

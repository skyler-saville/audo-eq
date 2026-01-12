from audo_eq.analyzer.loudness import LoudnessAnalyzer
from audo_eq.processor.loudness_comp import LoudnessCompProcessor


def test_loudness_comp_moves_toward_target(sine_wave):
    analyzer = LoudnessAnalyzer()
    processor = LoudnessCompProcessor(target_lufs=-12.0)

    before = analyzer.analyze(sine_wave["quiet"], sine_wave["sample_rate"])
    after = analyzer.analyze(
        processor.process(sine_wave["quiet"], sine_wave["sample_rate"]),
        sine_wave["sample_rate"],
    )

    assert abs(after - processor.target_lufs) < abs(before - processor.target_lufs)

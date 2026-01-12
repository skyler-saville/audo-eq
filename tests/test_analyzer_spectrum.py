import numpy as np

from src.analyzer.spectrum import SpectrumAnalyzer


def test_spectrum_analyzer_normalizes_output(sine_wave):
    analyzer = SpectrumAnalyzer()
    spectrum = analyzer.analyze(sine_wave["loud"], sine_wave["sample_rate"])

    assert spectrum.size > 0
    assert np.isclose(np.max(spectrum), 1.0)

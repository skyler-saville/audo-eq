import numpy as np

from audo_eq.processor.eq_match import EQMatchProcessor


def test_eq_match_applies_curve_shape(sine_wave):
    audio = sine_wave["loud"]
    spectrum_size = np.fft.rfft(audio).size
    target_curve = np.linspace(0.5, 1.0, spectrum_size)
    processor = EQMatchProcessor(target_eq_curve=target_curve, strength=1.0)

    processed = processor.process(audio, sine_wave["sample_rate"])

    assert processed.shape == audio.shape
    assert np.mean(np.abs(processed)) < np.mean(np.abs(audio))

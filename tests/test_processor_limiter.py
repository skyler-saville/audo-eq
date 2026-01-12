import numpy as np

from audo_eq.processor.limiter import LimiterProcessor


def test_limiter_clips_to_threshold():
    audio = np.array([-2.0, -0.25, 0.25, 2.0], dtype=float)
    limiter = LimiterProcessor(threshold_db=-6.0)

    processed = limiter.process(audio, sample_rate=44100)
    threshold = 10 ** (limiter.threshold_db / 20.0)

    assert np.max(np.abs(processed)) <= threshold + 1e-6

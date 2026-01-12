import numpy as np
import pytest


@pytest.fixture
def sine_wave():
    sample_rate = 44100
    duration_s = 5.0
    t = np.linspace(0.0, duration_s, int(sample_rate * duration_s), endpoint=False)
    base = np.sin(2 * np.pi * 440.0 * t)
    return {
        "sample_rate": sample_rate,
        "quiet": 0.1 * base,
        "loud": 0.5 * base,
    }

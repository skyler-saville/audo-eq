import pytest

from audo_eq.utils.config import ChainConfig


def test_chain_config_parses_discriminated_union():
    data = {
        "processors": [
            {"type": "eq_match", "strength": 0.5},
            {"type": "loudness_comp", "target_lufs": -14.0},
            {"type": "limiter", "threshold_db": -1.0, "mode": "true_peak"},
            {"type": "dither", "noise_amplitude": 1e-5},
        ]
    }

    config = ChainConfig.model_validate(data)

    assert len(config.processors) == 4
    assert config.processors[0].strength == 0.5


def test_chain_config_rejects_invalid_threshold():
    data = {
        "processors": [
            {"type": "limiter", "threshold_db": 2.0, "mode": "true_peak"},
        ]
    }

    with pytest.raises(ValueError):
        ChainConfig.model_validate(data)

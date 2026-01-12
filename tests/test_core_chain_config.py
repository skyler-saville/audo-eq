import numpy as np

from audo_eq.core import build_chain_from_config
from audo_eq.processor import EQMatchProcessor, LimiterProcessor, LoudnessCompProcessor
from audo_eq.utils.config import ChainConfig


def test_build_chain_from_config_uses_reference_defaults(sine_wave):
    config = ChainConfig.model_validate(
        {
            "processors": [
                {"type": "eq_match", "strength": 0.6},
                {"type": "loudness_comp", "max_gain_db": 10.0},
                {"type": "limiter", "threshold_db": -2.0, "mode": "true_peak"},
            ]
        }
    )

    ref_audio = sine_wave["loud"]
    chain = build_chain_from_config(config, ref_audio, sine_wave["sample_rate"])

    assert isinstance(chain[0], EQMatchProcessor)
    assert isinstance(chain[1], LoudnessCompProcessor)
    assert isinstance(chain[2], LimiterProcessor)
    assert np.isfinite(chain[1].target_lufs)

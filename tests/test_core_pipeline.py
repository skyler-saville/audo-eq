import numpy as np

from audo_eq.core import MasteringPipeline


class AddProcessor:
    def __init__(self, amount: float) -> None:
        self.amount = amount

    def process(self, audio: np.ndarray, sample_rate: float) -> np.ndarray:
        return audio + self.amount


def test_mastering_pipeline_applies_processors_in_order():
    audio = np.zeros(4, dtype=float)
    pipeline = MasteringPipeline([AddProcessor(1.0), AddProcessor(2.0)])

    processed = pipeline.run(audio, sample_rate=44100)

    assert np.allclose(processed, np.array([3.0, 3.0, 3.0, 3.0]))

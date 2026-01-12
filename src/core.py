import numpy as np
from typing import List
from .processor.base import BaseProcessor
from .analyzer.loudness import LoudnessAnalyzer
from .analyzer.spectrum import SpectrumAnalyzer

class MasteringPipeline:
    """Orchestrates the mastering chain."""
    def __init__(self, chain: List[BaseProcessor]):
        self.chain = chain

    def run(self, audio: np.ndarray, sample_rate: float) -> np.ndarray:
        processed = audio
        for processor in self.chain:
            processed = processor.process(processed, sample_rate)
        return processed

def create_tra_chain(target_audio: np.ndarray, ref_audio: np.ndarray, sr: float):
    """Factory function to build a chain based on reference analysis."""
    # Analyze reference
    ref_loudness = LoudnessAnalyzer().analyze(ref_audio, sr)
    ref_eq_curve = SpectrumAnalyzer().analyze(ref_audio, sr)

    # Build chain modules based on analysis
    from .processor.eq_match import EQMatchProcessor
    from .processor.loudness_comp import LoudnessCompProcessor
    from .processor.limiter import LimiterProcessor

    chain = [
        EQMatchProcessor(target_eq_curve=ref_eq_curve),
        LoudnessCompProcessor(target_lufs=ref_loudness),
        LimiterProcessor(threshold_db=-1.0, mode='true_peak')
    ]
    return chain
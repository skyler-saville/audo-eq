from __future__ import annotations

from typing import Iterable, List

import numpy as np

from .analyzer.loudness import LoudnessAnalyzer
from .analyzer.spectrum import SpectrumAnalyzer
from .processor.base import BaseProcessor
from .processor.dither import DitherProcessor
from .processor.eq_match import EQMatchProcessor
from .processor.limiter import LimiterProcessor
from .processor.loudness_comp import LoudnessCompProcessor
from .utils.config import (
    ChainConfig,
    DitherConfig,
    EQMatchConfig,
    LimiterConfig,
    LoudnessCompConfig,
)

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
    chain = [
        EQMatchProcessor(target_eq_curve=ref_eq_curve),
        LoudnessCompProcessor(target_lufs=ref_loudness),
        LimiterProcessor(threshold_db=-1.0, mode='true_peak')
    ]
    return chain


def build_chain_from_config(
    config: ChainConfig,
    ref_audio: np.ndarray,
    sample_rate: float,
) -> list[BaseProcessor]:
    ref_loudness = LoudnessAnalyzer().analyze(ref_audio, sample_rate)
    ref_eq_curve = SpectrumAnalyzer().analyze(ref_audio, sample_rate)

    chain: list[BaseProcessor] = []
    for processor in _normalize_processors(config.processors):
        if isinstance(processor, EQMatchConfig):
            chain.append(
                EQMatchProcessor(
                    target_eq_curve=ref_eq_curve,
                    strength=processor.strength,
                )
            )
        elif isinstance(processor, LoudnessCompConfig):
            target_lufs = (
                ref_loudness if processor.target_lufs is None else processor.target_lufs
            )
            chain.append(
                LoudnessCompProcessor(
                    target_lufs=target_lufs,
                    max_gain_db=processor.max_gain_db,
                )
            )
        elif isinstance(processor, LimiterConfig):
            chain.append(
                LimiterProcessor(
                    threshold_db=processor.threshold_db,
                    mode=processor.mode,
                )
            )
        elif isinstance(processor, DitherConfig):
            chain.append(DitherProcessor(noise_amplitude=processor.noise_amplitude))
        else:
            raise ValueError(f"Unsupported processor config: {processor!r}")

    return chain


def _normalize_processors(processors: Iterable[object]) -> list[object]:
    return list(processors)

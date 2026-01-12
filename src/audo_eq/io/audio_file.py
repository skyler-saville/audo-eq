from __future__ import annotations

from pathlib import Path

import soundfile as sf
import numpy as np


def read_audio(path: Path) -> tuple[np.ndarray, int]:
    audio, sample_rate = sf.read(path, always_2d=False)
    return audio, int(sample_rate)


def write_audio(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    sf.write(path, audio, samplerate=sample_rate, subtype="FLOAT")

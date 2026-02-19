"""Audio decode/encode adapters backed by pedalboard."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from pedalboard.io import AudioFile


def load_audio_file(path: Path) -> tuple[np.ndarray, int]:
    """Read an audio file into memory."""

    with AudioFile(str(path), "r") as audio_file:
        return audio_file.read(audio_file.frames), audio_file.samplerate


def write_audio_file(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    """Write mastered audio to disk."""

    with AudioFile(str(path), "w", sample_rate, audio.shape[0]) as output_file:
        output_file.write(audio)

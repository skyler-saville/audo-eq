"""Temporary-file infrastructure helpers."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterator


@contextmanager
def temporary_wav_path() -> Iterator[Path]:
    """Yield a temporary WAV file path that is deleted automatically."""

    with NamedTemporaryFile(suffix=".wav") as temp_file:
        yield Path(temp_file.name)

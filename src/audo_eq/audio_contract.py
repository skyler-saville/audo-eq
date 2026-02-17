"""Audio ingest contract shared by all external entry points.

Invariants
----------
* Ingest accepts only a known set of source formats.
* All processing modules downstream of ingest receive float PCM normalized to the
  target format defined here.
"""

from __future__ import annotations

from pathlib import Path

from .ingest_validation import SUPPORTED_EXTENSIONS, SUPPORTED_MIME_TYPES

# Supported source extensions (lower-case, with leading dot).
ACCEPTED_SOURCE_EXTENSIONS: tuple[str, ...] = SUPPORTED_EXTENSIONS

# Common MIME types accepted by API uploads.
ACCEPTED_SOURCE_MIME_TYPES: tuple[str, ...] = SUPPORTED_MIME_TYPES

# Normalization target used between ingest and DSP/reference/mastering modules.
TARGET_PCM_SAMPLE_RATE_HZ = 48_000
TARGET_PCM_CHANNEL_COUNT = 2
TARGET_PCM_ENCODING = "float32_pcm"


class UnsupportedAudioFormatError(ValueError):
    """Raised when ingest receives media outside the supported source contract."""


def ensure_supported_path(path: Path) -> None:
    """Validate a local file path against accepted ingest extensions."""

    if path.suffix.lower() not in ACCEPTED_SOURCE_EXTENSIONS:
        supported = ", ".join(ACCEPTED_SOURCE_EXTENSIONS)
        raise UnsupportedAudioFormatError(
            f"Unsupported audio format for '{path.name}'. Supported extensions: {supported}"
        )


def ensure_supported_upload(filename: str | None, content_type: str | None) -> None:
    """Validate API upload metadata against accepted ingest formats."""

    if content_type and content_type.lower() in ACCEPTED_SOURCE_MIME_TYPES:
        return

    if filename and Path(filename).suffix.lower() in ACCEPTED_SOURCE_EXTENSIONS:
        return

    supported_ext = ", ".join(ACCEPTED_SOURCE_EXTENSIONS)
    supported_mimes = ", ".join(ACCEPTED_SOURCE_MIME_TYPES)
    raise UnsupportedAudioFormatError(
        "Unsupported upload format. "
        f"Supported extensions: {supported_ext}. "
        f"Supported MIME types: {supported_mimes}."
    )

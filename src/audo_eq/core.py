"""Core mastering service layer shared by CLI and API interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .audio_contract import (
    TARGET_PCM_CHANNEL_COUNT,
    TARGET_PCM_ENCODING,
    TARGET_PCM_SAMPLE_RATE_HZ,
    ensure_supported_path,
)


class ValidationStatus(str, Enum):
    """Validation lifecycle states for an :class:`AudioAsset`."""

    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"


@dataclass(slots=True)
class AudioAsset:
    """Central domain model representing ingested audio.

    Invariants
    ----------
    * ``source_uri`` is a canonical locator for the original source, either a
      ``file://`` URI or a provider URI from an external ingest system.
    * ``raw_bytes`` contain original payload bytes as received at ingest.
    * All processing modules after ingest assume normalized float PCM using the
      target contract in :mod:`audo_eq.audio_contract`.
    """

    source_uri: str
    raw_bytes: bytes
    duration_seconds: float | None
    sample_rate_hz: int | None
    channel_count: int | None
    bit_depth: int | None
    encoding: str | None
    integrated_lufs: float | None
    loudness_range_lu: float | None
    true_peak_dbtp: float | None
    validation_status: ValidationStatus


@dataclass(slots=True)
class MasteringRequest:
    """Input parameters for a mastering operation."""

    target_asset: AudioAsset
    reference_asset: AudioAsset
    output_path: Path


def _validated_asset_from_path(path: Path) -> AudioAsset:
    if not path.exists():
        raise FileNotFoundError(f"Audio not found: {path}")

    ensure_supported_path(path)

    return AudioAsset(
        source_uri=path.resolve().as_uri(),
        raw_bytes=path.read_bytes(),
        duration_seconds=None,
        sample_rate_hz=TARGET_PCM_SAMPLE_RATE_HZ,
        channel_count=TARGET_PCM_CHANNEL_COUNT,
        bit_depth=32,
        encoding=TARGET_PCM_ENCODING,
        integrated_lufs=None,
        loudness_range_lu=None,
        true_peak_dbtp=None,
        validation_status=ValidationStatus.VALIDATED,
    )


def ingest_local_mastering_request(
    target_path: Path, reference_path: Path, output_path: Path
) -> MasteringRequest:
    """Build a mastering request from local sources using the ingest contract."""

    return MasteringRequest(
        target_asset=_validated_asset_from_path(target_path),
        reference_asset=_validated_asset_from_path(reference_path),
        output_path=output_path,
    )


def master_bytes(target_bytes: bytes, reference_bytes: bytes) -> bytes:
    """Master target audio bytes against a reference.

    This scaffold currently returns the target bytes unchanged so both CLI and API
    can share one stable execution path while DSP modules are implemented.
    """

    if not target_bytes:
        raise ValueError("Target audio is empty.")
    if not reference_bytes:
        raise ValueError("Reference audio is empty.")
    return target_bytes


def master_file(request: MasteringRequest) -> Path:
    """Master an ingested target asset and write result to output path."""

    request.output_path.parent.mkdir(parents=True, exist_ok=True)

    mastered_bytes = master_bytes(
        target_bytes=request.target_asset.raw_bytes,
        reference_bytes=request.reference_asset.raw_bytes,
    )
    request.output_path.write_bytes(mastered_bytes)
    return request.output_path

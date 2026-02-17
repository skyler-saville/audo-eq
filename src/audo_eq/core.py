"""Core mastering service layer shared by CLI and API interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .ingest_validation import AudioMetadata, validate_audio_file


class ValidationStatus(str, Enum):
    """Validation lifecycle states for an :class:`AudioAsset`."""

    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"


@dataclass(slots=True)
class AudioAsset:
    """Central domain model representing ingested audio."""

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


def _asset_from_metadata(source_uri: str, raw_bytes: bytes, metadata: AudioMetadata) -> AudioAsset:
    return AudioAsset(
        source_uri=source_uri,
        raw_bytes=raw_bytes,
        duration_seconds=metadata.duration_seconds,
        sample_rate_hz=metadata.sample_rate_hz,
        channel_count=metadata.channel_count,
        bit_depth=None,
        encoding=metadata.codec,
        integrated_lufs=None,
        loudness_range_lu=None,
        true_peak_dbtp=None,
        validation_status=ValidationStatus.VALIDATED,
    )


def _validated_asset_from_path(path: Path) -> AudioAsset:
    metadata = validate_audio_file(path)
    raw_bytes = path.read_bytes()
    return _asset_from_metadata(path.resolve().as_uri(), raw_bytes, metadata)


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
    """Master target audio bytes against a reference."""

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

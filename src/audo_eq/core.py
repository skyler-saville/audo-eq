"""Core mastering service layer shared by CLI and API interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
from pedalboard.io import AudioFile

from .analysis import AnalysisPayload, analyze_tracks
from .decision import DecisionPayload, decide_mastering
from .ingest_validation import AudioMetadata, validate_audio_bytes, validate_audio_file
from .processing import apply_processing


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


@dataclass(frozen=True, slots=True)
class MasteringResult:
    """Structured pipeline payloads produced during mastering."""

    analysis: AnalysisPayload
    decision: DecisionPayload
    mastered_audio: np.ndarray


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


def _load_audio_file(path: Path) -> tuple[np.ndarray, int]:
    with AudioFile(str(path), "r") as audio_file:
        return audio_file.read(audio_file.frames), audio_file.samplerate


def _run_mastering_pipeline(
    target_audio: np.ndarray,
    reference_audio: np.ndarray,
    sample_rate: int,
) -> MasteringResult:
    analysis = analyze_tracks(target_audio=target_audio, reference_audio=reference_audio, sample_rate=sample_rate)
    decision = decide_mastering(analysis)
    mastered_audio = apply_processing(target_audio=target_audio, sample_rate=sample_rate, decision=decision)
    return MasteringResult(analysis=analysis, decision=decision, mastered_audio=mastered_audio)


def _master_path_to_path(target_path: Path, reference_path: Path, output_path: Path) -> MasteringResult:
    target_audio, sample_rate = _load_audio_file(target_path)
    reference_audio, _ = _load_audio_file(reference_path)

    result = _run_mastering_pipeline(
        target_audio=target_audio,
        reference_audio=reference_audio,
        sample_rate=sample_rate,
    )

    with AudioFile(str(output_path), "w", sample_rate, result.mastered_audio.shape[0]) as output_file:
        output_file.write(result.mastered_audio)

    return result


def master_bytes(target_bytes: bytes, reference_bytes: bytes) -> bytes:
    """Master target audio bytes against a reference."""

    if not target_bytes:
        raise ValueError("Target audio is empty.")
    if not reference_bytes:
        raise ValueError("Reference audio is empty.")

    validate_audio_bytes(target_bytes, filename="target.wav")
    validate_audio_bytes(reference_bytes, filename="reference.wav")

    with NamedTemporaryFile(suffix=".wav") as target_file, NamedTemporaryFile(
        suffix=".wav"
    ) as reference_file, NamedTemporaryFile(suffix=".wav") as output_file:
        target_path = Path(target_file.name)
        reference_path = Path(reference_file.name)
        output_path = Path(output_file.name)

        target_path.write_bytes(target_bytes)
        reference_path.write_bytes(reference_bytes)

        _master_path_to_path(target_path=target_path, reference_path=reference_path, output_path=output_path)
        return output_path.read_bytes()


def master_file(request: MasteringRequest) -> Path:
    """Master an ingested target asset and write result to output path."""

    request.output_path.parent.mkdir(parents=True, exist_ok=True)

    with NamedTemporaryFile(suffix=".wav") as target_file, NamedTemporaryFile(
        suffix=".wav"
    ) as reference_file:
        target_path = Path(target_file.name)
        reference_path = Path(reference_file.name)

        target_path.write_bytes(request.target_asset.raw_bytes)
        reference_path.write_bytes(request.reference_asset.raw_bytes)

        _master_path_to_path(
            target_path=target_path,
            reference_path=reference_path,
            output_path=request.output_path,
        )

    return request.output_path

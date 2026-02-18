"""Core mastering service layer shared by CLI and API interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
from pedalboard import (
    Compressor,
    Gain,
    HighpassFilter,
    Limiter,
    LowShelfFilter,
    Pedalboard,
)
from pedalboard.io import AudioFile

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


def _rms_db(audio: np.ndarray) -> float:
    if audio.size == 0:
        return -96.0
    rms = float(np.sqrt(np.mean(np.square(audio), dtype=np.float64)))
    if rms <= 0:
        return -96.0
    return 20.0 * np.log10(rms)


def _build_mastering_board(target_audio: np.ndarray, reference_audio: np.ndarray) -> Pedalboard:
    target_rms_db = _rms_db(target_audio)
    reference_rms_db = _rms_db(reference_audio)

    gain_to_reference_db = float(np.clip(reference_rms_db - target_rms_db, -8.0, 8.0))

    return Pedalboard(
        [
            HighpassFilter(cutoff_frequency_hz=30.0),
            LowShelfFilter(cutoff_frequency_hz=125.0, gain_db=0.75),
            Compressor(threshold_db=-22.0, ratio=2.5, attack_ms=15.0, release_ms=120.0),
            Gain(gain_db=gain_to_reference_db),
            Limiter(threshold_db=-0.9, release_ms=150.0),
        ]
    )


def _master_audio(target_audio: np.ndarray, reference_audio: np.ndarray, sample_rate: int) -> np.ndarray:
    board = _build_mastering_board(target_audio=target_audio, reference_audio=reference_audio)
    return board(target_audio, sample_rate)


def _load_audio_file(path: Path) -> tuple[np.ndarray, int]:
    with AudioFile(str(path), "r") as audio_file:
        return audio_file.read(audio_file.frames), audio_file.samplerate


def _master_path_to_path(target_path: Path, reference_path: Path, output_path: Path) -> None:
    target_audio, sample_rate = _load_audio_file(target_path)
    reference_audio, _ = _load_audio_file(reference_path)

    mastered_audio = _master_audio(
        target_audio=target_audio,
        reference_audio=reference_audio,
        sample_rate=sample_rate,
    )

    with AudioFile(str(output_path), "w", sample_rate, mastered_audio.shape[0]) as output_file:
        output_file.write(mastered_audio)


def master_bytes(target_bytes: bytes, reference_bytes: bytes) -> bytes:
    """Master target audio bytes against a reference."""

    if not target_bytes:
        raise ValueError("Target audio is empty.")
    if not reference_bytes:
        raise ValueError("Reference audio is empty.")

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

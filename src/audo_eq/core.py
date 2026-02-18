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
from .normalization import normalize_audio
from .processing import EqMode, apply_processing_with_loudness_target, measure_integrated_lufs

_LOUDNESS_GAIN_MIN_DB = -12.0
_LOUDNESS_GAIN_MAX_DB = 12.0


def _compute_loudness_gain_delta_db(target_lufs: float, reference_lufs: float) -> float:
    """Compute a safe loudness gain delta from LUFS difference."""

    return float(np.clip(reference_lufs - target_lufs, _LOUDNESS_GAIN_MIN_DB, _LOUDNESS_GAIN_MAX_DB))


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
    asset = _asset_from_metadata(path.resolve().as_uri(), raw_bytes, metadata)
    audio, sample_rate = _load_audio_file(path)
    asset.integrated_lufs = measure_integrated_lufs(audio, sample_rate)
    return asset


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
    eq_mode: EqMode = EqMode.FIXED,
) -> MasteringResult:
    target_lufs = measure_integrated_lufs(target_audio, sample_rate)
    reference_lufs = measure_integrated_lufs(reference_audio, sample_rate)
    loudness_gain_db = _compute_loudness_gain_delta_db(target_lufs, reference_lufs)

    analysis = analyze_tracks(target_audio=target_audio, reference_audio=reference_audio, sample_rate=sample_rate)
    decision = decide_mastering(analysis)
    mastered_audio = apply_processing_with_loudness_target(
        target_audio=target_audio,
        sample_rate=sample_rate,
        decision=decision,
        loudness_gain_db=loudness_gain_db,
        target_lufs=reference_lufs,
        eq_mode=eq_mode,
        eq_band_corrections=analysis.eq_band_corrections,
    )
    return MasteringResult(analysis=analysis, decision=decision, mastered_audio=mastered_audio)


def _master_audio_to_path(
    target_audio: np.ndarray,
    reference_audio: np.ndarray,
    sample_rate: int,
    output_path: Path,
    eq_mode: EqMode = EqMode.FIXED,
) -> MasteringResult:

    result = _run_mastering_pipeline(
        target_audio=target_audio,
        reference_audio=reference_audio,
        sample_rate=sample_rate,
        eq_mode=eq_mode,
    )

    with AudioFile(str(output_path), "w", sample_rate, result.mastered_audio.shape[0]) as output_file:
        output_file.write(result.mastered_audio)

    return result


def master_bytes(
    target_bytes: bytes,
    reference_bytes: bytes,
    eq_mode: EqMode = EqMode.FIXED,
) -> bytes:
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

        target_audio, target_sample_rate = _load_audio_file(target_path)
        reference_audio, reference_sample_rate = _load_audio_file(reference_path)

        normalized_target = normalize_audio(target_audio, target_sample_rate)
        normalized_reference = normalize_audio(reference_audio, reference_sample_rate)

        _master_audio_to_path(
            target_audio=normalized_target.audio,
            reference_audio=normalized_reference.audio,
            sample_rate=normalized_target.sample_rate_hz,
            output_path=output_path,
            eq_mode=eq_mode,
        )
        return output_path.read_bytes()


def master_file(request: MasteringRequest, eq_mode: EqMode = EqMode.FIXED) -> Path:
    """Master an ingested target asset and write result to output path."""

    request.output_path.parent.mkdir(parents=True, exist_ok=True)

    with NamedTemporaryFile(suffix=".wav") as target_file, NamedTemporaryFile(
        suffix=".wav"
    ) as reference_file:
        target_path = Path(target_file.name)
        reference_path = Path(reference_file.name)

        target_path.write_bytes(request.target_asset.raw_bytes)
        reference_path.write_bytes(request.reference_asset.raw_bytes)

        target_audio, target_sample_rate = _load_audio_file(target_path)
        reference_audio, reference_sample_rate = _load_audio_file(reference_path)

        normalized_target = normalize_audio(target_audio, target_sample_rate)
        normalized_reference = normalize_audio(reference_audio, reference_sample_rate)

        _master_audio_to_path(
            target_audio=normalized_target.audio,
            reference_audio=normalized_reference.audio,
            sample_rate=normalized_target.sample_rate_hz,
            output_path=request.output_path,
            eq_mode=eq_mode,
        )

    with AudioFile(str(request.output_path), "r") as output_audio_file:
        output_audio = output_audio_file.read(output_audio_file.frames)
        request.target_asset.integrated_lufs = measure_integrated_lufs(output_audio, output_audio_file.samplerate)

    return request.output_path

"""Compatibility wrappers around DDD application services."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .application.mastering_service import MasterTrackAgainstReference, ValidateIngest
from .domain.models import AudioAsset, MasteringRequest, MasteringResult, ValidationStatus
from .ingest_validation import AudioMetadata
from .mastering_options import EqMode, EqPreset

_validate_ingest = ValidateIngest()
_mastering_service = MasterTrackAgainstReference()


def _compute_loudness_gain_delta_db(target_lufs: float, reference_lufs: float) -> float:
    """Backward-compatible wrapper for legacy tests/internal callers."""

    from .domain.services import compute_loudness_gain_delta_db

    return compute_loudness_gain_delta_db(target_lufs, reference_lufs)


def _asset_from_metadata(source_uri: str, raw_bytes: bytes, metadata: AudioMetadata) -> AudioAsset:
    return _validate_ingest.asset_from_metadata(source_uri, raw_bytes, metadata)


def _validated_asset_from_path(path: Path) -> AudioAsset:
    return _validate_ingest.validated_asset_from_path(path)


def ingest_local_mastering_request(target_path: Path, reference_path: Path, output_path: Path) -> MasteringRequest:
    return _validate_ingest.ingest_local_mastering_request(target_path, reference_path, output_path)


def _load_audio_file(path: Path) -> tuple[np.ndarray, int]:
    from .infrastructure.pedalboard_codec import load_audio_file

    return load_audio_file(path)


def _run_mastering_pipeline(
    target_audio: np.ndarray,
    reference_audio: np.ndarray,
    sample_rate: int,
    eq_mode: EqMode = EqMode.FIXED,
    eq_preset: EqPreset = EqPreset.NEUTRAL,
) -> MasteringResult:
    return _mastering_service.run_pipeline(target_audio, reference_audio, sample_rate, eq_mode=eq_mode, eq_preset=eq_preset)


def _master_audio_to_path(
    target_audio: np.ndarray,
    reference_audio: np.ndarray,
    sample_rate: int,
    output_path: Path,
    eq_mode: EqMode = EqMode.FIXED,
    eq_preset: EqPreset = EqPreset.NEUTRAL,
) -> MasteringResult:
    return _mastering_service.master_to_path(
        target_audio=target_audio,
        reference_audio=reference_audio,
        sample_rate=sample_rate,
        output_path=output_path,
        eq_mode=eq_mode,
        eq_preset=eq_preset,
    )


def master_bytes(
    target_bytes: bytes,
    reference_bytes: bytes,
    eq_mode: EqMode = EqMode.FIXED,
    eq_preset: EqPreset = EqPreset.NEUTRAL,
) -> bytes:
    return _mastering_service.master_bytes(target_bytes, reference_bytes, eq_mode=eq_mode, eq_preset=eq_preset)


def master_file(
    request: MasteringRequest,
    eq_mode: EqMode = EqMode.FIXED,
    eq_preset: EqPreset = EqPreset.NEUTRAL,
) -> Path:
    return _mastering_service.master_file(request, eq_mode=eq_mode, eq_preset=eq_preset)

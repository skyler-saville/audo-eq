"""API-facing handlers that delegate to application services."""

from __future__ import annotations

from audo_eq.application.mastering_service import MasterTrackAgainstReference, ValidateIngest
from audo_eq.ingest_validation import IngestValidationError, validate_audio_bytes
from audo_eq.mastering_options import EqMode, EqPreset


validate_ingest = ValidateIngest()
mastering_service = MasterTrackAgainstReference()


def build_asset(source_uri: str, payload: bytes, filename: str | None):
    metadata = validate_audio_bytes(payload, filename=filename)
    return validate_ingest.asset_from_metadata(source_uri, payload, metadata)


def master_uploaded_bytes(target_bytes: bytes, reference_bytes: bytes, eq_mode: EqMode, eq_preset: EqPreset) -> bytes:
    return mastering_service.master_bytes(
        target_bytes=target_bytes,
        reference_bytes=reference_bytes,
        eq_mode=eq_mode,
        eq_preset=eq_preset,
    )


__all__ = ["IngestValidationError", "build_asset", "master_uploaded_bytes"]

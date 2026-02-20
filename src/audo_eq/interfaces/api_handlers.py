"""API-facing handlers that delegate to application services."""

from __future__ import annotations

from audo_eq.application.mastering_service import (
    MasterTrackAgainstReference,
    ValidateIngest,
)
from audo_eq.infrastructure.logging_event_publisher import LoggingEventPublisher
from audo_eq.ingest_validation import IngestValidationError, validate_audio_bytes
from audo_eq.mastering_options import DeEsserMode, EqMode, EqPreset


_event_publisher = LoggingEventPublisher()
validate_ingest = ValidateIngest(event_publisher=_event_publisher)
mastering_service = MasterTrackAgainstReference(event_publisher=_event_publisher)


def build_asset(source_uri: str, payload: bytes, filename: str | None):
    metadata = validate_audio_bytes(payload, filename=filename)
    return validate_ingest.asset_from_metadata(source_uri, payload, metadata)


def master_uploaded_bytes(
    target_bytes: bytes,
    reference_bytes: bytes,
    eq_mode: EqMode,
    eq_preset: EqPreset,
    de_esser_mode: DeEsserMode,
    correlation_id: str,
) -> bytes:
    return mastering_service.master_bytes(
        target_bytes=target_bytes,
        reference_bytes=reference_bytes,
        correlation_id=correlation_id,
        eq_mode=eq_mode,
        eq_preset=eq_preset,
        de_esser_mode=de_esser_mode,
    )


__all__ = ["IngestValidationError", "build_asset", "master_uploaded_bytes"]

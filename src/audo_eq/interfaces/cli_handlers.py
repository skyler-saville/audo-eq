"""CLI-facing handlers that delegate to application services."""

from __future__ import annotations

from pathlib import Path

from audo_eq.application.mastering_service import (
    MasterTrackAgainstReference,
    ValidateIngest,
)
from audo_eq.infrastructure.logging_event_publisher import LoggingEventPublisher
from audo_eq.mastering_options import DeEsserMode, EqMode, EqPreset

_event_publisher = LoggingEventPublisher()
validate_ingest = ValidateIngest(event_publisher=_event_publisher)
mastering_service = MasterTrackAgainstReference(event_publisher=_event_publisher)


def master_from_paths(
    target: Path,
    reference: Path,
    output: Path,
    correlation_id: str,
    eq_mode: EqMode,
    eq_preset: EqPreset,
    de_esser_mode: DeEsserMode,
) -> Path:
    request = validate_ingest.ingest_local_mastering_request(
        target, reference, output, correlation_id=correlation_id
    )
    return mastering_service.master_file(
        request,
        correlation_id=correlation_id,
        eq_mode=eq_mode,
        eq_preset=eq_preset,
        de_esser_mode=de_esser_mode,
    )

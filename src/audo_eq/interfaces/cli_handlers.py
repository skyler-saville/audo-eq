"""CLI-facing handlers that delegate to application services."""

from __future__ import annotations

from pathlib import Path

from audo_eq.application.mastering_service import MasterTrackAgainstReference, ValidateIngest
from audo_eq.mastering_options import EqMode, EqPreset

validate_ingest = ValidateIngest()
mastering_service = MasterTrackAgainstReference()


def master_from_paths(target: Path, reference: Path, output: Path, eq_mode: EqMode, eq_preset: EqPreset) -> Path:
    request = validate_ingest.ingest_local_mastering_request(target, reference, output)
    return mastering_service.master_file(request, eq_mode=eq_mode, eq_preset=eq_preset)

"""Public package exports for Audo_EQ with lazy imports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "AnalysisPayload",
    "TrackMetrics",
    "DecisionPayload",
    "AudioAsset",
    "MasteringRequest",
    "ingest_local_mastering_request",
    "master_bytes",
    "master_file",
    "IngestValidationError",
    "ValidationPolicy",
    "validate_audio_bytes",
    "validate_audio_file",
]

_EXPORT_MODULES: dict[str, str] = {
    "AnalysisPayload": "audo_eq.analysis",
    "TrackMetrics": "audo_eq.analysis",
    "DecisionPayload": "audo_eq.decision",
    "AudioAsset": "audo_eq.core",
    "MasteringRequest": "audo_eq.core",
    "ingest_local_mastering_request": "audo_eq.core",
    "master_bytes": "audo_eq.core",
    "master_file": "audo_eq.core",
    "IngestValidationError": "audo_eq.ingest_validation",
    "ValidationPolicy": "audo_eq.ingest_validation",
    "validate_audio_bytes": "audo_eq.ingest_validation",
    "validate_audio_file": "audo_eq.ingest_validation",
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORT_MODULES:
        raise AttributeError(f"module 'audo_eq' has no attribute {name!r}")

    module = import_module(_EXPORT_MODULES[name])
    value = getattr(module, name)
    globals()[name] = value
    return value

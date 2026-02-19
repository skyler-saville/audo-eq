"""DDD domain layer."""

from .events import ArtifactStored, DomainEvent, IngestValidated, MasteringDecided, MasteringFailed, MasteringRendered, TrackAnalyzed
from .models import AudioAsset, MasteringRequest, MasteringResult, ValidationStatus
from .policies import (
    DEFAULT_INGEST_POLICY,
    DEFAULT_MASTERING_PROFILE,
    DEFAULT_NORMALIZATION_POLICY,
    IngestPolicy,
    MasteringProfile,
    NormalizationPolicy,
)
from .services import compute_loudness_gain_delta_db

__all__ = [
    "DomainEvent",
    "IngestValidated",
    "TrackAnalyzed",
    "MasteringDecided",
    "MasteringRendered",
    "ArtifactStored",
    "MasteringFailed",
    "AudioAsset",
    "MasteringRequest",
    "MasteringResult",
    "ValidationStatus",
    "IngestPolicy",
    "NormalizationPolicy",
    "MasteringProfile",
    "DEFAULT_INGEST_POLICY",
    "DEFAULT_NORMALIZATION_POLICY",
    "DEFAULT_MASTERING_PROFILE",
    "compute_loudness_gain_delta_db",
]

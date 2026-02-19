"""Domain models for mastering and ingest workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np

from audo_eq.analysis import AnalysisPayload
from audo_eq.decision import DecisionPayload
from audo_eq.domain.policies import IngestPolicy, MasteringProfile, NormalizationPolicy


class ValidationStatus(str, Enum):
    """Validation lifecycle states for an audio asset."""

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
    ingest_policy: IngestPolicy
    normalization_policy: NormalizationPolicy
    mastering_profile: MasteringProfile
    policy_version: str = "v1"


@dataclass(frozen=True, slots=True)
class MasteringResult:
    """Structured pipeline payloads produced during mastering."""

    analysis: AnalysisPayload
    decision: DecisionPayload
    mastered_audio: np.ndarray
    ingest_policy_id: str
    normalization_policy_id: str
    mastering_profile_id: str
    policy_version: str = "v1"

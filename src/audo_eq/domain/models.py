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
    diagnostics: "MasteringDiagnostics"
    policy_version: str = "v1"


@dataclass(frozen=True, slots=True)
class SpectralBalanceSummary:
    """Compact target/reference spectral-balance deltas."""

    low_band_delta: float
    mid_band_delta: float
    high_band_delta: float


@dataclass(frozen=True, slots=True)
class LimiterTruePeakDiagnostics:
    """Limiter configuration and measured true-peak result."""

    limiter_ceiling_db: float
    measured_true_peak_dbtp: float
    true_peak_margin_db: float


@dataclass(frozen=True, slots=True)
class AppliedChainParameters:
    """Applied chain parameters used for this mastering run."""

    eq_mode: str
    eq_preset: str
    de_esser_mode: str
    loudness_gain_db: float
    gain_db: float
    low_shelf_gain_db: float
    high_shelf_gain_db: float
    compressor_threshold_db: float
    compressor_ratio: float
    de_esser_threshold: float
    de_esser_depth_db: float


@dataclass(frozen=True, slots=True)
class MasteringDiagnostics:
    """User-facing diagnostics emitted from a mastering run."""

    input_lufs: float
    output_lufs: float
    reference_lufs: float
    crest_factor_delta_db: float
    spectral_balance: SpectralBalanceSummary
    limiter_true_peak: LimiterTruePeakDiagnostics
    applied_chain: AppliedChainParameters

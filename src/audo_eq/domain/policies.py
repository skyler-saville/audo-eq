"""Domain value objects representing stable processing policies."""

from __future__ import annotations

from dataclasses import dataclass

from audo_eq.audio_contract import TARGET_PCM_CHANNEL_COUNT, TARGET_PCM_SAMPLE_RATE_HZ


@dataclass(frozen=True, slots=True)
class IngestPolicy:
    """Policy describing ingest validation expectations and identity."""

    policy_id: str
    policy_version: str = "v1"


@dataclass(frozen=True, slots=True)
class NormalizationPolicy:
    """Policy describing canonical audio normalization targets and clipping bounds."""

    policy_id: str
    target_sample_rate_hz: int = TARGET_PCM_SAMPLE_RATE_HZ
    target_channel_count: int = TARGET_PCM_CHANNEL_COUNT
    clip_floor: float = -1.0
    clip_ceiling: float = 1.0
    policy_version: str = "v1"


@dataclass(frozen=True, slots=True)
class MasteringProfile:
    """Policy describing a mastering profile identity and version."""

    profile_id: str
    policy_version: str = "v1"


DEFAULT_INGEST_POLICY = IngestPolicy(policy_id="ingest-validation-default", policy_version="v1")
DEFAULT_NORMALIZATION_POLICY = NormalizationPolicy(policy_id="pcm-canonical-default", policy_version="v1")
DEFAULT_MASTERING_PROFILE = MasteringProfile(profile_id="reference-mastering-default", policy_version="v1")

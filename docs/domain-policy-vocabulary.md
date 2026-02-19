# Domain Policy Vocabulary (DDD)

This page documents the policy value objects used in `audo_eq.domain` to make mastering behavior reproducible and debuggable.

## Why policy objects exist

In Domain-Driven Design terms, these are **value objects** that capture stable business intent:

- they are immutable,
- identity comes from their values,
- they can be attached to requests/results as traceable metadata.

The goal is to avoid hidden defaults in orchestration code and to make each mastering run explainable with explicit policy identifiers.

## Policy value objects

## `IngestPolicy`

Represents ingest/validation rule identity.

Fields:

- `policy_id`: semantic identifier (example: `ingest-validation-default`)
- `policy_version`: version tag (example: `v1`)

## `NormalizationPolicy`

Represents canonical audio normalization targets and clipping boundaries.

Fields:

- `policy_id`: semantic identifier (example: `pcm-canonical-default`)
- `target_sample_rate_hz`: sample-rate target for downstream DSP
- `target_channel_count`: channel layout target
- `clip_floor`: lower clipping bound
- `clip_ceiling`: upper clipping bound
- `policy_version`: version tag (example: `v1`)

## `MasteringProfile`

Represents mastering profile identity and version.

Fields:

- `profile_id`: semantic identifier (example: `reference-mastering-default`)
- `policy_version`: version tag (example: `v1`)

## Default vocabulary

The domain layer currently exposes these defaults:

- `DEFAULT_INGEST_POLICY = IngestPolicy(policy_id="ingest-validation-default", policy_version="v1")`
- `DEFAULT_NORMALIZATION_POLICY = NormalizationPolicy(policy_id="pcm-canonical-default", policy_version="v1")`
- `DEFAULT_MASTERING_PROFILE = MasteringProfile(profile_id="reference-mastering-default", policy_version="v1")`

## Where policy metadata is propagated

- `MasteringRequest` carries the selected ingest, normalization, and mastering profile value objects.
- `MasteringResult` carries policy IDs and `policy_version` metadata for auditability.
- API responses expose policy IDs/version via response headers so callers can correlate outputs with governing policy versions.

## Compatibility guidance

When evolving policy behavior:

1. Keep old IDs/versions available when possible.
2. Introduce a new `policy_version` (for example `v2`) for behavior changes.
3. Prefer additive fields over repurposing existing semantics.
4. Update this page and API contract notes in the same change.

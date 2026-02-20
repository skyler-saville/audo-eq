# DDD Roadmap (Next 2–4 Releases)

This document captures the domain-driven architecture direction for the next 2–4 releases so that feature delivery remains aligned with bounded contexts, explicit contracts, and measurable outcomes.

## Vision and scope

### Release horizon
- **R+1 (Foundations):** Stabilize context boundaries and data contracts between ingest, core mastering orchestration, and artifact persistence.
- **R+2 (Policy evolution):** Introduce versioned decisioning policies with safe rollout controls and compatibility checks.
- **R+3 (Event-driven observability):** Add domain events for major pipeline transitions and improve diagnostics, replay, and auditability.
- **R+4 (Adapter hardening):** Harden external adapters (API, storage, queue/event transport) behind anti-corruption boundaries and conformance tests.

### In scope
- Domain model decomposition by bounded context.
- Explicit interfaces between contexts and adapter layers.
- Decision policy lifecycle and version compatibility.
- Milestone-based acceptance criteria for architecture outcomes.

## Bounded contexts

| Context | Responsibility | Owns | Publishes | Depends on |
| --- | --- | --- | --- | --- |
| **Ingest** | Validate and normalize incoming mastering requests and source media metadata. | Request envelope, validation rules, media descriptors. | `IngestAccepted`, `IngestRejected`. | Delivery adapters, shared core contracts. |
| **Analysis** | Extract measurable audio features used for downstream policy and processing choices. | Feature schema, analysis workflows, quality signals. | `AnalysisCompleted`. | Ingest outputs, shared core DSP utilities. |
| **Decisioning** | Convert analysis outputs into actionable mastering policy decisions. | Policy definitions, rule evaluation, policy version metadata. | `DecisionPlanGenerated`. | Analysis outputs, policy registry. |
| **Processing** | Execute mastering chain according to a decision plan and produce mastered artifacts. | Processing orchestration, plugin chain config, run-level telemetry. | `ProcessingCompleted`, `ProcessingFailed`. | Decision plans, shared core DSP components. |
| **Delivery** | Return mastering results to callers (HTTP/CLI) and expose status/diagnostics surfaces. | Response mapping, error contracts, delivery DTOs. | `DeliverySucceeded`, `DeliveryFailed`. | Processing results, adapter interfaces. |
| **Artifact Storage** | Persist mastered outputs and associated metadata with reliability guarantees. | Artifact metadata, persistence state, retention metadata. | `ArtifactPersisted`, `ArtifactPersistenceFailed`. | Processing artifacts, storage adapters. |

## Milestones

| Milestone | Target release | Expected outcomes | Primary risks | Acceptance criteria |
| --- | --- | --- | --- | --- |
| Context boundary baseline | R+1 | Context-owned models and interfaces are separated from transport/storage adapters. | Existing shared code paths leak adapter concerns into domain services. | No direct adapter imports in bounded-context domain modules; boundary review checklist passes for all architecture PRs. |
| Policy versioning v1 | R+2 | Decisioning can select and execute explicit policy versions with backward-compatible defaults. | Policy drift or incompatible rule changes can alter mastering behavior unexpectedly. | Every decision run records `policy_id` + `policy_version`; compatibility tests validate old policy execution. |
| Event contract rollout | R+3 | Pipeline emits versioned domain events for ingest, analysis, decisioning, processing, and persistence. | Event schema churn and missing idempotency controls. | Event schemas documented and versioned; consumers handle at-least-once delivery in conformance tests. |
| Adapter conformance hardening | R+4 | Delivery/storage adapters are replaceable without domain-layer changes. | Hidden adapter coupling blocks backend swaps. | Adapter test suite validates all required ports; at least one alternative adapter passes without domain code changes. |

## Architectural decisions (ADR-lite)

### ADR-01: Shared core remains framework-agnostic
- **Status:** Accepted
- **Decision:** Keep core domain and processing orchestration free of FastAPI/CLI/storage SDK dependencies.
- **Rationale:** Enables reuse, simpler testing, and lower blast radius when delivery adapters evolve.
- **Consequence:** Introduce explicit ports/interfaces where adapters need to call or receive domain operations.

### ADR-02: Decision policies are versioned artifacts
- **Status:** Accepted
- **Decision:** Treat policy rules/configuration as versioned artifacts selected at runtime.
- **Rationale:** Preserves reproducibility of mastering outcomes and supports safe gradual rollout.
- **Consequence:** Decision outputs and run metadata must persist policy identity and version.

### ADR-03: Domain eventing for cross-context communication
- **Status:** Accepted (incremental)
- **Decision:** Use versioned domain events for cross-context state transitions instead of implicit in-process coupling.
- **Rationale:** Improves observability, traceability, and future async scalability.
- **Consequence:** Event contracts require lifecycle management, compatibility checks, and idempotent consumption.

### ADR-04: Adapter boundaries via anti-corruption layers
- **Status:** Accepted
- **Decision:** Isolate HTTP, CLI, object storage, and message transport specifics behind adapter boundaries.
- **Rationale:** Prevents vendor/framework concepts from leaking into domain language.
- **Consequence:** Additional mapping code is required, but context models remain stable and portable.

## Non-goals

To prevent scope creep during this roadmap horizon, the following are out of scope:
- Rewriting the DSP chain solely for architectural purity.
- Building a generalized workflow engine beyond current mastering pipeline needs.
- Supporting every possible storage/event backend before contract stabilization.
- Introducing cross-context shared mutable state stores.
- Expanding product UX surfaces beyond current CLI/API and existing test frontend needs.

## Delivery plan for mastering quality and scale risks

This section translates common operational and product-quality pain points into a concrete delivery sequence for the next 6–12 months.

### Phase 1: Perceptual reference matching baseline (near term)

**Goals**
- Improve perceived loudness matching and tonal decisions beyond simple RMS targeting.
- Add explicit mastering targets that can be user-driven or reference-driven.

**Plan**
1. Add loudness metering primitives (integrated LUFS + short-term/momentary windows) to the Analysis context output schema.
2. Extend Decisioning policy inputs to include loudness deltas, low/high-band energy deltas, and optional user target constraints (`target_lufs`, `true_peak_ceiling_dbtp`).
3. Implement a minimal tonal correction strategy (tilt + low/high shelf adjustments) before considering full match-EQ.
4. Persist target-vs-achieved loudness and peak diagnostics for post-run evaluation.

**Acceptance criteria**
- Decision plans no longer rely solely on RMS for gain matching.
- API/CLI options support explicit loudness and true-peak targets with safe defaults.
- Processing output metadata includes achieved LUFS and true-peak values.

### Phase 2: Throughput and memory hardening (near to mid term)

**Goals**
- Handle long/high-resolution inputs and batch workloads without excessive memory pressure.
- Prevent long-running HTTP requests from becoming reliability bottlenecks.

**Plan**
1. Add chunked/streaming processing mode for long files in Processing context orchestration.
2. Introduce configurable memory guardrails and temporary-file spillover behavior.
3. Define asynchronous job execution contract for API delivery (queued/background execution, progress states, and completion retrieval).
4. Emit progress and stage timing events to support observability and future webhooks.

**Acceptance criteria**
- Long-form inputs can be processed with bounded memory growth.
- API supports asynchronous mastering jobs with status polling.
- Processing stage timing is exposed via run telemetry/events.

### Phase 3: Format reliability and DSP edge-case coverage (mid term)

**Goals**
- Improve robustness for common upload formats and problematic media inputs.
- Reduce silent failures and unexpected output quality regressions.

**Plan**
1. Expand ingest validation and decoder coverage for MP3/AAC/common container variants.
2. Define explicit behavior for multi-channel inputs (reject, fold-down policy, or channel-preserving path) and document it in API contracts.
3. Add guards for silence-only, ultra-short, and corrupted-header files with structured error codes.
4. Introduce sample-rate mismatch policy and output bit-depth rules, including dithering behavior when reducing depth.

**Acceptance criteria**
- Supported/unsupported format behavior is deterministic and documented.
- Edge-case failures map to stable, test-covered error contracts.
- Output sample-rate/bit-depth decisions are explicit in run metadata.

### Phase 4: Verification strategy for DSP confidence (mid to long term)

**Goals**
- Build confidence in audio outcomes despite floating-point and codec variability.
- Catch regressions early in CI with meaningful signal-focused checks.

**Plan**
1. Add golden-file regression tests for representative short fixtures across presets.
2. Add property-based tests for invariants (for example, true-peak ceiling and bounded loudness shifts).
3. Add integration smoke tests covering wav/flac/mp3 input paths and artifact persistence.
4. Add tolerance-based metric assertions (loudness, crest factor, spectral tilt) rather than strict sample equality.

**Acceptance criteria**
- CI includes deterministic DSP regression checks with documented tolerances.
- Critical invariants are validated across multiple input classes.
- Failures provide actionable diagnostics (metric deltas and stage attribution).

### Phase 5: Configurable mastering chain and presets (long term)

**Goals**
- Make pipeline behavior user-configurable without weakening domain boundaries.
- Enable product iteration through presets and stage-level controls.

**Plan**
1. Define versioned preset schema (JSON/YAML) for stage ordering, stage enablement, and parameter overrides.
2. Map preset schema to Decisioning policies so runtime choices remain auditable and reproducible.
3. Add validation + compatibility checks for preset versions and unsupported stage/plugin options.
4. Surface per-stage controls in API/CLI incrementally behind capability flags.

**Acceptance criteria**
- Presets are first-class, versioned artifacts referenced in run metadata.
- Stage-level enable/disable and parameter override paths are test-covered.
- Invalid preset configurations fail fast with stable validation errors.

## PR review maintenance checklist

Use this checklist in architecture-impacting PRs:
- [ ] Does the change clearly map to exactly one bounded context ownership area?
- [ ] Are new interfaces expressed as ports/contracts rather than direct adapter dependencies?
- [ ] Are decisioning changes tied to explicit policy version semantics?
- [ ] If events are added/changed, are schema versions and compatibility notes documented?
- [ ] Do delivery/storage integrations stay behind anti-corruption mappings?
- [ ] Are acceptance criteria for the relevant milestone updated or referenced?
- [ ] Are non-goals respected (no scope expansion without explicit roadmap amendment)?

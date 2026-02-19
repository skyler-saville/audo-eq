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

## PR review maintenance checklist

Use this checklist in architecture-impacting PRs:
- [ ] Does the change clearly map to exactly one bounded context ownership area?
- [ ] Are new interfaces expressed as ports/contracts rather than direct adapter dependencies?
- [ ] Are decisioning changes tied to explicit policy version semantics?
- [ ] If events are added/changed, are schema versions and compatibility notes documented?
- [ ] Do delivery/storage integrations stay behind anti-corruption mappings?
- [ ] Are acceptance criteria for the relevant milestone updated or referenced?
- [ ] Are non-goals respected (no scope expansion without explicit roadmap amendment)?

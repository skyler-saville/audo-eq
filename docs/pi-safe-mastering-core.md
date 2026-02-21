# Pi-Safe Automatic Mastering Core (Phase 1)

This document captures the implementation direction for a deterministic, testable mastering core that runs on Raspberry Pi hardware.

## Architecture

### Layer 1: Deterministic DSP Core

Owned directly in `audo_eq` for reproducibility and measurable behavior:

- Integrated loudness measurement (LUFS)
- True-peak estimation (oversampled)
- Gain staging and loudness convergence
- Minimum-phase shelf-based EQ and reference-match deltas
- Feed-forward compression
- True-peak limiting with post-limit true-peak guard

### Layer 2: Optional Color (Future)

Plugin character processing is optional and must remain replaceable. Functional correctness (LUFS/TP compliance) stays in Layer 1.

## Core guardrails

- Enforce a profile-specific true-peak ceiling (dBTP)
- Cap post-limiter loudness correction per profile
- Keep mastering behavior deterministic by bounded convergence iterations
- Always run post-limit true-peak guard

## Phase 1 presets

The deterministic core supports profile aliases for streaming outcomes:

- `streaming-balanced` → `default`
- `streaming-loud` → `aggressive`

These aliases are resolved by `resolve_mastering_profile(...)` and keep policy IDs stable while exposing user-facing names.

## Closed-loop loudness behavior

`apply_processing_with_loudness_target(...)` runs bounded iterative convergence after the limiter:

1. Measure output LUFS
2. Compute bounded correction gain
3. Re-limit
4. Repeat until within tolerance or maximum iterations are reached

This preserves deterministic runtime and gives more reliable target matching than one-shot correction.

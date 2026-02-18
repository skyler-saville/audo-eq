# Mastering Pipeline Guide

This guide explains how `audo-eq` processes audio in both CLI and API workflows, what each stage does, and how to troubleshoot common mastering outcomes.

## Who this is for

Use this guide if you need to:

- Understand the exact mastering flow end-to-end.
- Predict why a given track gets a specific EQ/compression profile.
- Tune integration expectations (loudness, clipping behavior, response headers).
- Debug cases where output sounds too bright, too dark, too compressed, or too quiet.

## Pipeline overview

The same core service powers every interface (`audo_eq.core`), so mastering behavior is consistent whether you call:

- `audo-eq master` (CLI), or
- `POST /master` (FastAPI).

At a high level:

1. **Ingest + validation** checks each audio input before DSP.
2. **Decoding + normalization** converts to arrays and aligns sample-rate/channel expectations.
3. **Analysis** derives loudness, spectrum, crest factor, and optional per-band EQ deltas.
4. **Decisioning** maps analysis deltas into DSP parameters.
5. **Processing** applies EQ, dynamics, and limiting with loudness targeting.
6. **Output** writes mastered audio bytes/file and optional object storage upload.

---

## 1) Ingest and validation

`master_bytes()` and `master_file()` fail fast on empty or unsupported inputs.

### What is validated

- Input bytes are non-empty.
- Container/codec validity is checked with ingest validation helpers.
- Local-file workflows build typed `AudioAsset` metadata and mark assets as validated.

### Why it matters

Validation keeps malformed media from reaching the DSP chain, reducing hard-to-debug runtime failures later in analysis or processing.

---

## 2) Decode and normalize

Both target and reference audio are loaded with `pedalboard.io.AudioFile`, then normalized via `normalize_audio()` before mastering.

### Notes

- Processing is performed on decoded arrays (not directly on raw bytes).
- Sample rate for downstream processing is taken from the normalized target payload.
- The reference track is used to steer tonal and loudness decisions, not as an output source.

---

## 3) Analysis stage

Analysis computes metrics for **target** and **reference**, then creates an `AnalysisPayload`.

### Track metrics

For each track, analysis includes:

- RMS loudness (dBFS-style).
- Spectral centroid and rolloff.
- Low/mid/high band energy proportions.
- Crest factor.
- Clipping and silence flags.

### Reference-match EQ preparation

When reference matching is used, the analysis layer:

1. Converts each signal to mono for spectral comparison.
2. RMS-normalizes both tracks to a fixed level (so tone comparison is less biased by level).
3. Computes octave-like band energies from FFT power.
4. Converts band deltas to dB, smooths them, clamps them, and drops tiny corrections.

This yields bounded per-band corrections (`EqBandCorrection`) that can be translated into shelf filter moves.

---

## 4) Decision stage

`decide_mastering()` translates analysis deltas into a stable `DecisionPayload`:

- **Broad gain** from RMS delta (clamped).
- **Low/high shelf gain** from energy-balance deltas (clamped).
- **Compressor threshold + ratio** from crest-factor relationship.
- **Limiter ceiling** based on clipping risk.

The design goal is predictable behavior with bounded parameter ranges, avoiding extreme swings from outlier analysis values.

---

## 5) DSP processing stage

`apply_processing_with_loudness_target()` performs mastering around a final loudness objective:

1. Build pre-limiter chain:
   - high-pass cleanup,
   - fixed shelves from decision payload,
   - optional reference-match shelf bank,
   - compressor,
   - gain (decision gain + loudness delta).
2. Apply limiter.
3. Measure integrated LUFS post-limiter.
4. If LUFS misses target beyond tolerance, apply bounded post gain and re-limit.

### Loudness targeting behavior

- Initial loudness delta is based on `reference_lufs - target_lufs` and clamped to a safe range.
- Post-limiter correction is intentionally bounded, with a tolerance window to avoid micro-adjustment churn.

This gives practical loudness alignment while reducing over-correction artifacts.

---

## 6) Output stage

Depending on entrypoint:

- **CLI** writes mastered audio to your requested output path.
- **API** returns mastered bytes and may also upload to object storage (if enabled), exposing a temporary URL header.

After file mastering, the target asset metadata is updated with measured integrated LUFS from the produced output.

---

## Operational behavior by interface

## CLI (`audo-eq master`)

- Validates both files.
- Creates output directories when missing.
- Writes mastered output to disk.
- Uses the same core pipeline as API.

## API (`POST /master`)

- Accepts multipart `target` and `reference` uploads.
- Returns binary mastered audio.
- Uses structured error responses for invalid payloads.
- Can upload artifacts to S3-compatible storage and return a response header URL.

---

## EQ modes

`audo-eq` supports two EQ behavior profiles:

- `fixed` (default): applies only baseline shelves from decision payload.
- `reference-match`: augments fixed shelves with a compact shelf-bank approximation derived from band corrections.

Use `reference-match` when a closer tonal fingerprint match is desired. Use `fixed` for a more conservative, broadly musical profile.

---

## Practical troubleshooting

## Output sounds too compressed

- Inspect source/reference crest-factor mismatch.
- Try a less aggressive reference track.
- Prefer `fixed` EQ mode first to reduce stacked tonal moves.

## Output is too bright / too dark

- Compare target/reference spectral balance before mastering.
- In `reference-match` mode, large broad-band deltas can legitimately push shelves harder.
- Re-test with a more stylistically aligned reference.

## Loudness is still not exactly matched

- The pipeline intentionally uses bounded gain and tolerance windows.
- Final LUFS tracks the reference directionally but may avoid exact-match at all costs to preserve stability.

## API returns `415`

- Verify that uploaded files are decodable and supported.
- Re-export problematic files to a known-good WAV/PCM baseline and retry.

---

## Recommended workflow for consistent results

1. Pick a clean reference in the same genre and arrangement density.
2. Start with default behavior and listen for dynamics first, tone second.
3. If needed, move to `reference-match` for closer tonal fit.
4. Compare output LUFS/peak with your downstream platform constraints.
5. Keep a small set of trusted references and avoid swapping references mid-project.

---

## Developer extension points

If you are extending the pipeline, start with these modules:

- `audo_eq.analysis` for new metrics or revised band logic.
- `audo_eq.decision` for parameter mapping strategy.
- `audo_eq.processing` for chain architecture and plugin behavior.
- `audo_eq.core` for orchestration and interface invariants.

Keep transport concerns in API/CLI layers and mastering behavior in the core pipeline so both interfaces remain behaviorally identical.

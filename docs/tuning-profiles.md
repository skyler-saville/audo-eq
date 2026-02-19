# Mastering Tuning Profiles

This project exposes mastering constant sets as typed tuning objects:

- `AnalysisTuning` in `src/audo_eq/analysis.py`
- `DecisionTuning` in `src/audo_eq/decision.py`
- `LoudnessTuning` in `src/audo_eq/processing.py`

Named profiles are supported:

- `default`
- `conservative`
- `aggressive`

## Profile selection

At runtime, the pipeline resolves a profile in this order:

1. Use `MasteringProfile.profile_id` when it maps to a known alias (`reference-mastering-default`, `reference-mastering-conservative`, `reference-mastering-aggressive`) or directly to a named profile.
2. Otherwise map from `EqPreset`.

This allows product-facing voicing (`EqPreset`) and policy-driven mastering (`MasteringProfile`) to coexist.

## Safe tuning workflow

1. **Start from one profile only**
   - Pick one target profile (`conservative` or `aggressive`) and avoid changing all three at once.
2. **Change one dimension at a time**
   - Analysis: adjust `eq_max_abs_db`, `eq_min_correction_db`, and smoothing kernel first.
   - Decision: adjust `shelf_scale`, compressor threshold/ratio controls, then clamp ranges.
   - Loudness: adjust post-limiter tolerance and max correction bounds.
3. **Run regression tests**
   - `pytest tests/test_tuning_regression.py`
4. **If drift is intentional, refresh fixture deliberately**
   - Regenerate `tests/fixtures/tuning_regression.json` with a scripted export from current outputs.
   - Include a PR note describing expected sonic impact and why drift is acceptable.
5. **Run broader checks**
   - `pytest tests/test_analysis_eq.py tests/test_processing_presets.py`

## Evaluating side effects

When tuning constants, evaluate:

- **Tonal side effects**: count and polarity of `eq_band_corrections` across profiles.
- **Dynamics side effects**: compressor ratio/threshold movement on transients.
- **Loudness side effects**: whether post-limiter correction oscillates or repeatedly re-hits limiter.
- **Preset consistency**: ensure `EqPreset` intent remains recognizable (e.g., warm should not become brighter than bright).

Keep these evaluations in PR notes so future tuning changes have historical context.

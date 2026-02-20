from __future__ import annotations

from audo_eq.analysis import AnalysisPayload, TrackMetrics
from audo_eq.decision import (
    DECISION_STRATEGY_POLICIES,
    StrategyCondition,
    StrategySelection,
    decide_mastering,
    select_decision_strategy,
)


def _metrics(
    *,
    low_band_energy: float,
    high_band_energy: float,
    sibilance_ratio: float,
    crest_factor_db: float,
    is_clipping: bool = False,
    rms_db: float = -16.0,
) -> TrackMetrics:
    return TrackMetrics(
        rms_db=rms_db,
        spectral_centroid_hz=1200.0,
        spectral_rolloff_hz=6500.0,
        low_band_energy=low_band_energy,
        mid_band_energy=0.5,
        high_band_energy=high_band_energy,
        sibilance_ratio=sibilance_ratio,
        crest_factor_db=crest_factor_db,
        is_clipping=is_clipping,
        is_silent=False,
    )


def test_strategy_selection_classifies_combo_conditions() -> None:
    analysis = AnalysisPayload(
        target=_metrics(
            low_band_energy=0.35,
            high_band_energy=0.38,
            sibilance_ratio=0.16,
            crest_factor_db=8.0,
            is_clipping=True,
            rms_db=-8.0,
        ),
        reference=_metrics(
            low_band_energy=0.2,
            high_band_energy=0.2,
            sibilance_ratio=0.08,
            crest_factor_db=11.0,
        ),
        eq_band_corrections=tuple(),
    )

    selection = select_decision_strategy(analysis)

    assert selection.policy.strategy_id == "corrective_combo"
    assert selection.conditions == (
        StrategyCondition.BASS_HEAVY,
        StrategyCondition.HARSH_UPPER_MIDS,
        StrategyCondition.OVER_COMPRESSED,
        StrategyCondition.CLIPPING_PRONE,
    )


def test_strategy_policy_modifies_decision_output() -> None:
    analysis = AnalysisPayload(
        target=_metrics(
            low_band_energy=0.35,
            high_band_energy=0.35,
            sibilance_ratio=0.15,
            crest_factor_db=8.0,
            is_clipping=True,
            rms_db=-8.0,
        ),
        reference=_metrics(
            low_band_energy=0.2,
            high_band_energy=0.2,
            sibilance_ratio=0.08,
            crest_factor_db=11.0,
        ),
        eq_band_corrections=tuple(),
    )

    baseline = decide_mastering(
        analysis,
        strategy=StrategySelection(
            policy=DECISION_STRATEGY_POLICIES["balanced"],
            conditions=tuple(),
        ),
    )
    corrective = decide_mastering(analysis)

    assert corrective.limiter_ceiling_db < baseline.limiter_ceiling_db
    assert corrective.de_esser_depth_db >= baseline.de_esser_depth_db

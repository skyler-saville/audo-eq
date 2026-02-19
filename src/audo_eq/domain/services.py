"""Domain services that contain pure business rules."""

from __future__ import annotations

import numpy as np

_LOUDNESS_GAIN_MIN_DB = -12.0
_LOUDNESS_GAIN_MAX_DB = 12.0


def compute_loudness_gain_delta_db(target_lufs: float, reference_lufs: float) -> float:
    """Compute a safe loudness gain delta from LUFS difference."""

    return float(np.clip(reference_lufs - target_lufs, _LOUDNESS_GAIN_MIN_DB, _LOUDNESS_GAIN_MAX_DB))

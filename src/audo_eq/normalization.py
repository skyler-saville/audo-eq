"""Audio normalization between ingest validation and DSP processing.

Normalization guarantees the processing pipeline receives channel-first float32 PCM
in the canonical contract format:

* Sample rate: ``TARGET_PCM_SAMPLE_RATE_HZ``
* Channel count: ``TARGET_PCM_CHANNEL_COUNT``
* Encoding: float32 PCM in ``[-1.0, 1.0]``

Channel policy
--------------
* mono -> stereo: duplicate the mono channel into left/right.
* stereo -> mono: average left/right equally.
* other channel count conversions: downmix by averaging to mono then duplicate,
  or truncate to the first ``N`` channels when reducing from more channels.

Peak/clipping policy
--------------------
Input audio is converted to float32. If peak magnitude exceeds ``1.0``, samples
are hard-clipped to ``[-1.0, 1.0]`` and clipping statistics are exposed in the
returned :class:`NormalizationResult`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .audio_contract import TARGET_PCM_CHANNEL_COUNT, TARGET_PCM_SAMPLE_RATE_HZ


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """Result payload for normalized audio and peak/clipping metadata."""

    audio: np.ndarray
    sample_rate_hz: int
    channel_count: int
    peak_before_clipping: float
    clipped_samples: int


def _ensure_channel_first(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio[np.newaxis, :]
    if audio.ndim != 2:
        raise ValueError("Audio must be a 1D mono or 2D channel-first array.")
    return audio


def _resample_linear(audio: np.ndarray, source_rate_hz: int, target_rate_hz: int) -> np.ndarray:
    if source_rate_hz <= 0:
        raise ValueError("Sample rate must be a positive integer.")
    if source_rate_hz == target_rate_hz:
        return audio

    source_frames = audio.shape[1]
    if source_frames == 0:
        return np.zeros((audio.shape[0], 0), dtype=np.float32)

    target_frames = max(1, int(round(source_frames * target_rate_hz / source_rate_hz)))
    source_positions = np.linspace(0.0, 1.0, num=source_frames, endpoint=False)
    target_positions = np.linspace(0.0, 1.0, num=target_frames, endpoint=False)

    resampled = np.empty((audio.shape[0], target_frames), dtype=np.float32)
    for idx in range(audio.shape[0]):
        resampled[idx] = np.interp(target_positions, source_positions, audio[idx]).astype(np.float32, copy=False)
    return resampled


def _convert_channel_layout(audio: np.ndarray, target_channel_count: int) -> np.ndarray:
    current_channels = audio.shape[0]
    if current_channels == target_channel_count:
        return audio

    if current_channels == 1 and target_channel_count == 2:
        return np.repeat(audio, repeats=2, axis=0)

    if current_channels == 2 and target_channel_count == 1:
        return np.mean(audio, axis=0, keepdims=True, dtype=np.float32)

    if target_channel_count == 1:
        return np.mean(audio, axis=0, keepdims=True, dtype=np.float32)

    if current_channels == 1:
        return np.repeat(audio, repeats=target_channel_count, axis=0)

    if current_channels > target_channel_count:
        return audio[:target_channel_count]

    repeats = target_channel_count - current_channels
    return np.concatenate((audio, np.repeat(audio[-1:], repeats=repeats, axis=0)), axis=0)


def normalize_audio(
    audio: np.ndarray,
    sample_rate_hz: int,
    *,
    target_sample_rate_hz: int = TARGET_PCM_SAMPLE_RATE_HZ,
    target_channel_count: int = TARGET_PCM_CHANNEL_COUNT,
) -> NormalizationResult:
    """Normalize audio to canonical PCM sample rate/channel/dtype requirements."""

    channel_first = _ensure_channel_first(np.asarray(audio))
    float_audio = channel_first.astype(np.float32, copy=False)

    resampled_audio = _resample_linear(float_audio, sample_rate_hz, target_sample_rate_hz)
    channel_mapped_audio = _convert_channel_layout(resampled_audio, target_channel_count)

    peak_before_clipping = float(np.max(np.abs(channel_mapped_audio))) if channel_mapped_audio.size else 0.0
    clipped_audio = np.clip(channel_mapped_audio, -1.0, 1.0).astype(np.float32, copy=False)
    clipped_samples = int(np.count_nonzero(np.abs(channel_mapped_audio) > 1.0))

    return NormalizationResult(
        audio=clipped_audio,
        sample_rate_hz=target_sample_rate_hz,
        channel_count=target_channel_count,
        peak_before_clipping=peak_before_clipping,
        clipped_samples=clipped_samples,
    )

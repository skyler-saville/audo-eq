import numpy as np

from audo_eq.audio_contract import TARGET_PCM_CHANNEL_COUNT, TARGET_PCM_SAMPLE_RATE_HZ
from audo_eq.domain.policies import DEFAULT_NORMALIZATION_POLICY
from audo_eq.normalization import normalize_audio


def test_normalize_audio_mono_to_stereo_duplicates_channel() -> None:
    mono = np.array([[0.1, -0.2, 0.3, -0.4]], dtype=np.float32)

    result = normalize_audio(mono, TARGET_PCM_SAMPLE_RATE_HZ, policy=DEFAULT_NORMALIZATION_POLICY)

    assert result.audio.shape == (TARGET_PCM_CHANNEL_COUNT, mono.shape[1])
    assert np.allclose(result.audio[0], mono[0])
    assert np.allclose(result.audio[1], mono[0])
    assert result.channel_count == TARGET_PCM_CHANNEL_COUNT


def test_normalize_audio_resamples_non_48k_source() -> None:
    source_rate = 44_100
    source_frames = source_rate // 10
    source_audio = np.linspace(-0.5, 0.5, source_frames, dtype=np.float32)[np.newaxis, :]

    result = normalize_audio(source_audio, source_rate, policy=DEFAULT_NORMALIZATION_POLICY)

    expected_frames = int(round(source_frames * TARGET_PCM_SAMPLE_RATE_HZ / source_rate))
    assert result.sample_rate_hz == TARGET_PCM_SAMPLE_RATE_HZ
    assert result.audio.shape == (TARGET_PCM_CHANNEL_COUNT, expected_frames)
    assert result.audio.dtype == np.float32

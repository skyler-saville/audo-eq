import numpy as np

from audo_eq.io.audio_file import read_audio, write_audio


def test_write_and_read_audio_roundtrip(tmp_path):
    audio = np.linspace(-0.5, 0.5, 4410, dtype=np.float32)
    sample_rate = 44100
    path = tmp_path / "roundtrip.wav"

    write_audio(path, audio, sample_rate)
    loaded_audio, loaded_sr = read_audio(path)

    assert loaded_sr == sample_rate
    assert loaded_audio.shape == audio.shape
    assert np.allclose(loaded_audio, audio, atol=1e-6)

import io
import wave

from fastapi.testclient import TestClient

from audo_eq.api import app


client = TestClient(app)


def make_wav_bytes(*, duration_seconds: float = 0.1, sample_rate: int = 48_000, channels: int = 2) -> bytes:
    frames = int(duration_seconds * sample_rate)
    with io.BytesIO() as buffer:
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(b"\x00\x00" * channels * frames)
        return buffer.getvalue()


def test_master_returns_storage_header_when_object_is_uploaded(monkeypatch) -> None:
    monkeypatch.setattr("audo_eq.api.store_mastered_audio", lambda **kwargs: "https://storage.local/mastered/file.wav")

    response = client.post(
        "/master",
        files={
            "target": ("target.wav", make_wav_bytes(), "audio/wav"),
            "reference": ("reference.wav", make_wav_bytes(), "audio/wav"),
        },
    )

    assert response.status_code == 200
    assert response.headers["x-mastered-object-url"] == "https://storage.local/mastered/file.wav"

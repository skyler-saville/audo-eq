import io
import wave

from fastapi.testclient import TestClient

from audo_eq import storage
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
    monkeypatch.setattr(
        "audo_eq.api.master_bytes",
        lambda **kwargs: make_wav_bytes(),
    )
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


def test_master_forwards_eq_mode(monkeypatch) -> None:
    captured = {}

    def fake_master_bytes(*, target_bytes: bytes, reference_bytes: bytes, eq_mode, eq_preset):
        captured["eq_mode"] = eq_mode
        captured["eq_preset"] = eq_preset
        return make_wav_bytes()

    monkeypatch.setattr("audo_eq.api.master_bytes", fake_master_bytes)
    monkeypatch.setattr("audo_eq.api.store_mastered_audio", lambda **kwargs: None)

    response = client.post(
        "/master?eq_mode=reference-match&eq_preset=warm",
        files={
            "target": ("target.wav", make_wav_bytes(), "audio/wav"),
            "reference": ("reference.wav", make_wav_bytes(), "audio/wav"),
        },
    )

    assert response.status_code == 200
    assert captured["eq_mode"].value == "reference-match"
    assert captured["eq_preset"].value == "warm"


def test_master_parses_query_options_case_insensitively(monkeypatch) -> None:
    captured = {}

    def fake_master_bytes(*, target_bytes: bytes, reference_bytes: bytes, eq_mode, eq_preset):
        captured["eq_mode"] = eq_mode
        captured["eq_preset"] = eq_preset
        return make_wav_bytes()

    monkeypatch.setattr("audo_eq.api.master_bytes", fake_master_bytes)
    monkeypatch.setattr("audo_eq.api.store_mastered_audio", lambda **kwargs: None)

    response = client.post(
        "/master?eq_mode=REFERENCE-MATCH&eq_preset=WARM",
        files={
            "target": ("target.wav", make_wav_bytes(), "audio/wav"),
            "reference": ("reference.wav", make_wav_bytes(), "audio/wav"),
        },
    )

    assert response.status_code == 200
    assert captured["eq_mode"].value == "reference-match"
    assert captured["eq_preset"].value == "warm"


def test_master_rejects_invalid_eq_preset_with_400() -> None:
    response = client.post(
        "/master?eq_preset=unknown",
        files={
            "target": ("target.wav", make_wav_bytes(), "audio/wav"),
            "reference": ("reference.wav", make_wav_bytes(), "audio/wav"),
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]["code"] == "invalid_query_parameter"
    assert payload["detail"]["parameter"] == "eq_preset"
    assert payload["detail"]["allowed_values"] == [
        "neutral",
        "warm",
        "bright",
        "vocal-presence",
        "bass-boost",
    ]


def test_master_returns_bytes_when_storage_write_fails_non_strict(monkeypatch) -> None:
    storage.load_storage_config.cache_clear()
    storage.get_storage_client.cache_clear()
    monkeypatch.setenv("AUDO_EQ_STORAGE_ENABLED", "true")
    monkeypatch.setenv("AUDO_EQ_STORAGE_STRICT", "false")

    class _FailingClient:
        def bucket_exists(self, bucket_name: str) -> bool:
            return True

        def put_object(self, bucket_name: str, object_name: str, data, length: int, content_type: str) -> None:
            raise RuntimeError("write failed")

    monkeypatch.setattr(storage, "get_storage_client", lambda: _FailingClient())
    monkeypatch.setattr("audo_eq.api.master_bytes", lambda **kwargs: make_wav_bytes())
    monkeypatch.setattr("audo_eq.api.store_mastered_audio", storage.store_mastered_audio)

    response = client.post(
        "/master",
        files={
            "target": ("target.wav", make_wav_bytes(), "audio/wav"),
            "reference": ("reference.wav", make_wav_bytes(), "audio/wav"),
        },
    )

    assert response.status_code == 200
    assert response.headers.get("x-mastered-object-url") is None
    assert response.content


def test_master_returns_503_when_storage_write_fails_strict(monkeypatch) -> None:
    storage.load_storage_config.cache_clear()
    storage.get_storage_client.cache_clear()
    monkeypatch.setenv("AUDO_EQ_STORAGE_ENABLED", "true")
    monkeypatch.setenv("AUDO_EQ_STORAGE_STRICT", "true")

    class _FailingClient:
        def bucket_exists(self, bucket_name: str) -> bool:
            return True

        def put_object(self, bucket_name: str, object_name: str, data, length: int, content_type: str) -> None:
            raise RuntimeError("write failed")

    monkeypatch.setattr(storage, "get_storage_client", lambda: _FailingClient())
    monkeypatch.setattr("audo_eq.api.master_bytes", lambda **kwargs: make_wav_bytes())
    monkeypatch.setattr("audo_eq.api.store_mastered_audio", storage.store_mastered_audio)

    response = client.post(
        "/master",
        files={
            "target": ("target.wav", make_wav_bytes(), "audio/wav"),
            "reference": ("reference.wav", make_wav_bytes(), "audio/wav"),
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "storage_unavailable"

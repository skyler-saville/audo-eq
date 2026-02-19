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
    monkeypatch.setattr(
        "audo_eq.api.master_bytes",
        lambda **kwargs: make_wav_bytes(),
    )
    class _Repo:
        def persist(self, **kwargs):
            from audo_eq.application.mastered_artifact_repository import PersistedArtifact

            return PersistedArtifact(status="stored", object_url="https://storage.local/mastered/file.wav", destination="https://storage.local/mastered/file.wav")

    monkeypatch.setattr("audo_eq.api._build_repository_for_mode", lambda mode: _Repo())

    response = client.post(
        "/master",
        files={
            "target": ("target.wav", make_wav_bytes(), "audio/wav"),
            "reference": ("reference.wav", make_wav_bytes(), "audio/wav"),
        },
    )

    assert response.status_code == 200
    assert response.headers["x-mastered-object-url"] == "https://storage.local/mastered/file.wav"
    assert response.headers["x-policy-version"] == "v1"
    assert response.headers["x-ingest-policy-id"] == "ingest-validation-default"
    assert response.headers["x-normalization-policy-id"] == "pcm-canonical-default"
    assert response.headers["x-mastering-profile-id"] == "reference-mastering-default"


def test_master_forwards_eq_mode(monkeypatch) -> None:
    captured = {}

    def fake_master_bytes(*, target_bytes: bytes, reference_bytes: bytes, eq_mode, eq_preset, correlation_id):
        captured["eq_mode"] = eq_mode
        captured["eq_preset"] = eq_preset
        return make_wav_bytes()

    monkeypatch.setattr("audo_eq.api.master_bytes", fake_master_bytes)
    class _Repo:
        def persist(self, **kwargs):
            from audo_eq.application.mastered_artifact_repository import PersistedArtifact

            return PersistedArtifact(status="skipped")

    monkeypatch.setattr("audo_eq.api._build_repository_for_mode", lambda mode: _Repo())

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

    def fake_master_bytes(*, target_bytes: bytes, reference_bytes: bytes, eq_mode, eq_preset, correlation_id):
        captured["eq_mode"] = eq_mode
        captured["eq_preset"] = eq_preset
        return make_wav_bytes()

    monkeypatch.setattr("audo_eq.api.master_bytes", fake_master_bytes)
    class _Repo:
        def persist(self, **kwargs):
            from audo_eq.application.mastered_artifact_repository import PersistedArtifact

            return PersistedArtifact(status="skipped")

    monkeypatch.setattr("audo_eq.api._build_repository_for_mode", lambda mode: _Repo())

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


def test_master_returns_bytes_when_immediate_persistence_skips_best_effort(monkeypatch) -> None:
    monkeypatch.setenv("AUDO_EQ_ARTIFACT_PERSISTENCE_MODE", "immediate")
    monkeypatch.setenv("AUDO_EQ_ARTIFACT_PERSISTENCE_GUARANTEE", "best-effort")

    class _Repo:
        def persist(self, **kwargs):
            from audo_eq.application.mastered_artifact_repository import PersistedArtifact

            return PersistedArtifact(status="skipped")

    monkeypatch.setattr("audo_eq.api._build_repository_for_mode", lambda mode: _Repo())
    monkeypatch.setattr("audo_eq.api.master_bytes", lambda **kwargs: make_wav_bytes())

    response = client.post(
        "/master",
        files={
            "target": ("target.wav", make_wav_bytes(), "audio/wav"),
            "reference": ("reference.wav", make_wav_bytes(), "audio/wav"),
        },
    )

    assert response.status_code == 200
    assert response.headers.get("x-mastered-object-url") is None
    assert response.headers["x-artifact-persistence-status"] == "skipped"


def test_master_returns_503_when_immediate_persistence_is_guaranteed(monkeypatch) -> None:
    monkeypatch.setenv("AUDO_EQ_ARTIFACT_PERSISTENCE_MODE", "immediate")
    monkeypatch.setenv("AUDO_EQ_ARTIFACT_PERSISTENCE_GUARANTEE", "guaranteed")

    class _Repo:
        def persist(self, **kwargs):
            from audo_eq.application.mastered_artifact_repository import PersistedArtifact

            return PersistedArtifact(status="skipped")

    monkeypatch.setattr("audo_eq.api._build_repository_for_mode", lambda mode: _Repo())
    monkeypatch.setattr("audo_eq.api.master_bytes", lambda **kwargs: make_wav_bytes())

    response = client.post(
        "/master",
        files={
            "target": ("target.wav", make_wav_bytes(), "audio/wav"),
            "reference": ("reference.wav", make_wav_bytes(), "audio/wav"),
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "storage_unavailable"


def test_health_returns_ok_status_shape() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_master_requires_both_uploads() -> None:
    response = client.post(
        "/master",
        files={
            "target": ("target.wav", make_wav_bytes(), "audio/wav"),
        },
    )

    assert response.status_code == 422


def test_master_rejects_invalid_or_corrupt_uploads() -> None:
    response = client.post(
        "/master",
        files={
            "target": ("target.txt", b"not audio", "text/plain"),
            "reference": ("reference.wav", make_wav_bytes(), "audio/wav"),
        },
    )

    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "unsupported_container"

    response = client.post(
        "/master",
        files={
            "target": ("target.wav", b"RIFF\x00\x00\x00\x00WAVE", "audio/wav"),
            "reference": ("reference.wav", make_wav_bytes(), "audio/wav"),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "corrupted_file"


def test_master_maps_value_error_to_invalid_payload(monkeypatch) -> None:
    monkeypatch.setattr("audo_eq.api.master_bytes", lambda **kwargs: (_ for _ in ()).throw(ValueError("bad payload")))

    response = client.post(
        "/master",
        files={
            "target": ("target.wav", make_wav_bytes(), "audio/wav"),
            "reference": ("reference.wav", make_wav_bytes(), "audio/wav"),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_payload"


def test_master_response_media_type_falls_back_to_audio_wav(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr("audo_eq.api.master_bytes", lambda **kwargs: make_wav_bytes())

    class _Repo:
        def persist(self, *, object_name: str, audio_bytes: bytes, content_type: str):
            from audo_eq.application.mastered_artifact_repository import PersistedArtifact

            captured["content_type"] = content_type
            return PersistedArtifact(status="skipped")

    monkeypatch.setattr("audo_eq.api._build_repository_for_mode", lambda mode: _Repo())

    response = client.post(
        "/master",
        files={
            "target": ("target.wav", make_wav_bytes(), "text/plain"),
            "reference": ("reference.wav", make_wav_bytes(), "audio/wav"),
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert captured["content_type"] == "text/plain"

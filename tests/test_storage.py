from __future__ import annotations

from audo_eq import storage


class _FakeMinioClient:
    def __init__(self) -> None:
        self.buckets: set[str] = set()
        self.put_calls: list[tuple[str, str, int, str]] = []

    def bucket_exists(self, bucket_name: str) -> bool:
        return bucket_name in self.buckets

    def make_bucket(self, bucket_name: str) -> None:
        self.buckets.add(bucket_name)

    def put_object(self, bucket_name: str, object_name: str, data, length: int, content_type: str) -> None:
        data.read()
        self.put_calls.append((bucket_name, object_name, length, content_type))

    def presigned_get_object(self, bucket_name: str, object_name: str, expires) -> str:
        return f"https://storage.local/{bucket_name}/{object_name}"


def _reset_caches() -> None:
    storage.load_storage_config.cache_clear()
    storage.get_storage_client.cache_clear()


def test_store_mastered_audio_disabled(monkeypatch) -> None:
    _reset_caches()
    monkeypatch.setenv("AUDO_EQ_STORAGE_ENABLED", "false")

    assert storage.store_mastered_audio(object_name="mastered/file.wav", audio_bytes=b"abc") is None


def test_store_mastered_audio_enabled(monkeypatch) -> None:
    _reset_caches()
    monkeypatch.setenv("AUDO_EQ_STORAGE_ENABLED", "true")
    monkeypatch.setenv("AUDO_EQ_S3_BUCKET", "unit-test-bucket")

    fake_client = _FakeMinioClient()
    monkeypatch.setattr(storage, "get_storage_client", lambda: fake_client)

    url = storage.store_mastered_audio(object_name="mastered/file.wav", audio_bytes=b"abc", content_type="audio/wav")

    assert url == "https://storage.local/unit-test-bucket/mastered/file.wav"
    assert "unit-test-bucket" in fake_client.buckets
    assert fake_client.put_calls == [("unit-test-bucket", "mastered/file.wav", 3, "audio/wav")]


def test_store_mastered_audio_non_strict_returns_none_on_storage_error(monkeypatch) -> None:
    _reset_caches()
    monkeypatch.setenv("AUDO_EQ_STORAGE_ENABLED", "true")
    monkeypatch.setenv("AUDO_EQ_STORAGE_STRICT", "false")

    class _FailingClient(_FakeMinioClient):
        def put_object(self, bucket_name: str, object_name: str, data, length: int, content_type: str) -> None:
            raise RuntimeError("write failed")

    monkeypatch.setattr(storage, "get_storage_client", lambda: _FailingClient())

    assert storage.store_mastered_audio(object_name="mastered/file.wav", audio_bytes=b"abc") is None


def test_store_mastered_audio_returns_none_on_storage_error(monkeypatch) -> None:
    _reset_caches()
    monkeypatch.setenv("AUDO_EQ_STORAGE_ENABLED", "true")

    class _FailingClient(_FakeMinioClient):
        def put_object(self, bucket_name: str, object_name: str, data, length: int, content_type: str) -> None:
            raise RuntimeError("write failed")

    monkeypatch.setattr(storage, "get_storage_client", lambda: _FailingClient())

    assert storage.store_mastered_audio(object_name="mastered/file.wav", audio_bytes=b"abc") is None
